"""Tests for credential redaction in logs and error messages."""

from votemarket_toolkit.shared.redact import (
    format_exception_safe,
    redact_secrets,
)


def test_redacts_alchemy_path_key():
    text = (
        "HTTPSConnectionPool(host='eth-mainnet.g.alchemy.com', port=443): "
        "Max retries exceeded with url: /v2/AbCdEf1234567890AbCdEf12"
    )
    redacted = redact_secrets(text)
    assert "AbCdEf1234567890" not in redacted
    assert "/v2/***" in redacted


def test_redacts_query_credentials():
    text = (
        "https://api.etherscan.io/v2/api?chainid=1&apikey=SECRETKEY123"
        "&module=logs"
    )
    redacted = redact_secrets(text)
    assert "SECRETKEY123" not in redacted
    assert "chainid=1" in redacted


def test_redacts_url_userinfo():
    redacted = redact_secrets("https://user:hunter2@rpc.example.com/path")
    assert "hunter2" not in redacted


def test_keeps_normal_text_untouched():
    message = "execution reverted: gauge_types for 0x2F50D538606Fa9EDD2B11E"
    assert redact_secrets(message) == message


def test_format_exception_safe_includes_type_and_redacts():
    formatted = format_exception_safe(
        ValueError("boom url: /v2/AbCdEf1234567890AbCdEf12")
    )
    assert formatted.startswith("ValueError:")
    assert "/v2/***" in formatted
    assert "AbCdEf1234567890" not in formatted
