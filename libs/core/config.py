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

    indexer_rpc_url: str | None = Field(default=None, alias="INDEXER_RPC_URL")
    indexer_chain_id: int = Field(default=8453, alias="INDEXER_CHAIN_ID")
    indexer_contracts: str = Field(default="", alias="INDEXER_CONTRACTS")
    indexer_confirmations: int = Field(default=2, alias="INDEXER_CONFIRMATIONS")
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

    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

