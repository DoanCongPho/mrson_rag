from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    openai_api_key: str
    phoenix_collector_endpoint: str
    phoenix_enabled: bool = True
    reranker_enabled: bool = False
    root_folder_id: str = "1gkgCe5WNw5EuxAwAx6jbGQZea900tjcW"
    rerank_candidate_k: int = 15
    context_expand_enabled: bool = True
    context_block_max_tokens: int = 1000


settings = Settings()


