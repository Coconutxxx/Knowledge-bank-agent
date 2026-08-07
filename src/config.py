"""从 .env 读取项目配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"环境变量 {name} 必须是整数，当前值为 {value!r}") from exc

def _float_env(name: str, default: float) -> float:
    value = os.getenv(name, str(default))

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"环境变量 {name} 必须是数字，当前值为 {value!r}"
        ) from exc

@dataclass(frozen=True)
class Settings:
     # =========================
    # 大模型配置
    # =========================
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    # =========================
    # 向量模型配置
    # =========================
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )
    chroma_path: str = os.getenv("CHROMA_PATH", "./storage/chroma")
    collection_name: str = os.getenv("COLLECTION_NAME", "local_knowledge")

    # =========================
    # 关系数据库配置
    # =========================
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./storage/knowledge.db",
    )
    # =========================
    # 登录会话配置
    # =========================
    session_timeout_minutes: int = _int_env(
        "SESSION_TIMEOUT_MINUTES",
        120,
    )
    # =========================
    # 检索配置
    # =========================
    top_k: int = _int_env("TOP_K", 5)
    retrieval_candidate_k: int = _int_env(
        "RETRIEVAL_CANDIDATE_K",
        10,
    )
    final_context_k: int = _int_env(
        "FINAL_CONTEXT_K",
        5,
    )
    display_source_k: int = _int_env(
        "DISPLAY_SOURCE_K",
        3,
    )
    chunk_size: int = _int_env("CHUNK_SIZE", 700)
    chunk_overlap: int = _int_env("CHUNK_OVERLAP", 120)
    max_agent_steps: int = _int_env("MAX_AGENT_STEPS", 4)
    retrieval_distance_threshold: float = _float_env(
    "RETRIEVAL_DISTANCE_THRESHOLD",
    0.8,)
    
    def validate_llm(self) -> None:
        if not self.api_key:
            raise ValueError(
                "没有找到 OPENAI_API_KEY。请把 .env.example 复制为 .env，"
                "再填写所用模型服务的 API Key。"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP 必须小于 CHUNK_SIZE。")
        if self.retrieval_candidate_k <= 0:
            raise ValueError(
                "RETRIEVAL_CANDIDATE_K必须大于0。"
            )
        if self.final_context_k <= 0:
            raise ValueError(
                "FINAL_CONTEXT_K必须大于0。"
            )
        if self.display_source_k <= 0:
            raise ValueError(
                "DISPLAY_SOURCE_K必须大于0。"
            )
        if (
            self.retrieval_candidate_k
            < self.final_context_k
        ):
            raise ValueError(
                "RETRIEVAL_CANDIDATE_K不能小于"
                "FINAL_CONTEXT_K。"
            )
        if (
            self.final_context_k
            < self.display_source_k
        ):
            raise ValueError(
                "FINAL_CONTEXT_K不能小于"
                "DISPLAY_SOURCE_K。"
            )


settings = Settings()

