import base64
import json
import logging
from functools import lru_cache

import boto3
from auth import validate_token

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients outside handler for reuse
try:
    control_client = boto3.client("bedrock-agentcore-control")
    runtime_client = boto3.client("bedrock-agentcore")
except Exception as e:
    logger.warning(f"Failed to initialize boto3 clients: {e}")
    control_client = None
    runtime_client = None


def normalize(name):
    """Normalize agent name for canonical matching (ignore case and separators)."""
    return name.replace("_", "").replace("-", "").lower()


def error_response(code, error, message):
    return {
        "statusCode": code,
        "body": json.dumps({"error": error, "message": message}),
        "headers": {"Content-Type": "application/json"},
    }


@lru_cache(maxsize=128)
def resolve_agent_arn(agent_id):
    """Resolve agent ID to ARN. Results are cached to avoid repeated API calls."""
    if not control_client:
        return None

    try:
        response = control_client.list_agent_runtimes()
        for agent in response.get("agentRuntimes", []):
            name = agent.get("agentRuntimeName")
            if name == agent_id:
                return agent.get("agentRuntimeArn")
            # Canonical matching (ignore case and separators)
            if normalize(name) == normalize(agent_id):
                return agent.get("agentRuntimeArn")
    except Exception as e:
        logger.error(f"Failed to resolve agent ARN: {e}")


def list_agents(allowed_agents):
    if not control_client:
        return error_response(500, "Configuration Error", "Control client not initialized")

    try:
        response = control_client.list_agent_runtimes()
        all_agents = response.get("agentRuntimes", [])

        # Normalize allowed agents for canonical matching
        normalized_allowed = {normalize(a): a for a in allowed_agents if a != "*"}
        allow_all = "*" in allowed_agents

        filtered_agents = []
        for agent in all_agents:
            agent_name = agent.get("agentRuntimeName")
            # Check if agent is allowed (exact or canonical match)
            if (
                allow_all
                or agent_name in allowed_agents
                or normalize(agent_name) in normalized_allowed
            ):
                filtered_agents.append(
                    {"id": agent_name, "name": agent_name, "description": f"Agent {agent_name}"}
                )

        return {
            "statusCode": 200,
            "body": json.dumps({"agents": filtered_agents}),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return error_response(500, "Internal Server Error", str(e))


def invoke_agent(agent_id, body, user_id):
    if not runtime_client:
        return error_response(500, "Configuration Error", "Runtime client not initialized")

    try:
        if isinstance(body, str):
            body = json.loads(body)

        message = body.get("message")
        client_session_id = body.get("sessionId")

        if not message or not client_session_id:
            return error_response(400, "Bad Request", "Missing message or sessionId")

        logger.info(f"Invoking agent {agent_id} for user {user_id} session {client_session_id}")

        arn = resolve_agent_arn(agent_id)
        if not arn:
            return error_response(404, "Not Found", f"Agent {agent_id} not found")

        payload = json.dumps({"prompt": message}).encode("utf-8")

        response = runtime_client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeUserId=user_id,
            runtimeSessionId=client_session_id,
            contentType="application/json",
            accept="application/json",
            payload=payload,
        )

        # Read response
        response_body = response.get("response")
        output = ""
        if response_body:
            output = response_body.read().decode("utf-8")
            if output.startswith('"') and output.endswith('"'):
                output = output[1:-1]

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"output": output, "sessionId": client_session_id, "userId": user_id}
            ),
            "headers": {"Content-Type": "application/json"},
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {e}")
        return error_response(400, "Bad Request", "Invalid JSON in request body")
    except runtime_client.exceptions.ClientError as e:
        logger.error(f"AWS client error during invocation: {e}")
        return error_response(502, "Bad Gateway", "Failed to invoke agent")
    except Exception as e:
        logger.error(f"Unexpected error during invocation: {e}")
        return error_response(502, "Bad Gateway", "Internal server error")


def lambda_handler(event, context):  # noqa: ARG001
    """
    Frontend Gateway Lambda Handler.
    Routes requests to appropriate handlers based on path and method.
    """
    logger.info("Received event: %s", json.dumps(event))

    path = event.get("rawPath")
    method = event.get("requestContext", {}).get("http", {}).get("method")
    headers = event.get("headers", {})

    # Auth Validation
    auth_header = headers.get("authorization") or headers.get("Authorization")
    if not auth_header:
        return error_response(401, "Unauthorized", "Missing Authorization header")

    # Validate Authorization header format
    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.error(f"Malformed Authorization header: {auth_header}")
        return error_response(
            401, "Unauthorized", "Malformed Authorization header. Expected format: 'Bearer <token>'"
        )

    try:
        token = parts[1]
        claims = validate_token(token)
    except Exception as e:
        logger.error(f"Auth failed: {e}")
        return error_response(401, "Unauthorized", "Invalid token")

    user_id = claims.get("sub")
    allowed_agents_raw = claims.get("custom:allowed_agents", claims.get("allowedAgents", []))

    allowed_agents = []
    if isinstance(allowed_agents_raw, list):
        allowed_agents = allowed_agents_raw
    elif isinstance(allowed_agents_raw, str):
        try:
            allowed_agents = json.loads(allowed_agents_raw)
            if not isinstance(allowed_agents, list):
                allowed_agents = [str(allowed_agents)]
        except Exception as e:  # noqa: S110
            logger.warning(
                f"Failed to parse allowed_agents_raw as JSON: {allowed_agents_raw!r}. "
                f"Exception: {e}. Falling back to comma-separated parsing."
            )
            allowed_agents = [s.strip() for s in allowed_agents_raw.split(",")]

    logger.info(f"User {user_id} authorized. Allowed agents: {allowed_agents}")

    # Route: GET /agents
    if path == "/agents" and method == "GET":
        return list_agents(allowed_agents)

    # Route: POST /agents/{agentId}/invoke
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "agents" and parts[2] == "invoke" and method == "POST":
        agent_id = parts[1]

        # Normalize for canonical matching
        normalized_allowed = {normalize(a) for a in allowed_agents if a != "*"}
        allow_all = "*" in allowed_agents

        # Check authorization (exact or canonical match)
        if not (
            allow_all or agent_id in allowed_agents or normalize(agent_id) in normalized_allowed
        ):
            return error_response(403, "Forbidden", f"Access to agent {agent_id} denied")

        body = event.get("body", "{}")
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body).decode("utf-8")

        return invoke_agent(agent_id, body, user_id)

    return error_response(404, "Not Found", f"No handler for {method} {path}")
