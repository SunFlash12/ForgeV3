// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title SimpleEscrow
 * @notice ETH-based escrow for ACP (Agent Communication Protocol) job lifecycle.
 *         Buyer locks ETH when creating an escrow. The buyer can release funds
 *         to the provider upon job completion, or the provider/buyer can trigger
 *         a refund if the job is rejected or the deadline passes.
 * @dev Deployed to Base Sepolia for testnet lifecycle validation.
 */
contract SimpleEscrow is ReentrancyGuard {
    // ═══════════════════════════════════════════════════════════════════════
    // Types
    // ═══════════════════════════════════════════════════════════════════════

    enum EscrowState {
        Active,     // ETH locked, job in progress
        Released,   // Buyer approved, ETH sent to provider
        Refunded    // Job rejected or deadline passed, ETH returned to buyer
    }

    struct Escrow {
        address buyer;
        address provider;
        uint256 amount;
        uint256 deadline;
        bytes32 jobHash;
        EscrowState state;
        uint256 createdAt;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // State
    // ═══════════════════════════════════════════════════════════════════════

    /// @notice escrowId => Escrow
    mapping(uint256 => Escrow) public escrows;

    /// @notice Auto-incrementing escrow counter
    uint256 public escrowCount;

    /// @notice Maximum ETH per escrow (safety guard for testnet)
    uint256 public constant MAX_ESCROW_AMOUNT = 0.01 ether;

    // ═══════════════════════════════════════════════════════════════════════
    // Events
    // ═══════════════════════════════════════════════════════════════════════

    event EscrowCreated(
        uint256 indexed escrowId,
        address indexed buyer,
        address indexed provider,
        uint256 amount,
        uint256 deadline,
        bytes32 jobHash
    );

    event EscrowReleased(
        uint256 indexed escrowId,
        address indexed provider,
        uint256 amount
    );

    event EscrowRefunded(
        uint256 indexed escrowId,
        address indexed buyer,
        uint256 amount
    );

    // ═══════════════════════════════════════════════════════════════════════
    // Errors
    // ═══════════════════════════════════════════════════════════════════════

    error InvalidAddress();
    error InvalidDeadline();
    error AmountTooLarge();
    error NoETHSent();
    error EscrowNotActive();
    error NotBuyer();
    error NotBuyerOrProvider();
    error DeadlineNotPassed();
    error TransferFailed();

    // ═══════════════════════════════════════════════════════════════════════
    // External Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Create a new escrow by locking ETH.
     * @param provider The address that will receive payment on completion
     * @param deadline Unix timestamp after which a refund becomes available
     * @param jobHash  Hash of the ACP job description for on-chain reference
     * @return escrowId The ID of the newly created escrow
     */
    function createEscrow(
        address provider,
        uint256 deadline,
        bytes32 jobHash
    ) external payable nonReentrant returns (uint256 escrowId) {
        if (provider == address(0)) revert InvalidAddress();
        if (provider == msg.sender) revert InvalidAddress();
        if (deadline <= block.timestamp) revert InvalidDeadline();
        if (msg.value == 0) revert NoETHSent();
        if (msg.value > MAX_ESCROW_AMOUNT) revert AmountTooLarge();

        escrowId = escrowCount++;

        escrows[escrowId] = Escrow({
            buyer: msg.sender,
            provider: provider,
            amount: msg.value,
            deadline: deadline,
            jobHash: jobHash,
            state: EscrowState.Active,
            createdAt: block.timestamp
        });

        emit EscrowCreated(
            escrowId,
            msg.sender,
            provider,
            msg.value,
            deadline,
            jobHash
        );
    }

    /**
     * @notice Release escrowed ETH to the provider (buyer approves job completion).
     * @param escrowId The escrow to release
     */
    function releaseToProvider(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        if (e.state != EscrowState.Active) revert EscrowNotActive();
        if (msg.sender != e.buyer) revert NotBuyer();

        e.state = EscrowState.Released;

        (bool success, ) = payable(e.provider).call{value: e.amount}("");
        if (!success) revert TransferFailed();

        emit EscrowReleased(escrowId, e.provider, e.amount);
    }

    /**
     * @notice Refund escrowed ETH to the buyer.
     *         - The provider can refund at any time (job rejection).
     *         - The buyer can refund only after the deadline has passed.
     * @param escrowId The escrow to refund
     */
    function refundToBuyer(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        if (e.state != EscrowState.Active) revert EscrowNotActive();

        if (msg.sender == e.provider) {
            // Provider can refund anytime (job rejection)
        } else if (msg.sender == e.buyer) {
            // Buyer can only refund after deadline
            if (block.timestamp <= e.deadline) revert DeadlineNotPassed();
        } else {
            revert NotBuyerOrProvider();
        }

        e.state = EscrowState.Refunded;

        (bool success, ) = payable(e.buyer).call{value: e.amount}("");
        if (!success) revert TransferFailed();

        emit EscrowRefunded(escrowId, e.buyer, e.amount);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // View Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Get the full escrow record.
     * @param escrowId The escrow to look up
     * @return The Escrow struct
     */
    function getEscrow(uint256 escrowId) external view returns (Escrow memory) {
        return escrows[escrowId];
    }

    /**
     * @notice Check if an escrow is still active.
     * @param escrowId The escrow to check
     * @return True if the escrow is in Active state
     */
    function isActive(uint256 escrowId) external view returns (bool) {
        return escrows[escrowId].state == EscrowState.Active;
    }
}
