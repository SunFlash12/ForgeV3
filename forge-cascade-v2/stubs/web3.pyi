"""Type stubs for web3 library."""

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

class TxParams(TypedDict, total=False):
    to: str
    from_: str
    value: int
    gas: int
    gasPrice: int
    maxFeePerGas: int
    maxPriorityFeePerGas: int
    data: bytes | str
    nonce: int
    chainId: int

class TxReceipt(TypedDict):
    transactionHash: bytes
    blockHash: bytes
    blockNumber: int
    gasUsed: int
    status: int
    contractAddress: str | None
    logs: list[dict[str, Any]]

class Wei(int):
    """Wei denomination."""

class Gwei(int):
    """Gwei denomination."""

class AsyncHTTPProvider:
    """Async HTTP provider for Web3."""

    def __init__(
        self,
        endpoint_uri: str,
        request_kwargs: dict[str, Any] | None = None,
    ) -> None: ...

class AsyncEth:
    """Async Ethereum API."""

    chain_id: int
    default_account: str | None

    async def get_balance(self, account: str, block_identifier: str | int = "latest") -> Wei: ...
    async def get_transaction_count(self, account: str, block_identifier: str | int = "latest") -> int: ...
    async def get_block(self, block_identifier: str | int) -> dict[str, Any]: ...
    async def get_transaction(self, tx_hash: str | bytes) -> dict[str, Any]: ...
    async def get_transaction_receipt(self, tx_hash: str | bytes) -> TxReceipt | None: ...
    async def send_raw_transaction(self, raw_tx: bytes) -> bytes: ...
    async def estimate_gas(self, tx: TxParams) -> int: ...
    async def call(self, tx: TxParams, block_identifier: str | int = "latest") -> bytes: ...
    async def get_gas_price(self) -> Wei: ...
    async def wait_for_transaction_receipt(
        self, tx_hash: bytes, timeout: float = 120, poll_latency: float = 0.1
    ) -> TxReceipt: ...

class AsyncContract:
    """Async contract interface."""

    address: str

    @property
    def functions(self) -> Any: ...
    @property
    def events(self) -> Any: ...

class AsyncWeb3:
    """Async Web3 interface."""

    eth: AsyncEth

    def __init__(self, provider: AsyncHTTPProvider) -> None: ...

    @staticmethod
    def to_checksum_address(address: str) -> str: ...
    @staticmethod
    def to_hex(value: bytes | int) -> str: ...
    @staticmethod
    def to_bytes(hexstr: str | None = None, primitive: int | None = None, text: str | None = None) -> bytes: ...
    @staticmethod
    def to_wei(value: int | float | str, denomination: str) -> Wei: ...
    @staticmethod
    def from_wei(value: int, denomination: str) -> float: ...
    @staticmethod
    def is_address(address: str) -> bool: ...
    @staticmethod
    def is_checksum_address(address: str) -> bool: ...
    @staticmethod
    def keccak(primitive: bytes | None = None, text: str | None = None, hexstr: str | None = None) -> bytes: ...

    async def is_connected(self) -> bool: ...

# Submodule: web3.exceptions
class Web3Exception(Exception):
    """Base Web3 exception."""

class TransactionNotFound(Web3Exception):
    """Transaction not found exception."""

class ContractLogicError(Web3Exception):
    """Contract logic error."""

class InvalidAddress(Web3Exception):
    """Invalid address exception."""

class BadFunctionCallOutput(Web3Exception):
    """Bad function call output."""
