"""Product information and documentation tools for warranty-docs agent.

These are agent-specific local tools (not shared via Gateway).
Focused on warranty use cases: product specs, documentation search.
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

from strands.tools import tool


class ProductRecord(TypedDict):
    product_id: str
    name: str
    category: str
    warranty_months: int
    specs: dict[str, Any]
    compatible_accessories: list[str]


class DocumentationEntry(TypedDict):
    doc_id: str
    title: str
    category: str
    excerpt: str
    relevance_score: float
    url: str


class ScoredDocumentationEntry(DocumentationEntry, total=False):
    computed_score: float


@tool
def get_product_info(product_id: str) -> ProductRecord | dict[str, Any]:
    """
    Retrieve detailed product information including warranty details.

    Args:
        product_id: Unique product identifier (e.g., 'laptop-x1', 'monitor-hd27')

    Returns:
        Product details including name, category, specs, warranty months

    Example:
        >>> get_product_info('laptop-x1')
        {
            'product_id': 'laptop-x1',
            'name': 'Professional Laptop X1',
            'category': 'Laptops',
            'warranty_months': 24,
            'specs': {'processor': 'Intel Core i7', ...}
        }
    """
    # Mock product database
    # In production, this would query a real database or API
    mock_products: dict[str, ProductRecord] = {
        "laptop-x1": {
            "product_id": "laptop-x1",
            "name": "Professional Laptop X1",
            "category": "Laptops",
            "warranty_months": 24,
            "specs": {
                "processor": "Intel Core i7-12700H",
                "ram": "16GB DDR5",
                "storage": "512GB NVMe SSD",
                "display": "14-inch FHD",
                "weight": "1.4kg",
            },
            "compatible_accessories": ["docking-station-pro", "travel-case-14"],
        },
        "monitor-hd27": {
            "product_id": "monitor-hd27",
            "name": "27-inch HD Monitor",
            "category": "Monitors",
            "warranty_months": 12,
            "specs": {
                "resolution": "2560x1440",
                "refresh_rate": "144Hz",
                "panel_type": "IPS",
                "response_time": "1ms",
                "ports": "HDMI 2.0, DisplayPort 1.4, USB-C",
            },
            "compatible_accessories": ["monitor-arm-dual", "hdmi-cable-2m"],
        },
        "keyboard-k95": {
            "product_id": "keyboard-k95",
            "name": "Mechanical Keyboard K95",
            "category": "Keyboards",
            "warranty_months": 24,
            "specs": {
                "switch_type": "Cherry MX Red",
                "backlighting": "RGB per-key",
                "connectivity": "USB-C wired",
                "macro_keys": 6,
            },
            "compatible_accessories": ["wrist-rest-pro", "usb-c-cable-braided"],
        },
    }

    product = mock_products.get(product_id)
    if not product:
        return {
            "error": f"Product '{product_id}' not found in catalog",
            "available_products": list(mock_products.keys()),
        }

    return product


@tool
def search_documentation(query: str, category: str | None = None, limit: int = 5) -> dict[str, Any]:
    """
    Search product documentation and knowledge base.

    Args:
        query: Search query string
        category: Optional category filter (warranty, setup, troubleshooting, maintenance)
        limit: Maximum number of results (default 5, max 10)

    Returns:
        Matching documentation articles with excerpts and URLs

    Example:
        >>> search_documentation('warranty claim', category='warranty')
        {
            'query': 'warranty claim',
            'category': 'warranty',
            'total_results': 2,
            'results': [
                {
                    'title': 'How to File a Warranty Claim',
                    'category': 'warranty',
                    'excerpt': '...',
                    'url': '/docs/warranty-claim-process'
                }
            ]
        }
    """
    # Mock documentation database
    # In production, this would query Knowledge Base via BedrockAgent retrieve API
    mock_docs: list[DocumentationEntry] = [
        {
            "doc_id": "doc-w001",
            "title": "Warranty Coverage Overview",
            "category": "warranty",
            "excerpt": "All products include manufacturer warranty covering defects in materials and workmanship. Laptops have 24-month coverage, monitors 12 months, keyboards 24 months. Extended warranties available for purchase.",
            "relevance_score": 0.95,
            "url": "/docs/warranty-overview",
        },
        {
            "doc_id": "doc-w002",
            "title": "How to File a Warranty Claim",
            "category": "warranty",
            "excerpt": "To file a warranty claim: 1) Have your serial number ready, 2) Check warranty status online, 3) Contact authorized service center, 4) Provide proof of purchase. Claims processed within 5 business days.",
            "relevance_score": 0.93,
            "url": "/docs/warranty-claim-process",
        },
        {
            "doc_id": "doc-w003",
            "title": "Find Authorized Service Centers",
            "category": "warranty",
            "excerpt": "Use our service locator to find authorized repair centers near you. Service centers can verify warranty status, perform repairs, and issue replacements under warranty coverage.",
            "relevance_score": 0.88,
            "url": "/docs/service-center-locator",
        },
        {
            "doc_id": "doc-s001",
            "title": "Laptop Initial Setup Guide",
            "category": "setup",
            "excerpt": "Step-by-step laptop setup: 1) Connect power adapter, 2) Press power button, 3) Select language and region, 4) Connect to WiFi, 5) Create user account. Setup takes approximately 15 minutes.",
            "relevance_score": 0.82,
            "url": "/docs/laptop-setup",
        },
        {
            "doc_id": "doc-t001",
            "title": "Laptop Won't Power On - Troubleshooting",
            "category": "troubleshooting",
            "excerpt": "If laptop won't power on: 1) Check power adapter connection, 2) Remove battery and reconnect, 3) Hold power button for 30 seconds to reset, 4) Test with different outlet. If issue persists, contact support.",
            "relevance_score": 0.75,
            "url": "/docs/laptop-power-troubleshooting",
        },
        {
            "doc_id": "doc-t002",
            "title": "Monitor Display Issues",
            "category": "troubleshooting",
            "excerpt": "Common monitor issues: No signal (check cable connections), Flickering (update graphics drivers), Color calibration (use OSD menu). Detailed troubleshooting steps included.",
            "relevance_score": 0.71,
            "url": "/docs/monitor-troubleshooting",
        },
        {
            "doc_id": "doc-t003",
            "title": "Keyboard Not Responding - Quick Fixes",
            "category": "troubleshooting",
            "excerpt": "Keyboard troubleshooting: 1) Check USB connection or wireless pairing, 2) Test on different port/device, 3) Clean debris from keys, 4) Update keyboard drivers. Try on-screen keyboard to isolate hardware vs software issues.",
            "relevance_score": 0.73,
            "url": "/docs/keyboard-troubleshooting",
        },
        {
            "doc_id": "doc-t004",
            "title": "WiFi Connectivity Problems",
            "category": "troubleshooting",
            "excerpt": "WiFi not working? Try: 1) Toggle WiFi off/on, 2) Restart router and device, 3) Forget network and reconnect, 4) Update network drivers, 5) Check for interference from other devices. Distance from router matters.",
            "relevance_score": 0.77,
            "url": "/docs/wifi-troubleshooting",
        },
        {
            "doc_id": "doc-t005",
            "title": "Slow Performance and Freezing",
            "category": "troubleshooting",
            "excerpt": "Device running slow? Common causes: Low disk space, too many startup programs, insufficient RAM, malware, outdated drivers. Solutions: Free up storage, disable unnecessary startups, add RAM, run antivirus scan, update drivers.",
            "relevance_score": 0.79,
            "url": "/docs/performance-troubleshooting",
        },
        {
            "doc_id": "doc-t006",
            "title": "Battery Draining Quickly",
            "category": "troubleshooting",
            "excerpt": "Battery issues: Check battery health in system settings, reduce screen brightness, close background apps, disable Bluetooth/WiFi when not needed, check for power-hungry processes. Battery replacement may be needed after 2-3 years.",
            "relevance_score": 0.74,
            "url": "/docs/battery-troubleshooting",
        },
        {
            "doc_id": "doc-m001",
            "title": "Laptop Maintenance Best Practices",
            "category": "maintenance",
            "excerpt": "Keep your laptop running smoothly: Clean vents monthly, update software regularly, use surge protector, avoid extreme temperatures. Battery calibration recommended every 3 months.",
            "relevance_score": 0.68,
            "url": "/docs/laptop-maintenance",
        },
    ]

    # Validate limit
    limit = max(1, min(limit, 10))

    # Enhanced keyword matching with scoring
    # In production: semantic search with embeddings via BedrockAgent Knowledge Base
    query_lower = query.lower()
    query_tokens = set(query_lower.split())

    scored_docs: list[ScoredDocumentationEntry] = []
    for doc in mock_docs:
        # Start with base relevance score
        score = float(doc["relevance_score"])

        # Boost score for keyword matches
        title_lower = doc["title"].lower()
        excerpt_lower = doc["excerpt"].lower()

        # Title match boost (stronger signal)
        if query_lower in title_lower:
            score += 0.15

        # Excerpt match boost
        if query_lower in excerpt_lower:
            score += 0.10

        # Token overlap boost (catch partial matches)
        title_tokens = set(title_lower.split())
        excerpt_tokens = set(excerpt_lower.split())
        overlap = len(query_tokens & (title_tokens | excerpt_tokens))
        if overlap > 0:
            score += 0.05 * overlap

        # Category match boost (if filtering by category)
        if category and doc["category"] == category:
            score += 0.10

        # Only include docs with some relevance
        if (
            query_lower in title_lower or query_lower in excerpt_lower or overlap > 0 or not query
        ):  # Include all if no query (just filtering by category)
            scored_docs.append({**doc, "computed_score": min(score, 1.0)})

    # Apply category filter if specified
    if category:
        scored_docs = [doc for doc in scored_docs if doc["category"] == category]

    # Sort by computed score (descending) and limit
    filtered_docs = sorted(
        scored_docs,
        key=lambda x: x["computed_score"],
        reverse=True,
    )[:limit]

    # Remove computed_score from output (keep original relevance_score)
    for doc in filtered_docs:
        doc.pop("computed_score", None)

    return {
        "query": query,
        "category": category,
        "total_results": len(filtered_docs),
        "results": filtered_docs,
    }


@tool
def list_compatible_accessories(product_id: str) -> dict[str, Any]:
    """
    List compatible accessories for a given product.

    Args:
        product_id: Unique product identifier

    Returns:
        List of compatible accessory IDs and names

    Example:
        >>> list_compatible_accessories('laptop-x1')
        {
            'product_id': 'laptop-x1',
            'compatible_accessories': [
                {'id': 'docking-station-pro', 'name': 'USB-C Docking Station Pro'},
                {'id': 'travel-case-14', 'name': '14-inch Travel Case'}
            ]
        }
    """
    # Mock accessory catalog
    accessory_catalog: dict[str, dict[str, str]] = {
        "docking-station-pro": {"id": "docking-station-pro", "name": "USB-C Docking Station Pro"},
        "travel-case-14": {"id": "travel-case-14", "name": "14-inch Protective Travel Case"},
        "monitor-arm-dual": {"id": "monitor-arm-dual", "name": "Dual Monitor Desk Arm"},
        "hdmi-cable-2m": {"id": "hdmi-cable-2m", "name": "HDMI 2.0 Cable (2 meters)"},
        "wrist-rest-pro": {"id": "wrist-rest-pro", "name": "Ergonomic Wrist Rest"},
        "usb-c-cable-braided": {"id": "usb-c-cable-braided", "name": "Braided USB-C Cable"},
    }

    # Get product info to find compatible accessories
    product_info = get_product_info(product_id)
    if isinstance(product_info, dict) and "error" in product_info:
        return cast(dict[str, Any], product_info)

    typed_product = cast(ProductRecord, product_info)

    # Get accessory IDs from product
    accessory_ids: list[str] = typed_product.get("compatible_accessories", [])
    accessories = [
        accessory_catalog[acc_id] for acc_id in accessory_ids if acc_id in accessory_catalog
    ]

    return {
        "product_id": product_id,
        "product_name": typed_product.get("name"),
        "compatible_accessories": accessories,
        "total_count": len(accessories),
    }
