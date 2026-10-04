from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = (
        "postgresql+psycopg://receiptsplit:receiptsplit@localhost:55432/receiptsplit"
    )
    public_origin: str = "http://localhost:5173"
    bot_token: str = ""
    bot_username: str = ""
    dev_auth_enabled: bool = False
    storage_path: str = "./storage"

    @model_validator(mode="after")
    def secure_production(self) -> "Settings":
        if self.app_env == "production" and (
            self.dev_auth_enabled or not self.public_origin.startswith("https://")
        ):
            raise ValueError("Production requires HTTPS and disabled dev authentication")
        return self
