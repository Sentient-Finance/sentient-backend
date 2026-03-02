import { BigInt } from '@graphprotocol/graph-ts'

import { VaultCreated } from '../generated/VaultFactory/VaultFactory'
import {
  Portfolio as PortfolioTemplate,
  PortfolioVault as PortfolioVaultTemplate,
} from '../generated/templates'
import { Vault } from '../generated/schema'

export function handleVaultCreated(event: VaultCreated): void {
  const id = event.params.vault.toHexString().toLowerCase()

  let vault = Vault.load(id)
  if (vault == null) {
    vault = new Vault(id)
    vault.address = event.params.vault
    vault.portfolioAddress = event.params.portfolio
    vault.owner = event.params.owner
    vault.executor = event.params.executor
    vault.createdAtBlock = event.block.number
    vault.createdAtTimestamp = event.block.timestamp
    vault.createdTxHash = event.transaction.hash
    vault.eventCount = BigInt.zero()
    vault.save()
  }

  PortfolioVaultTemplate.create(event.params.vault)
  PortfolioTemplate.create(event.params.portfolio)
}
