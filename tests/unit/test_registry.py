"""Unit tests for the registry module against the new address-book schema."""

from unittest.mock import MagicMock, patch

from votemarket_toolkit.shared.registry import Registry


MOCK_ADDRESS_BOOK = {
    "protocols": {
        "curve": {
            "name": "Curve",
            "key": "curve",
            "chains": {
                "ethereum": {
                    "key": "curve-1",
                    "id": 1,
                    "name": "Ethereum",
                    "explorer": "https://etherscan.io/address/",
                    "contracts": [
                        {"name": "GAUGE_CONTROLLER", "address": "0xCurveGC", "category": "protocol", "url": None},
                        {"name": "VECRV", "address": "0xVeCRV", "category": "protocol", "url": None},
                        {"name": "PLATFORM", "address": "0xCurvePlatformV1", "category": "votemarket", "url": None},
                    ],
                },
                "arbitrum": {
                    "key": "curve-42161",
                    "id": 42161,
                    "name": "Arbitrum",
                    "explorer": "https://arbiscan.io/address/",
                    "contracts": [
                        {"name": "PLATFORM", "address": "0xCurvePlatformArb", "category": "votemarket", "url": None},
                    ],
                },
            },
        },
        "balancer": {
            "name": "Balancer",
            "key": "balancer",
            "chains": {
                "ethereum": {
                    "key": "balancer-1",
                    "id": 1,
                    "name": "Ethereum",
                    "explorer": "https://etherscan.io/address/",
                    "contracts": [
                        {"name": "GAUGE_CONTROLLER", "address": "0xBalancerGC", "category": "protocol", "url": None},
                        {"name": "VEBAL", "address": "0xVeBAL", "category": "protocol", "url": None},
                        {"name": "PLATFORM", "address": "0xBalancerPlatformV1", "category": "votemarket", "url": None},
                    ],
                },
                "base": {
                    "key": "balancer-8453",
                    "id": 8453,
                    "name": "Base",
                    "explorer": "https://basescan.org/address/",
                    "contracts": [
                        {"name": "PLATFORM", "address": "0xBalancerPlatformBase", "category": "votemarket", "url": None},
                    ],
                },
            },
        },
    }
}


def _make_registry_with_mock(data):
    """Instantiate Registry with mocked HTTP response."""
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        return Registry()


class TestRegistryParsesNewSchema:
    def test_platforms_ethereum_mapped_to_v1(self):
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert r._platforms["curve"]["v1"][1] == "0xCurvePlatformV1"

    def test_platforms_l2_mapped_to_v2(self):
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert r._platforms["curve"]["v2"][42161] == "0xCurvePlatformArb"
        assert r._platforms["balancer"]["v2"][8453] == "0xBalancerPlatformBase"

    def test_controllers_parsed_from_ethereum(self):
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert r._controllers["curve"] == "0xCurveGC"
        assert r._controllers["balancer"] == "0xBalancerGC"

    def test_ve_addresses_parsed_from_ethereum(self):
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert r._ve_addresses["curve"] == "0xVeCRV"
        assert r._ve_addresses["balancer"] == "0xVeBAL"

    def test_historical_v2_old_always_added_for_curve(self):
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert "v2_old" in r._platforms["curve"]
        assert r._platforms["curve"]["v2_old"][42161] == "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"

    def test_missing_protocol_falls_back_to_static(self):
        """Protocols absent from registry (e.g. pendle) use FALLBACK_PLATFORMS."""
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert "pendle" in r._platforms
        assert r._controllers.get("pendle") == Registry.FALLBACK_CONTROLLERS["pendle"]

    def test_missing_ve_address_falls_back_to_static(self):
        r = _make_registry_with_mock(MOCK_ADDRESS_BOOK)
        assert r._ve_addresses.get("pendle") == Registry.FALLBACK_VE_ADDRESSES["pendle"]


class TestRegistryFallbackOnFetchFailure:
    def test_fallback_used_when_fetch_fails(self):
        with patch("httpx.get", side_effect=OSError("network error")):
            r = Registry()

        assert r._platforms == {
            k: dict(v) for k, v in Registry.FALLBACK_PLATFORMS.items()
        }
        assert r._controllers == Registry.FALLBACK_CONTROLLERS
        assert r._ve_addresses == Registry.FALLBACK_VE_ADDRESSES

    def test_controllers_fall_through_to_class_fallback(self):
        """get_gauge_controller falls through to FALLBACK_CONTROLLERS if controller missing."""
        from votemarket_toolkit.shared import registry as reg_module

        original = reg_module._registry
        try:
            with patch("httpx.get", side_effect=OSError("down")):
                reg_module._registry = Registry()
            ctrl = reg_module.get_gauge_controller("yb")
            assert ctrl == Registry.FALLBACK_CONTROLLERS["yb"]
        finally:
            reg_module._registry = original


class TestFindContract:
    def test_find_by_name_and_category(self):
        contracts = [
            {"name": "FOO", "address": "0x1", "category": "protocol"},
            {"name": "BAR", "address": "0x2", "category": "votemarket"},
        ]
        result = Registry._find_contract(contracts, "BAR", "votemarket")
        assert result["address"] == "0x2"

    def test_returns_none_when_not_found(self):
        contracts = [{"name": "FOO", "address": "0x1", "category": "protocol"}]
        assert Registry._find_contract(contracts, "MISSING") is None

    def test_category_filter_excludes_wrong_category(self):
        contracts = [{"name": "FOO", "address": "0x1", "category": "locker"}]
        assert Registry._find_contract(contracts, "FOO", "protocol") is None
