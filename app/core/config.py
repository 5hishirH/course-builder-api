from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str
    DB_URL: str
    S3_ENDPOINT: str
    S3_KEY_ID: str
    S3_ACCESS_KEY: str
    S3_REGION: str = Field(default="ap-south-1")
    S3_BUCKET_NAME: str = Field(default="batch-point-dev-ap-south-1")

    # folders
    S3_MATERIAL_FOLDER: str = Field(default="materials")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()