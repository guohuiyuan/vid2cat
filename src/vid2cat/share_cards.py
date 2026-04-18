from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps


DEFAULT_SITE_URL = "https://vid2cat.zeabur.app/"
CARD_WIDTH = 1080
CARD_HEIGHT = 1520
LOGO_PATH = Path(__file__).resolve().parent / "static" / "favicon.png"
RARITY_COLORS = {
    "SSR": ("#ff8f2f", "#fff2dc"),
    "SR": ("#a659ff", "#f5e8ff"),
    "R": ("#2a9df4", "#e6f5ff"),
    "N": ("#7e8a97", "#edf1f5"),
}


def render_cat_share_card(
    cat: dict[str, Any],
    owner_name: str = "",
    site_url: str = DEFAULT_SITE_URL,
) -> bytes:
    canvas = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), "#f7f3ec")
    draw = ImageDraw.Draw(canvas)
    _paint_background(draw)

    title_font = _load_font(58, bold=True)
    subtitle_font = _load_font(30)
    name_font = _load_font(52, bold=True)
    section_font = _load_font(30, bold=True)
    body_font = _load_font(28)
    small_font = _load_font(24)
    badge_font = _load_font(24, bold=True)
    logo = _load_logo()
    rarity = _resolve_rarity(cat)

    draw.rounded_rectangle(
        (48, 40, CARD_WIDTH - 48, CARD_HEIGHT - 40), radius=44, fill="#fffaf4"
    )
    draw.text((84, 84), "VID2CAT", fill="#1f5fae", font=title_font)
    draw.text((84, 154), "猫咪分享卡", fill="#f08a2c", font=subtitle_font)
    if logo:
        canvas.paste(logo, (CARD_WIDTH - 196, 72), logo)

    image_box = (84, 240, 996, 836)
    cat_image = _load_cat_image(str(cat.get("image_url") or ""), image_box)
    canvas.paste(cat_image, (image_box[0], image_box[1]))
    _draw_rarity_badge(draw, rarity, badge_font)

    draw.rounded_rectangle((84, 862, 996, 1118), radius=32, fill="#fff1df")
    draw.text(
        (118, 900), str(cat.get("name") or "未命名猫咪"), fill="#4f2b15", font=name_font
    )

    meta_items = [
        f"阶段 {cat.get('stage') or '初始态'}",
        f"Lv.{int(cat.get('level') or 0)}/6",
        f"总属性 {int(cat.get('overall_power') or 0)}",
        f"喂养 {int(cat.get('feed_count') or 0)}/{int(cat.get('max_feed_count') or 6)}",
    ]
    _draw_tag_row(draw, meta_items, (118, 980), body_font)

    owner_display = str(owner_name or cat.get("highest_level_owner_name") or "匿名主人")
    draw.text((118, 1048), f"当前主人 @{owner_display}", fill="#7c5a45", font=body_font)

    qr_box = (734, 1170, 958, 1394)
    _draw_qr_block(canvas, draw, qr_box, site_url, small_font)

    draw.text((84, 1168), "猫咪档案", fill="#4f2b15", font=section_font)
    summary = str(
        cat.get("story_summary")
        or cat.get("personality")
        or "这只小猫正在等待新的成长故事。"
    ).strip()
    _draw_wrapped_text(
        draw, summary, (84, 1212), 590, body_font, "#6f4d38", line_spacing=14
    )

    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def _paint_background(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 0, CARD_WIDTH, CARD_HEIGHT), fill="#f6efe5")
    draw.ellipse((-120, -80, 420, 420), fill="#dff3ff")
    draw.ellipse((780, -40, 1220, 360), fill="#ffe7c7")
    draw.ellipse((700, 1120, 1260, 1640), fill="#fde1ea")
    draw.ellipse((-180, 1050, 360, 1600), fill="#e4f5e7")


def _draw_tag_row(
    draw: ImageDraw.ImageDraw,
    tags: list[str],
    origin: tuple[int, int],
    font: ImageFont.ImageFont,
) -> None:
    x, y = origin
    for tag in tags:
        box = draw.textbbox((0, 0), tag, font=font)
        width = box[2] - box[0]
        draw.rounded_rectangle(
            (x, y, x + width + 28, y + 48), radius=20, fill="#ffffff"
        )
        draw.text((x + 14, y + 8), tag, fill="#5f4737", font=font)
        x += width + 42


def _draw_skill_badges(
    draw: ImageDraw.ImageDraw,
    skills: list[dict[str, Any]],
    origin: tuple[int, int],
    font: ImageFont.ImageFont,
) -> None:
    x, y = origin
    for skill in skills[:3]:
        rarity = str(skill.get("rarity") or "N").upper()
        fill, bg = RARITY_COLORS.get(rarity, RARITY_COLORS["N"])
        name = str(skill.get("name") or "").strip() or "未命名技能"
        label = f"{rarity} {name}"
        box = draw.textbbox((0, 0), label, font=font)
        width = box[2] - box[0]
        draw.rounded_rectangle((x, y, x + width + 28, y + 46), radius=20, fill=bg)
        draw.text((x + 14, y + 8), label, fill=fill, font=font)
        x += width + 38


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    origin: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
    line_spacing: int = 10,
) -> None:
    x, y = origin
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    for line in lines[:4]:
        draw.text((x, y), line, fill=fill, font=font)
        box = draw.textbbox((0, 0), line, font=font)
        y += (box[3] - box[1]) + line_spacing


def _draw_qr_block(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    qr_box: tuple[int, int, int, int],
    site_url: str,
    label_font: ImageFont.ImageFont,
) -> None:
    left, top, right, bottom = qr_box
    draw.rounded_rectangle(
        (left - 26, top - 26, right + 26, bottom + 96), radius=32, fill="#ffffff"
    )
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(site_url or DEFAULT_SITE_URL)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_image = qr_image.resize((right - left, bottom - top), Image.Resampling.NEAREST)
    canvas.paste(qr_image, (left, top))


def _draw_rarity_badge(
    draw: ImageDraw.ImageDraw, rarity: str, font: ImageFont.ImageFont
) -> None:
    fill, bg = RARITY_COLORS.get(rarity, RARITY_COLORS["N"])
    points = [(842, 240), (996, 240), (996, 392)]
    draw.polygon(points, fill=fill)
    box = draw.textbbox((0, 0), rarity, font=font)
    text_width = box[2] - box[0]
    draw.text((996 - text_width - 28, 262), rarity, fill="#ffffff", font=font)


def _resolve_rarity(cat: dict[str, Any]) -> str:
    rarity_order = ["SSR", "SR", "R", "N"]
    skills = cat.get("learned_skills") or []
    skill_rarities = [
        str(skill.get("rarity") or "N").upper()
        for skill in skills
        if isinstance(skill, dict)
    ]
    explicit = str(cat.get("rarity") or "").upper()
    candidates = [explicit, *skill_rarities]
    for rarity in rarity_order:
        if rarity in candidates:
            return rarity
    return "N"


def _load_cat_image(
    image_url: str, image_box: tuple[int, int, int, int]
) -> Image.Image:
    width = image_box[2] - image_box[0]
    height = image_box[3] - image_box[1]
    image = None
    if image_url:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                response = client.get(image_url)
                response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
        except Exception:
            image = None
    if image is None:
        image = _build_placeholder(width, height)
    fitted = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=40, fill=255)
    fitted.putalpha(mask)
    background = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    background.alpha_composite(fitted)
    return background.convert("RGBA")


def _build_placeholder(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "#fff4e8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width, height), radius=40, fill="#fff4e8")
    draw.ellipse(
        (width * 0.18, height * 0.12, width * 0.82, height * 0.76), fill="#ffd59f"
    )
    draw.ellipse(
        (width * 0.3, height * 0.28, width * 0.42, height * 0.4), fill="#5b3219"
    )
    draw.ellipse(
        (width * 0.58, height * 0.28, width * 0.7, height * 0.4), fill="#5b3219"
    )
    draw.rounded_rectangle(
        (width * 0.4, height * 0.44, width * 0.6, height * 0.5),
        radius=20,
        fill="#f4978e",
    )
    draw.arc(
        (width * 0.34, height * 0.44, width * 0.66, height * 0.64),
        start=15,
        end=165,
        fill="#8b4c2f",
        width=6,
    )
    return image


def _load_logo() -> Image.Image | None:
    if not LOGO_PATH.exists():
        return None
    try:
        image = Image.open(LOGO_PATH).convert("RGBA")
    except Exception:
        return None
    return image.resize((96, 96), Image.Resampling.LANCZOS)


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path(
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
            if bold
            else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        ),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                continue
    return ImageFont.load_default()
