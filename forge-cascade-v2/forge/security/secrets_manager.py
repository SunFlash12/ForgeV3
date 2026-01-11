"""
Secrets Manager - Secure secrets management abstraction.

This module provides a unified interface for retrieving secrets from various
backends (environment variables, HashiCorp Vault, AWS Secrets Manager, etc.).

SECURITY NOTE: In production, always use a proper secrets manager like Vault
or cloud-native solutions. Environment variables should only be used in development.

Usage:
    secrets = get_secrets_manager()
    jwt_secret = await secrets.get_secret("jwt_secret_key")
    private_key = await secrets.get_secret("operator_private_key")
"""

import abc
import asyncio
import logging
import os
import warnings
from datetime import UTC, datetime
from enum import Enum
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


class SecretsBackend(str, Enum):
    """Supported secrets management backends."""

    ENVIRONMENT = "environment"  # Development only - NOT for production
    VAULT = "vault"  # HashiCorp Vault
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_SECRET_MANAGER = "gcp_secret_manager"


class SecretNotFoundError(Exception):
    """Raised when a secret cannot be found."""

    pass


class SecretsBackendError(Exception):
    """Raised when the secrets backend encounters an error."""

    pass


class SecurityWarning(UserWarning):
    """Warning for security-related issues (insecure configurations, etc.)."""

    pass


class BaseSecretsManager(abc.ABC):
    """Abstract base class for secrets managers."""

    @abc.abstractmethod
    async def get_secret(self, key: str) -> str:
        """
        Retrieve a secret by key.

        Args:
            key: The secret identifier

        Returns:
            The secret value

        Raises:
            SecretNotFoundError: If the secret doesn't exist
            SecretsBackendError: If there's an error accessing the backend
        """
        pass

    @abc.abstractmethod
    async def get_secret_with_metadata(self, key: str) -> dict[str, Any]:
        """
        Retrieve a secret with metadata (version, created_at, etc.).

        Args:
            key: The secret identifier

        Returns:
            Dict with 'value' and metadata fields
        """
        pass

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check if the secrets backend is healthy and accessible."""
        pass


class EnvironmentSecretsManager(BaseSecretsManager):
    """
    Environment variable-based secrets manager.

    WARNING: This should ONLY be used in development environments.
    In production, use Vault, AWS Secrets Manager, or similar.
    """

    # Mapping of logical secret names to environment variable names
    SECRET_ENV_MAPPING = {
        # JWT and Auth
        "jwt_secret_key": ["JWT_SECRET_KEY", "FORGE_JWT_SECRET"],
        "compliance_jwt_secret": ["COMPLIANCE_JWT_SECRET", "JWT_SECRET_KEY"],
        # Database
        "neo4j_password": ["NEO4J_PASSWORD", "NEO4J_AUTH"],
        "redis_password": ["REDIS_PASSWORD"],
        # Blockchain
        "operator_private_key": ["VIRTUALS_OPERATOR_PRIVATE_KEY", "OPERATOR_PRIVATE_KEY"],
        "solana_private_key": ["VIRTUALS_SOLANA_PRIVATE_KEY", "SOLANA_PRIVATE_KEY"],
        # API Keys
        "llm_api_key": ["LLM_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"],
        "embedding_api_key": ["EMBEDDING_API_KEY", "OPENAI_API_KEY"],
        "virtuals_api_key": ["VIRTUALS_API_KEY"],
    }

    def __init__(self, environment: str = "development"):
        self._environment = environment
        self._warned_keys: set[str] = set()

        if environment == "production":
            logger.critical(
                "SECURITY WARNING: EnvironmentSecretsManager should NOT be used in production! "
                "Configure a proper secrets backend (Vault, AWS Secrets Manager, etc.)"
            )
            warnings.warn(
                "Using environment variables for secrets in production is insecure!",
                SecurityWarning,
                stacklevel=2,
            )

    async def get_secret(self, key: str) -> str:
        """Get secret from environment variable."""
        env_vars = self.SECRET_ENV_MAPPING.get(key, [key.upper()])

        for env_var in env_vars:
            value = os.environ.get(env_var)
            if value:
                # Log warning only once per key in non-development
                if self._environment != "development" and key not in self._warned_keys:
                    logger.warning(
                        f"Secret '{key}' loaded from environment variable. "
                        "Consider using a secure secrets manager in production."
                    )
                    self._warned_keys.add(key)
                return value

        raise SecretNotFoundError(
            f"Secret '{key}' not found. Set one of: {env_vars}"
        )

    async def get_secret_with_metadata(self, key: str) -> dict[str, Any]:
        """Get secret with basic metadata."""
        value = await self.get_secret(key)
        return {
            "value": value,
            "backend": "environment",
            "version": "N/A",
            "retrieved_at": datetime.now(UTC).isoformat(),
        }

    async def health_check(self) -> bool:
        """Environment variables are always 'healthy'."""
        return True


class VaultSecretsManager(BaseSecretsManager):
    """
    HashiCorp Vault secrets manager.

    Requires:
        - hvac package: pip install hvac
        - VAULT_ADDR environment variable
        - VAULT_TOKEN or VAULT_ROLE_ID/VAULT_SECRET_ID for AppRole auth
    """

    def __init__(
        self,
        vault_addr: str | None = None,
        vault_token: str | None = None,
        vault_namespace: str | None = None,
        secrets_path: str = "secret/data/forge",
    ):
        self._vault_addr = vault_addr or os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        self._vault_token = vault_token or os.environ.get("VAULT_TOKEN")
        self._vault_namespace = vault_namespace or os.environ.get("VAULT_NAMESPACE")
        self._secrets_path = secrets_path
        self._client = None

    def _get_client(self):
        """Lazily initialize Vault client."""
        if self._client is None:
            try:
                import hvac
            except ImportError:
                raise SecretsBackendError(
                    "hvac package required for Vault integration. Install with: pip install hvac"
                )

            self._client = hvac.Client(
                url=self._vault_addr,
                token=self._vault_token,
                namespace=self._vault_namespace,
            )

            # Try AppRole auth if token not provided
            if not self._vault_token:
                role_id = os.environ.get("VAULT_ROLE_ID")
                secret_id = os.environ.get("VAULT_SECRET_ID")
                if role_id and secret_id:
                    self._client.auth.approle.login(
                        role_id=role_id,
                        secret_id=secret_id,
                    )

        return self._client

    async def get_secret(self, key: str) -> str:
        """Get secret from Vault KV store."""
        try:
            client = self._get_client()
            # Read from KV v2 secrets engine
            secret = await asyncio.to_thread(
                client.secrets.kv.v2.read_secret_version,
                path=f"{self._secrets_path}/{key}",
                raise_on_deleted_version=True,
            )
            return secret["data"]["data"]["value"]
        except Exception as e:
            if "404" in str(e) or "secret not found" in str(e).lower():
                raise SecretNotFoundError(f"Secret '{key}' not found in Vault")
            raise SecretsBackendError(f"Vault error: {e}")

    async def get_secret_with_metadata(self, key: str) -> dict[str, Any]:
        """Get secret with Vault metadata."""
        try:
            client = self._get_client()
            secret = await asyncio.to_thread(
                client.secrets.kv.v2.read_secret_version,
                path=f"{self._secrets_path}/{key}",
                raise_on_deleted_version=True,
            )
            return {
                "value": secret["data"]["data"]["value"],
                "backend": "vault",
                "version": secret["data"]["metadata"]["version"],
                "created_time": secret["data"]["metadata"]["created_time"],
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            if "404" in str(e) or "secret not found" in str(e).lower():
                raise SecretNotFoundError(f"Secret '{key}' not found in Vault")
            raise SecretsBackendError(f"Vault error: {e}")

    async def health_check(self) -> bool:
        """Check Vault connectivity and authentication."""
        try:
            client = self._get_client()
            return await asyncio.to_thread(client.is_authenticated)
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return False


class AWSSecretsManager(BaseSecretsManager):
    """
    AWS Secrets Manager integration.

    Requires:
        - boto3 package: pip install boto3
        - AWS credentials configured (IAM role, env vars, or ~/.aws/credentials)
    """

    def __init__(self, region_name: str | None = None, secret_prefix: str = "forge/"):
        self._region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self._secret_prefix = secret_prefix
        self._client = None

    def _get_client(self):
        """Lazily initialize AWS client."""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise SecretsBackendError(
                    "boto3 package required for AWS Secrets Manager. Install with: pip install boto3"
                )
            self._client = boto3.client("secretsmanager", region_name=self._region_name)
        return self._client

    async def get_secret(self, key: str) -> str:
        """Get secret from AWS Secrets Manager."""
        try:
            client = self._get_client()
            secret_name = f"{self._secret_prefix}{key}"
            response = await asyncio.to_thread(
                client.get_secret_value,
                SecretId=secret_name,
            )
            return response["SecretString"]
        except Exception as e:
            if "ResourceNotFoundException" in str(type(e).__name__):
                raise SecretNotFoundError(f"Secret '{key}' not found in AWS Secrets Manager")
            raise SecretsBackendError(f"AWS Secrets Manager error: {e}")

    async def get_secret_with_metadata(self, key: str) -> dict[str, Any]:
        """Get secret with AWS metadata."""
        try:
            client = self._get_client()
            secret_name = f"{self._secret_prefix}{key}"
            response = await asyncio.to_thread(
                client.get_secret_value,
                SecretId=secret_name,
            )
            return {
                "value": response["SecretString"],
                "backend": "aws_secrets_manager",
                "version": response.get("VersionId", "N/A"),
                "arn": response["ARN"],
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            if "ResourceNotFoundException" in str(type(e).__name__):
                raise SecretNotFoundError(f"Secret '{key}' not found in AWS Secrets Manager")
            raise SecretsBackendError(f"AWS Secrets Manager error: {e}")

    async def health_check(self) -> bool:
        """Check AWS Secrets Manager accessibility."""
        try:
            client = self._get_client()
            # List secrets to verify connectivity (limited to 1)
            await asyncio.to_thread(client.list_secrets, MaxResults=1)
            return True
        except Exception as e:
            logger.error(f"AWS Secrets Manager health check failed: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Factory and Global Access
# ═══════════════════════════════════════════════════════════════════════════════

_secrets_manager: BaseSecretsManager | None = None


def _detect_backend() -> SecretsBackend:
    """Auto-detect which secrets backend to use based on environment."""
    # Check for explicit configuration
    backend_env = os.environ.get("SECRETS_BACKEND", "").lower()
    if backend_env:
        try:
            return SecretsBackend(backend_env)
        except ValueError:
            logger.warning(f"Invalid SECRETS_BACKEND: {backend_env}, using auto-detection")

    # Auto-detect based on available credentials
    if os.environ.get("VAULT_ADDR") and (
        os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_ROLE_ID")
    ):
        return SecretsBackend.VAULT

    if os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("AWS_ROLE_ARN"):
        return SecretsBackend.AWS_SECRETS_MANAGER

    if os.environ.get("AZURE_KEY_VAULT_URL"):
        return SecretsBackend.AZURE_KEY_VAULT

    if os.environ.get("GCP_PROJECT_ID") and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return SecretsBackend.GCP_SECRET_MANAGER

    # Default to environment variables
    return SecretsBackend.ENVIRONMENT


def create_secrets_manager(
    backend: SecretsBackend | None = None,
    **kwargs,
) -> BaseSecretsManager:
    """
    Create a secrets manager instance.

    Args:
        backend: Which backend to use (auto-detected if not specified)
        **kwargs: Backend-specific configuration

    Returns:
        Configured secrets manager instance
    """
    if backend is None:
        backend = _detect_backend()

    environment = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development"))

    logger.info(f"Initializing secrets manager with backend: {backend.value}")

    if backend == SecretsBackend.ENVIRONMENT:
        return EnvironmentSecretsManager(environment=environment)

    elif backend == SecretsBackend.VAULT:
        return VaultSecretsManager(
            vault_addr=kwargs.get("vault_addr"),
            vault_token=kwargs.get("vault_token"),
            vault_namespace=kwargs.get("vault_namespace"),
            secrets_path=kwargs.get("secrets_path", "secret/data/forge"),
        )

    elif backend == SecretsBackend.AWS_SECRETS_MANAGER:
        return AWSSecretsManager(
            region_name=kwargs.get("region_name"),
            secret_prefix=kwargs.get("secret_prefix", "forge/"),
        )

    elif backend == SecretsBackend.AZURE_KEY_VAULT:
        raise NotImplementedError("Azure Key Vault support coming soon")

    elif backend == SecretsBackend.GCP_SECRET_MANAGER:
        raise NotImplementedError("GCP Secret Manager support coming soon")

    else:
        raise ValueError(f"Unknown secrets backend: {backend}")


@lru_cache
def get_secrets_manager() -> BaseSecretsManager:
    """
    Get the global secrets manager instance.

    Uses lazy initialization with auto-detection of the appropriate backend.
    """
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = create_secrets_manager()
    return _secrets_manager


def configure_secrets_manager(manager: BaseSecretsManager) -> None:
    """
    Configure a custom secrets manager instance.

    Useful for testing or when configuration needs to be loaded
    from a non-standard source.
    """
    global _secrets_manager
    _secrets_manager = manager
    get_secrets_manager.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════


async def get_secret(key: str, default: str | None = None) -> str | None:
    """
    Convenience function to get a secret.

    Args:
        key: Secret identifier
        default: Default value if secret not found

    Returns:
        Secret value or default
    """
    try:
        manager = get_secrets_manager()
        return await manager.get_secret(key)
    except SecretNotFoundError:
        if default is not None:
            return default
        raise


async def get_required_secret(key: str) -> str:
    """
    Get a required secret (raises if not found).

    Args:
        key: Secret identifier

    Returns:
        Secret value

    Raises:
        SecretNotFoundError: If secret doesn't exist
    """
    manager = get_secrets_manager()
    return await manager.get_secret(key)
