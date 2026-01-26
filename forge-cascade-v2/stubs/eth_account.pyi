"""Type stubs for eth_account library."""

from typing import TypedDict

class SignedMessage(TypedDict):
    messageHash: bytes
    r: int
    s: int
    v: int
    signature: bytes

class SignedTransaction(TypedDict):
    rawTransaction: bytes
    hash: bytes
    r: int
    s: int
    v: int

class SignableMessage:
    """A message that can be signed."""
    version: bytes
    header: bytes
    body: bytes

class Account:
    """Ethereum account for signing."""

    address: str
    key: bytes

    @classmethod
    def create(cls, extra_entropy: str = "") -> "Account": ...

    @classmethod
    def from_key(cls, private_key: str | bytes) -> "Account": ...

    @classmethod
    def recover_message(
        cls,
        signable_message: SignableMessage,
        signature: bytes | str,
    ) -> str: ...

    def sign_message(self, signable_message: SignableMessage) -> SignedMessage: ...

    def sign_transaction(
        self,
        transaction_dict: dict[str, int | str | bytes],
        blobs: list[bytes] | None = None,
    ) -> SignedTransaction: ...

# Submodule: eth_account.signers.local
class LocalAccount(Account):
    """Local account signer."""

# Submodule: eth_account.messages
def encode_defunct(
    primitive: bytes | None = None,
    hexstr: str | None = None,
    text: str | None = None,
) -> SignableMessage: ...

def encode_typed_data(
    domain_data: dict[str, str | int] | None = None,
    message_types: dict[str, list[dict[str, str]]] | None = None,
    message_data: dict[str, str | int | list[str] | dict[str, str]] | None = None,
    full_message: dict[str, dict[str, str | int | list[dict[str, str]] | dict[str, str | int]]] | None = None,
) -> SignableMessage: ...
