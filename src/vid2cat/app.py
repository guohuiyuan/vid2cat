from __future__ import annotations

from pathlib import Path
import tempfile
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .db import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_SETTINGS,
    add_comment,
    authenticate_admin,
    authenticate_user,
    get_atlas,
    get_rating_summary,
    get_settings,
    get_user_by_id,
    get_user_rating,
    init_db,
    list_atlases,
    list_comments,
    list_recent_users,
    register_user,
    save_atlas,
    update_settings,
    update_user_password,
    upsert_rating,
    verify_password,
)
from .integrations import ImageHostScaffold
from .services import extract_first_url, is_douyin_url, parse_cat_profile, parse_douyin_to_atlas, parse_model1_analysis


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
CAT_PROFILE_LABELS = {
    "name": "猫咪名字",
    "breed": "猫咪品种",
    "skill": "技能设定",
    "power": "种族值",
    "personality": "性格",
    "story": "背景故事",
    "appearance": "外貌描述",
    "rarity": "稀有度",
    "image_prompt": "绘图提示词",
}


def build_atlas_card(atlas: dict) -> dict:
    profile = parse_cat_profile(atlas.get("cat_profile_json") or "")
    cat_name = profile.get("name") or profile.get("breed") or atlas.get("title") or "未命名猫咪"
    breed = profile.get("breed") or "待补全品种"
    image_url = atlas.get("cat_image_url") or atlas.get("cover_url") or ""
    summary = profile.get("personality") or atlas.get("ai_summary") or atlas.get("description") or "暂无介绍"
    return {
        "id": atlas.get("id"),
        "cat_name": cat_name,
        "breed": breed,
        "image_url": image_url,
        "video_url": atlas.get("video_url") or "",
        "rarity": profile.get("rarity") or "待定",
        "summary": summary,
        "title": atlas.get("title") or "",
    }


def build_radar_chart(
    scores: list[tuple[str, float]],
    max_score: float,
    size: int = 260,
    radius: int = 92,
) -> dict:
    center = size / 2
    axes = [
        ("快乐", (0, -1)),
        ("知识", (1, 0)),
        ("节奏", (0, 1)),
        ("共鸣", (-1, 0)),
    ]

    def point(vector_x: float, vector_y: float, value: float, scale: float = 1.0) -> tuple[float, float]:
        factor = 0 if max_score == 0 else (value / max_score) * scale
        return center + vector_x * radius * factor, center + vector_y * radius * factor

    grid_polygons = []
    for scale in [0.25, 0.5, 0.75, 1.0]:
        polygon = []
        for _, (vx, vy) in axes:
            x, y = point(vx, vy, max_score, scale=scale)
            polygon.append(f"{x:.1f},{y:.1f}")
        grid_polygons.append(" ".join(polygon))

    value_map = {label: float(value or 0) for label, value in scores}
    polygon = []
    labels = []
    for label, (vx, vy) in axes:
        x, y = point(vx, vy, value_map.get(label, 0))
        polygon.append(f"{x:.1f},{y:.1f}")
        lx, ly = point(vx, vy, max_score, scale=1.18)
        labels.append({"label": label, "x": round(lx, 1), "y": round(ly, 1)})

    axis_lines = []
    for _, (vx, vy) in axes:
        x, y = point(vx, vy, max_score)
        axis_lines.append({"x1": center, "y1": center, "x2": round(x, 1), "y2": round(y, 1)})

    return {
        "size": size,
        "center": center,
        "grid_polygons": grid_polygons,
        "polygon": " ".join(polygon),
        "axis_lines": axis_lines,
        "labels": labels,
    }

app = FastAPI(title="vid2cat", version="0.1.0")
app.add_middleware(SessionMiddleware, secret_key="vid2cat-admin-session-secret")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def redirect_with_message(
    path: str,
    message: str = "",
    error: str = "",
    extra: dict[str, str] | None = None,
) -> RedirectResponse:
    params = []
    if message:
        params.append(f"message={quote(message)}")
    if error:
        params.append(f"error={quote(error)}")
    if extra:
        for key, value in extra.items():
            if value:
                params.append(f"{quote(str(key))}={quote(str(value))}")
    target = path if not params else f"{path}{'&' if '?' in path else '?'}{'&'.join(params)}"
    return RedirectResponse(target, status_code=303)


def get_current_admin(request: Request) -> dict | None:
    admin_user_id = request.session.get("admin_user_id")
    if not admin_user_id:
        return None
    user = get_user_by_id(int(admin_user_id))
    if not user or user.get("role") != "admin":
        request.session.pop("admin_user_id", None)
        return None
    return user


def get_current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = get_user_by_id(int(user_id))
    if not user or user.get("role") != "user":
        request.session.pop("user_id", None)
        return None
    return user


def require_admin(request: Request, allow_password_change: bool = False) -> tuple[dict | None, RedirectResponse | None]:
    admin = get_current_admin(request)
    if not admin:
        return None, redirect_with_message("/admin/login", error="请先登录管理员账号")
    if admin.get("must_change_password") and not allow_password_change:
        return None, redirect_with_message("/admin/password", error="首次登录请先修改管理员默认密码")
    return admin, None


@app.get("/")
def home(
    request: Request,
    text: str = Query(default=""),
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "text": text,
            "message": message,
            "error": error,
            "extracted_url": extract_first_url(text or ""),
            "admin_user": get_current_admin(request),
            "current_user": get_current_user(request),
            "image_host_status": ImageHostScaffold.describe(settings),
        },
    )


@app.post("/parse")
def parse_url(raw_input: str = Form(...)):
    parsed_url = extract_first_url(raw_input) or raw_input.strip()
    if not is_douyin_url(parsed_url):
        return redirect_with_message("/", error="请输入抖音作品链接")
    settings = get_settings()
    atlas = parse_douyin_to_atlas(parsed_url, settings=settings)
    atlas_id = save_atlas(atlas)
    message = "已完成基础解析并生成图鉴骨架"
    if atlas.get("parse_error"):
        message = "解析未完全成功，已生成可继续开发的图鉴骨架"
    elif settings.get("ai_model_1_model"):
        message = f"已完成基础解析，并使用模型1（{settings['ai_model_1_model']}）生成视频摘要"
    return redirect_with_message(f"/atlas/{atlas_id}", message=message)


@app.get("/atlases")
def atlas_list_page(
    request: Request,
    q: str = Query(default=""),
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    atlases = [build_atlas_card(row) for row in list_atlases(q, limit=36)]
    return templates.TemplateResponse(
        request=request,
        name="atlas_list.html",
        context={
            "request": request,
            "query": q,
            "message": message,
            "error": error,
            "atlas_cards": atlases,
            "admin_user": get_current_admin(request),
            "current_user": get_current_user(request),
        },
    )


@app.get("/register")
def register_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "admin_user": get_current_admin(request),
            "current_user": get_current_user(request),
        },
    )


@app.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if not username.strip() or not email.strip() or not password.strip():
        return redirect_with_message("/register", error="请完整填写注册信息")
    ok, msg = register_user(username, email, password)
    if ok:
        user = authenticate_user(username, password)
        if user:
            request.session["user_id"] = int(user["id"])
        return redirect_with_message("/atlases", message="注册成功，已自动登录")
    return redirect_with_message("/register", error=msg)


@app.get("/login")
def login_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
    next: str = Query(default="/atlases"),
):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "next": next,
            "admin_user": get_current_admin(request),
            "current_user": get_current_user(request),
        },
    )


@app.post("/login")
def login_submit(
    request: Request,
    identity: str = Form(...),
    password: str = Form(...),
    next: str = Form("/atlases"),
):
    user = authenticate_user(identity, password)
    if not user:
        return redirect_with_message("/login", error="用户名/邮箱或密码错误", extra={"next": next})
    request.session["user_id"] = int(user["id"])
    return redirect_with_message(next or "/atlases", message=f"欢迎回来，{user['username']}")


@app.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    return redirect_with_message("/", message="已退出登录")


@app.get("/atlas/{atlas_id}")
def atlas_detail(
    request: Request,
    atlas_id: int,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    atlas = get_atlas(atlas_id)
    if not atlas:
        raise HTTPException(status_code=404, detail="图鉴不存在")
    settings = get_settings()
    cat_profile = parse_cat_profile(atlas.get("cat_profile_json") or "")
    model1_analysis = parse_model1_analysis(atlas.get("model1_output") or "")
    current_user = get_current_user(request)
    user_rating = get_user_rating(atlas_id, int(current_user["id"])) if current_user else None
    rating_summary = get_rating_summary(atlas_id)
    ai_radar_chart = build_radar_chart(
        [
            ("快乐", model1_analysis.get("happiness_score", 0)),
            ("知识", model1_analysis.get("knowledge_score", 0)),
            ("节奏", model1_analysis.get("rhythm_score", 0)),
            ("共鸣", model1_analysis.get("resonance_score", 0)),
        ],
        max_score=100,
    )
    rating_radar_chart = build_radar_chart(
        [
            ("快乐", rating_summary.get("avg_happiness_score", 0)),
            ("知识", rating_summary.get("avg_knowledge_score", 0)),
            ("节奏", rating_summary.get("avg_rhythm_score", 0)),
            ("共鸣", rating_summary.get("avg_resonance_score", 0)),
        ],
        max_score=10,
    )
    ordered_profile_items = [
        {"key": key, "label": CAT_PROFILE_LABELS.get(key, key), "value": cat_profile[key]}
        for key in CAT_PROFILE_LABELS
        if cat_profile.get(key)
    ]
    ordered_profile_items.extend(
        {"key": key, "label": CAT_PROFILE_LABELS.get(key, key), "value": value}
        for key, value in cat_profile.items()
        if key not in CAT_PROFILE_LABELS and value
    )
    return templates.TemplateResponse(
        request=request,
        name="atlas_detail.html",
        context={
            "request": request,
            "atlas": atlas,
            "cat_profile": cat_profile,
            "profile_items": ordered_profile_items,
            "comments": list_comments(atlas_id),
            "message": message,
            "error": error,
            "admin_user": get_current_admin(request),
            "current_user": current_user,
            "cat_display_name": cat_profile.get("name") or cat_profile.get("breed") or atlas.get("title"),
            "model1_analysis": model1_analysis,
            "user_rating": user_rating,
            "rating_summary": rating_summary,
            "ai_radar_chart": ai_radar_chart,
            "rating_radar_chart": rating_radar_chart,
        },
    )


@app.post("/atlas/{atlas_id}/comment")
def comment_submit(
    request: Request,
    atlas_id: int,
    content: str = Form(...),
):
    atlas = get_atlas(atlas_id)
    if not atlas:
        raise HTTPException(status_code=404, detail="图鉴不存在")
    current_user = get_current_user(request)
    if not current_user:
        return redirect_with_message("/login", error="评论前请先登录", extra={"next": f"/atlas/{atlas_id}"})
    if not content.strip():
        return redirect_with_message(f"/atlas/{atlas_id}", error="请填写评论内容")
    add_comment(atlas_id, current_user["username"], content)
    return redirect_with_message(f"/atlas/{atlas_id}", message="评论已发布")


@app.post("/atlas/{atlas_id}/rating")
def rating_submit(
    request: Request,
    atlas_id: int,
    happiness_score: int = Form(...),
    knowledge_score: int = Form(...),
    rhythm_score: int = Form(...),
    resonance_score: int = Form(...),
):
    atlas = get_atlas(atlas_id)
    if not atlas:
        raise HTTPException(status_code=404, detail="图鉴不存在")
    current_user = get_current_user(request)
    if not current_user:
        return redirect_with_message("/login", error="评分前请先登录", extra={"next": f"/atlas/{atlas_id}"})
    values = [happiness_score, knowledge_score, rhythm_score, resonance_score]
    if any(score < 1 or score > 10 for score in values):
        return redirect_with_message(f"/atlas/{atlas_id}", error="评分必须在 1 到 10 之间")
    upsert_rating(
        atlas_id=atlas_id,
        user_id=int(current_user["id"]),
        happiness_score=happiness_score,
        knowledge_score=knowledge_score,
        rhythm_score=rhythm_score,
        resonance_score=resonance_score,
    )
    return redirect_with_message(f"/atlas/{atlas_id}", message="评分已保存")


@app.get("/admin/login")
def admin_login_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    admin = get_current_admin(request)
    if admin and not admin.get("must_change_password"):
        return RedirectResponse("/admin", status_code=303)
    if admin and admin.get("must_change_password"):
        return RedirectResponse("/admin/password", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "default_admin_username": DEFAULT_ADMIN_USERNAME,
            "default_admin_password": DEFAULT_ADMIN_PASSWORD,
        },
    )


@app.post("/admin/login")
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    admin = authenticate_admin(username, password)
    if not admin:
        return redirect_with_message("/admin/login", error="管理员账号或密码错误")
    request.session["admin_user_id"] = int(admin["id"])
    if admin.get("must_change_password"):
        return redirect_with_message("/admin/password", message="首次登录请先修改默认密码")
    return redirect_with_message("/admin", message="管理员登录成功")


@app.get("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return redirect_with_message("/admin/login", message="已退出管理员账号")


@app.get("/admin/password")
def admin_password_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    admin, redirect = require_admin(request, allow_password_change=True)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request,
        name="admin_password.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "admin": admin,
        },
    )


@app.post("/admin/password")
def admin_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    admin, redirect = require_admin(request, allow_password_change=True)
    if redirect:
        return redirect
    if not verify_password(admin.get("password", ""), current_password):
        return redirect_with_message("/admin/password", error="当前密码不正确")
    if len(new_password.strip()) < 8:
        return redirect_with_message("/admin/password", error="新密码至少 8 位")
    if new_password != confirm_password:
        return redirect_with_message("/admin/password", error="两次输入的新密码不一致")
    update_user_password(int(admin["id"]), new_password)
    return redirect_with_message("/admin", message="密码已修改，后台配置已解锁")


@app.get("/admin")
def admin_dashboard(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
    uploaded_url: str = Query(default=""),
):
    admin, redirect = require_admin(request)
    if redirect:
        return redirect
    settings = get_settings()
    prompt_examples = []
    for row in list_atlases(limit=6):
        profile = parse_cat_profile(row.get("cat_profile_json") or "")
        prompt_examples.append(
            {
                "id": row.get("id"),
                "title": row.get("title") or "未命名图鉴",
                "cat_name": profile.get("name") or profile.get("breed") or "未命名猫咪",
                "prompt_scaffold": row.get("prompt_scaffold") or "",
                "image_prompt": row.get("cat_image_prompt") or profile.get("image_prompt") or "",
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "admin": admin,
            "settings": settings,
            "uploaded_url": uploaded_url,
            "image_host_status": ImageHostScaffold.describe(settings),
            "recent_users": list_recent_users(limit=12),
            "prompt_examples": prompt_examples,
        },
    )


@app.post("/admin/settings")
async def admin_settings_submit(request: Request):
    admin, redirect = require_admin(request)
    if redirect:
        return redirect
    form = await request.form()
    payload = {
        key: str(form.get(key, ""))
        for key in DEFAULT_SETTINGS
    }
    update_settings(payload)
    return redirect_with_message("/admin", message="系统配置已保存")


@app.post("/admin/upload-test")
async def admin_upload_test(request: Request, image: UploadFile = File(...)):
    admin, redirect = require_admin(request)
    if redirect:
        return redirect
    settings = get_settings()
    if not image.filename:
        return redirect_with_message("/admin", error="请选择要上传的图片")
    suffix = Path(image.filename).suffix or ".png"
    temp_dir = PROJECT_ROOT / "data" / "admin_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_bytes = await image.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as handle:
        handle.write(file_bytes)
        temp_path = Path(handle.name)
    try:
        uploaded_url = ImageHostScaffold.upload(temp_path, settings)
        return redirect_with_message(
            "/admin",
            message="图床上传成功",
            extra={"uploaded_url": uploaded_url},
        )
    except Exception as exc:
        return redirect_with_message("/admin", error=f"图床上传失败：{exc}")
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def main() -> None:
    uvicorn.run("vid2cat.app:app", host="127.0.0.1", port=8000, reload=False)
