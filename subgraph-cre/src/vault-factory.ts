import {
  DefaultsUpdated as DefaultsUpdatedEvent,
  ExecutorUpdated as ExecutorUpdatedEvent,
  OwnershipTransferred as OwnershipTransferredEvent,
  RelayerUpdated as RelayerUpdatedEvent,
  VaultCreated as VaultCreatedEvent
} from "../generated/VaultFactory/VaultFactory"
import {
  DefaultsUpdated,
  ExecutorUpdated,
  OwnershipTransferred,
  RelayerUpdated,
  VaultCreated
} from "../generated/schema"

export function handleDefaultsUpdated(event: DefaultsUpdatedEvent): void {
  let entity = new DefaultsUpdated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.maxTradeAmount = event.params.maxTradeAmount
  entity.cooldownPeriod = event.params.cooldownPeriod

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleExecutorUpdated(event: ExecutorUpdatedEvent): void {
  let entity = new ExecutorUpdated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.oldExecutor = event.params.oldExecutor
  entity.newExecutor = event.params.newExecutor

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleOwnershipTransferred(
  event: OwnershipTransferredEvent
): void {
  let entity = new OwnershipTransferred(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.previousOwner = event.params.previousOwner
  entity.newOwner = event.params.newOwner

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleRelayerUpdated(event: RelayerUpdatedEvent): void {
  let entity = new RelayerUpdated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.oldRelayer = event.params.oldRelayer
  entity.newRelayer = event.params.newRelayer

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleVaultCreated(event: VaultCreatedEvent): void {
  let entity = new VaultCreated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.user = event.params.user
  entity.vault = event.params.vault
  entity.portfolio = event.params.portfolio
  entity.vaultIndex = event.params.vaultIndex

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}
