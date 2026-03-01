import { BigInt, dataSource } from '@graphprotocol/graph-ts'

import {
  CrossChainShieldTriggered,
  SwapExecuted,
  TokenRuleSet,
  VaultInitialized,
} from '../generated/templates/PortfolioVault/PortfolioVault'
import { Vault, VaultEvent } from '../generated/schema'

function getVaultIdFromDataSource(): string {
  return dataSource.address().toHexString().toLowerCase()
}

function getOrCreateVault(): Vault {
  const id = getVaultIdFromDataSource()
  let vault = Vault.load(id)
  if (vault == null) {
    vault = new Vault(id)
    vault.address = dataSource.address()
    vault.createdAtBlock = BigInt.zero()
    vault.createdAtTimestamp = BigInt.zero()
    vault.createdTxHash = dataSource.address()
    vault.eventCount = BigInt.zero()
  }
  return vault as Vault
}

function newEventEntity(eventName: string, txHash: string, logIndex: BigInt): VaultEvent {
  const id = txHash.concat('-').concat(logIndex.toString())
  const entity = new VaultEvent(id)
  entity.vault = getVaultIdFromDataSource()
  entity.eventName = eventName
  return entity
}

export function handleVaultInitialized(event: VaultInitialized): void {
  const vault = getOrCreateVault()
  vault.owner = event.params.owner
  vault.executor = event.params.executor
  vault.createdAtBlock = event.block.number
  vault.createdAtTimestamp = event.block.timestamp
  vault.createdTxHash = event.transaction.hash
  vault.eventCount = vault.eventCount.plus(BigInt.fromI32(1))
  vault.save()

  const e = newEventEntity('VaultInitialized', event.transaction.hash.toHexString(), event.logIndex)
  e.blockNumber = event.block.number
  e.blockTimestamp = event.block.timestamp
  e.txHash = event.transaction.hash
  e.logIndex = event.logIndex
  e.save()
}

export function handleTokenRuleSet(event: TokenRuleSet): void {
  const vault = getOrCreateVault()
  vault.eventCount = vault.eventCount.plus(BigInt.fromI32(1))
  vault.save()

  const e = newEventEntity('TokenRuleSet', event.transaction.hash.toHexString(), event.logIndex)
  e.blockNumber = event.block.number
  e.blockTimestamp = event.block.timestamp
  e.txHash = event.transaction.hash
  e.logIndex = event.logIndex
  e.token = event.params.token
  e.save()
}

export function handleSwapExecuted(event: SwapExecuted): void {
  const vault = getOrCreateVault()
  vault.eventCount = vault.eventCount.plus(BigInt.fromI32(1))
  vault.save()

  const e = newEventEntity('SwapExecuted', event.transaction.hash.toHexString(), event.logIndex)
  e.blockNumber = event.block.number
  e.blockTimestamp = event.block.timestamp
  e.txHash = event.transaction.hash
  e.logIndex = event.logIndex
  e.tokenIn = event.params.tokenIn
  e.tokenOut = event.params.tokenOut
  e.amountIn = event.params.amountIn
  e.amountOut = event.params.amountOut
  e.save()
}

export function handleCrossChainShieldTriggered(event: CrossChainShieldTriggered): void {
  const vault = getOrCreateVault()
  vault.eventCount = vault.eventCount.plus(BigInt.fromI32(1))
  vault.save()

  const e = newEventEntity(
    'CrossChainShieldTriggered',
    event.transaction.hash.toHexString(),
    event.logIndex,
  )
  e.blockNumber = event.block.number
  e.blockTimestamp = event.block.timestamp
  e.txHash = event.transaction.hash
  e.logIndex = event.logIndex
  e.amountOut = event.params.amount
  e.save()
}
