import logging
import os

import jwt
from jwt import PyJWKClient

logger = logging.getLogger()

COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Ensure we have the necessary environment variables
if COGNITO_USER_POOL_ID:
    JWKS_URL = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    jwk_client = PyJWKClient(JWKS_URL)
else:
    logger.warning("COGNITO_USER_POOL_ID not set. Token validation will fail.")
    jwk_client = None


def validate_token(token):
    """
    Validates the JWT token from Cognito.
    Returns the decoded claims if valid, raises exception otherwise.
    """
    if not jwk_client:
        raise ValueError("Configuration error: COGNITO_USER_POOL_ID not set")

    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
        )
        return claims
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise
