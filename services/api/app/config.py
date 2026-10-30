from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./ripple.db"
    cors_origins: str = "http://localhost:3000"

    # Text model for report summaries and what-if chat: an OpenAI-compatible endpoint
    # (Nebius Token Factory). Leave empty to run the deterministic engine only.
    nebius_api_key: str = ""
    nebius_base_url: str = ""
    nebius_model: str = ""
    nebius_timeout_seconds: float = 35.0
    nebius_json_mode: bool = False  # send response_format=json_object (not all models support it)

    # Image understanding for the camera feature.
    vision_provider: str = "auto"  # auto | gemini | nebius | off
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"  # check the current name at https://ai.google.dev/gemini-api/docs/models
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    nebius_vision_model: str = ""  # a Nebius vision-language model id, if you use vision_provider=nebius
    max_upload_mb: float = 8.0

    ai_rate_limit_per_minute: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return "ripple.db"

    @property
    def text_ai_configured(self) -> bool:
        return bool(self.nebius_api_key and self.nebius_base_url and self.nebius_model)

    @property
    def vision_resolved(self) -> str:
        """Which provider will read photos: gemini, nebius or off."""
        p = self.vision_provider.lower()
        if p == "off":
            return "off"
        if p == "gemini":
            return "gemini" if self.gemini_api_key else "off"
        if p == "nebius":
            return "nebius" if (self.nebius_api_key and self.nebius_base_url and self.nebius_vision_model) else "off"
        if self.gemini_api_key:
            return "gemini"
        if self.nebius_api_key and self.nebius_base_url and self.nebius_vision_model:
            return "nebius"
        return "off"


settings = Settings()
