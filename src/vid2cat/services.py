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


def build_fallback_model1_analysis(
    title: str,
    description: str,
    tags: list[str],
    hot: int,
    knowledge: int,
    rhythm: int,
    resonance: int,
) -> dict[str, Any]:
    happiness = max(60, min(98, round((hot + rhythm) / 2)))
    return {
        "total_score": hot,
        "happiness_score": happiness,
        "knowledge_score": knowledge,
        "rhythm_score": rhythm,
        "resonance_score": resonance,
        "key_moments": [
            {"time_range": "0-3秒", "summary": "开头需要更强的钩子，适合突出最有记忆点的角色或动作。"},
            {"time_range": "3-10秒", "summary": "中段承担信息展开和节奏推进，适合强化主题与情绪。"},
            {"time_range": "10秒后", "summary": "结尾适合补评论引导或收藏理由，延长传播尾效。"},
        ],
        "full_summary": description or f"视频《{title}》已经完成基础解析，适合进一步做成猫咪图鉴。",
        "optimization_tips": [
            "增强前三秒钩子",
            "突出角色辨识度与主题记忆点",
            "在结尾增加互动问题或收藏引导",
        ],
        "tags": tags[:6] or ["抖音", "猫咪图鉴"],
        "perspectives": {
            "review": "内容表达偏安全，建议继续注意素材版权、角色使用和平台规范。",
            "audience": "更容易被情绪记忆点和角色辨识度打动，建议强化互动感。",
            "author": "选题方向有潜力，可继续优化封面、节奏和评论区转化设计。",
        },
    }


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
        "输出适合图鉴系统展示的结构化中文分析。只返回 JSON，不要输出额外说明。"
    )
    user_prompt = (
        f"标题：{title}\n"
        f"作者：{author_name}\n"
        f"描述：{description or title}\n"
        f"标签：{'、'.join(tags) or '抖音、猫咪图鉴'}\n\n"
        "请返回 JSON，字段必须包含："
        "total_score, happiness_score, knowledge_score, rhythm_score, resonance_score, "
        "key_moments, full_summary, optimization_tips, tags, perspectives。\n"
        "其中：\n"
        "1. total_score 为 0-100 的总分\n"
        "2. happiness_score / knowledge_score / rhythm_score / resonance_score 分别代表快乐、知识、节奏、共鸣\n"
        "3. key_moments 为数组，每项包含 time_range 和 summary\n"
        "4. optimization_tips 为字符串数组\n"
        "5. tags 为字符串数组\n"
        "6. perspectives 为对象，必须包含 review, audience, author 三个字段"
    )
    result = AIModelRuntime.complete_text(config, system_prompt, user_prompt, temperature=0.5)
    data = json_repair.loads(result)
    key_moments = data.get("key_moments") or []
    normalized_key_moments = []
    for item in key_moments[:6]:
        if not isinstance(item, dict):
            continue
        normalized_key_moments.append(
            {
                "time_range": str(item.get("time_range") or item.get("time") or "未标注"),
                "summary": str(item.get("summary") or item.get("content") or ""),
            }
        )
    refined_tags = [str(tag).strip() for tag in (data.get("tags") or []) if str(tag).strip()][:8]
    optimization_tips = [str(tip).strip() for tip in (data.get("optimization_tips") or []) if str(tip).strip()][:8]
    perspectives = data.get("perspectives") or {}
    normalized = {
        "total_score": int(data.get("total_score") or 75),
        "happiness_score": int(data.get("happiness_score") or 72),
        "knowledge_score": int(data.get("knowledge_score") or 68),
        "rhythm_score": int(data.get("rhythm_score") or 70),
        "resonance_score": int(data.get("resonance_score") or 75),
        "key_moments": normalized_key_moments,
        "full_summary": str(data.get("full_summary") or description or title),
        "optimization_tips": optimization_tips,
        "tags": refined_tags,
        "perspectives": {
            "review": str(perspectives.get("review") or ""),
            "audience": str(perspectives.get("audience") or ""),
            "author": str(perspectives.get("author") or ""),
        },
    }
    return {
        "summary": normalized["full_summary"],
        "tips": "；".join(optimization_tips) or "建议继续补充前三秒钩子、评论区问题和封面表达。",
        "tags": refined_tags[:6],
        "raw": json.dumps(normalized, ensure_ascii=False),
        "structured": normalized,
    }


def build_cat_profile(title: str, description: str, tags: list[str]) -> dict[str, str]:
    keyword = tags[0] if tags else "猫咪"
    return {
        "name": f"{keyword}喵",
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
        "name, breed, skill, power, personality, story, appearance, rarity, image_prompt。"
    )
    raw = AIModelRuntime.complete_text(config, system_prompt, user_prompt, temperature=0.7)
    data = json_repair.loads(raw)
    profile = {
        "name": str(data.get("name") or f"{(tags[0] if tags else '猫咪')}喵"),
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
    fallback_model1 = build_fallback_model1_analysis(
        title=title,
        description=item.get("desc") or "",
        tags=tags,
        hot=hot,
        knowledge=knowledge,
        rhythm=rhythm,
        resonance=resonance,
    )
    summary = (
        f"已从抖音页面解析出基础元数据，适合作为视频图鉴雏形。标题为《{title}》，"
        "当前阶段先输出基础摘要、分数和猫咪人设草稿。"
    )
    optimization_tips = (
        "建议补封面文案、前三秒强钩子和评论区互动问题；"
        "后续可接入全模态模型补充更细的镜头分析。"
    )
    model1_output = json.dumps(fallback_model1, ensure_ascii=False)
    model2_output = ""
    model3_output = ""
    happiness_score = fallback_model1["happiness_score"]
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
            structured = model_result["structured"]
            hot = int(structured["total_score"])
            happiness_score = int(structured["happiness_score"])
            knowledge = int(structured["knowledge_score"])
            rhythm = int(structured["rhythm_score"])
            resonance = int(structured["resonance_score"])
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
        "happiness_score": happiness_score,
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
        "happiness_score": max(60, min(98, round((hot + rhythm) / 2))),
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


def parse_model1_analysis(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        data = json_repair.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    key_moments = []
    for item in data.get("key_moments") or []:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or "").strip()
        if not summary:
            continue
        key_moments.append(
            {
                "time_range": str(item.get("time_range") or "未标注"),
                "summary": summary,
            }
        )
    return {
        "total_score": int(data.get("total_score") or 0),
        "happiness_score": int(data.get("happiness_score") or 0),
        "knowledge_score": int(data.get("knowledge_score") or 0),
        "rhythm_score": int(data.get("rhythm_score") or 0),
        "resonance_score": int(data.get("resonance_score") or 0),
        "key_moments": key_moments,
        "full_summary": str(data.get("full_summary") or "").strip(),
        "optimization_tips": [str(t).strip() for t in (data.get("optimization_tips") or []) if str(t).strip()],
        "tags": [str(t).strip() for t in (data.get("tags") or []) if str(t).strip()],
        "perspectives": {
            "review": str((data.get("perspectives") or {}).get("review") or "").strip(),
            "audience": str((data.get("perspectives") or {}).get("audience") or "").strip(),
            "author": str((data.get("perspectives") or {}).get("author") or "").strip(),
        },
    }


def score_to_delta(score: int) -> int:
    if score >= 90:
        return 3
    if score >= 80:
        return 2
    if score >= 68:
        return 1
    if score >= 58:
        return 0
    return -1


def build_feed_deltas(title: str, analysis: dict[str, Any], tags: list[str]) -> dict[str, int]:
    novelty_seed = 60 + (sum(ord(ch) for ch in title) + len(tags) * 7) % 35
    grit_seed = round((analysis.get("total_score", 70) + analysis.get("resonance_score", 70)) / 2)
    return {
        "wisdom_delta": score_to_delta(int(analysis.get("knowledge_score", 70) or 70)),
        "grit_delta": score_to_delta(int(grit_seed or 70)),
        "creativity_delta": score_to_delta(int(novelty_seed)),
        "agility_delta": score_to_delta(int(analysis.get("rhythm_score", 70) or 70)),
        "cooperation_delta": score_to_delta(int(analysis.get("resonance_score", 70) or 70)),
    }


def build_initial_adoption_prompt(username: str, breed: str, color: str) -> str:
    selected_breed = breed.strip() or "动漫猫"
    selected_color = color.strip() or "奶油白"
    return (
        f"一只{selected_color}的{selected_breed}，动漫插画风格，"
        f"适合名字叫“{username}的小猫”的初始领养形象。"
        "大眼睛，柔软毛发，半身或全身立绘，表情亲人，"
        "画面干净，适合宠物养成卡片展示，高质量数字插画。"
    )


def generate_initial_cat_ai_data(
    settings: dict[str, str],
    username: str,
    breed: str = "",
    color: str = "",
    image_url: str = "",
) -> dict[str, Any]:
    selected_breed = breed.strip() or "初始动漫猫"
    selected_color = color.strip() or "奶油白"
    preferred_image_url = image_url.strip()
    default_prompt = build_initial_adoption_prompt(username, selected_breed, selected_color)
    config2 = build_model_config(settings, 2)
    system_prompt2 = (
        "你是猫咪图鉴设定师。请为一个新领养的动漫猫生成初始人设。"
        "只返回 JSON，不要输出额外说明。"
    )
    user_prompt2 = (
        f"主人名字是 {username}。\n"
        f"用户选择的品种是：{selected_breed}。\n"
        f"用户选择的毛色是：{selected_color}。\n"
        "如果没有额外图片参考，需要围绕这两个选项给出稳定、可直接生图的形象描述。\n"
        "请返回 JSON，字段必须包含："
        "name, breed, skill, power, personality, story, appearance, rarity, image_prompt。"
    )
    raw2 = AIModelRuntime.complete_text(config2, system_prompt2, user_prompt2, temperature=0.9)
    data2 = json_repair.loads(raw2)
    profile = {
        "name": str(data2.get("name") or f"{username}的小猫"),
        "breed": str(data2.get("breed") or selected_breed),
        "skill": str(data2.get("skill") or "卖萌"),
        "power": str(data2.get("power") or "50"),
        "personality": str(data2.get("personality") or "活泼可爱，充满好奇心。"),
        "story": str(data2.get("story") or f"这是 {username} 领养的第一只{selected_color}{selected_breed}。"),
        "appearance": str(
            data2.get("appearance") or f"一只{selected_color}的{selected_breed}，可爱的二次元小猫，大眼睛，毛茸茸。"
        ),
        "rarity": str(data2.get("rarity") or "N"),
        "image_prompt": str(data2.get("image_prompt") or default_prompt),
    }

    final_image_url = preferred_image_url
    if not final_image_url:
        try:
            image_result = generate_cat_image_with_model3(settings, profile["name"], profile["story"], profile)
            final_image_url = image_result["url"]
            profile["image_prompt"] = image_result.get("prompt") or profile["image_prompt"]
        except Exception:
            pass

    return {
        "profile": profile,
        "image_url": final_image_url,
    }


def generate_final_cat_persona(
    settings: dict[str, str],
    cat_name: str,
    summaries: list[str],
    stats: dict[str, int],
) -> dict[str, Any]:
    config = build_model_config(settings, 2)
    system_prompt = (
        "你是猫咪图鉴设定师。请根据猫咪成长过程中吸收的视频内容摘要，"
        "生成它的“进阶/终局”形态设定。猫咪名字叫 " + cat_name + "。"
        "只返回 JSON，不要输出额外说明。"
    )
    user_prompt = (
        f"这只猫咪的 5 维属性如下：\n"
        f"智慧: {stats.get('wisdom', 10)}\n"
        f"毅力: {stats.get('grit', 10)}\n"
        f"创造: {stats.get('creativity', 10)}\n"
        f"灵敏: {stats.get('agility', 10)}\n"
        f"协作: {stats.get('cooperation', 10)}\n\n"
        f"这只猫咪喂养过程中吸收的内容总结如下：\n"
        + "\n".join([f"{i+1}. {s}" for i, s in enumerate(summaries)])
        + "\n\n请返回 JSON，字段必须包含："
        "name, breed, skill, power, personality, story, appearance, rarity, image_prompt。"
    )
    raw = AIModelRuntime.complete_text(config, system_prompt, user_prompt, temperature=0.8)
    data = json_repair.loads(raw)
    profile = {
        "name": str(data.get("name") or cat_name),
        "breed": str(data.get("breed") or "进阶动漫猫"),
        "skill": str(data.get("skill") or "内容拟态"),
        "power": str(data.get("power") or "100"),
        "personality": str(data.get("personality") or "性格正在变得丰富。"),
        "story": str(data.get("story") or "在主人的陪伴下不断进化。"),
        "appearance": str(data.get("appearance") or "更加精致的形象。"),
        "rarity": str(data.get("rarity") or "SR"),
        "image_prompt": str(data.get("image_prompt") or ""),
    }
    return {"profile": profile, "raw": raw}


def generate_cat_response(
    settings: dict[str, str],
    cat: dict[str, Any],
    messages: list[dict[str, str]],
) -> str:
    config = build_model_config(settings, 2)
    system_prompt = (
        f"你现在是一只动漫猫，你的名字叫 {cat['name']}。"
        f"你的性格是：{cat['personality']}。"
        f"你的背景故事是：{cat['story_summary']}。"
        f"你的当前状态：智慧={cat['wisdom']}, 毅力={cat['grit']}, "
        f"创造={cat['creativity']}, 灵敏={cat['agility']}, 协作={cat['cooperation']}。"
        "请以猫咪的口吻和主人聊天。可以适当地卖萌，但要保持你的性格特色。"
        "回复要简短亲切，不要输出任何 AI 助手的客套话。"
    )
    # 限制上下文长度
    recent_messages = messages[-10:]
    history = "\n".join([f"{'主人' if m['role'] == 'user' else '猫咪'}: {m['content']}" for m in recent_messages])
    user_prompt = f"对话记录：\n{history}\n\n主人最后说：{messages[-1]['content']}\n\n请回复主人："
    return AIModelRuntime.complete_text(config, system_prompt, user_prompt, temperature=0.9)


def parse_douyin_to_feed(url: str, settings: dict[str, str] | None = None) -> dict[str, Any]:
    source_url = extract_first_url(url) or url.strip()
    if not is_douyin_url(source_url):
        raise ValueError("请输入抖音作品链接")

    try:
        canonical_url = resolve_douyin_url(source_url)
    except Exception:
        canonical_url = source_url
    aweme_id = ""
    try:
        aweme_id = extract_aweme_id(canonical_url)
    except Exception:
        aweme_id = "pending"

    title = "待解析的抖音内容"
    author_name = "未知作者"
    description = ""
    cover_url = ""
    tags: list[str] = []
    structured = build_fallback_model1_analysis(
        title=title,
        description=description,
        tags=tags,
        hot=75,
        knowledge=68,
        rhythm=72,
        resonance=70,
    )

    try:
        router_data, _ = fetch_router_payload(canonical_url, aweme_id)
        item = deep_get(
            router_data,
            ["loaderData", "video_(id)/page", "videoInfoRes", "item_list", 0],
            None,
        ) or deep_get(
            router_data,
            ["loaderData", "note_(id)/page", "videoInfoRes", "item_list", 0],
            {},
        )
        title = (item.get("desc") or f"抖音内容 {aweme_id}")[:120]
        author_name = deep_get(item, ["author", "nickname"], "未知作者")
        description = item.get("desc") or title
        cover_url = (
            deep_get(item, ["video", "cover", "url_list", 0], "")
            or deep_get(item, ["images", 0, "url_list", 0], "")
        )
        tags = [tag for tag in re.split(r"[#\s,，/]+", description) if tag][:8]
        hot, rhythm, knowledge, resonance = score_from_text(title, author_name, aweme_id)
        structured = build_fallback_model1_analysis(
            title=title,
            description=description,
            tags=tags,
            hot=hot,
            knowledge=knowledge,
            rhythm=rhythm,
            resonance=resonance,
        )
        if settings and settings.get("ai_model_1_model"):
            try:
                model_result = generate_video_analysis_with_model1(
                    settings=settings,
                    title=title,
                    description=description,
                    author_name=author_name,
                    tags=tags,
                )
                structured = model_result["structured"]
                if model_result["tags"]:
                    tags = model_result["tags"]
            except Exception:
                pass
    except Exception as exc:
        description = f"解析时出现异常：{exc}"

    deltas = build_feed_deltas(title, structured, tags)
    summary = str(structured.get("full_summary") or description or title).strip()
    return {
        "source_url": source_url,
        "canonical_url": canonical_url,
        "aweme_id": aweme_id,
        "video_title": title,
        "video_author": author_name,
        "video_cover_url": cover_url,
        "video_summary": summary,
        "tag_summary": "、".join(tags[:6]) or "抖音成长事件",
        "model1_output": json.dumps(structured, ensure_ascii=False),
        **deltas,
    }
