from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent.parent / ".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    PLATFORM_WITHDRAWAL_FEE_PERCENT: float = 2.5
    BITNOB_CLIENT_ID: str = ""
    BITNOB_CLIENT_SECRET: str = ""
    DEMO_GHS_USD_RATE: float = 15.5
    USMS_BASE_URL: str = "https://webapp.usmsgh.com"
    USMS_SENDER_ID: str = ""
    USMS_TOKEN: str = ""



settings = Settings()
