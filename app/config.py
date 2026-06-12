from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "大场镇新闻"
    database_url: str = "sqlite:///./data/news.db"
    refresh_keywords: str = "大场镇,上海大场,宝山区大场"
    news_per_source: int = 15
    scheduler_morning: str = "08:00"
    scheduler_afternoon: str = "14:00"
    timezone: str = "Asia/Shanghai"


settings = Settings()
