// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../SimpleEscrow.sol";

/**
 * @title ReentrancyAttacker
 * @notice Test helper that attempts reentrancy on SimpleEscrow during refund/release.
 */
contract ReentrancyAttacker {
    SimpleEscrow public escrow;
    uint256 public targetEscrowId;
    bool public attackOnRelease;
    uint256 public attackCount;

    constructor(address _escrow) {
        escrow = SimpleEscrow(_escrow);
    }

    /// @notice Create an escrow where this contract is the buyer.
    function createEscrow(
        address provider,
        uint256 deadline,
        bytes32 jobHash
    ) external payable returns (uint256) {
        return escrow.createEscrow{value: msg.value}(provider, deadline, jobHash);
    }

    /// @notice Trigger releaseToProvider (this contract must be the buyer).
    function attackRelease(uint256 escrowId) external {
        targetEscrowId = escrowId;
        attackOnRelease = true;
        attackCount = 0;
        escrow.releaseToProvider(escrowId);
    }

    /// @notice Trigger refundToBuyer (this contract may be buyer or provider).
    function attackRefund(uint256 escrowId) external {
        targetEscrowId = escrowId;
        attackOnRelease = false;
        attackCount = 0;
        escrow.refundToBuyer(escrowId);
    }

    /// @notice Re-enter on ETH receive.
    receive() external payable {
        attackCount++;
        if (attackCount < 2) {
            if (attackOnRelease) {
                // Try re-entering releaseToProvider
                try escrow.releaseToProvider(targetEscrowId) {} catch {}
            } else {
                // Try re-entering refundToBuyer
                try escrow.refundToBuyer(targetEscrowId) {} catch {}
            }
        }
    }
}

/**
 * @title ETHRejecter
 * @notice Test helper: a contract that can create escrows but always rejects
 *         incoming ETH (no receive/fallback). Useful for testing TransferFailed.
 */
contract ETHRejecter {
    SimpleEscrow public escrow;

    constructor(address _escrow) {
        escrow = SimpleEscrow(_escrow);
    }

    /// @notice Create an escrow where this contract is the buyer.
    function createEscrow(
        address provider,
        uint256 deadline,
        bytes32 jobHash
    ) external payable returns (uint256) {
        return escrow.createEscrow{value: msg.value}(provider, deadline, jobHash);
    }

    // No receive() or fallback() -- ETH transfers to this contract will revert.
}
