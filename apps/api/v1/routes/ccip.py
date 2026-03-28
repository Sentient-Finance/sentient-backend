"""CCIP config and fee estimation."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from eth_abi import encode
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from web3 import Web3
from web3.exceptions import ContractLogicError

from apps.api.limiter import limiter
from libs.core.config import Settings, get_settings

router = APIRouter(prefix="/vaults/ccip", tags=["ccip"])
settings = get_settings()

CCIP_ROUTERS: dict[int, str] = {
    84532: "0xD3b06cEbF099CE7DA4AcCf578aaebFDBd6e88a93",
    11155111: "0x0BF3dE8c5D3e8A2B34D2BEeB17ABfCeBaf363A59",
}

CCIP_CHAIN_SELECTORS: dict[str, int] = {
    "ethereum_sepolia": 16015286601757825753,
    "arbitrum_sepolia": 3478487238524512106,
    "op_sepolia": 5224473277236331295,
    "bnb_chain_testnet": 13264668187771770619,
}

_GET_FEE_ABI = [
    {
        "inputs": [
            {
                "internalType": "uint64",
                "name": "destChainSelector",
                "type": "uint64",
            },
            {
                "internalType": "tuple",
                "name": "message",
                "type": "tuple",
                "components": [
                    {"internalType": "bytes", "name": "receiver", "type": "bytes"},
                    {"internalType": "bytes", "name": "data", "type": "bytes"},
                    {
                        "internalType": "tuple[]",
                        "name": "tokenAmounts",
                        "type": "tuple[]",
                        "components": [
                            {
                                "internalType": "address",
                                "name": "token",
                                "type": "address",
                            },
                            {
                                "internalType": "uint256",
                                "name": "amount",
                                "type": "uint256",
                            },
                        ],
                    },
                    {"internalType": "address", "name": "feeToken", "type": "address"},
                    {"internalType": "bytes", "name": "extraArgs", "type": "bytes"},
                ],
            },
        ],
        "name": "getFee",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

_ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
_EXTRA_ARGS_TAG = bytes.fromhex("97a657c9")


class CCIPChainConfig(BaseModel):
    chain_id: int
    chain_name: str
    ccip_router: str


class CCIPDestinationConfig(BaseModel):
    chain_id: int | None = None
    chain_name: str
    selector: int


class CCIPConfigResponse(BaseModel):
    chains: list[CCIPChainConfig]
    destinations: list[CCIPDestinationConfig]


class EstimateFeeRequest(BaseModel):
    vault_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    chain_id: int = Field(default=84532, description="Source chain (vault chain)")
    destination_chain_selector: int = Field(
        ..., description="CCIP destination chain selector"
    )
    token_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    amount: str = Field(..., description="Raw amount (e.g. 1000000 for 1 USDC)")
    receiver: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")


class EstimateFeeResponse(BaseModel):
    fee_wei: str
    fee_eth: str


def _get_rpc_url(chain_id: int, settings: Settings) -> str:
    if chain_id == 84532:
        return settings.base_rpc_url or "https://sepolia.base.org"
    if chain_id == 11155111:
        return settings.eth_rpc_url or "https://rpc.sepolia.org"
    raise HTTPException(status_code=400, detail=f"Unsupported chain_id: {chain_id}")


@lru_cache(maxsize=4)
def _get_w3_for_chain(rpc_url: str) -> Web3:
    """Cache one Web3 instance per RPC URL — reuses the connection pool."""
    return Web3(Web3.HTTPProvider(rpc_url))


def _build_ccip_message(body: EstimateFeeRequest) -> tuple:  # type: ignore[type-arg]
    receiver_bytes = encode(["address"], [Web3.to_checksum_address(body.receiver)])
    extra_args = _EXTRA_ARGS_TAG + encode(["uint256"], [0])
    token_amounts = [(Web3.to_checksum_address(body.token_address), int(body.amount))]
    fee_token = Web3.to_checksum_address(_ZERO_ADDRESS)
    return (receiver_bytes, b"", token_amounts, fee_token, extra_args)


# Built once at import time — data is static, no need to reconstruct per request
_CCIP_CONFIG = CCIPConfigResponse(
    chains=[
        CCIPChainConfig(
            chain_id=84532, chain_name="Base Sepolia", ccip_router=CCIP_ROUTERS[84532]
        ),
        CCIPChainConfig(
            chain_id=11155111,
            chain_name="Ethereum Sepolia",
            ccip_router=CCIP_ROUTERS[11155111],
        ),
    ],
    destinations=[
        CCIPDestinationConfig(
            chain_name="Ethereum Sepolia",
            selector=CCIP_CHAIN_SELECTORS["ethereum_sepolia"],
        ),
        CCIPDestinationConfig(
            chain_name="Arbitrum Sepolia",
            selector=CCIP_CHAIN_SELECTORS["arbitrum_sepolia"],
        ),
        CCIPDestinationConfig(
            chain_name="OP Sepolia", selector=CCIP_CHAIN_SELECTORS["op_sepolia"]
        ),
        CCIPDestinationConfig(
            chain_name="BNB Chain Testnet",
            selector=CCIP_CHAIN_SELECTORS["bnb_chain_testnet"],
        ),
    ],
)


@router.get("/config", response_model=CCIPConfigResponse)
def get_ccip_config() -> CCIPConfigResponse:
    return _CCIP_CONFIG


@router.post("/estimate-fee", response_model=EstimateFeeResponse)
@limiter.limit(settings.rate_limit_heavy)
def estimate_ccip_fee(
    request: Request,
    body: EstimateFeeRequest,
    settings: Settings = Depends(get_settings),
):
    rpc_url = _get_rpc_url(body.chain_id, settings)
    w3 = _get_w3_for_chain(rpc_url)

    ccip_router = CCIP_ROUTERS.get(body.chain_id)
    if not ccip_router:
        raise HTTPException(
            status_code=400, detail=f"No CCIP router for chain_id {body.chain_id}"
        )

    message = _build_ccip_message(body)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(ccip_router), abi=_GET_FEE_ABI
    )

    try:
        fee = contract.functions.getFee(body.destination_chain_selector, message).call()
    except ContractLogicError:
        raise HTTPException(
            status_code=400,
            detail="getFee reverted: contract rejected the message parameters",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=503, detail="RPC error estimating CCIP fee"
        ) from None

    fee_eth = format(Decimal(w3.from_wei(fee, "ether")), "f")
    return EstimateFeeResponse(fee_wei=str(fee), fee_eth=fee_eth)
