from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://localhost/smart_building_dev"
    test_database_url: str = "postgresql://localhost/smart_building_test"
    anthropic_api_key: str = ""


settings = Settings()
