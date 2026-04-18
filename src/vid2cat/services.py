from __future__ import annotations

import json
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any

import httpx
import json_repair

from .integrations import AIModelConfig, AIModelRuntime, ImageHostScaffold, PromptEngineScaffold, PromptScaffoldPayload


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1"
    )
}
ROUTER_DATA_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.S | re.I)
DOUYIN_URL_RE = re.compile(r"https?://[^\s]+")
VIDEO_ID_RE = re.compile(r"(?:video|note)/(\d+)")


@dataclass(slots=True)
class SearchResult:
    title: str
    author_name: str
    share_url: str
    description: str
    tags: list[str]
    source: str = "douyin"
    cover_url: str = ""
    is_local: bool = False
    atlas_id: int | None = None


def extract_first_url(text: str) -> str | None:
    matched = DOUYIN_URL_RE.search(text or "")
    return matched.group(0) if matched else None


def is_douyin_url(text: str) -> bool:
    url = extract_first_url(text) or text.strip()
    return "douyin.com" in url or "iesdouyin.com" in url


def deep_get(data: dict[str, Any], path: list[str | int], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        try:
            if isinstance(key, int):
                current = current[key]
            else:
                current = current[key]
        except (KeyError, IndexError, TypeError):
            return default
    return current


def normalize_router_data(raw_data: str) -> dict[str, Any]:
    raw_data = raw_data.strip().rstrip("; \n\r\t")
    if not raw_data.startswith("{"):
        brace_idx = raw_data.find("{")
        if brace_idx >= 0:
            raw_data = raw_data[brace_idx:]
    return json_repair.loads(raw_data)


def score_from_text(*parts: str) -> tuple[int, int, int, int]:
    seed = sum(ord(char) for char in "".join(parts))
    hot = 70 + seed % 26
    rhythm = 66 + (seed // 3) % 28
    knowledge = 60 + (seed // 5) % 32
    resonance = 68 + (seed // 7) % 28
    return hot, rhythm, knowledge, resonance


def build_model_config(settings: dict[str, str], index: int) -> AIModelConfig:
    return AIModelConfig(
        api_url=settings.get(f"ai_model_{index}_api_url", "").strip(),
        api_key=settings.get(f"ai_model_{index}_api_key", "").strip(),
        model=settings.get(f"ai_model_{index}_model", "").strip(),
    )


def generate_video_analysis_with_model1(
    settings: dict[str, str],
    title: str,
    description: str,
    author_name: str,
    tags: list[str],
) -> dict[str, str]:
    config = build_model_config(settings, 1)
    system_prompt = (
        "你是短视频内容分析助手。请根据给定的抖音视频基础信息，"
        "输出适合图鉴系统展示的精炼中文分析。"
    )
    user_prompt = (
        f"标题：{title}\n"
        f"作者：{author_name}\n"
        f"描述：{description or title}\n"
        f"标签：{'、'.join(tags) or '抖音、猫咪图鉴'}\n\n"
        "请严格按以下格式输出：\n"
        "摘要：...\n"
        "建议：...\n"
        "标签：标签1、标签2、标签3\n"
    )
    result = AIModelRuntime.complete_text(config, system_prompt, user_prompt, temperature=0.5)
    summary = ""
    tips = ""
    refined_tags: list[str] = []
    for raw_line in result.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("摘要：") or line.startswith("摘要:"):
            summary = line.split("：", 1)[-1].split(":", 1)[-1].strip()
        elif line.startswith("建议：") or line.startswith("建议:"):
            tips = line.split("：", 1)[-1].split(":", 1)[-1].strip()
        elif line.startswith("标签：") or line.startswith("标签:"):
            tag_text = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            refined_tags = [tag.strip() for tag in re.split(r"[、,，/]+", tag_text) if tag.strip()]
    return {
        "summary": summary or result[:220],
        "tips": tips or "建议继续补充前三秒钩子、评论区问题和封面表达。",
        "tags": refined_tags[:6],
        "raw": result,
    }


def build_cat_profile(title: str, description: str, tags: list[str]) -> dict[str, str]:
    keyword = tags[0] if tags else "猫咪"
    return {
        "breed": "赛博短视频猫",
        "skill": f"{keyword}拟态",
        "power": str(82 + len(title) % 16),
        "personality": "灵动、会整活、擅长制造记忆点",
        "story": f"它从视频《{title[:18]}》里学会了把内容翻译成猫咪图鉴语言。",
        "rarity": "SSR" if len(description) % 2 == 0 else "SR",
    }


def generate_cat_profile_with_model2(
    settings: dict[str, str],
    title: str,
    summary: str,
    tags: list[str],
) -> dict[str, Any]:
    config = build_model_config(settings, 2)
    system_prompt = (
        "你是猫咪图鉴设定师。请根据视频摘要生成结构化猫咪人设。"
        "只返回 JSON，不要输出额外说明。"
    )
    user_prompt = (
        f"标题：{title}\n"
        f"摘要：{summary}\n"
        f"标签：{'、'.join(tags) or '抖音、猫咪图鉴'}\n\n"
        "请返回 JSON，字段必须包含："
        "breed, skill, power, personality, story, appearance, rarity, image_prompt。"
    )
    raw = AIModelRuntime.complete_text(config, system_prompt, user_prompt, temperature=0.7)
    data = json_repair.loads(raw)
    profile = {
        "breed": str(data.get("breed") or "赛博短视频猫"),
        "skill": str(data.get("skill") or "内容拟态"),
        "power": str(data.get("power") or "88"),
        "personality": str(data.get("personality") or "灵动、擅长表达"),
        "story": str(data.get("story") or f"它从《{title[:18]}》里获得了新的舞台感。"),
        "appearance": str(data.get("appearance") or "二次元猫咪造型，表情鲜明，色彩清爽。"),
        "rarity": str(data.get("rarity") or "SR"),
        "image_prompt": str(data.get("image_prompt") or ""),
    }
    return {"profile": profile, "raw": raw}


def generate_cat_image_with_model3(
    settings: dict[str, str],
    title: str,
    summary: str,
    profile: dict[str, str],
) -> dict[str, str]:
    config = build_model_config(settings, 3)
    if not settings.get("gitee_token"):
        raise ValueError("图传未配置 Gitee Token，模型3生成图无法上传")
    prompt = profile.get("image_prompt") or (
        f"根据短视频《{title}》生成一张二次元猫咪图鉴插画，"
        f"猫咪品种为{profile.get('breed', '赛博短视频猫')}，"
        f"技能为{profile.get('skill', '内容拟态')}，"
        f"性格为{profile.get('personality', '灵动')}，"
        f"外貌描述为{profile.get('appearance', '色彩清爽')}，"
        f"背景故事核心为：{profile.get('story', summary)}。"
        "画面精致，适合图鉴卡展示。"
    )
    result = AIModelRuntime.generate_image(config, prompt)
    source_url = result.get("url", "")
    final_url = ""
    image_host_status = ""
    if result.get("b64_json"):
        final_url = ImageHostScaffold.upload_base64_image(result["b64_json"], settings)
        image_host_status = "模型3返回 base64 图片，已上传到配置图床"
    elif source_url:
        final_url = ImageHostScaffold.mirror_remote_image(source_url, settings)
        image_host_status = "模型3返回远程图片，已镜像上传到配置图床"
    else:
        raise RuntimeError("模型3未返回可上传的图片内容")
    return {
        "url": final_url,
        "prompt": result.get("prompt", prompt),
        "status": image_host_status,
        "raw": json.dumps(
            {
                "uploaded_url": final_url,
                "source_url": source_url,
                "status": image_host_status,
                "prompt": result.get("prompt", prompt),
            },
            ensure_ascii=False,
        ),
    }


def build_prompt_scaffold(title: str, summary: str, tags: list[str]) -> str:
    return PromptEngineScaffold.build(
        PromptScaffoldPayload(
            title=title,
            summary=summary,
            tags=tags,
        )
    )


def build_search_candidates(keyword: str) -> list[SearchResult]:
    cleaned = keyword.strip()
    if not cleaned:
        return []

    presets = [
        (
            f"{cleaned} 的猫咪化爆款拆解",
            "猫咪图鉴实验室",
            f"https://www.douyin.com/search/{cleaned}",
            "当前为前端雏形阶段，真实抖音搜索接口尚未稳定接入，这里先返回可解析入口占位结果。",
            [cleaned, "搜索候选", "待接入真搜索"],
        ),
        (
            f"{cleaned} 的节奏型选题候选",
            "vid2cat-search",
            f"https://www.douyin.com/search/{cleaned}?type=video",
            "用于打通“搜索 -> 解析 -> 图鉴”链路，可直接复制链接到解析框继续处理。",
            [cleaned, "节奏", "抖音"],
        ),
        (
            f"{cleaned} 的知识型视频候选",
            "vid2cat-search",
            f"https://www.douyin.com/search/{cleaned}?type=general",
            "后续可替换为真正的站内搜索或聚合搜索适配器。",
            [cleaned, "知识", "预留扩展"],
        ),
    ]
    return [SearchResult(*item) for item in presets]


def resolve_douyin_url(url: str) -> str:
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=False, timeout=12.0) as client:
        response = client.get(url)
        location = response.headers.get("Location")
        if location:
            return location
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=12.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return str(response.url)


def extract_aweme_id(url: str) -> str:
    matched = VIDEO_ID_RE.search(url)
    if matched:
        return matched.group(1)
    fallback = re.search(r"\d{8,}", url)
    if fallback:
        return fallback.group(0)
    raise ValueError("未能从链接中提取抖音作品 ID")


def fetch_router_payload(canonical_url: str, aweme_id: str) -> tuple[dict[str, Any], str]:
    candidates = [
        canonical_url,
        f"https://www.iesdouyin.com/share/video/{aweme_id}",
        f"https://www.iesdouyin.com/share/note/{aweme_id}",
    ]
    last_error: Exception | None = None

    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=15.0) as client:
        for page_url in candidates:
            try:
                response = client.get(page_url)
                response.raise_for_status()
                matched = ROUTER_DATA_RE.search(response.text)
                if not matched:
                    continue
                return normalize_router_data(matched.group(1)), page_url
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc

    if last_error:
        raise last_error
    raise ValueError("未找到 window._ROUTER_DATA")


def build_atlas_from_router_data(
    source_url: str,
    canonical_url: str,
    aweme_id: str,
    router_data: dict[str, Any],
    settings: dict[str, str] | None = None,
) -> dict[str, Any]:
    item = deep_get(
        router_data,
        ["loaderData", "video_(id)/page", "videoInfoRes", "item_list", 0],
        None,
    ) or deep_get(
        router_data,
        ["loaderData", "note_(id)/page", "videoInfoRes", "item_list", 0],
        {},
    )

    title = (item.get("desc") or f"抖音图鉴 {aweme_id}")[:120]
    author_name = deep_get(item, ["author", "nickname"], "未知作者")
    cover_url = (
        deep_get(item, ["video", "cover", "url_list", 0], "")
        or deep_get(item, ["images", 0, "url_list", 0], "")
    )
    raw_video_url = deep_get(item, ["video", "play_addr", "url_list", 0], "")
    video_url = raw_video_url.replace("playwm", "play") if raw_video_url else ""
    duration_ms = int(deep_get(item, ["video", "duration"], 0) or 0)
    tags = [tag for tag in re.split(r"[#\s,，/]+", title) if tag][:6]
    hot, rhythm, knowledge, resonance = score_from_text(title, author_name, aweme_id)
    summary = (
        f"已从抖音页面解析出基础元数据，适合作为视频图鉴雏形。标题为《{title}》，"
        "当前阶段先输出基础摘要、分数和猫咪人设草稿。"
    )
    optimization_tips = (
        "建议补封面文案、前三秒强钩子和评论区互动问题；"
        "后续可接入全模态模型补充更细的镜头分析。"
    )
    model1_output = ""
    model2_output = ""
    model3_output = ""
    if settings:
        try:
            model_result = generate_video_analysis_with_model1(
                settings=settings,
                title=title,
                description=item.get("desc") or "",
                author_name=author_name,
                tags=tags,
            )
            summary = model_result["summary"]
            optimization_tips = model_result["tips"]
            if model_result["tags"]:
                tags = model_result["tags"]
            model1_output = model_result["raw"]
        except Exception as exc:
            optimization_tips += f" 模型1调用失败，已回退到本地摘要。原因：{exc}"
    cat_profile = build_cat_profile(title, summary, tags)
    prompt_scaffold = build_prompt_scaffold(title, summary, tags)
    cat_image_url = ""
    cat_image_prompt = ""
    image_host_status = ImageHostScaffold.describe(settings)
    if settings:
        try:
            profile_result = generate_cat_profile_with_model2(settings, title, summary, tags)
            cat_profile = profile_result["profile"]
            model2_output = profile_result["raw"]
            prompt_scaffold = build_prompt_scaffold(title, summary, tags)
        except Exception as exc:
            optimization_tips += f" 模型2调用失败，已回退到本地猫咪模板。原因：{exc}"
        try:
            image_result = generate_cat_image_with_model3(settings, title, summary, cat_profile)
            cat_image_url = image_result["url"]
            cat_image_prompt = image_result["prompt"]
            image_host_status = image_result["status"]
            model3_output = image_result["raw"]
        except Exception as exc:
            image_host_status = f"{image_host_status}；模型3调用失败：{exc}"
    if cat_profile.get("image_prompt") and not cat_image_prompt:
        cat_image_prompt = cat_profile["image_prompt"]
    return {
        "title": title,
        "source_url": source_url,
        "canonical_url": canonical_url,
        "aweme_id": aweme_id,
        "author_name": author_name,
        "author_avatar": deep_get(item, ["author", "avatar_thumb", "url_list", 0], ""),
        "cover_url": cover_url,
        "video_url": video_url,
        "duration_seconds": duration_ms // 1000,
        "description": item.get("desc") or "",
        "tags": tags or ["抖音", "猫咪图鉴"],
        "status": "parsed",
        "hot_score": hot,
        "rhythm_score": rhythm,
        "knowledge_score": knowledge,
        "resonance_score": resonance,
        "ai_summary": summary,
        "optimization_tips": optimization_tips,
        "model1_output": model1_output,
        "model2_output": model2_output,
        "model3_output": model3_output,
        "cat_profile_json": json.dumps(cat_profile, ensure_ascii=False),
        "prompt_scaffold": prompt_scaffold,
        "cat_image_url": cat_image_url,
        "cat_image_prompt": cat_image_prompt,
        "image_host_status": image_host_status,
        "parse_error": "",
    }


def build_fallback_atlas(
    source_url: str,
    canonical_url: str,
    error_message: str,
    settings: dict[str, str] | None = None,
) -> dict[str, Any]:
    aweme_id = extract_aweme_id(canonical_url) if re.search(r"\d{8,}", canonical_url) else "pending"
    summary = (
        "抖音解析暂未完全成功，已保留原始链接、失败原因和图鉴骨架。"
        "后续只需要替换解析器实现即可复用当前页面、评论和用户系统。"
    )
    hot, rhythm, knowledge, resonance = score_from_text(canonical_url, error_message)
    cat_profile = build_cat_profile("待补全图鉴", summary, ["占位", "待补全"])
    return {
        "title": "待补全的抖音图鉴",
        "source_url": source_url,
        "canonical_url": canonical_url,
        "aweme_id": aweme_id,
        "author_name": "解析器占位",
        "author_avatar": "",
        "cover_url": "",
        "video_url": "",
        "duration_seconds": 0,
        "description": "当前只生成可继续开发的图鉴骨架，便于后续接入真实解析和 AI 能力。",
        "tags": ["占位", "解析失败", "待接入"],
        "status": "fallback",
        "hot_score": hot,
        "rhythm_score": rhythm,
        "knowledge_score": knowledge,
        "resonance_score": resonance,
        "ai_summary": summary,
        "optimization_tips": "优先补 cookie、真搜索适配器和失败重试逻辑。",
        "model1_output": "",
        "model2_output": "",
        "model3_output": "",
        "cat_profile_json": json.dumps(cat_profile, ensure_ascii=False),
        "prompt_scaffold": build_prompt_scaffold("待补全图鉴", summary, ["占位", "待接入"]),
        "cat_image_url": "",
        "cat_image_prompt": "",
        "image_host_status": ImageHostScaffold.describe(settings),
        "parse_error": error_message,
    }


def parse_douyin_to_atlas(url: str, settings: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        source_url = extract_first_url(url) or url.strip()
        canonical_url = resolve_douyin_url(source_url)
        aweme_id = extract_aweme_id(canonical_url)
        router_data, resolved_page = fetch_router_payload(canonical_url, aweme_id)
        return build_atlas_from_router_data(source_url, resolved_page, aweme_id, router_data, settings=settings)
    except Exception as exc:  # pragma: no cover - network dependent
        source_url = extract_first_url(url) or url.strip()
        canonical_url = source_url
        if not canonical_url.startswith("http"):
            canonical_url = f"https://{canonical_url.lstrip('/')}"
        return build_fallback_atlas(source_url, canonical_url, str(exc), settings=settings)


def enrich_local_results(rows: list[dict[str, Any]]) -> list[SearchResult]:
    results: list[SearchResult] = []
    for row in rows:
        description = row.get("ai_summary") or row.get("description") or "本地图鉴记录"
        tags = [tag.strip() for tag in (row.get("tags") or "").split(",") if tag.strip()]
        results.append(
            SearchResult(
                title=row.get("title") or "未命名图鉴",
                author_name=row.get("author_name") or "未知作者",
                share_url=row.get("source_url") or "",
                description=description,
                tags=tags,
                cover_url=row.get("cover_url") or "",
                is_local=True,
                atlas_id=row.get("id"),
            )
        )
    return results


def score_overview(atlas: dict[str, Any]) -> dict[str, int]:
    values = {
        "爆款": int(atlas.get("hot_score") or 0),
        "节奏": int(atlas.get("rhythm_score") or 0),
        "知识": int(atlas.get("knowledge_score") or 0),
        "共鸣": int(atlas.get("resonance_score") or 0),
    }
    values["总分"] = round(mean(values.values()))
    return values


def parse_cat_profile(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(key): str(value) for key, value in data.items()}
