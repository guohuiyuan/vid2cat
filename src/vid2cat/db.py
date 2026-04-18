from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import secrets
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "vid2cat.db"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"
DEFAULT_SETTINGS = {
    "ai_model_1_api_url": "",
    "ai_model_1_api_key": "",
    "ai_model_1_model": "qwen3.5-omni",
    "ai_model_2_api_url": "",
    "ai_model_2_api_key": "",
    "ai_model_2_model": "longcat-flash-chat",
    "ai_model_3_api_url": "",
    "ai_model_3_api_key": "",
    "ai_model_3_model": "grok-imagine-image-lite",
    "gitee_repo": "linbingwei/heikeson",
    "gitee_branch": "master",
    "gitee_path": "images",
    "gitee_token": "",
    "gitee_custom_url": "",
    "extra_upload_token": "",
}


def utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def verify_password(stored_password: str, password: str) -> bool:
    if not stored_password:
        return False
    if stored_password.startswith("sha256$"):
        _, salt, expected = stored_password.split("$", 2)
        actual = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
        return secrets.compare_digest(actual, expected)
    return secrets.compare_digest(stored_password, password)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row["name"] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                must_change_password INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS atlases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL UNIQUE,
                canonical_url TEXT,
                aweme_id TEXT,
                author_name TEXT,
                author_avatar TEXT,
                cover_url TEXT,
                video_url TEXT,
                duration_seconds INTEGER DEFAULT 0,
                description TEXT,
                tags TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                hot_score INTEGER NOT NULL DEFAULT 72,
                happiness_score INTEGER NOT NULL DEFAULT 70,
                rhythm_score INTEGER NOT NULL DEFAULT 70,
                knowledge_score INTEGER NOT NULL DEFAULT 68,
                resonance_score INTEGER NOT NULL DEFAULT 75,
                ai_summary TEXT,
                optimization_tips TEXT,
                model1_output TEXT,
                model2_output TEXT,
                model3_output TEXT,
                cat_profile_json TEXT,
                prompt_scaffold TEXT,
                cat_image_url TEXT,
                cat_image_prompt TEXT,
                image_host_status TEXT,
                parse_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                atlas_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(atlas_id) REFERENCES atlases(id)
            );

            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                atlas_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                happiness_score INTEGER NOT NULL,
                knowledge_score INTEGER NOT NULL,
                rhythm_score INTEGER NOT NULL,
                resonance_score INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(atlas_id, user_id),
                FOREIGN KEY(atlas_id) REFERENCES atlases(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        ensure_column(conn, "users", "role", "TEXT NOT NULL DEFAULT 'user'")
        ensure_column(conn, "users", "must_change_password", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "atlases", "happiness_score", "INTEGER NOT NULL DEFAULT 70")
        ensure_column(conn, "atlases", "model1_output", "TEXT")
        ensure_column(conn, "atlases", "model2_output", "TEXT")
        ensure_column(conn, "atlases", "model3_output", "TEXT")
        ensure_column(conn, "atlases", "cat_image_url", "TEXT")
        ensure_column(conn, "atlases", "cat_image_prompt", "TEXT")
        bootstrap_settings(conn)
        bootstrap_admin(conn)
    seed_demo_data()


def bootstrap_settings(conn: sqlite3.Connection) -> None:
    now = utcnow()
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (key, value, now),
        )


def bootstrap_admin(conn: sqlite3.Connection) -> None:
    admin = conn.execute(
        "SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
    ).fetchone()
    if admin:
        return

    conn.execute(
        """
        INSERT INTO users (username, email, password, created_at, role, must_change_password)
        VALUES (?, ?, ?, ?, 'admin', 1)
        """,
        (
            DEFAULT_ADMIN_USERNAME,
            "admin@vid2cat.local",
            hash_password(DEFAULT_ADMIN_PASSWORD),
            utcnow(),
        ),
    )


def seed_demo_data() -> None:
    examples = [
        {
            "title": "样例猫咪图鉴：会踩点的橘猫",
            "source_url": "https://www.douyin.com/video/demo-orange-cat",
            "canonical_url": "https://www.douyin.com/video/demo-orange-cat",
            "aweme_id": "demo-orange-cat",
            "author_name": "vid2cat-demo",
            "cover_url": "",
            "video_url": "",
            "duration_seconds": 18,
            "description": "用于展示首页图鉴卡片、评论区和 AI 生成结果结构的示例数据。",
            "tags": "猫咪,踩点,样例",
            "status": "demo",
            "hot_score": 88,
            "happiness_score": 90,
            "rhythm_score": 92,
            "knowledge_score": 64,
            "resonance_score": 86,
            "ai_summary": "前 3 秒直接给出猫咪高能动作，中段节奏密集，结尾有记忆点，适合作为爆款宠物短视频模板。",
            "optimization_tips": "补一个字幕钩子；封面突出猫咪表情；评论区可引导观众二创。",
            "model1_output": "",
            "model2_output": "",
            "model3_output": "",
            "cat_profile_json": '{"breed":"橘猫","skill":"踩点突袭","power":"89","personality":"戏精、亲人、节奏感强","story":"它把每段爆款视频都当作自己的舞台。","rarity":"SSR"}',
            "prompt_scaffold": "请根据视频总结、标签和角色设定，生成二次元猫咪图鉴提示词。",
            "cat_image_url": "",
            "cat_image_prompt": "",
            "image_host_status": "待接入 PicGo/Core",
            "parse_error": "",
        },
        {
            "title": "样例猫咪图鉴：知识型布偶",
            "source_url": "https://www.douyin.com/video/demo-ragdoll",
            "canonical_url": "https://www.douyin.com/video/demo-ragdoll",
            "aweme_id": "demo-ragdoll",
            "author_name": "vid2cat-demo",
            "cover_url": "",
            "video_url": "",
            "duration_seconds": 35,
            "description": "模拟知识类视频转图鉴的展示数据，强调 HKRR 中的知识维度。",
            "tags": "知识,布偶,样例",
            "status": "demo",
            "hot_score": 81,
            "happiness_score": 72,
            "rhythm_score": 73,
            "knowledge_score": 91,
            "resonance_score": 78,
            "ai_summary": "适合讲解型内容，重点在于拆出知识点和猫咪人设的映射关系。",
            "optimization_tips": "增加章节感；补案例镜头；引导收藏。",
            "model1_output": "",
            "model2_output": "",
            "model3_output": "",
            "cat_profile_json": '{"breed":"布偶猫","skill":"冷静拆解","power":"84","personality":"温和、聪明、条理清晰","story":"专门把复杂视频拆成人人都能懂的猫咪图鉴。","rarity":"SR"}',
            "prompt_scaffold": "请输出猫咪品种、技能、稀有度、外貌描述和绘图提示词。",
            "cat_image_url": "",
            "cat_image_prompt": "",
            "image_host_status": "待接入 PicGo/Core",
            "parse_error": "",
        },
    ]

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM atlases").fetchone()[0]
        if count > 0:
            return
        for item in examples:
            now = utcnow()
            conn.execute(
                """
                INSERT INTO atlases (
                    title, source_url, canonical_url, aweme_id, author_name, cover_url, video_url,
                    duration_seconds, description, tags, status, hot_score, happiness_score, rhythm_score,
                    knowledge_score, resonance_score, ai_summary, optimization_tips, model1_output, model2_output, model3_output,
                    cat_profile_json, prompt_scaffold, cat_image_url, cat_image_prompt, image_host_status, parse_error,
                    created_at, updated_at, author_avatar
                ) VALUES (
                    :title, :source_url, :canonical_url, :aweme_id, :author_name, :cover_url, :video_url,
                    :duration_seconds, :description, :tags, :status, :hot_score, :happiness_score, :rhythm_score,
                    :knowledge_score, :resonance_score, :ai_summary, :optimization_tips, :model1_output, :model2_output, :model3_output,
                    :cat_profile_json, :prompt_scaffold, :cat_image_url, :cat_image_prompt, :image_host_status, :parse_error,
                    :created_at, :updated_at, ''
                )
                """,
                {
                    **item,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def normalize_tags(value: list[str] | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return ",".join(tag.strip() for tag in value if tag and tag.strip())


def save_atlas(atlas: dict[str, Any]) -> int:
    now = utcnow()
    payload = {
        "title": atlas.get("title") or "未命名抖音图鉴",
        "source_url": atlas["source_url"],
        "canonical_url": atlas.get("canonical_url", atlas["source_url"]),
        "aweme_id": atlas.get("aweme_id", ""),
        "author_name": atlas.get("author_name", "未知作者"),
        "author_avatar": atlas.get("author_avatar", ""),
        "cover_url": atlas.get("cover_url", ""),
        "video_url": atlas.get("video_url", ""),
        "duration_seconds": int(atlas.get("duration_seconds") or 0),
        "description": atlas.get("description", ""),
        "tags": normalize_tags(atlas.get("tags")),
        "status": atlas.get("status", "draft"),
        "hot_score": int(atlas.get("hot_score") or 72),
        "happiness_score": int(atlas.get("happiness_score") or 70),
        "rhythm_score": int(atlas.get("rhythm_score") or 70),
        "knowledge_score": int(atlas.get("knowledge_score") or 68),
        "resonance_score": int(atlas.get("resonance_score") or 75),
        "ai_summary": atlas.get("ai_summary", ""),
        "optimization_tips": atlas.get("optimization_tips", ""),
        "model1_output": atlas.get("model1_output", ""),
        "model2_output": atlas.get("model2_output", ""),
        "model3_output": atlas.get("model3_output", ""),
        "cat_profile_json": atlas.get("cat_profile_json", ""),
        "prompt_scaffold": atlas.get("prompt_scaffold", ""),
        "cat_image_url": atlas.get("cat_image_url", ""),
        "cat_image_prompt": atlas.get("cat_image_prompt", ""),
        "image_host_status": atlas.get("image_host_status", ""),
        "parse_error": atlas.get("parse_error", ""),
        "created_at": now,
        "updated_at": now,
    }

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, created_at FROM atlases WHERE source_url = ?",
            (payload["source_url"],),
        ).fetchone()
        if existing:
            payload["created_at"] = existing["created_at"]
            conn.execute(
                """
                UPDATE atlases
                SET title = :title,
                    canonical_url = :canonical_url,
                    aweme_id = :aweme_id,
                    author_name = :author_name,
                    author_avatar = :author_avatar,
                    cover_url = :cover_url,
                    video_url = :video_url,
                    duration_seconds = :duration_seconds,
                    description = :description,
                    tags = :tags,
                    status = :status,
                    hot_score = :hot_score,
                    happiness_score = :happiness_score,
                    rhythm_score = :rhythm_score,
                    knowledge_score = :knowledge_score,
                    resonance_score = :resonance_score,
                    ai_summary = :ai_summary,
                    optimization_tips = :optimization_tips,
                    model1_output = :model1_output,
                    model2_output = :model2_output,
                    model3_output = :model3_output,
                    cat_profile_json = :cat_profile_json,
                    prompt_scaffold = :prompt_scaffold,
                    cat_image_url = :cat_image_url,
                    cat_image_prompt = :cat_image_prompt,
                    image_host_status = :image_host_status,
                    parse_error = :parse_error,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                {**payload, "id": existing["id"]},
            )
            return int(existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO atlases (
                title, source_url, canonical_url, aweme_id, author_name, author_avatar, cover_url,
                video_url, duration_seconds, description, tags, status, hot_score, happiness_score, rhythm_score,
                knowledge_score, resonance_score, ai_summary, optimization_tips, model1_output, model2_output, model3_output,
                cat_profile_json, prompt_scaffold, cat_image_url, cat_image_prompt, image_host_status, parse_error, created_at, updated_at
            ) VALUES (
                :title, :source_url, :canonical_url, :aweme_id, :author_name, :author_avatar, :cover_url,
                :video_url, :duration_seconds, :description, :tags, :status, :hot_score, :happiness_score, :rhythm_score,
                :knowledge_score, :resonance_score, :ai_summary, :optimization_tips, :model1_output, :model2_output, :model3_output,
                :cat_profile_json, :prompt_scaffold, :cat_image_url, :cat_image_prompt, :image_host_status, :parse_error, :created_at, :updated_at
            )
            """,
            payload,
        )
        return int(cursor.lastrowid)


def list_atlases(keyword: str = "", limit: int = 12) -> list[dict[str, Any]]:
    query = """
        SELECT * FROM atlases
    """
    params: list[Any] = []
    if keyword.strip():
        query += """
            WHERE title LIKE ? OR author_name LIKE ? OR tags LIKE ? OR source_url LIKE ? OR cat_profile_json LIKE ?
        """
        fuzzy = f"%{keyword.strip()}%"
        params.extend([fuzzy, fuzzy, fuzzy, fuzzy, fuzzy])
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_atlas(atlas_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM atlases WHERE id = ?", (atlas_id,)).fetchone()
    return dict(row) if row else None


def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    now = utcnow()
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (username, email, password, created_at, role, must_change_password)
                VALUES (?, ?, ?, ?, 'user', 0)
                """,
                (username.strip(), email.strip(), hash_password(password.strip()), now),
            )
        return True, "注册成功"
    except sqlite3.IntegrityError:
        return False, "用户名或邮箱已存在"


def list_recent_users(limit: int = 8) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, created_at, role, must_change_password, password
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def authenticate_user(identity: str, password: str) -> dict[str, Any] | None:
    cleaned = identity.strip()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, created_at, role, must_change_password, password
            FROM users
            WHERE (username = ? OR email = ?) AND role = 'user'
            LIMIT 1
            """,
            (cleaned, cleaned),
        ).fetchone()
    if not row:
        return None
    user = dict(row)
    if not verify_password(user.get("password", ""), password.strip()):
        return None
    return user


def authenticate_admin(username: str, password: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, created_at, role, must_change_password, password
            FROM users
            WHERE username = ? AND role = 'admin'
            """,
            (username.strip(),),
        ).fetchone()
    if not row:
        return None
    user = dict(row)
    if not verify_password(user.get("password", ""), password.strip()):
        return None
    return user


def update_user_password(user_id: int, new_password: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET password = ?, must_change_password = 0
            WHERE id = ?
            """,
            (hash_password(new_password.strip()), user_id),
        )


def get_settings() -> dict[str, str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings ORDER BY key").fetchall()
    settings = DEFAULT_SETTINGS.copy()
    settings.update({row["key"]: row["value"] for row in rows})
    return settings


def update_settings(values: dict[str, str]) -> None:
    allowed = set(DEFAULT_SETTINGS)
    now = utcnow()
    with get_connection() as conn:
        for key, value in values.items():
            if key not in allowed:
                continue
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str(value).strip(), now),
            )


def add_comment(atlas_id: int, username: str, content: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO comments (atlas_id, username, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (atlas_id, username.strip(), content.strip(), utcnow()),
        )


def list_comments(atlas_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                comments.id,
                comments.atlas_id,
                comments.username,
                comments.content,
                comments.created_at,
                ratings.happiness_score,
                ratings.knowledge_score,
                ratings.rhythm_score,
                ratings.resonance_score
            FROM comments
            LEFT JOIN users
                ON users.username = comments.username
                AND users.role = 'user'
            LEFT JOIN ratings
                ON ratings.atlas_id = comments.atlas_id
                AND ratings.user_id = users.id
            WHERE comments.atlas_id = ?
            ORDER BY comments.created_at DESC
            """,
            (atlas_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_rating(
    atlas_id: int,
    user_id: int,
    happiness_score: int,
    knowledge_score: int,
    rhythm_score: int,
    resonance_score: int,
) -> None:
    now = utcnow()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ratings (
                atlas_id, user_id, happiness_score, knowledge_score, rhythm_score, resonance_score,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(atlas_id, user_id) DO UPDATE SET
                happiness_score = excluded.happiness_score,
                knowledge_score = excluded.knowledge_score,
                rhythm_score = excluded.rhythm_score,
                resonance_score = excluded.resonance_score,
                updated_at = excluded.updated_at
            """,
            (
                atlas_id,
                user_id,
                happiness_score,
                knowledge_score,
                rhythm_score,
                resonance_score,
                now,
                now,
            ),
        )


def get_user_rating(atlas_id: int, user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT atlas_id, user_id, happiness_score, knowledge_score, rhythm_score, resonance_score, updated_at
            FROM ratings
            WHERE atlas_id = ? AND user_id = ?
            """,
            (atlas_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def get_rating_summary(atlas_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS rating_count,
                AVG(happiness_score) AS avg_happiness_score,
                AVG(knowledge_score) AS avg_knowledge_score,
                AVG(rhythm_score) AS avg_rhythm_score,
                AVG(resonance_score) AS avg_resonance_score
            FROM ratings
            WHERE atlas_id = ?
            """,
            (atlas_id,),
        ).fetchone()
    if not row:
        return {
            "rating_count": 0,
            "avg_happiness_score": 0,
            "avg_knowledge_score": 0,
            "avg_rhythm_score": 0,
            "avg_resonance_score": 0,
        }
    return {
        "rating_count": int(row["rating_count"] or 0),
        "avg_happiness_score": round(float(row["avg_happiness_score"] or 0), 1),
        "avg_knowledge_score": round(float(row["avg_knowledge_score"] or 0), 1),
        "avg_rhythm_score": round(float(row["avg_rhythm_score"] or 0), 1),
        "avg_resonance_score": round(float(row["avg_resonance_score"] or 0), 1),
    }
