from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")

    postgres_host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="sentient", alias="POSTGRES_DB")
    postgres_user: str = Field(default="sentient", alias="POSTGRES_USER")
    postgres_password: str = Field(default="sentient", alias="POSTGRES_PASSWORD")

    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        alias="REDIS_URL",
    )

    eth_rpc_url: str | None = Field(default=None, alias="ETH_RPC_URL")
    base_rpc_url: str | None = Field(default=None, alias="BASE_RPC_URL")
    arbitrum_rpc_url: str | None = Field(default=None, alias="ARBITRUM_RPC_URL")

    chainlink_feed_registry_address: str | None = Field(
        default=None,
        alias="CHAINLINK_FEED_REGISTRY_ADDRESS",
    )

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")

    max_notional_per_trade: float = Field(
        default=0.0,
        alias="MAX_NOTIONAL_PER_TRADE",
    )
    max_daily_notional: float = Field(
        default=0.0,
        alias="MAX_DAILY_NOTIONAL",
    )
    max_open_positions: int = Field(
        default=0,
        alias="MAX_OPEN_POSITIONS",
    )

    indexer_poll_interval_seconds: int = Field(
        default=10,
        alias="INDEXER_POLL_INTERVAL_SECONDS",
    )
    indexer_start_block: int | None = Field(
        default=None,
        alias="INDEXER_START_BLOCK",
    )
    indexer_batch_size: int = Field(
        default=1000,
        alias="INDEXER_BATCH_SIZE",
    )
    subgraph_url: str | None = Field(
        default=None,
        alias="SUBGRAPH_URL",
        description="GraphQL endpoint for subgraph (e.g. The Graph Studio)",
    )
    subgraph_api_key: str | None = Field(
        default=None,
        alias="SUBGRAPH_API_KEY",
        description="API key for The Graph (required for 403 fix)",
    )
    subgraph_id: str | None = Field(
        default=None,
        alias="SUBGRAPH_ID",
        description="Subgraph deployment ID for Gateway URL (find in Studio Query tab)",
    )
    chain_base_sepolia_id: int = Field(
        default=84532,
        alias="CHAIN_BASE_SEPOLIA_ID",
        description="Chain ID for Base Sepolia (subgraph network)",
    )

    strategy_tick_seconds: int = Field(
        default=60,
        alias="STRATEGY_TICK_SECONDS",
    )
    risk_tick_seconds: int = Field(
        default=60,
        alias="RISK_TICK_SECONDS",
    )
    stale_price_seconds: int = Field(
        default=180,
        alias="STALE_PRICE_SECONDS",
    )
    alert_dedupe_seconds: int = Field(
        default=300,
        alias="ALERT_DEDUPE_SECONDS",
    )

    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="ALLOWED_ORIGINS",
    )

    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgresql://") or url.startswith("postgres://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            return url

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

