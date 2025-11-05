"""REST API handlers for authorization endpoints."""

from __future__ import annotations

import logging
from typing import Any

from agentcore_governance import authorization, classification, evidence

logger = logging.getLogger(__name__)


def get_agent_tools(agent_id: str) -> dict[str, Any]:
    """Handle GET /authorization/agents/{agentId}/tools request.

    Args:
        agent_id: Agent identifier

    Returns:
        Response with authorized tools list
    """
    try:
        tools = authorization.get_authorized_tools(agent_id)

        return {
            "agent_id": agent_id,
            "authorized_tools": tools,
            "total_count": len(tools),
        }

    except Exception as e:
        logger.error(f"Error fetching authorized tools for {agent_id}: {e}", exc_info=True)
        return {
            "error": str(e),
            "agent_id": agent_id,
            "authorized_tools": [],
            "total_count": 0,
        }


def update_agent_tools(
    agent_id: str,
    tools: list[str],
    reason: str | None = None,
    validate_classification: bool = True,
    approval_records: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Handle PUT /authorization/agents/{agentId}/tools request.

    Args:
        agent_id: Agent identifier
        tools: List of tool IDs to authorize
        reason: Optional justification for the change
        validate_classification: Whether to enforce classification rules
        approval_records: Optional dict of tool_id -> approval_record for SENSITIVE tools

    Returns:
        Response with update status and differential report
    """
    try:
        validation_errors = []
        approval_records = approval_records or {}

        # Validate tool classifications if requested
        if validate_classification:
            registry = classification.load_tool_classifications()

            for tool_id in tools:
                is_valid, validation_reason = classification.validate_tool_authorization(
                    tool_id=tool_id,
                    approval_record=approval_records.get(tool_id),
                    registry=registry,
                )

                if not is_valid:
                    validation_errors.append({
                        "tool_id": tool_id,
                        "reason": validation_reason,
                    })

        # If there are validation errors, return them without updating
        if validation_errors:
            return {
                "success": False,
                "agent_id": agent_id,
                "validation_errors": validation_errors,
                "message": "Authorization update failed due to classification violations",
            }

        # Update authorization mapping
        diff_report = authorization.set_authorized_tools(
            agent_id=agent_id,
            tools=tools,
            reason=reason,
        )

        # Log authorization change events
        audit_events = []
        correlation_id = f"auth-update-{agent_id}-{diff_report['timestamp']}"

        for tool_id in diff_report["added"]:
            event = evidence.construct_authorization_decision_event(
                agent_id=agent_id,
                tool_id=tool_id,
                effect="allow",
                reason=f"Tool added to authorized list. {reason or ''}".strip(),
                correlation_id=correlation_id,
            )
            audit_events.append(event)

        for tool_id in diff_report["removed"]:
            event = evidence.construct_authorization_decision_event(
                agent_id=agent_id,
                tool_id=tool_id,
                effect="deny",
                reason=f"Tool removed from authorized list. {reason or ''}".strip(),
                correlation_id=correlation_id,
            )
            audit_events.append(event)

        return {
            "success": True,
            "agent_id": agent_id,
            "authorized_tools": tools,
            "total_count": len(tools),
            "changes": {
                "added": diff_report["added"],
                "removed": diff_report["removed"],
                "unchanged": diff_report["unchanged"],
            },
            "audit_events": audit_events,
            "message": f"Authorization updated: +{len(diff_report['added'])} -{len(diff_report['removed'])}",
        }

    except Exception as e:
        logger.error(f"Error updating authorized tools for {agent_id}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "agent_id": agent_id,
            "message": "Authorization update failed",
        }


def check_tool_access(
    agent_id: str,
    tool_id: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Check if an agent is authorized to access a specific tool.

    Args:
        agent_id: Agent identifier
        tool_id: Tool identifier
        correlation_id: Optional correlation ID for tracing

    Returns:
        Authorization decision with effect and reason
    """
    try:
        is_authorized = authorization.check_tool_authorized(agent_id, tool_id)

        if is_authorized:
            effect = "allow"
            reason = f"Tool '{tool_id}' is in authorized list for agent '{agent_id}'"
        else:
            effect = "deny"
            reason = f"Tool '{tool_id}' is NOT in authorized list for agent '{agent_id}'"

        # Get tool classification
        tool = classification.get_tool_classification(tool_id)
        tool_classification = tool.get("classification") if tool else None

        # Log authorization decision
        event = evidence.construct_authorization_decision_event(
            agent_id=agent_id,
            tool_id=tool_id,
            effect=effect,
            reason=reason,
            correlation_id=correlation_id,
            classification=tool_classification,
        )

        return {
            "agent_id": agent_id,
            "tool_id": tool_id,
            "effect": effect,
            "authorized": is_authorized,
            "reason": reason,
            "classification": tool_classification,
            "audit_event": event,
        }

    except Exception as e:
        logger.error(f"Error checking tool access for {agent_id}/{tool_id}: {e}", exc_info=True)
        return {
            "agent_id": agent_id,
            "tool_id": tool_id,
            "effect": "deny",
            "authorized": False,
            "reason": f"Authorization check failed: {str(e)}",
            "error": str(e),
        }
