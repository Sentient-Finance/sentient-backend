# Sentient Subgraph (Dynamic Data Source)

This subgraph follows the **Factory -> Template.create(vault)** flow:
- Index `VaultFactory` event `VaultCreated`
- Dynamically create `PortfolioVault` data source for each new vault
- Index vault-level events for all user-created vaults

## Configure before build/deploy
Edit `subgraph.yaml`:
- `dataSources[0].source.address` => factory contract address
- `dataSources[0].source.startBlock` => factory deployment block
- `network` => `base`/`base-sepolia` according to deployment

## Commands
```bash
cd subgraph
npm install
npm run codegen
npm run build
```

## Notes
- Dynamic data source only starts indexing vault events from the creation point onward.
- Keep backend indexer as operational source for retries/execution state.
- The Graph is used as read/query layer for FE.
