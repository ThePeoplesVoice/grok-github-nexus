"""Tests for nexus.monetization — x402 Layer 2 scaffold."""

import pytest

from nexus.monetization import (
    PaymentRequiredException,
    build_402_response_headers,
    verify_x402_header,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DISABLED_CONFIG = {
    "layers": {
        "2_micropayment_agent": {
            "enabled": False,
        }
    }
}

_ENABLED_CONFIG = {
    "layers": {
        "2_micropayment_agent": {
            "enabled": True,
            "usdc_address": "0x1234567890abcdef1234567890abcdef12345678",
            "base_fee_usdc": 0.25,
            "network": "base-mainnet",
        }
    }
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_layer2_disabled_bypasses_payment():
    """When Layer 2 is disabled, no payment check fires — Open Core unaffected."""
    result = verify_x402_header(headers={}, config_data=_DISABLED_CONFIG)
    assert result["status"] == "bypassed"
    assert "disabled" in result["reason"].lower()


def test_layer2_enabled_missing_header_raises_402():
    """When Layer 2 is enabled and no payment signature is present, raise PaymentRequiredException."""
    with pytest.raises(PaymentRequiredException) as exc_info:
        verify_x402_header(headers={}, config_data=_ENABLED_CONFIG)

    err = exc_info.value
    assert err.usdc_address == "0x1234567890abcdef1234567890abcdef12345678"
    assert err.fee_usdc == 0.25
    assert err.network == "base-mainnet"
    assert "0.25 USDC" in str(err)


def test_layer2_enabled_with_header_returns_verified():
    """A request carrying an X-Payment-Signature header passes the stub verification."""
    result = verify_x402_header(
        headers={"X-Payment-Signature": "sig_abc123"},
        config_data=_ENABLED_CONFIG,
    )
    assert result["status"] == "verified"
    assert result["signature"] == "sig_abc123"


def test_layer2_enabled_lowercase_header_accepted():
    """Header lookup is case-insensitive for x-payment-signature."""
    result = verify_x402_header(
        headers={"x-payment-signature": "sig_lower"},
        config_data=_ENABLED_CONFIG,
    )
    assert result["status"] == "verified"


def test_402_header_construction():
    """build_402_response_headers returns the full set of agent-readable x402 fields."""
    headers = build_402_response_headers(
        usdc_address="0x1234",
        fee_usdc=0.10,
        network="base-mainnet",
    )
    assert headers["X-Payment-Required"] == "true"
    assert headers["X-Payment-Address"] == "0x1234"
    assert headers["X-Payment-Amount"] == "0.1"
    assert headers["X-Payment-Currency"] == "USDC"
    assert headers["X-Payment-Network"] == "base-mainnet"


def test_empty_config_defaults_to_disabled():
    """Missing layer config always falls back to disabled — no surprise payment gates."""
    result = verify_x402_header(headers={}, config_data={})
    assert result["status"] == "bypassed"
