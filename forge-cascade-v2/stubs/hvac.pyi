"""Type stubs for hvac (HashiCorp Vault) library."""

from typing import Any, TypedDict

class SecretData(TypedDict, total=False):
    data: dict[str, str]
    metadata: dict[str, Any]

class SecretResponse(TypedDict):
    request_id: str
    lease_id: str
    renewable: bool
    lease_duration: int
    data: SecretData
    wrap_info: dict[str, str] | None
    warnings: list[str] | None
    auth: dict[str, Any] | None

class KVv2Methods:
    """KV v2 secrets engine methods."""

    def read_secret_version(
        self,
        path: str,
        version: int | None = None,
        mount_point: str = "secret",
        raise_on_deleted_version: bool = True,
    ) -> SecretResponse: ...

    def create_or_update_secret(
        self,
        path: str,
        secret: dict[str, str],
        cas: int | None = None,
        mount_point: str = "secret",
    ) -> SecretResponse: ...

    def delete_latest_version_of_secret(
        self,
        path: str,
        mount_point: str = "secret",
    ) -> None: ...

    def delete_secret_versions(
        self,
        path: str,
        versions: list[int],
        mount_point: str = "secret",
    ) -> None: ...

    def undelete_secret_versions(
        self,
        path: str,
        versions: list[int],
        mount_point: str = "secret",
    ) -> None: ...

    def destroy_secret_versions(
        self,
        path: str,
        versions: list[int],
        mount_point: str = "secret",
    ) -> None: ...

    def list_secrets(
        self,
        path: str,
        mount_point: str = "secret",
    ) -> dict[str, list[str]]: ...

class KVv2:
    """KV v2 secrets engine with v2 property for compatibility."""
    v2: KVv2Methods

class Secrets:
    """Secrets engines."""
    kv: KVv2

class AppRole:
    """AppRole authentication method."""
    def login(
        self,
        role_id: str,
        secret_id: str | None = None,
        use_token: bool = True,
        mount_point: str = "approle",
    ) -> dict[str, Any]: ...

class AuthMethods:
    """Authentication methods."""
    approle: AppRole

    def token(self) -> dict[str, Any]: ...

class Client:
    """HashiCorp Vault client."""

    secrets: Secrets
    auth: AuthMethods

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        cert: tuple[str, str] | None = None,
        verify: bool | str = True,
        timeout: int = 30,
        proxies: dict[str, str] | None = None,
        allow_redirects: bool = True,
        session: Any | None = None,
        adapter: Any = None,
        namespace: str | None = None,
        strict_http: bool = False,
    ) -> None: ...

    @property
    def is_authenticated(self) -> bool: ...

    def read(self, path: str, wrap_ttl: str | None = None) -> dict[str, Any] | None: ...
    def write(self, path: str, wrap_ttl: str | None = None, **kwargs: Any) -> dict[str, Any]: ...
    def delete(self, path: str) -> dict[str, Any]: ...
    def list(self, path: str) -> dict[str, Any] | None: ...

    def lookup_token(self, token: str | None = None) -> dict[str, Any]: ...
    def revoke_token(self, token: str, orphan: bool = False, accessor: bool = False) -> None: ...
