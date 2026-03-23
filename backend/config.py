import logging
import os
import secrets
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:35b"
    COMFYUI_URL: str = "http://localhost:8188"
    DATA_DIR: str = "data"
    REFERENCE_VOICE: str = "assets/reference_voice.wav"
    WHISPER_MODEL: str = "base.en"
    WHISPER_DEVICE: str = "auto"

    # PostgreSQL
    DATABASE_URL: str = "postgresql://reading_tutor:password@localhost:5432/reading_tutor"
    DB_POOL_MIN: int = 10
    DB_POOL_MAX: int = 50

    # JWT Authentication
    JWT_SECRET: str = ""
    JWT_ACCESS_EXPIRES_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_EXPIRES_DAYS: int = 90

    # Redis
    REDIS_URL: str = "redis://localhost:6380"

    # AWS / Cloud settings
    LLM_BACKEND: str = "ollama"  # "ollama" or "bedrock"
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-haiku-20241022"
    AWS_REGION: str = "us-east-1"

    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    S3_BUCKET: str = ""
    CLOUDFRONT_DOMAIN: str = ""

    TTS_BACKEND: str = "local"  # "local" or "remote"
    TTS_URL: str = "http://tts.gpu.svc.cluster.local:8080"

    # Mock services (for testing without GPU)
    USE_MOCK_SERVICES: bool = False

    # Request timeout (seconds)
    REQUEST_TIMEOUT: int = 30

    model_config = {
        "env_file": os.environ.get("ENV_FILE", ".env"),
        "env_file_encoding": "utf-8",
    }

    @model_validator(mode="after")
    def ensure_jwt_secret(self):
        if not self.JWT_SECRET:
            self.JWT_SECRET = secrets.token_urlsafe(32)
            logger.warning(
                "JWT_SECRET not set — generated a random secret. "
                "Set JWT_SECRET in your .env file for multi-process deployments."
            )
        return self

    @property
    def data_path(self) -> Path:
        return Path(__file__).parent / self.DATA_DIR


settings = Settings()
