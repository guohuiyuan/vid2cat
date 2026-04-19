from __future__ import annotations

import hashlib
import json
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
    "public_site_url": "https://vid2cat.zeabur.app/",
}
MAX_CAT_LEVEL = 6
DEFAULT_EXP_TO_NEXT = 100
DAILY_TRAINING_ACTIONS: dict[str, dict[str, Any]] = {
    "sunbath": {
        "label": "晒太阳",
        "exp_gain": 18,
        "description": "猫族经典，晒太阳时状态自然恢复。",
        "summary": "晒了一会儿太阳，毛茸茸的身体慢慢暖起来了，状态也在静静回升。",
    },
    "groom": {
        "label": "冥想",
        "exp_gain": 30,
        "description": "舔毛动作是最高效的冥想方式。",
        "summary": "通过舔毛和整理呼吸进入冥想状态，心绪沉静下来，经验涨得很快。",
    },
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


def ensure_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
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
                must_change_password INTEGER NOT NULL DEFAULT 0,
                is_guest INTEGER NOT NULL DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS cats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cat_no TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT '初始态',
                feed_count INTEGER NOT NULL DEFAULT 0,
                max_feed_count INTEGER NOT NULL DEFAULT 6,
                level INTEGER NOT NULL DEFAULT 0,
                exp INTEGER NOT NULL DEFAULT 0,
                exp_to_next INTEGER NOT NULL DEFAULT 100,
                learned_skills_json TEXT NOT NULL DEFAULT '[]',
                wisdom INTEGER NOT NULL DEFAULT 50,
                grit INTEGER NOT NULL DEFAULT 50,
                creativity INTEGER NOT NULL DEFAULT 50,
                agility INTEGER NOT NULL DEFAULT 50,
                cooperation INTEGER NOT NULL DEFAULT 50,
                overall_power INTEGER NOT NULL DEFAULT 250,
                image_url TEXT NOT NULL DEFAULT '',
                personality TEXT NOT NULL DEFAULT '',
                story_summary TEXT NOT NULL DEFAULT '',
                latest_summary TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                is_public INTEGER NOT NULL DEFAULT 0,
                available_for_adoption INTEGER NOT NULL DEFAULT 0,
                released_at TEXT NOT NULL DEFAULT '',
                highest_level_owner_id INTEGER NOT NULL DEFAULT 0,
                highest_level_owner_name TEXT NOT NULL DEFAULT '',
                highest_level_reached INTEGER NOT NULL DEFAULT 0,
                final_persona_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS cat_feed_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER NOT NULL,
                feed_index INTEGER NOT NULL,
                source_url TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                aweme_id TEXT NOT NULL DEFAULT '',
                video_title TEXT NOT NULL,
                video_author TEXT NOT NULL DEFAULT '',
                video_cover_url TEXT NOT NULL DEFAULT '',
                video_summary TEXT NOT NULL DEFAULT '',
                tag_summary TEXT NOT NULL DEFAULT '',
                wisdom_delta INTEGER NOT NULL DEFAULT 0,
                grit_delta INTEGER NOT NULL DEFAULT 0,
                creativity_delta INTEGER NOT NULL DEFAULT 0,
                agility_delta INTEGER NOT NULL DEFAULT 0,
                cooperation_delta INTEGER NOT NULL DEFAULT 0,
                learned_skill TEXT NOT NULL DEFAULT '',
                skill_commentary TEXT NOT NULL DEFAULT '',
                model1_output TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(cat_id) REFERENCES cats(id)
            );
            CREATE TABLE IF NOT EXISTS cat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(cat_id) REFERENCES cats(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cat_training_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER NOT NULL,
                action_key TEXT NOT NULL,
                exp_gain INTEGER NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(cat_id) REFERENCES cats(id)
            );
            """
        )
        ensure_column(conn, "users", "role", "TEXT NOT NULL DEFAULT 'user'")
        ensure_column(
            conn, "users", "must_change_password", "INTEGER NOT NULL DEFAULT 0"
        )
        ensure_column(conn, "users", "is_guest", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "atlases", "happiness_score", "INTEGER NOT NULL DEFAULT 70")
        ensure_column(conn, "atlases", "model1_output", "TEXT")
        ensure_column(conn, "atlases", "model2_output", "TEXT")
        ensure_column(conn, "atlases", "model3_output", "TEXT")
        ensure_column(conn, "atlases", "cat_image_url", "TEXT")
        ensure_column(conn, "atlases", "cat_image_prompt", "TEXT")
        ensure_column(conn, "ratings", "total_score", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "cats", "is_active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "cats", "is_public", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(
            conn, "cats", "available_for_adoption", "INTEGER NOT NULL DEFAULT 0"
        )
        ensure_column(conn, "cats", "released_at", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "cats", "final_persona_json", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "cats", "level", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "cats", "exp", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "cats", "exp_to_next", "INTEGER NOT NULL DEFAULT 100")
        ensure_column(conn, "cats", "learned_skills_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(
            conn, "cats", "highest_level_owner_id", "INTEGER NOT NULL DEFAULT 0"
        )
        ensure_column(
            conn, "cats", "highest_level_owner_name", "TEXT NOT NULL DEFAULT ''"
        )
        ensure_column(
            conn, "cats", "highest_level_reached", "INTEGER NOT NULL DEFAULT 0"
        )
        ensure_column(
            conn, "cat_feed_records", "learned_skill", "TEXT NOT NULL DEFAULT ''"
        )
        ensure_column(
            conn,
            "cat_feed_records",
            "skill_commentary",
            "TEXT NOT NULL DEFAULT ''",
        )

        # 迁移：移除 cats 表 user_id 的 UNIQUE 约束 (SQLite 需要通过重建表实现)
        rows = conn.execute("PRAGMA table_info(cats)").fetchall()
        if rows:
            indexes = conn.execute("PRAGMA index_list(cats)").fetchall()
            has_unique_userid = any(
                idx["unique"] == 1
                and "user_id"
                in [
                    info["name"]
                    for info in conn.execute(
                        f"PRAGMA index_info({idx['name']})"
                    ).fetchall()
                ]
                for idx in indexes
            )
            if has_unique_userid:
                rebuild_cats_table_without_user_unique(conn)
            conn.execute(
                "UPDATE cats SET max_feed_count = ? WHERE max_feed_count != ?",
                (MAX_CAT_LEVEL, MAX_CAT_LEVEL),
            )
            conn.execute(
                """
                UPDATE cats
                SET level = CASE
                    WHEN COALESCE(level, 0) = 0 AND COALESCE(feed_count, 0) > 0 THEN MIN(COALESCE(feed_count, 0), ?)
                    ELSE MIN(COALESCE(level, 0), ?)
                END
                """,
                (MAX_CAT_LEVEL, MAX_CAT_LEVEL),
            )
            conn.execute(
                """
                UPDATE cats
                SET learned_skills_json = CASE
                    WHEN TRIM(COALESCE(learned_skills_json, '')) = '' THEN '[]'
                    ELSE learned_skills_json
                END,
                    highest_level_owner_id = CASE
                        WHEN COALESCE(highest_level_owner_id, 0) = 0 THEN user_id
                        ELSE highest_level_owner_id
                    END,
                    highest_level_owner_name = CASE
                        WHEN TRIM(COALESCE(highest_level_owner_name, '')) = '' THEN COALESCE(
                            (SELECT username FROM users WHERE users.id = cats.user_id LIMIT 1),
                            ''
                        )
                        ELSE highest_level_owner_name
                    END,
                    highest_level_reached = MAX(COALESCE(highest_level_reached, 0), COALESCE(level, 0))
                """
            )
            conn.execute(
                """
                UPDATE cats
                SET exp_to_next = CASE WHEN level >= ? THEN 0 ELSE ? END
                """,
                (MAX_CAT_LEVEL, DEFAULT_EXP_TO_NEXT),
            )
            conn.execute(
                """
                UPDATE cats
                SET exp = CASE
                    WHEN level >= ? THEN 0
                    ELSE MIN(COALESCE(exp, 0), COALESCE(exp_to_next, ?))
                END
                """,
                (MAX_CAT_LEVEL, DEFAULT_EXP_TO_NEXT),
            )
            conn.execute(
                """
                UPDATE cats
                SET overall_power = COALESCE(wisdom, 0) + COALESCE(grit, 0) + COALESCE(creativity, 0)
                    + COALESCE(agility, 0) + COALESCE(cooperation, 0)
                """
            )
            conn.execute(
                """
                UPDATE cats
                SET stage = CASE
                    WHEN available_for_adoption = 1 THEN '待领养'
                    WHEN level >= ? OR feed_count >= max_feed_count THEN '已满级'
                    WHEN level > 0 OR feed_count > 0 THEN '成长中'
                    ELSE '初始态'
                END
                """,
                (MAX_CAT_LEVEL,),
            )
        conn.execute(
            """
            UPDATE ratings
            SET total_score = MIN(
                5,
                MAX(
                    1,
                    CAST(
                        ROUND(
                            (
                                COALESCE(happiness_score, 0) +
                                COALESCE(knowledge_score, 0) +
                                COALESCE(rhythm_score, 0) +
                                COALESCE(resonance_score, 0)
                            ) / 8.0
                        ) AS INTEGER
                    )
                )
            )
            WHERE total_score = 0
            """
        )
        bootstrap_settings(conn)
        bootstrap_admin(conn)
    seed_demo_data()


def rebuild_cats_table_without_user_unique(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS cats_new")
    conn.execute(
        """
        CREATE TABLE cats_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cat_no TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT '初始态',
            feed_count INTEGER NOT NULL DEFAULT 0,
            max_feed_count INTEGER NOT NULL DEFAULT 6,
            level INTEGER NOT NULL DEFAULT 0,
            exp INTEGER NOT NULL DEFAULT 0,
            exp_to_next INTEGER NOT NULL DEFAULT 100,
            learned_skills_json TEXT NOT NULL DEFAULT '[]',
            wisdom INTEGER NOT NULL DEFAULT 50,
            grit INTEGER NOT NULL DEFAULT 50,
            creativity INTEGER NOT NULL DEFAULT 50,
            agility INTEGER NOT NULL DEFAULT 50,
            cooperation INTEGER NOT NULL DEFAULT 50,
            overall_power INTEGER NOT NULL DEFAULT 250,
            image_url TEXT NOT NULL DEFAULT '',
            personality TEXT NOT NULL DEFAULT '',
            story_summary TEXT NOT NULL DEFAULT '',
            latest_summary TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_public INTEGER NOT NULL DEFAULT 0,
            available_for_adoption INTEGER NOT NULL DEFAULT 0,
            released_at TEXT NOT NULL DEFAULT '',
            highest_level_owner_id INTEGER NOT NULL DEFAULT 0,
            highest_level_owner_name TEXT NOT NULL DEFAULT '',
            highest_level_reached INTEGER NOT NULL DEFAULT 0,
            final_persona_json TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO cats_new (
            id, user_id, cat_no, name, stage, feed_count, max_feed_count, level, exp, exp_to_next, learned_skills_json,
            wisdom, grit, creativity, agility, cooperation, overall_power,
            image_url, personality, story_summary, latest_summary,
            is_active, is_public, available_for_adoption, released_at, final_persona_json,
            highest_level_owner_id, highest_level_owner_name, highest_level_reached,
            created_at, updated_at
        )
        SELECT
            id, user_id, cat_no, name,
            CASE
                WHEN COALESCE(available_for_adoption, 0) = 1 THEN '待领养'
                WHEN MIN(COALESCE(feed_count, 0), 6) >= 6 THEN '已满级'
                WHEN COALESCE(feed_count, 0) > 0 THEN '成长中'
                ELSE COALESCE(stage, '初始态')
            END,
            feed_count,
            6,
            MIN(COALESCE(feed_count, 0), 6),
            CASE WHEN MIN(COALESCE(feed_count, 0), 6) >= 6 THEN 0 ELSE MIN(COALESCE(exp, 0), 100) END,
            CASE WHEN MIN(COALESCE(feed_count, 0), 6) >= 6 THEN 0 ELSE 100 END,
            CASE
                WHEN TRIM(COALESCE(learned_skills_json, '')) = '' THEN '[]'
                ELSE learned_skills_json
            END,
            COALESCE(wisdom, 50), COALESCE(grit, 50), COALESCE(creativity, 50),
            COALESCE(agility, 50), COALESCE(cooperation, 50),
            COALESCE(wisdom, 0) + COALESCE(grit, 0) + COALESCE(creativity, 0)
                + COALESCE(agility, 0) + COALESCE(cooperation, 0),
            COALESCE(image_url, ''), COALESCE(personality, ''), COALESCE(story_summary, ''),
            COALESCE(latest_summary, ''), COALESCE(is_active, 1), COALESCE(is_public, 0),
            COALESCE(available_for_adoption, 0), COALESCE(released_at, ''), COALESCE(final_persona_json, ''),
            COALESCE(highest_level_owner_id, user_id),
            COALESCE(NULLIF(highest_level_owner_name, ''), (SELECT username FROM users WHERE users.id = cats.user_id LIMIT 1), ''),
            MAX(COALESCE(highest_level_reached, 0), MIN(COALESCE(feed_count, 0), 6)),
            created_at, updated_at
        FROM cats
        """
    )
    conn.execute("DROP TABLE cats")
    conn.execute("ALTER TABLE cats_new RENAME TO cats")


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


def create_guest_user() -> dict[str, Any]:
    now = utcnow()
    while True:
        suffix = secrets.token_hex(4)
        username = f"游客{suffix}"
        email = f"guest_{suffix}@guest.local"
        password = hash_password(secrets.token_hex(16))
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (username, email, password, created_at, role, must_change_password, is_guest)
                    VALUES (?, ?, ?, ?, 'user', 0, 1)
                    """,
                    (username, email, password, now),
                )
            break
        except sqlite3.IntegrityError:
            continue
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, created_at, role, must_change_password, password, is_guest
            FROM users
            WHERE username = ?
            LIMIT 1
            """,
            (username,),
        ).fetchone()
    return dict(row) if row else {}


def transfer_guest_progress(guest_user_id: int, target_user_id: int) -> int:
    if int(guest_user_id) == int(target_user_id):
        return 0

    guest_user = get_user_by_id(int(guest_user_id))
    target_user = get_user_by_id(int(target_user_id))
    if not guest_user or not target_user:
        raise ValueError("用户不存在，无法接管游客进度")
    if int(guest_user.get("is_guest") or 0) != 1:
        raise ValueError("当前会话不是游客模式，无法接管游客进度")

    guest_owned = count_user_owned_cats(int(guest_user_id))
    target_owned = count_user_owned_cats(int(target_user_id))
    if guest_owned + target_owned > 3:
        raise ValueError("接管失败，登录账号当前拥有的猫太多，接管后会超过 3 只上限")

    with get_connection() as conn:
        total_transferred = conn.execute(
            "SELECT COUNT(*) AS total FROM cats WHERE user_id = ?",
            (int(guest_user_id),),
        ).fetchone()
        moved_count = int((total_transferred["total"] if total_transferred else 0) or 0)
        if moved_count <= 0:
            return 0

        conn.execute(
            "UPDATE cats SET is_active = 0, updated_at = ? WHERE user_id = ? AND available_for_adoption = 0",
            (utcnow(), int(target_user_id)),
        )
        conn.execute(
            "UPDATE cats SET user_id = ?, updated_at = ? WHERE user_id = ?",
            (int(target_user_id), utcnow(), int(guest_user_id)),
        )

    get_or_activate_user_cat(int(target_user_id))
    return moved_count


def clamp_stat(value: int) -> int:
    return max(0, min(100, int(value)))


def compute_exp_to_next(level: int) -> int:
    if int(level) >= MAX_CAT_LEVEL:
        return 0
    return DEFAULT_EXP_TO_NEXT


def parse_skill_list(raw: str) -> list[dict[str, str]]:
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in data:
        if isinstance(item, dict) and "name" in item:
            cleaned.append(
                {"name": str(item["name"]), "rarity": str(item.get("rarity", "N"))}
            )
        elif isinstance(item, str) and item.strip():
            cleaned.append({"name": item.strip(), "rarity": "N"})
    return cleaned


def dump_skill_list(skills: list[dict[str, str]]) -> str:
    cleaned = []
    for skill in skills:
        if isinstance(skill, dict) and "name" in skill and str(skill["name"]).strip():
            cleaned.append(
                {
                    "name": str(skill["name"]).strip(),
                    "rarity": str(skill.get("rarity", "N")),
                }
            )
        elif isinstance(skill, str) and str(skill).strip():
            cleaned.append({"name": str(skill).strip(), "rarity": "N"})
    return json.dumps(cleaned, ensure_ascii=False)


def build_cat_stage(
    level: int, feed_count: int, max_feed_count: int, available_for_adoption: int = 0
) -> str:
    if int(available_for_adoption):
        return "待领养"
    if int(level) >= MAX_CAT_LEVEL or int(feed_count) >= int(max_feed_count):
        return "已满级"
    if int(level) > 0 or int(feed_count) > 0:
        return "成长中"
    return "初始态"


def compute_overall_power(
    wisdom: int,
    grit: int,
    creativity: int,
    agility: int,
    cooperation: int,
) -> int:
    return wisdom + grit + creativity + agility + cooperation


def build_initial_cat_payload(
    user_id: int, username: str, ai_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    now = utcnow()
    base_name = (username.strip() or "新手")[:8]
    wisdom = grit = creativity = agility = cooperation = 50
    profile = ai_data.get("profile") if ai_data else {}
    return {
        "user_id": user_id,
        "cat_no": f"CAT-{user_id:05d}-{int(datetime.utcnow().timestamp())}",
        "name": profile.get("name") or f"{base_name}的小猫",
        "stage": "初始态",
        "feed_count": 0,
        "max_feed_count": MAX_CAT_LEVEL,
        "level": 0,
        "exp": 0,
        "exp_to_next": compute_exp_to_next(0),
        "learned_skills_json": "[]",
        "wisdom": wisdom,
        "grit": grit,
        "creativity": creativity,
        "agility": agility,
        "cooperation": cooperation,
        "overall_power": compute_overall_power(
            wisdom, grit, creativity, agility, cooperation
        ),
        "image_url": ai_data.get("image_url") if ai_data else "",
        "personality": profile.get("personality")
        or "亲人、好奇、会观察主人的心情，正等待第一条抖音链接来塑造自己。",
        "story_summary": profile.get("story")
        or "这是一只刚刚被领取的小猫，它想慢慢长成最懂主人的那个陪伴者。",
        "latest_summary": "还没有喂过抖音链接，先试着喂第一条吧。",
        "is_active": 1,
        "is_public": 0,
        "available_for_adoption": 0,
        "released_at": "",
        "highest_level_owner_id": user_id,
        "highest_level_owner_name": username.strip(),
        "highest_level_reached": 0,
        "created_at": now,
        "updated_at": now,
    }


def create_initial_cat_for_user(
    user_id: int, username: str, ai_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = build_initial_cat_payload(user_id, username, ai_data)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cats (
                user_id, cat_no, name, stage, feed_count, max_feed_count, level, exp, exp_to_next, learned_skills_json,
                wisdom, grit, creativity, agility, cooperation, overall_power,
                image_url, personality, story_summary, latest_summary, is_active, is_public,
                available_for_adoption, released_at, highest_level_owner_id, highest_level_owner_name,
                highest_level_reached, created_at, updated_at
            ) VALUES (
                :user_id, :cat_no, :name, :stage, :feed_count, :max_feed_count, :level, :exp, :exp_to_next, :learned_skills_json,
                :wisdom, :grit, :creativity, :agility, :cooperation, :overall_power,
                :image_url, :personality, :story_summary, :latest_summary, :is_active, :is_public,
                :available_for_adoption, :released_at, :highest_level_owner_id, :highest_level_owner_name,
                :highest_level_reached, :created_at, :updated_at
            )
            """,
            payload,
        )
    return get_user_cat(user_id) or payload


def count_user_owned_cats(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM cats
            WHERE user_id = ? AND available_for_adoption = 0
            """,
            (user_id,),
        ).fetchone()
    return int((row["total"] if row else 0) or 0)


def list_user_cats(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM cats
            WHERE user_id = ? AND available_for_adoption = 0
            ORDER BY is_active DESC, updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_cat_by_id(cat_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cats WHERE id = ? LIMIT 1", (cat_id,)
        ).fetchone()
    return dict(row) if row else None


def get_user_cat(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM cats
            WHERE user_id = ? AND is_active = 1 AND available_for_adoption = 0
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_or_activate_user_cat(user_id: int) -> dict[str, Any] | None:
    cat = get_user_cat(user_id)
    if cat:
        return cat
    owned_cats = list_user_cats(user_id, limit=1)
    if not owned_cats:
        return None
    return activate_cat_for_user(user_id, int(owned_cats[0]["id"])) or owned_cats[0]


def set_all_user_cats_inactive(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cats SET is_active = 0, updated_at = ? WHERE user_id = ? AND available_for_adoption = 0",
            (utcnow(), user_id),
        )


def activate_cat_for_user(user_id: int, cat_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cats SET is_active = 0, updated_at = ? WHERE user_id = ? AND available_for_adoption = 0",
            (utcnow(), user_id),
        )
        conn.execute(
            """
            UPDATE cats
            SET is_active = 1, updated_at = ?
            WHERE id = ? AND user_id = ? AND available_for_adoption = 0
            """,
            (utcnow(), cat_id, user_id),
        )
    return get_cat_by_id(cat_id)


def ensure_user_cat(
    user_id: int, username: str, settings: dict[str, str] | None = None
) -> dict[str, Any]:
    cat = get_user_cat(user_id)
    if cat:
        return cat

    owned_cats = list_user_cats(user_id, limit=1)
    if owned_cats:
        return activate_cat_for_user(user_id, int(owned_cats[0]["id"])) or owned_cats[0]

    if count_user_owned_cats(user_id) >= 3:
        raise ValueError("每位用户最多只能拥有 3 只猫")

    ai_data = None
    if settings:
        from .services import generate_initial_cat_ai_data

        try:
            ai_data = generate_initial_cat_ai_data(settings, username)
        except Exception:
            pass

    return create_initial_cat_for_user(user_id, username, ai_data)


def list_cat_feed_records(cat_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM cat_feed_records
            WHERE cat_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (cat_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_cat_timeline(cat_id: int, limit: int = 20) -> list[dict[str, Any]]:
    feeds = list_cat_feed_records(cat_id, limit)
    with get_connection() as conn:
        train_rows = conn.execute(
            """
            SELECT *
            FROM cat_training_records
            WHERE cat_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (cat_id, limit),
        ).fetchall()
    trains = [dict(row) for row in train_rows]

    timeline = []
    for f in feeds:
        timeline.append(
            {
                "event_type": "feed",
                "time": f["created_at"],
                "title": f"视频投喂：{f.get('video_title', '未命名')}",
                "summary": f.get("video_summary", ""),
                "data": dict(f),
            }
        )
    for t in trains:
        timeline.append(
            {
                "event_type": "train",
                "time": t["created_at"],
                "title": f"日常修炼：{t.get('action_key', '')}",
                "summary": t.get("summary", ""),
                "data": dict(t),
            }
        )

    timeline.sort(key=lambda x: x["time"], reverse=True)
    return timeline[:limit]


def add_cat_feed_record(
    cat_id: int, feed_result: dict[str, Any], current_owner_name: str = ""
) -> dict[str, Any]:
    now = utcnow()
    with get_connection() as conn:
        cat_row = conn.execute(
            "SELECT * FROM cats WHERE id = ? LIMIT 1", (cat_id,)
        ).fetchone()
        if not cat_row:
            raise ValueError("猫咪不存在")
        cat = dict(cat_row)
        next_feed_count = int(cat["feed_count"]) + 1
        max_feeds = int(cat["max_feed_count"])
        if next_feed_count > max_feeds:
            raise ValueError(
                f"这只猫已经喂满了 {max_feeds} 次，无法继续喂食，但可以继续对话。"
            )
        current_level = int(cat.get("level") or 0)
        if current_level >= MAX_CAT_LEVEL:
            raise ValueError("这只猫已经满级，不能继续喂养视频。")
        exp_to_next = int(cat.get("exp_to_next") or compute_exp_to_next(current_level))
        current_exp = int(cat.get("exp") or 0)
        if current_exp < exp_to_next:
            raise ValueError("经验条还没满，先完成日常修炼，再喂视频让它升级。")

        updated_stats = {
            "wisdom": clamp_stat(
                int(cat["wisdom"]) + int(feed_result.get("wisdom_delta") or 0)
            ),
            "grit": clamp_stat(
                int(cat["grit"]) + int(feed_result.get("grit_delta") or 0)
            ),
            "creativity": clamp_stat(
                int(cat["creativity"]) + int(feed_result.get("creativity_delta") or 0)
            ),
            "agility": clamp_stat(
                int(cat["agility"]) + int(feed_result.get("agility_delta") or 0)
            ),
            "cooperation": clamp_stat(
                int(cat["cooperation"]) + int(feed_result.get("cooperation_delta") or 0)
            ),
        }
        overall_power = compute_overall_power(
            updated_stats["wisdom"],
            updated_stats["grit"],
            updated_stats["creativity"],
            updated_stats["agility"],
            updated_stats["cooperation"],
        )
        learned_skills = parse_skill_list(str(cat.get("learned_skills_json") or ""))
        learned_skill_raw = str(feed_result.get("learned_skill") or "").strip()
        skill_commentary = str(feed_result.get("skill_commentary") or "").strip()
        learned_skill_obj = None
        learned_skill_name = ""
        if learned_skill_raw:
            try:
                learned_skill_obj = json.loads(learned_skill_raw)
                learned_skill_name = learned_skill_obj.get("name", "")
            except Exception:
                learned_skill_obj = {"name": learned_skill_raw, "rarity": "N"}
                learned_skill_name = learned_skill_raw

        if learned_skill_obj and learned_skill_name:
            if not any(s.get("name") == learned_skill_name for s in learned_skills):
                learned_skills.append(learned_skill_obj)

        next_level = min(MAX_CAT_LEVEL, current_level + 1)
        next_exp = 0
        next_exp_to_next = compute_exp_to_next(next_level)
        owner_name = current_owner_name.strip()
        if not owner_name:
            owner_row = conn.execute(
                "SELECT username FROM users WHERE id = ? LIMIT 1",
                (int(cat["user_id"]),),
            ).fetchone()
            owner_name = str((owner_row["username"] if owner_row else "") or "")
        highest_level_reached = int(cat.get("highest_level_reached") or 0)
        highest_level_owner_id = int(cat.get("highest_level_owner_id") or 0)
        highest_level_owner_name = str(cat.get("highest_level_owner_name") or "")
        if next_level > highest_level_reached:
            highest_level_reached = next_level
            highest_level_owner_id = int(cat["user_id"])
            highest_level_owner_name = owner_name
        stage = build_cat_stage(
            next_level,
            next_feed_count,
            max_feeds,
            int(cat.get("available_for_adoption") or 0),
        )
        latest_summary = (
            str(feed_result.get("video_summary") or "").strip()
            or "这次喂养让它完成了一次新的突破。"
        )
        if learned_skill_name:
            latest_summary = f"通过视频《{str(feed_result.get('video_title') or '未命名视频')}》升到 {next_level} 级，并学会技能「{learned_skill_name}」。"
        else:
            latest_summary = f"通过视频《{str(feed_result.get('video_title') or '未命名视频')}》升到 {next_level} 级。"
        if skill_commentary:
            latest_summary = f"{latest_summary} {skill_commentary}"

        conn.execute(
            """
            INSERT INTO cat_feed_records (
                cat_id, feed_index, source_url, canonical_url, aweme_id, video_title, video_author,
                video_cover_url, video_summary, tag_summary, wisdom_delta, grit_delta,
                creativity_delta, agility_delta, cooperation_delta, learned_skill, skill_commentary, model1_output, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                cat_id,
                next_feed_count,
                str(feed_result.get("source_url") or ""),
                str(feed_result.get("canonical_url") or ""),
                str(feed_result.get("aweme_id") or ""),
                str(feed_result.get("video_title") or "未命名视频"),
                str(feed_result.get("video_author") or ""),
                str(feed_result.get("video_cover_url") or ""),
                str(feed_result.get("video_summary") or ""),
                str(feed_result.get("tag_summary") or ""),
                int(feed_result.get("wisdom_delta") or 0),
                int(feed_result.get("grit_delta") or 0),
                int(feed_result.get("creativity_delta") or 0),
                int(feed_result.get("agility_delta") or 0),
                int(feed_result.get("cooperation_delta") or 0),
                learned_skill_raw,
                skill_commentary,
                str(feed_result.get("model1_output") or ""),
                now,
            ),
        )

        conn.execute(
            """
            UPDATE cats
            SET stage = ?,
                feed_count = ?,
                level = ?,
                exp = ?,
                exp_to_next = ?,
                learned_skills_json = ?,
                wisdom = ?,
                grit = ?,
                creativity = ?,
                agility = ?,
                cooperation = ?,
                overall_power = ?,
                highest_level_owner_id = ?,
                highest_level_owner_name = ?,
                highest_level_reached = ?,
                latest_summary = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                stage,
                next_feed_count,
                next_level,
                next_exp,
                next_exp_to_next,
                dump_skill_list(learned_skills),
                updated_stats["wisdom"],
                updated_stats["grit"],
                updated_stats["creativity"],
                updated_stats["agility"],
                updated_stats["cooperation"],
                overall_power,
                highest_level_owner_id,
                highest_level_owner_name,
                highest_level_reached,
                latest_summary,
                now,
                cat_id,
            ),
        )
    return get_user_cat(int(cat["user_id"])) or {}


def perform_daily_training(cat_id: int, action_key: str) -> dict[str, Any]:
    action = DAILY_TRAINING_ACTIONS.get(action_key)
    if not action:
        raise ValueError("未知的修炼方式")
    now = utcnow()
    with get_connection() as conn:
        cat_row = conn.execute(
            "SELECT * FROM cats WHERE id = ? LIMIT 1", (cat_id,)
        ).fetchone()
        if not cat_row:
            raise ValueError("猫咪不存在")
        cat = dict(cat_row)
        level = int(cat.get("level") or 0)
        if level >= MAX_CAT_LEVEL:
            raise ValueError("这只猫已经满级，不需要继续修炼经验了。")
        exp_to_next = int(cat.get("exp_to_next") or compute_exp_to_next(level))
        current_exp = int(cat.get("exp") or 0)
        new_exp = min(exp_to_next, current_exp + int(action["exp_gain"]))
        latest_summary = f"{action['label']}完成，获得 {int(action['exp_gain'])} 点经验。{action['summary']}"
        if new_exp >= exp_to_next:
            latest_summary += f" 当前经验已满，可以喂第 {int(cat.get('feed_count') or 0) + 1} 个视频了。"

        conn.execute(
            """
            INSERT INTO cat_training_records (cat_id, action_key, exp_gain, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cat_id, action["label"], int(action["exp_gain"]), latest_summary, now),
        )

        conn.execute(
            """
            UPDATE cats
            SET exp = ?,
                latest_summary = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (new_exp, latest_summary, now, cat_id),
        )
    updated_cat = get_cat_by_id(cat_id)
    if not updated_cat:
        raise ValueError("修炼后未找到猫咪数据")
    return {
        "cat": updated_cat,
        "action": action,
        "exp_gain": int(action["exp_gain"]),
        "exp_full": int(updated_cat.get("exp") or 0)
        >= int(updated_cat.get("exp_to_next") or 0)
        > 0,
    }


def list_recent_users(limit: int = 8) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE is_guest = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, created_at, role, must_change_password, password, is_guest
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
            SELECT id, username, email, created_at, role, must_change_password, password, is_guest
            FROM users
            WHERE (username = ? OR email = ?) AND role = 'user' AND is_guest = 0
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
        rows = conn.execute(
            "SELECT key, value FROM app_settings ORDER BY key"
        ).fetchall()
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
                ratings.total_score
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
    total_score: int,
) -> None:
    now = utcnow()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ratings (
                atlas_id, user_id, happiness_score, knowledge_score, rhythm_score, resonance_score, total_score,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(atlas_id, user_id) DO UPDATE SET
                total_score = excluded.total_score,
                updated_at = excluded.updated_at
            """,
            (
                atlas_id,
                user_id,
                0,
                0,
                0,
                0,
                total_score,
                now,
                now,
            ),
        )


def get_user_rating(atlas_id: int, user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT atlas_id, user_id, total_score, updated_at
            FROM ratings
            WHERE atlas_id = ? AND user_id = ?
            """,
            (atlas_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def update_cat_public_status(cat_id: int, is_public: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cats SET is_public = ?, updated_at = ? WHERE id = ?",
            (1 if is_public else 0, utcnow(), cat_id),
        )


def count_public_cats() -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM cats
            WHERE is_public = 1 OR available_for_adoption = 1
            """
        ).fetchone()
    return int((row["total"] if row else 0) or 0)


def list_public_cats(limit: int = 12, offset: int = 0) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cats.*, users.username
            FROM cats
            JOIN users ON users.id = cats.user_id
            WHERE is_public = 1 OR available_for_adoption = 1
            ORDER BY available_for_adoption DESC, cats.updated_at DESC
            LIMIT ?
            OFFSET ?
            """,
            (limit, max(0, int(offset))),
        ).fetchall()
    return [dict(row) for row in rows]


def release_cat_to_plaza(cat_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM cats
            WHERE id = ? AND user_id = ? AND available_for_adoption = 0
            LIMIT 1
            """,
            (cat_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            """
            UPDATE cats
            SET is_active = 0,
                is_public = 1,
                available_for_adoption = 1,
                released_at = ?,
                stage = '待领养',
                updated_at = ?
            WHERE id = ?
            """,
            (utcnow(), utcnow(), cat_id),
        )
    return True


def adopt_plaza_cat(cat_id: int, new_user_id: int) -> dict[str, Any] | None:
    if count_user_owned_cats(new_user_id) >= 3:
        raise ValueError("每位用户最多只能拥有 3 只猫")
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM cats
            WHERE id = ? AND available_for_adoption = 1
            LIMIT 1
            """,
            (cat_id,),
        ).fetchone()
        if not row:
            raise ValueError("这只猫当前不可领养")
        conn.execute(
            "UPDATE cats SET is_active = 0, updated_at = ? WHERE user_id = ? AND available_for_adoption = 0",
            (utcnow(), new_user_id),
        )
        conn.execute(
            """
            UPDATE cats
            SET user_id = ?,
                is_active = 1,
                is_public = 0,
                available_for_adoption = 0,
                released_at = '',
                stage = CASE
                    WHEN level >= ? OR feed_count >= max_feed_count THEN '已满级'
                    WHEN level > 0 OR feed_count > 0 THEN '成长中'
                    ELSE '初始态'
                END,
                updated_at = ?
            WHERE id = ?
            """,
            (new_user_id, MAX_CAT_LEVEL, utcnow(), cat_id),
        )
    return get_cat_by_id(cat_id)


def admin_delete_cat(cat_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM cats WHERE id = ? LIMIT 1",
            (cat_id,),
        ).fetchone()
        if not row:
            return False

        conn.execute("DELETE FROM cat_messages WHERE cat_id = ?", (cat_id,))
        conn.execute("DELETE FROM cat_training_records WHERE cat_id = ?", (cat_id,))
        conn.execute("DELETE FROM cat_feed_records WHERE cat_id = ?", (cat_id,))
        conn.execute("DELETE FROM cats WHERE id = ?", (cat_id,))
    return True


def add_cat_message(cat_id: int, role: str, content: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO cat_messages (cat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (cat_id, role, content, utcnow()),
        )


def list_cat_messages(cat_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM cat_messages
            WHERE cat_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (cat_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def update_cat_final_persona(
    cat_id: int,
    persona_json: str,
    image_url: str,
    personality: str,
    story: str,
    stage: str = "已完结",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE cats
            SET stage = ?,
                final_persona_json = ?,
                image_url = ?,
                personality = ?,
                story_summary = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (stage, persona_json, image_url, personality, story, utcnow(), cat_id),
        )


def get_rating_summary(atlas_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS rating_count,
                AVG(total_score) AS avg_total_score
            FROM ratings
            WHERE atlas_id = ?
            """,
            (atlas_id,),
        ).fetchone()
    if not row:
        return {
            "rating_count": 0,
            "avg_total_score": 0,
        }
    return {
        "rating_count": int(row["rating_count"] or 0),
        "avg_total_score": round(float(row["avg_total_score"] or 0), 1),
    }
