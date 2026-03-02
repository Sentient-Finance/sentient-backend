# Sentient Subgraph (Factory -> Vault dynamic datasource)

Current MVP architecture is **single runtime contract per user** (`PortfolioVault`).

Flow:
- Index `VaultFactory` event `VaultCreated(user, vault, vaultIndex)`
- Dynamically create `PortfolioVault` datasource for each new vault address
- Index vault-level events for all created vaults

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
- Backend indexer remains operational source for retries/execution state.
- Subgraph is read/query layer for FE.
