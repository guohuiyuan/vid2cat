from __future__ import annotations

from dataclasses import dataclass
import base64
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

import httpx


@dataclass(slots=True)
class PromptScaffoldPayload:
    title: str
    summary: str
    tags: list[str]


@dataclass(slots=True)
class AIModelConfig:
    api_url: str
    api_key: str
    model: str


class PromptEngineScaffold:
    """Placeholder for future LLM prompt generation."""

    @staticmethod
    def build(payload: PromptScaffoldPayload) -> str:
        tag_text = "、".join(payload.tags[:6]) or "猫咪、二次元、图鉴"
        return (
            "你是一名猫咪图鉴设定师。\n"
            f"视频标题：{payload.title}\n"
            f"视频摘要：{payload.summary}\n"
            f"视频标签：{tag_text}\n"
            "请输出：猫咪品种、技能、种族值、性格、背景故事、外貌描述、稀有度，"
            "并在最后给出适用于绘图模型的中文提示词。\n"
            "备注：当前是 scaffold，后续可替换为真实模型调用。"
        )


class AIModelRuntime:
    """OpenAI-compatible text model client."""

    @staticmethod
    def _chat_endpoint(api_url: str) -> str:
        normalized = api_url.strip().rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return normalized + "/chat/completions"
        return normalized + "/v1/chat/completions"

    @staticmethod
    def _image_endpoint(api_url: str) -> str:
        normalized = api_url.strip().rstrip("/")
        if normalized.endswith("/images/generations"):
            return normalized
        if normalized.endswith("/v1"):
            return normalized + "/images/generations"
        return normalized + "/v1/images/generations"

    @staticmethod
    def complete_text(
        config: AIModelConfig,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
    ) -> str:
        if not config.api_url or not config.api_key or not config.model:
            raise ValueError("模型配置不完整")

        endpoint = AIModelRuntime._chat_endpoint(config.api_url)
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = AIModelRuntime._extract_text(data)
        if not content:
            raise RuntimeError("模型返回内容为空")
        return content.strip()

    @staticmethod
    def generate_image(
        config: AIModelConfig,
        prompt: str,
        size: str = "1024x1024",
    ) -> dict[str, str]:
        if not config.api_url or not config.api_key or not config.model:
            raise ValueError("模型配置不完整")

        endpoint = AIModelRuntime._image_endpoint(config.api_url)
        payload = {
            "model": config.model,
            "prompt": prompt,
            "size": size,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=180.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        items = data.get("data") or []
        if not items:
            raise RuntimeError("绘图模型未返回 data")
        first = items[0]
        image_url = str(first.get("url") or "").strip()
        b64_json = str(first.get("b64_json") or "").strip()
        revised_prompt = str(first.get("revised_prompt") or prompt).strip()
        if not image_url and not b64_json:
            raise RuntimeError("绘图模型未返回 url 或 b64_json")
        return {
            "url": image_url,
            "b64_json": b64_json,
            "prompt": revised_prompt,
        }

    @staticmethod
    def _flatten_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        chunks.append(str(text))
                elif item:
                    chunks.append(str(item))
            return "\n".join(chunks)
        return "" if content is None else str(content)

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if choices:
            first = choices[0] or {}
            message = first.get("message") or {}
            text = AIModelRuntime._flatten_content(message.get("content"))
            if text:
                return text
            text = AIModelRuntime._flatten_content(first.get("text"))
            if text:
                return text
            delta = first.get("delta") or {}
            text = AIModelRuntime._flatten_content(delta.get("content"))
            if text:
                return text

        text = AIModelRuntime._flatten_content(data.get("output_text"))
        if text:
            return text

        outputs = data.get("output") or []
        if isinstance(outputs, list):
            chunks: list[str] = []
            for item in outputs:
                if not isinstance(item, dict):
                    continue
                content = item.get("content") or []
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            text = block.get("text")
                            if text:
                                chunks.append(str(text))
            if chunks:
                return "\n".join(chunks)

        raise RuntimeError("模型未返回可识别的文本字段")


class ImageHostScaffold:
    """PicGo-Core based image upload integration."""

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    DEFAULTS = {
        "gitee_repo": "linbingwei/heikeson",
        "gitee_branch": "master",
        "gitee_path": "images",
        "gitee_token": "",
        "gitee_custom_url": "",
        "extra_upload_token": "",
    }

    @staticmethod
    def describe(settings: dict[str, str] | None = None) -> str:
        merged = ImageHostScaffold.DEFAULTS.copy()
        if settings:
            merged.update(settings)
        if merged.get("gitee_token"):
            return (
                "已接入 PicGo-Core + picgo-plugin-github-plus，"
                f"当前目标为 {merged['gitee_repo']} / {merged['gitee_branch']} / {merged['gitee_path']}。"
            )
        return "已接入 PicGo-Core 图床脚本，待管理员填写 Gitee Token 后即可上传。"

    @staticmethod
    def upload(local_file: Path, settings: dict[str, str]) -> str:
        if not local_file.exists():
            raise FileNotFoundError(f"文件不存在: {local_file}")
        if not settings.get("gitee_token"):
            raise ValueError("未配置 GITEE_TOKEN，无法执行图床上传")

        env = os.environ.copy()
        env.update(
            {
                "GITEE_REPO": settings.get("gitee_repo", ImageHostScaffold.DEFAULTS["gitee_repo"]),
                "GITEE_BRANCH": settings.get("gitee_branch", ImageHostScaffold.DEFAULTS["gitee_branch"]),
                "GITEE_PATH": settings.get("gitee_path", ImageHostScaffold.DEFAULTS["gitee_path"]),
                "GITEE_TOKEN": settings.get("gitee_token", ""),
                "GITEE_CUSTOM_URL": settings.get("gitee_custom_url", ""),
            }
        )
        result = subprocess.run(
            ["node", "./scripts/upload.js", str(local_file)],
            cwd=str(ImageHostScaffold.PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip() or "未知上传失败"
            raise RuntimeError(message)

        for line in (result.stdout or "").splitlines():
            if " -> " in line:
                return line.split(" -> ", 1)[1].strip()
        raise RuntimeError("上传完成，但没有解析到图片 URL")

    @staticmethod
    def upload_bytes(file_bytes: bytes, suffix: str, settings: dict[str, str]) -> str:
        temp_dir = ImageHostScaffold.PROJECT_ROOT / "data" / "image_host"
        temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as handle:
            handle.write(file_bytes)
            temp_path = Path(handle.name)
        try:
            return ImageHostScaffold.upload(temp_path, settings)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def upload_base64_image(b64_json: str, settings: dict[str, str], suffix: str = ".png") -> str:
        file_bytes = base64.b64decode(b64_json)
        return ImageHostScaffold.upload_bytes(file_bytes, suffix, settings)

    @staticmethod
    def mirror_remote_image(image_url: str, settings: dict[str, str], suffix: str = ".png") -> str:
        with httpx.Client(timeout=120.0) as client:
            response = client.get(image_url)
            response.raise_for_status()
            file_bytes = response.content
        return ImageHostScaffold.upload_bytes(file_bytes, suffix, settings)
