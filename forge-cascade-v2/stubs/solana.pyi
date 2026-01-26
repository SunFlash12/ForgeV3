"""Type stubs for solana-py library."""

from typing import Any, TypedDict

# RPC types
class RpcResult(TypedDict):
    context: dict[str, int]
    value: Any

class SendTransactionResp(TypedDict):
    result: str  # Transaction signature

class GetBalanceResp(TypedDict):
    context: dict[str, int]
    value: int

class GetTransactionResp(TypedDict):
    slot: int
    transaction: dict[str, Any]
    blockTime: int | None
    meta: dict[str, Any] | None

class GetSignatureStatusesResp(TypedDict):
    context: dict[str, int]
    value: list[dict[str, Any] | None]

# Transaction types
class Pubkey:
    """Solana public key."""

    def __init__(self, value: bytes | str) -> None: ...
    def __str__(self) -> str: ...
    def __bytes__(self) -> bytes: ...
    def to_json(self) -> str: ...

    @classmethod
    def from_string(cls, s: str) -> "Pubkey": ...

class Keypair:
    """Solana keypair for signing."""

    @property
    def pubkey(self) -> Pubkey: ...
    @property
    def secret(self) -> bytes: ...

    @classmethod
    def generate(cls) -> "Keypair": ...
    @classmethod
    def from_secret_key(cls, secret_key: bytes) -> "Keypair": ...
    @classmethod
    def from_seed(cls, seed: bytes) -> "Keypair": ...

    def sign(self, message: bytes) -> bytes: ...

class Instruction:
    """Solana instruction."""

    program_id: Pubkey
    accounts: list["AccountMeta"]
    data: bytes

    def __init__(
        self,
        program_id: Pubkey,
        accounts: list["AccountMeta"],
        data: bytes,
    ) -> None: ...

class AccountMeta:
    """Account metadata for instructions."""

    pubkey: Pubkey
    is_signer: bool
    is_writable: bool

    def __init__(self, pubkey: Pubkey, is_signer: bool, is_writable: bool) -> None: ...

class Transaction:
    """Solana transaction."""

    signatures: list[bytes]
    message: "Message"

    def __init__(
        self,
        recent_blockhash: str | None = None,
        fee_payer: Pubkey | None = None,
    ) -> None: ...

    def add(self, *instructions: Instruction) -> "Transaction": ...
    def sign(self, *signers: Keypair) -> None: ...
    def serialize(self) -> bytes: ...

    @classmethod
    def deserialize(cls, data: bytes) -> "Transaction": ...

class Message:
    """Transaction message."""

    @classmethod
    def new_with_blockhash(
        cls,
        instructions: list[Instruction],
        payer: Pubkey | None,
        blockhash: str,
    ) -> "Message": ...

# RPC client
class AsyncClient:
    """Async Solana RPC client."""

    def __init__(
        self,
        endpoint: str,
        commitment: str = "confirmed",
        timeout: float = 10.0,
    ) -> None: ...

    async def is_connected(self) -> bool: ...
    async def close(self) -> None: ...

    async def get_balance(self, pubkey: Pubkey) -> GetBalanceResp: ...
    async def get_latest_blockhash(self) -> RpcResult: ...
    async def get_transaction(
        self,
        tx_sig: str,
        encoding: str = "json",
        max_supported_transaction_version: int | None = None,
    ) -> GetTransactionResp | None: ...
    async def get_signature_statuses(
        self,
        signatures: list[str],
        search_transaction_history: bool = False,
    ) -> GetSignatureStatusesResp: ...
    async def send_transaction(
        self,
        txn: Transaction,
        *signers: Keypair,
        opts: dict[str, Any] | None = None,
    ) -> SendTransactionResp: ...
    async def send_raw_transaction(
        self,
        txn: bytes,
        opts: dict[str, Any] | None = None,
    ) -> SendTransactionResp: ...
    async def confirm_transaction(
        self,
        tx_sig: str,
        commitment: str = "confirmed",
        sleep_seconds: float = 0.5,
        last_valid_block_height: int | None = None,
    ) -> RpcResult: ...

# Submodule structure for imports
class rpc:
    class async_api:
        AsyncClient = AsyncClient

class transaction:
    Transaction = Transaction
    Instruction = Instruction
