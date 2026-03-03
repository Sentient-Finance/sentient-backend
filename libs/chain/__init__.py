"""On-chain interaction utilities (RPC client, ABI helpers, event decoders).

Intended to wrap web3.py / eth_abi calls so that the indexer and worker
can import a stable interface rather than raw library calls.
"""
