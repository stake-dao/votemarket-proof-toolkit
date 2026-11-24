from types import SimpleNamespace

import pytest

from votemarket_toolkit.campaigns import service

REWARD_TOKEN = "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F"


@pytest.fixture
def calculator(monkeypatch):
    calculator = service.CampaignService()
    monkeypatch.setattr(
        calculator, "get_token_per_vetoken", lambda protocol: 0.023
    )
    web3 = SimpleNamespace(
        eth=SimpleNamespace(
            contract=lambda **kwargs: SimpleNamespace(
                functions=SimpleNamespace(
                    decimals=lambda: SimpleNamespace(call=lambda: 18)
                )
            )
        )
    )
    monkeypatch.setattr(
        calculator,
        "get_web3_service",
        lambda chain_id: SimpleNamespace(w3=web3),
    )
    return calculator


@pytest.mark.parametrize("protocol", ["curve", "fxn"])
@pytest.mark.parametrize("leg", ["emission", "reward"])
@pytest.mark.parametrize(
    "price", [None, 0, -0.2, float("nan"), float("inf"), float("-inf")]
)
def test_efficiency_rejects_unavailable_or_invalid_prices(
    monkeypatch, calculator, protocol, leg, price
):
    emission_token = calculator._get_protocol_config(protocol)[
        "emission_token"
    ]

    def prices(chain_id, token_amounts):
        token, _ = token_amounts[0]
        invalid_token = emission_token if leg == "emission" else REWARD_TOKEN
        if token.lower() == invalid_token.lower():
            return [] if price is None else [("unused", price)]
        return [("unused", 0.2)]

    monkeypatch.setattr(service, "get_erc20_prices_in_usd", prices)
    with pytest.raises(ValueError, match=f"{leg} token price"):
        calculator.calculate_max_reward_for_efficiency(
            1.15, REWARD_TOKEN, protocol
        )


@pytest.mark.parametrize("protocol", ["curve", "fxn"])
@pytest.mark.parametrize(
    "emission_price,reward_price,expected",
    [
        (2.0, 0.2, 0.2),
        (1.0, 0.2, 0.1),
        (2.0, 1.0, 0.04),
    ],
)
def test_efficiency_uses_real_prices_including_one_dollar(
    monkeypatch, calculator, protocol, emission_price, reward_price, expected
):
    emission_token = calculator._get_protocol_config(protocol)[
        "emission_token"
    ]
    monkeypatch.setattr(
        service,
        "get_erc20_prices_in_usd",
        lambda chain_id, tokens: [
            (
                "unused",
                emission_price
                if tokens[0][0].lower() == emission_token.lower()
                else reward_price,
            )
        ],
    )
    result = calculator.calculate_max_reward_for_efficiency(
        1.15, REWARD_TOKEN, protocol
    )
    assert result["max_reward_tokens"] == pytest.approx(expected)
    assert result["emission_token_price"] == emission_price
    assert result["reward_token_price"] == reward_price
