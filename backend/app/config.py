from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] is the project root (the folder containing .env)
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Secret: SecretStr hides the value if it is ever printed or logged.
    groq_api_key: SecretStr = SecretStr("")

    # Embeddings run locally on CPU (no API key, no rate limit).
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Chunking (we use these in Step 3)
    chunk_chars: int = 1000
    chunk_overlap_chars: int = 200

    # How many chunks to retrieve per question (Step 5)
    top_k: int = 5


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it everywhere."""
    return Settings()