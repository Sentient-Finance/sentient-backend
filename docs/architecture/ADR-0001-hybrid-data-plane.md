# ADR-0001 — Hybrid Data Plane (The Graph + Backend Indexer)

## Status
Accepted (MVP)

## Date
2026-03-01

## Context
Sentient backend needs to support:
- Fast FE read/query for vault/history pages
- Reliable backend execution workflows (strategy tick, CRE execution, retries, risk alerts)

Using only one system for both concerns creates tradeoffs:
- The Graph is excellent for FE read patterns, but is not an execution state machine.
- Backend-only query APIs can serve FE, but lose GraphQL ergonomics and query flexibility for UI.

## Decision
Adopt hybrid architecture:

1. **The Graph is the read layer for FE**
   - GraphQL queries
   - Filter/sort/history UX
   - Dynamic data source (Factory -> Vault templates) where needed

2. **Backend Indexer + Postgres is the operational source for BE**
   - Event ingestion with checkpointing and dedupe
   - Idempotency, retries, dead-letter workflows
   - Execution lifecycle + audit trail
   - Risk/alert logic

## Source-of-Truth Boundaries
- **On-chain state**: final financial truth
- **Backend Postgres**: operational truth for automation/execution
- **The Graph**: read-optimized projection for frontend

## Event Priority for Indexer
### P0 (MVP)
- `VaultCreated` (Factory)
- `VaultInitialized`
- `TokenRuleSet`
- `SwapExecuted`
- `CrossChainShieldTriggered`

### P1 (next)
- `TokenDeposited`, `TokenWithdrawn`
- `RouterUpdated`, `ExecutorUpdated`, `AuthorizedExecutorUpdated`
- `MaxTradeAmountUpdated`, `CooldownPeriodUpdated`, `MaxSlippageUpdated`
- `PriceFeedUpdated`, `OwnershipTransferred`
- `CCIPRouterUpdated`, `AutomationConfigUpdated`

## Consequences
### Positive
- FE gets flexible, fast GraphQL reads
- BE gets deterministic ops behavior and restart safety
- Better auditability from event -> task -> execution

### Tradeoffs
- Two data planes to maintain
- Need clear ownership boundaries and observability

## Implementation Notes (MVP)
- Keep API issue #4 focused on read endpoints
- Keep indexer issue #3 focused on ingestion/reliability
- Keep strategy/CRE/risk on issues #5/#6/#7

## Related
- #28 (architecture tracking)
- #1 (EPIC)
- #3 #4 #5 #6 #7
