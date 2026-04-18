from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
import tempfile
from typing import Any
from urllib.parse import quote, urlencode
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .db import (
    DAILY_TRAINING_ACTIONS,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_SETTINGS,
    MAX_CAT_LEVEL,
    add_comment,
    admin_delete_cat,
    adopt_plaza_cat,
    add_cat_feed_record,
    add_cat_message,
    activate_cat_for_user,
    authenticate_admin,
    authenticate_user,
    count_user_owned_cats,
    create_guest_user,
    create_initial_cat_for_user,
    get_atlas,
    get_cat_by_id,
    get_or_activate_user_cat,
    get_user_cat,
    get_rating_summary,
    get_settings,
    get_user_by_id,
    get_user_rating,
    init_db,
    list_cat_feed_records,
    list_cat_timeline,
    list_cat_messages,
    list_public_cats,
    list_atlases,
    list_comments,
    list_recent_users,
    list_user_cats,
    parse_skill_list,
    perform_daily_training,
    release_cat_to_plaza,
    register_user,
    save_atlas,
    set_all_user_cats_inactive,
    transfer_guest_progress,
    update_cat_final_persona,
    update_cat_public_status,
    update_settings,
    update_user_password,
    upsert_rating,
    verify_password,
)
from .integrations import ImageHostScaffold
from .services import (
    build_growth_image_profile,
    extract_first_url,
    generate_cat_response,
    generate_cat_image_with_model3,
    generate_initial_cat_ai_data,
    is_douyin_url,
    parse_cat_profile,
    parse_douyin_to_atlas,
    parse_douyin_to_feed,
    parse_model1_analysis,
)
from .share_cards import render_cat_share_card


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
ASYNC_TASKS: dict[str, dict[str, Any]] = {}
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
CAT_STAT_LABELS = {
    "wisdom": "智慧",
    "grit": "毅力",
    "creativity": "创造",
    "agility": "灵敏",
    "cooperation": "协作",
}
INITIAL_CAT_BREEDS = ["布偶猫", "橘猫", "英短", "缅因猫", "奶牛猫", "森林猫"]
INITIAL_CAT_COLORS = ["奶油白", "橘金色", "雾霾灰", "黑白双色", "琥珀棕", "樱花粉"]


def build_atlas_card(atlas: dict) -> dict:
    profile = parse_cat_profile(atlas.get("cat_profile_json") or "")
    cat_name = (
        profile.get("name")
        or profile.get("breed")
        or atlas.get("title")
        or "未命名猫咪"
    )
    breed = profile.get("breed") or "待补全品种"
    image_url = atlas.get("cat_image_url") or atlas.get("cover_url") or ""
    summary = (
        profile.get("personality")
        or atlas.get("ai_summary")
        or atlas.get("description")
        or "暂无介绍"
    )
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


def build_cat_card(cat: dict) -> dict:
    image_url = cat.get("image_url") or ""
    exp = int(cat.get("exp") or 0)
    exp_to_next = int(cat.get("exp_to_next") or 0)
    exp_percent = 100 if exp_to_next <= 0 else min(100, round(exp / exp_to_next * 100))
    return {
        "id": cat.get("id"),
        "cat_name": cat.get("name") or "未命名猫咪",
        "username": cat.get("username") or "未知主人",
        "image_url": image_url,
        "stage": cat.get("stage") or "初始态",
        "feed_count": cat.get("feed_count") or 0,
        "max_feed_count": cat.get("max_feed_count") or MAX_CAT_LEVEL,
        "level": int(cat.get("level") or 0),
        "exp": exp,
        "exp_to_next": exp_to_next,
        "exp_percent": exp_percent,
        "overall_power": cat.get("overall_power") or 250,
        "summary": cat.get("personality") or cat.get("story_summary") or "暂无介绍",
        "learned_skills": parse_skill_list(str(cat.get("learned_skills_json") or "")),
        "highest_level_owner_name": cat.get("highest_level_owner_name")
        or cat.get("username")
        or "未知主人",
        "highest_level_reached": int(
            cat.get("highest_level_reached") or cat.get("level") or 0
        ),
        "available_for_adoption": int(cat.get("available_for_adoption") or 0),
        "is_active": int(cat.get("is_active") or 0),
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

    def point(
        vector_x: float, vector_y: float, value: float, scale: float = 1.0
    ) -> tuple[float, float]:
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
        axis_lines.append(
            {"x1": center, "y1": center, "x2": round(x, 1), "y2": round(y, 1)}
        )

    return {
        "size": size,
        "center": center,
        "grid_polygons": grid_polygons,
        "polygon": " ".join(polygon),
        "axis_lines": axis_lines,
        "labels": labels,
    }


def build_cat_stat_cards(cat: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, "value": int(cat.get(key) or 0)}
        for key, label in CAT_STAT_LABELS.items()
    ]


def build_feed_record_cards(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    delta_labels = {
        "wisdom_delta": "智慧",
        "grit_delta": "毅力",
        "creativity_delta": "创造",
        "agility_delta": "灵敏",
        "cooperation_delta": "协作",
    }
    for row in records:
        delta_items = []
        for key, label in delta_labels.items():
            value = int(row.get(key) or 0)
            if value == 0:
                continue
            delta_items.append(
                {
                    "label": label,
                    "display": f"{value:+d}",
                    "positive": value > 0,
                }
            )
        cards.append(
            {
                **row,
                "learned_skill": str(row.get("learned_skill") or "").strip(),
                "delta_items": delta_items,
            }
        )
    return cards


def build_skill_badges(cat: dict[str, Any] | None) -> list[dict[str, str]]:
    if not cat:
        return []
    skills = parse_skill_list(str(cat.get("learned_skills_json") or ""))
    badges = []
    for skill in skills:
        badges.append(
            {
                "name": skill.get("name", ""),
                "rarity": skill.get("rarity", "N"),
                "class": f"rarity-{skill.get('rarity', 'N')}",
            }
        )
    return badges


def build_exp_progress(cat: dict[str, Any]) -> dict[str, int]:
    level = int(cat.get("level") or 0)
    exp = int(cat.get("exp") or 0)
    exp_to_next = int(cat.get("exp_to_next") or 0)
    percent = 100 if exp_to_next <= 0 else min(100, round(exp / exp_to_next * 100))
    return {
        "level": level,
        "exp": exp,
        "exp_to_next": exp_to_next,
        "percent": percent,
        "remaining": 0 if exp_to_next <= 0 else max(0, exp_to_next - exp),
    }


def build_training_cards() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": str(config["label"]),
            "description": str(config["description"]),
            "exp_gain": int(config["exp_gain"]),
        }
        for key, config in DAILY_TRAINING_ACTIONS.items()
    ]


def build_current_cat_payload(cat: dict[str, Any]) -> dict[str, Any]:
    exp_progress = build_exp_progress(cat)
    can_feed, feed_gate_hint = get_feed_gate_status(cat)
    return {
        "id": int(cat["id"]),
        "cat_no": str(cat.get("cat_no") or ""),
        "name": str(cat.get("name") or "未命名猫咪"),
        "image_url": str(cat.get("image_url") or ""),
        "stage": str(cat.get("stage") or "初始态"),
        "level": int(cat.get("level") or 0),
        "is_public": int(cat.get("is_public") or 0),
        "feed_count": int(cat.get("feed_count") or 0),
        "max_feed_count": int(cat.get("max_feed_count") or MAX_CAT_LEVEL),
        "remaining_feeds": max(
            0,
            int(cat.get("max_feed_count") or MAX_CAT_LEVEL)
            - int(cat.get("feed_count") or 0),
        ),
        "overall_power": int(cat.get("overall_power") or 0),
        "wisdom": int(cat.get("wisdom") or 0),
        "grit": int(cat.get("grit") or 0),
        "creativity": int(cat.get("creativity") or 0),
        "agility": int(cat.get("agility") or 0),
        "cooperation": int(cat.get("cooperation") or 0),
        "personality": str(cat.get("personality") or ""),
        "story_summary": str(cat.get("story_summary") or ""),
        "latest_summary": str(cat.get("latest_summary") or ""),
        "highest_level_owner_name": str(cat.get("highest_level_owner_name") or ""),
        "highest_level_reached": int(cat.get("highest_level_reached") or 0),
        "exp_progress": exp_progress,
        "skill_badges": build_skill_badges(cat),
        "feed_gate_hint": feed_gate_hint,
        "can_feed": can_feed,
    }


def build_cat_sync_payload(user_id: int, cat: dict[str, Any]) -> dict[str, Any]:
    payload = build_current_cat_payload(cat)
    owned_cards = [build_cat_card(row) for row in list_user_cats(user_id, limit=3)]
    feed_events = list_cat_timeline(int(cat["id"]), limit=10)
    latest_feed_event = next(
        (event for event in reversed(feed_events) if event.get("event_type") == "feed"),
        None,
    )
    payload["owned_cats"] = owned_cards
    payload["growth_log"] = (
        {
            "title": latest_feed_event.get("title") or "进化完成",
            "summary": build_feed_growth_summary(latest_feed_event.get("data") or {}),
            "time": latest_feed_event.get("time") or "",
        }
        if latest_feed_event
        else None
    )
    return payload


def build_share_card_payload(cat: dict[str, Any]) -> dict[str, Any]:
    persona = parse_cat_profile(str(cat.get("final_persona_json") or ""))
    return {
        "name": str(cat.get("name") or "未命名猫咪"),
        "stage": str(cat.get("stage") or "初始态"),
        "level": int(cat.get("level") or 0),
        "feed_count": int(cat.get("feed_count") or 0),
        "max_feed_count": int(cat.get("max_feed_count") or MAX_CAT_LEVEL),
        "overall_power": int(cat.get("overall_power") or 0),
        "image_url": str(cat.get("image_url") or ""),
        "personality": str(cat.get("personality") or ""),
        "story_summary": str(cat.get("story_summary") or ""),
        "highest_level_owner_name": str(cat.get("highest_level_owner_name") or ""),
        "learned_skills": parse_skill_list(str(cat.get("learned_skills_json") or "")),
        "rarity": str(persona.get("rarity") or ""),
    }


def build_feed_growth_summary(event_data: dict[str, Any]) -> str:
    delta_labels = [
        ("智慧", int(event_data.get("wisdom_delta") or 0)),
        ("毅力", int(event_data.get("grit_delta") or 0)),
        ("创造", int(event_data.get("creativity_delta") or 0)),
        ("灵敏", int(event_data.get("agility_delta") or 0)),
        ("协作", int(event_data.get("cooperation_delta") or 0)),
    ]
    delta_parts = [f"{label} +{value}" for label, value in delta_labels if value > 0]
    growth_text = (
        f"属性增长：{'，'.join(delta_parts)}"
        if delta_parts
        else "属性增长：本次没有可见变化"
    )

    learned_skill_raw = str(event_data.get("learned_skill") or "").strip()
    if not learned_skill_raw:
        return growth_text
    try:
        skill_data = json.loads(learned_skill_raw)
        skill_name = str(skill_data.get("name") or learned_skill_raw).strip()
        skill_rarity = str(skill_data.get("rarity") or "").strip().upper()
    except Exception:
        skill_name = learned_skill_raw
        skill_rarity = ""
    skill_text = (
        f"新技能：{skill_rarity}「{skill_name}」"
        if skill_rarity
        else f"新技能：「{skill_name}」"
    )
    return f"{skill_text} | {growth_text}"


def ensure_share_card_access(
    cat: dict[str, Any], current_user: dict[str, Any] | None
) -> tuple[bool, str]:
    is_owner = current_user and int(cat.get("user_id") or 0) == int(current_user["id"])
    is_public = bool(
        int(cat.get("is_public") or 0) or int(cat.get("available_for_adoption") or 0)
    )
    if is_owner or is_public:
        return True, ""
    return False, "这张分享卡暂时不可访问"


def get_feed_gate_status(cat: dict[str, Any] | None) -> tuple[bool, str]:
    if not cat:
        return False, "请先领养第一只猫。"
    level = int(cat.get("level") or 0)
    feed_count = int(cat.get("feed_count") or 0)
    max_feed_count = int(cat.get("max_feed_count") or MAX_CAT_LEVEL)
    if level >= MAX_CAT_LEVEL or feed_count >= max_feed_count:
        return (
            False,
            f"这只猫已经升到 {MAX_CAT_LEVEL} 级，无法继续喂食，但可以继续对话。",
        )
    exp_to_next = int(cat.get("exp_to_next") or 0)
    exp = int(cat.get("exp") or 0)
    if exp_to_next > 0 and exp < exp_to_next:
        return (
            False,
            f"经验还差 {exp_to_next - exp} 点，先完成日常修炼，再喂视频让它升级。",
        )
    return (
        True,
        f"经验条已满，可以喂第 {feed_count + 1} 个视频，让它升到 {level + 1} 级并学会一个新技能。",
    )


def build_cat_stage_hint(cat: dict[str, Any]) -> str:
    feed_count = int(cat.get("feed_count") or 0)
    level = int(cat.get("level") or 0)
    max_feed_count = int(cat.get("max_feed_count") or MAX_CAT_LEVEL)
    exp_progress = build_exp_progress(cat)
    can_feed, hint = get_feed_gate_status(cat)
    if level <= 0 and feed_count <= 0 and exp_progress["exp"] <= 0:
        return (
            "新领养的小猫还是 0 级，先做一次日常修炼，把经验条练满后再喂第 1 个视频。"
        )
    if can_feed:
        return hint
    if level >= MAX_CAT_LEVEL or feed_count >= max_feed_count:
        return (
            f"这只猫已经升到 {MAX_CAT_LEVEL} 级，6 个视频都学完了，之后只能继续对话。"
        )
    return f"当前 {level} 级，经验 {exp_progress['exp']}/{exp_progress['exp_to_next']}，还差 {exp_progress['remaining']} 点经验才能继续喂视频。"


def build_adoption_context(owned_count: int) -> dict[str, Any]:
    return {
        "breed_options": INITIAL_CAT_BREEDS,
        "color_options": INITIAL_CAT_COLORS,
        "can_adopt_new": owned_count < 3,
        "needs_initial_adoption": owned_count == 0,
    }


def create_async_task(task_type: str, cat_id: int | None = None) -> dict[str, Any]:
    task_id = uuid4().hex
    task = {
        "id": task_id,
        "type": task_type,
        "cat_id": int(cat_id or 0),
        "status": "pending",
        "message": "任务排队中",
        "error": "",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    ASYNC_TASKS[task_id] = task
    return task


def update_async_task(task_id: str, **kwargs: Any) -> None:
    task = ASYNC_TASKS.get(task_id)
    if not task:
        return
    task.update(kwargs)
    task["updated_at"] = time.time()


async def run_feed_task(
    task_id: str,
    cat: dict[str, Any],
    parsed_url: str,
    settings: dict[str, str],
    current_owner_name: str,
) -> None:
    update_async_task(task_id, status="running", message="正在分析视频内容")
    try:
        feed_result = await asyncio.wait_for(
            asyncio.to_thread(parse_douyin_to_feed, parsed_url, settings),
            timeout=45,
        )
        update_async_task(task_id, message="正在写入成长记录")
        updated_cat = await asyncio.to_thread(
            add_cat_feed_record, int(cat["id"]), feed_result, current_owner_name
        )

        feed_count = int(updated_cat.get("feed_count") or 0)
        update_async_task(
            task_id, message=f"第 {feed_count} 次喂养完成，正在按当前设定生成新形象"
        )
        profile = await asyncio.to_thread(
            build_growth_image_profile, updated_cat, feed_result
        )
        image_result = await asyncio.wait_for(
            asyncio.to_thread(
                generate_cat_image_with_model3,
                settings,
                updated_cat["name"],
                str(feed_result.get("video_summary") or profile["story"]),
                profile,
            ),
            timeout=60,
        )
        await asyncio.to_thread(
            update_cat_final_persona,
            int(updated_cat["id"]),
            json.dumps(profile, ensure_ascii=False),
            image_result["url"],
            profile["personality"],
            profile["story"],
            (
                "已满级"
                if int(updated_cat.get("level") or 0) >= MAX_CAT_LEVEL
                else "成长中"
            ),
        )
        update_async_task(
            task_id,
            status="done",
            message=f"第 {feed_count} 次喂养完成，已升到 {int(updated_cat.get('level') or 0)} 级并刷新猫咪形象",
        )
        return

        update_async_task(
            task_id,
            status="done",
            message=f"第 {updated_cat['feed_count']} 次喂养完成，{updated_cat['name']} 已吸收新的成长能量",
        )
    except Exception as exc:
        update_async_task(
            task_id, status="error", error=str(exc), message="喂养任务失败"
        )


async def run_adopt_task(
    task_id: str,
    user_id: int,
    owner_name: str,
    breed: str,
    color: str,
    settings: dict[str, str],
) -> None:
    update_async_task(task_id, status="running", message="正在准备领养信息")
    try:
        owned_count = await asyncio.to_thread(count_user_owned_cats, int(user_id))
        if owned_count >= 3:
            raise ValueError("每位用户最多只能拥有 3 只猫")

        await asyncio.to_thread(set_all_user_cats_inactive, int(user_id))
        update_async_task(task_id, message="正在生成初始故事与形象")

        ai_data = None
        try:
            ai_data = await asyncio.wait_for(
                asyncio.to_thread(
                    generate_initial_cat_ai_data,
                    settings,
                    owner_name,
                    breed=breed,
                    color=color,
                ),
                timeout=75,
            )
        except Exception:
            ai_data = None

        new_cat = await asyncio.to_thread(
            create_initial_cat_for_user, int(user_id), owner_name, ai_data
        )
        update_async_task(
            task_id,
            status="done",
            cat_id=int(new_cat.get("id") or 0),
            message=f"已领养一只{color}{breed}",
        )
    except Exception as exc:
        update_async_task(task_id, status="error", error=str(exc), message="领养失败")


def submit_feed_for_current_user(request: Request, raw_input: str) -> RedirectResponse:
    current_user = get_or_create_session_user(request)
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        return redirect_with_message(
            "/my-cat", error="请先领养第一只猫，再开始喂养和对话。"
        )
    can_feed, reason = get_feed_gate_status(cat)
    if not can_feed:
        return redirect_with_message("/my-cat", error=reason)
    parsed_url = extract_first_url(raw_input) or raw_input.strip()
    if not is_douyin_url(parsed_url):
        return redirect_with_message("/my-cat", error="请输入抖音作品链接")
    return redirect_with_message("/my-cat", message="任务已提交")


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
    target = (
        path if not params else f"{path}{'&' if '?' in path else '?'}{'&'.join(params)}"
    )
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


def get_or_create_session_user(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    if user:
        return user
    guest = create_guest_user()
    if not guest:
        raise HTTPException(status_code=500, detail="创建匿名用户失败")
    request.session["user_id"] = int(guest["id"])
    if not request.session.get("growth_guide_seen"):
        request.session["show_growth_guide"] = True
    return guest


def require_admin(
    request: Request, allow_password_change: bool = False
) -> tuple[dict | None, RedirectResponse | None]:
    admin = get_current_admin(request)
    if not admin:
        return None, redirect_with_message("/admin/login", error="请先登录管理员账号")
    if admin.get("must_change_password") and not allow_password_change:
        return None, redirect_with_message(
            "/admin/password", error="首次登录请先修改管理员默认密码"
        )
    return admin, None


@app.get("/")
def home(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    return redirect_with_message("/my-cat", message=message, error=error)


@app.post("/parse")
def parse_url(request: Request, raw_input: str = Form(...)):
    return submit_feed_for_current_user(request, raw_input)


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
    session_user = get_current_user(request)
    if not username.strip() or not email.strip() or not password.strip():
        return redirect_with_message("/register", error="请完整填写注册信息")
    ok, msg = register_user(username, email, password)
    if ok:
        user = authenticate_user(username, password)
        transferred = 0
        if user:
            if session_user and int(session_user.get("is_guest") or 0) == 1:
                try:
                    transferred = transfer_guest_progress(
                        int(session_user["id"]), int(user["id"])
                    )
                except Exception as exc:
                    return redirect_with_message("/register", error=str(exc))
            request.session["user_id"] = int(user["id"])
            if transferred <= 0 and not request.session.get("growth_guide_seen"):
                request.session["show_growth_guide"] = True
            else:
                request.session.pop("show_growth_guide", None)
        if transferred > 0:
            return redirect_with_message(
                "/my-cat", message="注册成功，已自动接管当前游客进度"
            )
        return redirect_with_message(
            "/my-cat", message="注册成功，请先领养你的第一只猫"
        )
    return redirect_with_message("/register", error=msg)


@app.get("/login")
def login_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
    next: str = Query(default="/my-cat"),
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
    next: str = Form("/my-cat"),
    takeover_guest: str = Form(default=""),
):
    session_user = get_current_user(request)
    user = authenticate_user(identity, password)
    if not user:
        return redirect_with_message(
            "/login", error="用户名/邮箱或密码错误", extra={"next": next}
        )
    transferred = 0
    if takeover_guest and session_user and int(session_user.get("is_guest") or 0) == 1:
        try:
            transferred = transfer_guest_progress(
                int(session_user["id"]), int(user["id"])
            )
        except Exception as exc:
            return redirect_with_message("/login", error=str(exc), extra={"next": next})
    request.session["user_id"] = int(user["id"])
    if transferred > 0:
        return redirect_with_message(
            next or "/my-cat",
            message=f"欢迎回来，{user['username']}，已接管当前游客进度",
        )
    return redirect_with_message(
        next or "/my-cat", message=f"欢迎回来，{user['username']}"
    )


@app.get("/logout")
def logout(request: Request):
    current_user = get_current_user(request)
    request.session.pop("user_id", None)
    if current_user and int(current_user.get("is_guest") or 0) == 1:
        return redirect_with_message("/", message="已退出当前会话")
    return redirect_with_message("/", message="已退出登录")


@app.get("/my-cat")
def my_cat_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    current_user = get_or_create_session_user(request)
    owned_count = count_user_owned_cats(int(current_user["id"]))
    cat = get_or_activate_user_cat(int(current_user["id"]))
    owned_cats = [
        build_cat_card(row) for row in list_user_cats(int(current_user["id"]), limit=3)
    ]
    timeline_events = list_cat_timeline(int(cat["id"]), limit=15) if cat else []
    chat_history_only = list_cat_messages(int(cat["id"]), limit=15) if cat else []

    merged_chat = []
    for msg in chat_history_only:
        merged_chat.append(
            {
                "type": "chat",
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"],
            }
        )
    for ev in timeline_events:
        content = f"[{ev['title']}] {ev['summary']}"
        if ev["event_type"] == "feed":
            content += f" | {build_feed_growth_summary(ev['data'])}"
        merged_chat.append(
            {
                "type": "event",
                "role": "system",
                "content": content,
                "created_at": ev["time"],
                "event_type": ev["event_type"],
            }
        )
    merged_chat.sort(key=lambda x: x["created_at"])

    adoption_context = build_adoption_context(owned_count)
    exp_progress = (
        build_exp_progress(cat)
        if cat
        else {"level": 0, "exp": 0, "exp_to_next": 0, "percent": 0, "remaining": 0}
    )
    skill_badges = build_skill_badges(cat) if cat else []
    training_actions = build_training_cards()
    can_feed, feed_gate_hint = get_feed_gate_status(cat)
    growth_guide_seen = bool(request.session.get("growth_guide_seen"))
    show_growth_guide = (
        (not growth_guide_seen)
        and bool(request.session.get("show_growth_guide"))
        and (
            cat is not None
            and owned_count == 1
            and int(cat.get("feed_count") or 0) == 0
        )
    )
    if show_growth_guide:
        request.session["growth_guide_seen"] = True
        request.session.pop("show_growth_guide", None)
    elif cat and int(cat.get("feed_count") or 0) > 0:
        request.session["growth_guide_seen"] = True
        request.session.pop("show_growth_guide", None)

    return templates.TemplateResponse(
        request=request,
        name="my_cat.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "admin_user": get_current_admin(request),
            "current_user": current_user,
            "cat": cat,
            "owned_cats": owned_cats,
            "owned_count": owned_count,
            "stat_cards": build_cat_stat_cards(cat) if cat else [],
            "timeline_events": timeline_events,
            "chat_history": merged_chat,
            "stage_hint": (
                build_cat_stage_hint(cat)
                if cat
                else "先完成首次领养，再开始喂养和聊天。"
            ),
            "remaining_feeds": (
                max(
                    0,
                    int(cat.get("max_feed_count") or MAX_CAT_LEVEL)
                    - int(cat.get("feed_count") or 0),
                )
                if cat
                else 0
            ),
            "can_feed": bool(cat) and can_feed,
            "feed_gate_hint": feed_gate_hint if cat else "",
            "can_generate_final": False,
            "can_adopt_new": adoption_context["can_adopt_new"],
            "can_release": bool(cat),
            "needs_initial_adoption": adoption_context["needs_initial_adoption"],
            "breed_options": adoption_context["breed_options"],
            "color_options": adoption_context["color_options"],
            "show_growth_guide": show_growth_guide,
            "exp_progress": exp_progress,
            "skill_badges": skill_badges,
            "training_actions": training_actions,
        },
    )


@app.post("/my-cat/chat")
async def my_cat_chat_submit(request: Request, content: str = Form(...)):
    current_user = get_or_create_session_user(request)
    settings = get_settings()
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        return redirect_with_message("/my-cat", error="请先领养第一只猫")
    if not content.strip():
        return redirect_with_message("/my-cat", error="请输入对话内容")

    add_cat_message(int(cat["id"]), "user", content)
    chat_history = list_cat_messages(int(cat["id"]), limit=10)
    try:
        response = generate_cat_response(settings, cat, chat_history)
        add_cat_message(int(cat["id"]), "assistant", response)
    except Exception as exc:
        add_cat_message(
            int(cat["id"]), "assistant", f"喵...我有点累了，暂时不想说话（{exc}）"
        )

    return redirect_with_message("/my-cat")


@app.post("/api/my-cat/chat/stream")
async def my_cat_chat_stream(request: Request, content: str = Form(...)):
    current_user = get_or_create_session_user(request)
    settings = get_settings()
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        raise HTTPException(status_code=400, detail="请先领养第一只猫")
    cleaned = content.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="请输入对话内容")

    add_cat_message(int(cat["id"]), "user", cleaned)
    chat_history = list_cat_messages(int(cat["id"]), limit=10)

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)
            response = await asyncio.to_thread(
                generate_cat_response, settings, cat, chat_history
            )
            assembled = ""
            for chunk in response:
                assembled += chunk
                yield f"data: {json.dumps({'type': 'token', 'token': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            add_cat_message(int(cat["id"]), "assistant", assembled)
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            error_text = f"喵...我有点累了，暂时不想说话（{exc}）"
            add_cat_message(int(cat["id"]), "assistant", error_text)
            yield f"data: {json.dumps({'type': 'error', 'message': error_text}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/my-cat/feed")
async def my_cat_feed_async(request: Request, raw_input: str = Form(...)):
    current_user = get_or_create_session_user(request)
    settings = get_settings()
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        raise HTTPException(status_code=400, detail="请先领养第一只猫")
    can_feed, reason = get_feed_gate_status(cat)
    if not can_feed:
        raise HTTPException(status_code=400, detail=reason)
    parsed_url = extract_first_url(raw_input) or raw_input.strip()
    if not is_douyin_url(parsed_url):
        raise HTTPException(status_code=400, detail="请输入抖音作品链接")

    task = create_async_task("feed", int(cat["id"]))
    asyncio.create_task(
        run_feed_task(
            task["id"], cat, parsed_url, settings, str(current_user["username"])
        )
    )
    return JSONResponse(
        {"task_id": task["id"], "status": task["status"], "message": "喂养任务已创建"}
    )


@app.post("/my-cat/train")
def my_cat_train(request: Request, action_key: str = Form(...)):
    current_user = get_or_create_session_user(request)
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        return redirect_with_message("/my-cat", error="请先领养第一只猫")
    try:
        result = perform_daily_training(int(cat["id"]), action_key)
    except Exception as exc:
        return redirect_with_message("/my-cat", error=str(exc))
    action = result["action"]
    updated_cat = result["cat"]
    remaining = max(
        0, int(updated_cat.get("exp_to_next") or 0) - int(updated_cat.get("exp") or 0)
    )
    if result["exp_full"]:
        return redirect_with_message(
            "/my-cat",
            message=f"{action['label']}完成，经验条已满，现在可以喂视频让 {updated_cat['name']} 升级了",
        )
    return redirect_with_message(
        "/my-cat",
        message=f"{action['label']}完成，获得 {result['exp_gain']} 点经验，还差 {remaining} 点经验才能喂视频",
    )


@app.post("/api/my-cat/train")
def my_cat_train_api(request: Request, action_key: str = Form(...)):
    current_user = get_or_create_session_user(request)
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        raise HTTPException(status_code=400, detail="请先领养第一只猫")
    try:
        result = perform_daily_training(int(cat["id"]), action_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    action = result["action"]
    updated_cat = result["cat"]
    remaining = max(
        0, int(updated_cat.get("exp_to_next") or 0) - int(updated_cat.get("exp") or 0)
    )
    message = (
        f"{action['label']}完成，经验条已满，现在可以喂视频让 {updated_cat['name']} 升级了"
        if result["exp_full"]
        else f"{action['label']}完成，获得 {result['exp_gain']} 点经验，还差 {remaining} 点经验才能喂视频"
    )
    return JSONResponse(
        {
            "message": message,
            "cat": build_cat_sync_payload(int(current_user["id"]), updated_cat),
        }
    )


@app.get("/api/tasks/{task_id}")
def task_status(task_id: str):
    task = ASYNC_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JSONResponse(task)


@app.get("/api/my-cat/current")
def current_cat_state(request: Request):
    current_user = get_or_create_session_user(request)
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        raise HTTPException(status_code=404, detail="当前没有猫咪")
    return JSONResponse(build_cat_sync_payload(int(current_user["id"]), cat))


@app.post("/api/my-cat/adopt")
async def my_cat_adopt_async(
    request: Request,
    breed: str = Form(...),
    color: str = Form(...),
):
    current_user = get_or_create_session_user(request)
    if not breed.strip() or not color.strip():
        raise HTTPException(status_code=400, detail="请先选择猫咪的品种和颜色")
    if count_user_owned_cats(int(current_user["id"])) >= 3:
        raise HTTPException(status_code=400, detail="每位用户最多只能拥有 3 只猫")

    settings = get_settings()
    task = create_async_task("adopt")
    asyncio.create_task(
        run_adopt_task(
            task["id"],
            int(current_user["id"]),
            str(current_user.get("username") or "未知主人"),
            breed.strip(),
            color.strip(),
            settings,
        )
    )
    return JSONResponse(
        {"task_id": task["id"], "status": task["status"], "message": "领养任务已创建"}
    )


@app.get("/cats/{cat_id}/share-card.png")
def cat_share_card(
    request: Request, cat_id: int, download: bool = Query(default=False)
):
    current_user = get_current_user(request)
    settings = get_settings()
    cat = get_cat_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="猫咪不存在")

    allowed, error_message = ensure_share_card_access(cat, current_user)
    if not allowed:
        raise HTTPException(status_code=403, detail=error_message)

    owner_name = ""
    if current_user and int(cat.get("user_id") or 0) == int(current_user["id"]):
        owner_name = str(current_user.get("username") or "")
    elif cat.get("highest_level_owner_name"):
        owner_name = str(cat.get("highest_level_owner_name") or "")

    site_url = (
        str(settings.get("public_site_url") or "").strip()
        or "https://vid2cat.zeabur.app/"
    )
    image_bytes = render_cat_share_card(
        build_share_card_payload(cat),
        owner_name=owner_name,
        site_url=site_url,
    )
    disposition = "attachment" if download else "inline"
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'{disposition}; filename="cat-{cat_id}-share-card.png"',
            "Cache-Control": "no-cache",
        },
    )


@app.post("/api/cats/{cat_id}/share-card/link")
def cat_share_card_link(request: Request, cat_id: int):
    current_user = get_current_user(request)
    settings = get_settings()
    cat = get_cat_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="猫咪不存在")

    allowed, error_message = ensure_share_card_access(cat, current_user)
    if not allowed:
        raise HTTPException(status_code=403, detail=error_message)
    if not settings.get("gitee_token"):
        raise HTTPException(
            status_code=400, detail="请先在管理员后台配置图床 Token，再生成分享链接"
        )

    owner_name = ""
    if current_user and int(cat.get("user_id") or 0) == int(current_user["id"]):
        owner_name = str(current_user.get("username") or "")
    elif cat.get("highest_level_owner_name"):
        owner_name = str(cat.get("highest_level_owner_name") or "")

    site_url = (
        str(settings.get("public_site_url") or "").strip()
        or "https://vid2cat.zeabur.app/"
    )
    image_bytes = render_cat_share_card(
        build_share_card_payload(cat),
        owner_name=owner_name,
        site_url=site_url,
    )
    uploaded_url = ImageHostScaffold.upload_bytes(image_bytes, ".png", settings)
    share_title = f"{cat.get('name') or 'vid2cat猫咪'} 的分享卡"
    share_text = f"来看看 {cat.get('name') or '这只小猫'} 在 vid2cat 的成长分享卡"
    query = urlencode(
        {"url": uploaded_url, "title": share_title, "summary": share_text}
    )
    qq_query = urlencode(
        {
            "url": uploaded_url,
            "title": share_title,
            "desc": share_text,
            "summary": share_text,
        }
    )
    return JSONResponse(
        {
            "uploaded_url": uploaded_url,
            "share_title": share_title,
            "share_text": share_text,
            "qzone_url": f"https://sns.qzone.qq.com/cgi-bin/qzshare/cgi_qzshare_onekey?{query}",
            "qq_url": f"https://connect.qq.com/widget/shareqq/index.html?{qq_query}",
            "weibo_url": f"https://service.weibo.com/share/share.php?{query}",
            "wechat_tip": "已生成分享卡链接，可复制后发送到微信或在移动端使用系统分享。",
        }
    )


@app.post("/my-cat/adopt")
@app.post("/my-cat/adopt-new")
def my_cat_adopt_new(
    request: Request,
    breed: str = Form(...),
    color: str = Form(...),
):
    current_user = get_or_create_session_user(request)
    if not breed.strip() or not color.strip():
        return redirect_with_message("/my-cat", error="请先选择猫咪的品种和颜色")
    if count_user_owned_cats(int(current_user["id"])) >= 3:
        return redirect_with_message("/my-cat", error="每位用户最多只能拥有 3 只猫")
    set_all_user_cats_inactive(int(current_user["id"]))
    settings = get_settings()
    ai_data = None
    try:
        ai_data = generate_initial_cat_ai_data(
            settings,
            current_user["username"],
            breed=breed,
            color=color,
        )
    except Exception:
        pass
    create_initial_cat_for_user(
        int(current_user["id"]), current_user["username"], ai_data
    )
    return redirect_with_message("/my-cat", message=f"已领养一只{color}{breed}")


@app.post("/my-cat/switch")
def my_cat_switch(request: Request, cat_id: int = Form(...)):
    current_user = get_or_create_session_user(request)
    switched = activate_cat_for_user(int(current_user["id"]), cat_id)
    if not switched:
        return redirect_with_message("/my-cat", error="切换猫咪失败")
    return redirect_with_message("/my-cat", message=f"已切换到 {switched['name']}")


@app.post("/my-cat/release")
def my_cat_release(request: Request, cat_id: int = Form(...)):
    current_user = get_or_create_session_user(request)
    target = get_cat_by_id(cat_id)
    if not target or int(target.get("user_id") or 0) != int(current_user["id"]):
        return redirect_with_message("/my-cat", error="这只猫不属于你")
    ok = release_cat_to_plaza(cat_id, int(current_user["id"]))
    if not ok:
        return redirect_with_message("/my-cat", error="放生失败")
    get_or_activate_user_cat(int(current_user["id"]))
    return redirect_with_message(
        "/my-cat", message=f"{target['name']} 已进入猫咪广场，等待新主人领养"
    )


@app.post("/my-cat/feed")
def my_cat_feed_submit(request: Request, raw_input: str = Form(...)):
    return submit_feed_for_current_user(request, raw_input)


@app.post("/my-cat/generate-final")
def my_cat_generate_final(request: Request):
    return redirect_with_message(
        "/my-cat", message="系统现在会在每次喂养后自动生成新形象。"
    )


@app.post("/my-cat/publish")
def my_cat_publish_toggle(request: Request, is_public: int = Form(...)):
    current_user = get_or_create_session_user(request)
    cat = get_or_activate_user_cat(int(current_user["id"]))
    if not cat:
        return redirect_with_message("/my-cat", error="请先领养第一只猫")
    update_cat_public_status(int(cat["id"]), bool(is_public))
    status_str = "已发布到猫咪广场" if is_public else "已从猫咪广场撤回"
    return redirect_with_message("/my-cat", message=status_str)


@app.get("/plaza")
def cat_plaza_page(
    request: Request,
    message: str = Query(default=""),
    error: str = Query(default=""),
):
    public_cats = [build_cat_card(row) for row in list_public_cats(limit=36)]
    return templates.TemplateResponse(
        request=request,
        name="plaza.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "cat_cards": public_cats,
            "admin_user": get_current_admin(request),
            "current_user": get_current_user(request),
        },
    )


@app.post("/plaza/adopt")
def plaza_adopt(request: Request, cat_id: int = Form(...)):
    current_user = get_or_create_session_user(request)
    try:
        adopted = adopt_plaza_cat(cat_id, int(current_user["id"]))
    except Exception as exc:
        return redirect_with_message("/plaza", error=str(exc))
    if not adopted:
        return redirect_with_message("/plaza", error="领养失败")
    return redirect_with_message("/my-cat", message=f"已成功领养 {adopted['name']}")


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
    user_rating = (
        get_user_rating(atlas_id, int(current_user["id"])) if current_user else None
    )
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
    ordered_profile_items = [
        {
            "key": key,
            "label": CAT_PROFILE_LABELS.get(key, key),
            "value": cat_profile[key],
        }
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
            "cat_display_name": cat_profile.get("name")
            or cat_profile.get("breed")
            or atlas.get("title"),
            "model1_analysis": model1_analysis,
            "user_rating": user_rating,
            "rating_summary": rating_summary,
            "ai_radar_chart": ai_radar_chart,
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
        return redirect_with_message(
            "/login", error="评论前请先登录", extra={"next": f"/atlas/{atlas_id}"}
        )
    if not content.strip():
        return redirect_with_message(f"/atlas/{atlas_id}", error="请填写评论内容")
    add_comment(atlas_id, current_user["username"], content)
    return redirect_with_message(f"/atlas/{atlas_id}", message="评论已发布")


@app.post("/atlas/{atlas_id}/rating")
def rating_submit(
    request: Request,
    atlas_id: int,
    total_score: int = Form(...),
):
    atlas = get_atlas(atlas_id)
    if not atlas:
        raise HTTPException(status_code=404, detail="图鉴不存在")
    current_user = get_current_user(request)
    if not current_user:
        return redirect_with_message(
            "/login", error="评分前请先登录", extra={"next": f"/atlas/{atlas_id}"}
        )
    if total_score < 1 or total_score > 5:
        return redirect_with_message(
            f"/atlas/{atlas_id}", error="评分必须在 1 到 5 星之间"
        )
    upsert_rating(
        atlas_id=atlas_id,
        user_id=int(current_user["id"]),
        total_score=total_score,
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
        return redirect_with_message(
            "/admin/password", message="首次登录请先修改默认密码"
        )
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
    market_cats = [build_cat_card(row) for row in list_public_cats(limit=200)]
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "message": message,
            "error": error,
            "admin": admin,
            "current_user": admin,
            "admin_user": admin,
            "header_dropdown_links": [
                {"href": "/admin/password", "label": "修改密码"},
                {"href": "/admin/logout", "label": "退出后台"},
            ],
            "settings": settings,
            "uploaded_url": uploaded_url,
            "image_host_status": ImageHostScaffold.describe(settings),
            "market_cats": market_cats,
            "market_cats_count": len(market_cats),
        },
    )


@app.post("/admin/settings")
async def admin_settings_submit(request: Request):
    admin, redirect = require_admin(request)
    if redirect:
        return redirect
    form = await request.form()
    payload = {key: str(form.get(key, "")) for key in DEFAULT_SETTINGS}
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
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, dir=temp_dir
    ) as handle:
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


@app.post("/admin/cats/delete")
def admin_delete_cat_submit(request: Request, cat_id: int = Form(...)):
    admin, redirect = require_admin(request)
    if redirect:
        return redirect
    deleted = admin_delete_cat(cat_id)
    if not deleted:
        return redirect_with_message("/admin", error="猫咪不存在或已被删除")
    return redirect_with_message("/admin", message=f"已删除猫咪 #{cat_id}")


def main() -> None:
    uvicorn.run("vid2cat.app:app", host="127.0.0.1", port=8000, reload=False)
