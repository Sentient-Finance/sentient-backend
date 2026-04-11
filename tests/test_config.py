class TestSettingsCcipDefaults:
    """Tests for CCIP-related Settings fields."""

    def test_ccip_routers_default_values(self):
        from libs.core.config import Settings

        settings = Settings()
        assert (
            settings.ccip_routers[84532] == "0xD3b06cEbF099CE7DA4AcCf578aaebFDBd6e88a93"
        )
        assert (
            settings.ccip_routers[11155111]
            == "0x0BF3dE8c5D3e8A2B34D2BEeB17ABfCeBaf363A59"
        )

    def test_ccip_chain_selectors_default_values(self):
        from libs.core.config import Settings

        settings = Settings()
        assert settings.ccip_chain_selectors["ethereum_sepolia"] == 16015286601757825753
        assert settings.ccip_chain_selectors["arbitrum_sepolia"] == 3478487238524512106
        assert settings.ccip_chain_selectors["op_sepolia"] == 5224473277236331295
        assert (
            settings.ccip_chain_selectors["bnb_chain_testnet"] == 13264668187771770619
        )

    def test_chain_eth_sepolia_id_default(self):
        from libs.core.config import Settings

        settings = Settings()
        assert settings.chain_eth_sepolia_id == 11155111

    def test_chain_base_sepolia_id_default(self):
        from libs.core.config import Settings

        settings = Settings()
        assert settings.chain_base_sepolia_id == 84532

    def test_ccip_routers_custom_override(self):
        from libs.core.config import Settings

        custom_routers = {84532: "0xCustomRouter1", 11155111: "0xCustomRouter2"}
        settings = Settings(ccip_routers=custom_routers)
        assert settings.ccip_routers == custom_routers

    def test_ccip_chain_selectors_custom_override(self):
        from libs.core.config import Settings

        custom_selectors = {"ethereum_sepolia": 999999}
        settings = Settings(ccip_chain_selectors=custom_selectors)
        assert settings.ccip_chain_selectors["ethereum_sepolia"] == 999999
