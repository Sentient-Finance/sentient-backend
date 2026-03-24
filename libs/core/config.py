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
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")

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
        description="Max USD notional per single trade. 0.0 = unlimited (no cap enforced).",
    )
    max_daily_notional: float = Field(
        default=0.0,
        alias="MAX_DAILY_NOTIONAL",
        description="Max USD notional across all trades in a rolling 24-hour window. 0.0 = unlimited.",
    )
    max_open_positions: int = Field(
        default=0,
        alias="MAX_OPEN_POSITIONS",
        description="Max number of simultaneously open positions. 0 = unlimited.",
    )

    indexer_tick_seconds: int = Field(
        default=10,
        alias="INDEXER_TICK_SECONDS",
        description="Celery Beat interval for indexer sync (default 10s)",
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
    execution_cooldown_seconds: int = Field(
        default=3600,
        alias="EXECUTION_COOLDOWN_SECONDS",
        description="Min seconds between same-action executions on the same vault",
    )
    stale_price_seconds: int = Field(
        default=3600,
        alias="STALE_PRICE_SECONDS",
        description="Chainlink testnet feeds update ~hourly; mainnet use 180",
    )
    alert_dedupe_seconds: int = Field(
        default=300,
        alias="ALERT_DEDUPE_SECONDS",
    )

    rate_limit_public: str = Field(
        default="60/minute",
        alias="RATE_LIMIT_PUBLIC",
        description="Rate limit for standard public APIs",
    )
    rate_limit_heavy: str = Field(
        default="20/minute",
        alias="RATE_LIMIT_HEAVY",
        description="Rate limit for heavy RPC/write APIs",
    )

    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="ALLOWED_ORIGINS",
    )

    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # Executor wallet — signs & sends executeSwap transactions
    executor_private_key: str | None = Field(
        default=None,
        alias="EXECUTOR_PRIVATE_KEY",
        description="Hex private key of the on-chain executor wallet",
    )
    executor_dry_run: bool = Field(
        default=True,
        alias="EXECUTOR_DRY_RUN",
        description="If True, simulate via eth_call only — no real transactions sent",
    )
    executor_gas_limit: int = Field(
        default=350_000,
        alias="EXECUTOR_GAS_LIMIT",
    )
    # Base token used as the swap counter-asset (USDC on Base Sepolia by default)
    base_token_address: str = Field(
        default="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        alias="BASE_TOKEN_ADDRESS",
        description="ERC-20 address of the base/quote token (USDC on Base Sepolia)",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            return url

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
