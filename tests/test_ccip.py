import pytest
from fastapi import HTTPException


class TestGetRpcUrl:
    """Tests for _get_rpc_url function."""

    def test_base_sepolia_chain(self):
        from apps.api.v1.routes.ccip import _get_rpc_url
        from libs.core.config import Settings

        settings = Settings(
            chain_base_sepolia_id=84532,
            base_rpc_url="https://custom.base.rpc",
        )
        result = _get_rpc_url(84532, settings)
        assert result == "https://custom.base.rpc"

    def test_eth_sepolia_chain(self):
        from apps.api.v1.routes.ccip import _get_rpc_url
        from libs.core.config import Settings

        settings = Settings(
            chain_eth_sepolia_id=11155111,
            eth_rpc_url="https://custom.eth.rpc",
        )
        result = _get_rpc_url(11155111, settings)
        assert result == "https://custom.eth.rpc"

    def test_fallback_to_default_base_rpc(self):
        from apps.api.v1.routes.ccip import _get_rpc_url
        from libs.core.config import Settings

        settings = Settings(chain_base_sepolia_id=84532, base_rpc_url=None)
        result = _get_rpc_url(84532, settings)
        assert result == "https://sepolia.base.org"

    def test_fallback_to_default_eth_rpc(self):
        from apps.api.v1.routes.ccip import _get_rpc_url
        from libs.core.config import Settings

        settings = Settings(chain_eth_sepolia_id=11155111, eth_rpc_url=None)
        result = _get_rpc_url(11155111, settings)
        assert result == "https://rpc.sepolia.org"

    def test_unsupported_chain_raises_400(self):
        from apps.api.v1.routes.ccip import _get_rpc_url
        from libs.core.config import Settings

        settings = Settings()
        with pytest.raises(HTTPException) as exc_info:
            _get_rpc_url(99999, settings)
        assert exc_info.value.status_code == 400
        assert "Unsupported chain_id" in exc_info.value.detail


class TestBuildCcipMessage:
    """Tests for _build_ccip_message function."""

    def test_build_message_with_valid_addresses(self):
        from apps.api.v1.routes.ccip import _build_ccip_message
        from apps.schemas.ccip import EstimateFeeRequest

        body = EstimateFeeRequest(
            vault_address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            chain_id=84532,
            destination_chain_selector=16015286601757825753,
            token_address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            amount="1000000",
            receiver="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        )
        result = _build_ccip_message(body)
        assert isinstance(result, tuple)
        assert len(result) == 5


class TestEstimateCcipFee:
    """Integration tests for estimate_ccip_fee endpoint."""

    def test_estimate_fee_rejects_unknown_chain_router(self, client):
        """estimate_ccip_fee returns 400 when chain_id has no CCIP router."""
        response = client.post(
            "/api/v1/vaults/ccip/estimate-fee",
            json={
                "vault_address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
                "chain_id": 99999,  # No router for this
                "destination_chain_selector": 16015286601757825753,
                "token_address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
                "amount": "1000000",
                "receiver": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            },
        )
        assert response.status_code == 400
        assert "No CCIP router" in response.json()["detail"]
