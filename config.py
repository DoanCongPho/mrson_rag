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

    # Login (Google sign-in + session cookie)
    google_client_id: str = ""
    session_secret: str = ""
    session_days: int = 30
    cookie_secure: bool = False  # set true in production (HTTPS)
    cors_origins: str = "http://localhost:5501,http://127.0.0.1:5501"  # comma-separated
    daily_message_limit: int = 50  # questions per user per 24h; 0 = no limit

    # Conversation memory
    history_turns: int = 4  # last N exchanges (user + assistant) sent to the LLM
    history_message_max_tokens: int = 300  # each replayed message is cut to this
    router_history_turns: int = 2  # exchanges the router sees to rewrite follow-ups
    summary_batch_turns: int = 2  # summarize once this many exchanges left the window
    summary_max_words: int = 200


settings = Settings()


