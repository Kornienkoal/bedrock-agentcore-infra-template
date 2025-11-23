import json
import logging
from datetime import datetime
from typing import Any, TypedDict

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Mock warranty database


class WarrantyRecord(TypedDict):
    product_id: str
    product_name: str
    purchase_date: str
    warranty_months: int
    warranty_type: str
    expires: str


WARRANTY_DB: dict[str, WarrantyRecord] = {
    "laptop-x1": {
        "product_id": "laptop-x1",
        "product_name": "Professional Laptop X1",
        "purchase_date": "2024-01-15",
        "warranty_months": 24,
        "warranty_type": "Standard",
        "expires": "2026-01-15",
    },
    "monitor-hd27": {
        "product_id": "monitor-hd27",
        "product_name": "27-inch HD Monitor",
        "purchase_date": "2024-06-01",
        "warranty_months": 12,
        "warranty_type": "Standard",
        "expires": "2025-06-01",
    },
    "keyboard-k95": {
        "product_id": "keyboard-k95",
        "product_name": "Mechanical Keyboard K95",
        "purchase_date": "2023-12-10",
        "warranty_months": 36,
        "warranty_type": "Extended",
        "expires": "2026-12-10",
    },
}


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:  # noqa: ARG001
    """
    Check warranty status and coverage for a product.

    This is a global MCP tool deployed to AgentCore Gateway.
    Available to all agents via Gateway Target.
    """
    payload: dict[str, Any] = event or {}

    # Log invocation for debugging
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(
        json.dumps(
            {
                "tool": "check_warranty",
                "request_id": request_id,
                "event_keys": list(payload.keys()),
                "has_body": "body" in payload,
                "event_type": type(payload).__name__,
            }
        )
    )

    try:
        # Parse input - handle both API Gateway and direct invocation formats
        raw_body = payload.get("body")
        if isinstance(raw_body, str):
            body: dict[str, Any] = json.loads(raw_body)
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            body = payload
        product_id = str(body.get("product_id", ""))
        user_id = str(body.get("user_id", "unknown"))

        logger.info(json.dumps({"action": "warranty_lookup", "product_id": product_id}))

        # Validate input
        if not product_id:
            return {"error": "product_id is required"}

        # Look up warranty
        warranty = WARRANTY_DB.get(product_id)

        if not warranty:
            return {
                "error": f"Warranty not found for product: {product_id}",
                "available_products": list(WARRANTY_DB.keys()),
            }

        # Calculate warranty status
        expires_date = datetime.strptime(warranty["expires"], "%Y-%m-%d")
        today = datetime.now()
        is_active = today < expires_date
        days_remaining = (expires_date - today).days if is_active else 0

        # Build response - return data directly for Gateway MCP
        result = {
            **warranty,
            "is_active": is_active,
            "days_remaining": days_remaining,
            "status": "active" if is_active else "expired",
            "checked_by": user_id,
            "checked_at": today.isoformat(),
        }

        logger.info(
            json.dumps(
                {"action": "success", "status": result["status"], "days_remaining": days_remaining}
            )
        )
        return result

    except Exception as e:
        logger.error(json.dumps({"action": "error", "error": str(e)}), exc_info=True)
        return {"error": str(e)}
