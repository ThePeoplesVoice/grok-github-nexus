"""
Nexus Layer 2 Monetization & x402 Protocol Scaffold.

Design Principle: Open Core (Layer 0) never calls or requires this module.
Layer 2 is inert until config/progressive.json "2_micropayment_agent.enabled" is set to true
and real infrastructure (USDC address, Base network endpoint) is configured.
"""

from typing import Dict, Any


class PaymentRequiredException(Exception):
    """Raised when an agent endpoint requires an x402 header payment."""

    def __init__(self, usdc_address: str, fee_usdc: float, network: str) -> None:
        self.usdc_address = usdc_address
        self.fee_usdc = fee_usdc
        self.network = network
        self.message = (
            f"Payment of {fee_usdc} USDC on {network} required to {usdc_address}"
        )
        super().__init__(self.message)


def get_layer2_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts Layer 2 config safely from the progressive configuration state."""
    layers = config_data.get("layers", {})
    l2 = layers.get("2_micropayment_agent", {})
    return {
        "enabled": l2.get("enabled", False),
        "x402_endpoint_url": l2.get("x402_endpoint_url"),
        "usdc_address": l2.get("usdc_address"),
        "base_fee_usdc": l2.get("base_fee_usdc", 0.10),
        "network": l2.get("network", "base-mainnet"),
    }


def verify_x402_header(
    headers: Dict[str, str], config_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates x402 payment headers against the configured Layer 2 policy.

    Returns a dict with verification status. If Layer 2 is disabled, execution is
    always permitted without enforcing micropayments.

    Raises:
        PaymentRequiredException: when Layer 2 is enabled and no payment signature
            is present in the request headers.
    """
    l2_cfg = get_layer2_config(config_data)

    if not l2_cfg.get("enabled", False):
        return {"status": "bypassed", "reason": "Layer 2 disabled"}

    payment_header = headers.get("X-Payment-Signature") or headers.get(
        "x-payment-signature"
    )

    if not payment_header:
        usdc_addr = l2_cfg.get("usdc_address") or "0x0000000000000000000000000000000000000000"
        fee = l2_cfg.get("base_fee_usdc", 0.10)
        network = l2_cfg.get("network", "base-mainnet")
        raise PaymentRequiredException(
            usdc_address=usdc_addr, fee_usdc=fee, network=network
        )

    # Stub verification path — future Base network signature validation goes here.
    return {"status": "verified", "signature": payment_header}


def build_402_response_headers(
    usdc_address: str, fee_usdc: float, network: str
) -> Dict[str, str]:
    """Constructs HTTP 402 response headers for agent consumption."""
    return {
        "X-Payment-Required": "true",
        "X-Payment-Address": usdc_address,
        "X-Payment-Amount": str(fee_usdc),
        "X-Payment-Currency": "USDC",
        "X-Payment-Network": network,
    }
