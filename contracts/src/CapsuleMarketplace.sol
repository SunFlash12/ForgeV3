// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title CapsuleMarketplace
 * @notice Marketplace for purchasing Forge Capsules with $VIRTUAL token on Base
 * @dev Handles payments and automatic distribution to sellers, lineage, platform, and DAO
 *
 * Payment Distribution:
 * - 70% to Seller (capsule author)
 * - 15% to Lineage (ancestor capsules)
 * - 10% to Platform Treasury
 * - 5% to DAO Treasury
 */
contract CapsuleMarketplace is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    // ============ Constants ============
    uint256 public constant SELLER_SHARE = 7000;      // 70%
    uint256 public constant LINEAGE_SHARE = 1500;     // 15%
    uint256 public constant PLATFORM_SHARE = 1000;    // 10%
    uint256 public constant DAO_SHARE = 500;          // 5%
    uint256 public constant BASIS_POINTS = 10000;     // 100%

    // ============ State Variables ============
    IERC20 public immutable virtualToken;
    address public platformTreasury;
    address public daoTreasury;

    // Capsule ID => Listing
    mapping(bytes32 => Listing) public listings;

    // Track purchases for verification
    mapping(bytes32 => Purchase[]) public capsulePurchases;

    // Total volume traded
    uint256 public totalVolume;
    uint256 public totalPurchases;

    // ============ Structs ============
    struct Listing {
        bytes32 capsuleId;          // Unique capsule identifier
        address seller;              // Seller address (receives 70%)
        address[] lineageAddresses;  // Ancestor addresses (split 15%)
        uint256 priceInVirtual;      // Price in $VIRTUAL (18 decimals)
        bool active;
        uint256 salesCount;
        uint256 createdAt;
    }

    struct Purchase {
        address buyer;
        uint256 amount;
        uint256 timestamp;
        bytes32 txId;
    }

    // ============ Events ============
    event ListingCreated(
        bytes32 indexed capsuleId,
        address indexed seller,
        uint256 priceInVirtual
    );

    event ListingUpdated(
        bytes32 indexed capsuleId,
        uint256 newPrice,
        bool active
    );

    event CapsulePurchased(
        bytes32 indexed capsuleId,
        address indexed buyer,
        address indexed seller,
        uint256 totalAmount,
        uint256 sellerAmount,
        uint256 lineageAmount,
        uint256 platformAmount,
        uint256 daoAmount
    );

    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury, string treasuryType);
    event LineageAddressesUpdated(bytes32 indexed capsuleId, address[] newAddresses);

    // ============ Errors ============
    error InvalidAddress();
    error ListingNotActive();
    error ListingAlreadyExists();
    error InsufficientAllowance();
    error InsufficientBalance();
    error InvalidPrice();
    error Unauthorized();
    error TransferFailed();

    // ============ Constructor ============
    /**
     * @notice Initialize the marketplace
     * @param _virtualToken Address of the $VIRTUAL token contract
     * @param _platformTreasury Address to receive platform fees (frowg.base.eth)
     * @param _daoTreasury Address to receive DAO fees
     */
    constructor(
        address _virtualToken,
        address _platformTreasury,
        address _daoTreasury
    ) Ownable(msg.sender) {
        if (_virtualToken == address(0)) revert InvalidAddress();
        if (_platformTreasury == address(0)) revert InvalidAddress();
        if (_daoTreasury == address(0)) revert InvalidAddress();

        virtualToken = IERC20(_virtualToken);
        platformTreasury = _platformTreasury;
        daoTreasury = _daoTreasury;
    }

    // ============ External Functions ============

    /**
     * @notice Create a new capsule listing
     * @param capsuleId Unique identifier for the capsule
     * @param priceInVirtual Price in $VIRTUAL tokens (18 decimals)
     * @param lineageAddresses Array of ancestor capsule owner addresses
     */
    function createListing(
        bytes32 capsuleId,
        uint256 priceInVirtual,
        address[] calldata lineageAddresses
    ) external whenNotPaused {
        if (listings[capsuleId].seller != address(0)) revert ListingAlreadyExists();
        if (priceInVirtual == 0) revert InvalidPrice();

        // Validate lineage addresses
        for (uint256 i = 0; i < lineageAddresses.length; i++) {
            if (lineageAddresses[i] == address(0)) revert InvalidAddress();
        }

        listings[capsuleId] = Listing({
            capsuleId: capsuleId,
            seller: msg.sender,
            lineageAddresses: lineageAddresses,
            priceInVirtual: priceInVirtual,
            active: true,
            salesCount: 0,
            createdAt: block.timestamp
        });

        emit ListingCreated(capsuleId, msg.sender, priceInVirtual);
    }

    /**
     * @notice Purchase a capsule
     * @param capsuleId The capsule to purchase
     */
    function purchaseCapsule(bytes32 capsuleId) external nonReentrant whenNotPaused {
        Listing storage listing = listings[capsuleId];

        if (!listing.active) revert ListingNotActive();

        uint256 totalAmount = listing.priceInVirtual;

        // Check buyer has approved enough tokens
        if (virtualToken.allowance(msg.sender, address(this)) < totalAmount) {
            revert InsufficientAllowance();
        }

        // Check buyer has enough balance
        if (virtualToken.balanceOf(msg.sender) < totalAmount) {
            revert InsufficientBalance();
        }

        // Calculate distribution amounts
        uint256 sellerAmount = (totalAmount * SELLER_SHARE) / BASIS_POINTS;
        uint256 lineageAmount = (totalAmount * LINEAGE_SHARE) / BASIS_POINTS;
        uint256 platformAmount = (totalAmount * PLATFORM_SHARE) / BASIS_POINTS;
        uint256 daoAmount = (totalAmount * DAO_SHARE) / BASIS_POINTS;

        // Transfer from buyer to this contract first
        virtualToken.safeTransferFrom(msg.sender, address(this), totalAmount);

        // Distribute to seller (70%)
        virtualToken.safeTransfer(listing.seller, sellerAmount);

        // Distribute to lineage (15% split among ancestors)
        if (listing.lineageAddresses.length > 0) {
            uint256 perLineage = lineageAmount / listing.lineageAddresses.length;
            for (uint256 i = 0; i < listing.lineageAddresses.length; i++) {
                virtualToken.safeTransfer(listing.lineageAddresses[i], perLineage);
            }
            // Handle remainder (dust) - send to first ancestor
            uint256 remainder = lineageAmount - (perLineage * listing.lineageAddresses.length);
            if (remainder > 0) {
                virtualToken.safeTransfer(listing.lineageAddresses[0], remainder);
            }
        } else {
            // No lineage - add to platform treasury
            platformAmount += lineageAmount;
        }

        // Distribute to platform treasury (10%)
        virtualToken.safeTransfer(platformTreasury, platformAmount);

        // Distribute to DAO treasury (5%)
        virtualToken.safeTransfer(daoTreasury, daoAmount);

        // Update listing stats
        listing.salesCount++;

        // Record purchase
        capsulePurchases[capsuleId].push(Purchase({
            buyer: msg.sender,
            amount: totalAmount,
            timestamp: block.timestamp,
            txId: keccak256(abi.encodePacked(msg.sender, capsuleId, block.timestamp, block.number))
        }));

        // Update totals
        totalVolume += totalAmount;
        totalPurchases++;

        emit CapsulePurchased(
            capsuleId,
            msg.sender,
            listing.seller,
            totalAmount,
            sellerAmount,
            lineageAmount,
            platformAmount,
            daoAmount
        );
    }

    /**
     * @notice Batch purchase multiple capsules
     * @param capsuleIds Array of capsule IDs to purchase
     */
    function batchPurchase(bytes32[] calldata capsuleIds) external nonReentrant whenNotPaused {
        for (uint256 i = 0; i < capsuleIds.length; i++) {
            _executePurchase(capsuleIds[i]);
        }
    }

    /**
     * @notice Update listing price
     * @param capsuleId The capsule listing to update
     * @param newPrice New price in $VIRTUAL
     */
    function updateListingPrice(bytes32 capsuleId, uint256 newPrice) external {
        Listing storage listing = listings[capsuleId];
        if (listing.seller != msg.sender) revert Unauthorized();
        if (newPrice == 0) revert InvalidPrice();

        listing.priceInVirtual = newPrice;
        emit ListingUpdated(capsuleId, newPrice, listing.active);
    }

    /**
     * @notice Toggle listing active status
     * @param capsuleId The capsule listing to toggle
     */
    function toggleListing(bytes32 capsuleId) external {
        Listing storage listing = listings[capsuleId];
        if (listing.seller != msg.sender && msg.sender != owner()) revert Unauthorized();

        listing.active = !listing.active;
        emit ListingUpdated(capsuleId, listing.priceInVirtual, listing.active);
    }

    /**
     * @notice Update lineage addresses for a listing
     * @param capsuleId The capsule listing to update
     * @param newLineageAddresses New array of lineage addresses
     */
    function updateLineageAddresses(
        bytes32 capsuleId,
        address[] calldata newLineageAddresses
    ) external {
        Listing storage listing = listings[capsuleId];
        if (listing.seller != msg.sender && msg.sender != owner()) revert Unauthorized();

        for (uint256 i = 0; i < newLineageAddresses.length; i++) {
            if (newLineageAddresses[i] == address(0)) revert InvalidAddress();
        }

        listing.lineageAddresses = newLineageAddresses;
        emit LineageAddressesUpdated(capsuleId, newLineageAddresses);
    }

    // ============ Admin Functions ============

    /**
     * @notice Update platform treasury address
     * @param newTreasury New treasury address
     */
    function setPlatformTreasury(address newTreasury) external onlyOwner {
        if (newTreasury == address(0)) revert InvalidAddress();
        address old = platformTreasury;
        platformTreasury = newTreasury;
        emit TreasuryUpdated(old, newTreasury, "platform");
    }

    /**
     * @notice Update DAO treasury address
     * @param newTreasury New treasury address
     */
    function setDaoTreasury(address newTreasury) external onlyOwner {
        if (newTreasury == address(0)) revert InvalidAddress();
        address old = daoTreasury;
        daoTreasury = newTreasury;
        emit TreasuryUpdated(old, newTreasury, "dao");
    }

    /**
     * @notice Pause the marketplace
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @notice Unpause the marketplace
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Emergency withdrawal of stuck tokens
     * @param token Token address to withdraw
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(address token, uint256 amount) external onlyOwner {
        IERC20(token).safeTransfer(owner(), amount);
    }

    // ============ View Functions ============

    /**
     * @notice Get listing details
     * @param capsuleId The capsule ID
     * @return The listing struct
     */
    function getListing(bytes32 capsuleId) external view returns (Listing memory) {
        return listings[capsuleId];
    }

    /**
     * @notice Get purchase history for a capsule
     * @param capsuleId The capsule ID
     * @return Array of purchases
     */
    function getPurchaseHistory(bytes32 capsuleId) external view returns (Purchase[] memory) {
        return capsulePurchases[capsuleId];
    }

    /**
     * @notice Check if a purchase is valid (for backend verification)
     * @param capsuleId The capsule ID
     * @param buyer The buyer address
     * @param txId The transaction ID from purchase event
     * @return bool Whether the purchase exists
     */
    function verifyPurchase(
        bytes32 capsuleId,
        address buyer,
        bytes32 txId
    ) external view returns (bool) {
        Purchase[] memory purchases = capsulePurchases[capsuleId];
        for (uint256 i = 0; i < purchases.length; i++) {
            if (purchases[i].buyer == buyer && purchases[i].txId == txId) {
                return true;
            }
        }
        return false;
    }

    /**
     * @notice Get lineage addresses for a listing
     * @param capsuleId The capsule ID
     * @return Array of lineage addresses
     */
    function getLineageAddresses(bytes32 capsuleId) external view returns (address[] memory) {
        return listings[capsuleId].lineageAddresses;
    }

    // ============ Internal Functions ============

    function _executePurchase(bytes32 capsuleId) internal {
        Listing storage listing = listings[capsuleId];

        if (!listing.active) revert ListingNotActive();

        uint256 totalAmount = listing.priceInVirtual;

        // Calculate distribution
        uint256 sellerAmount = (totalAmount * SELLER_SHARE) / BASIS_POINTS;
        uint256 lineageAmount = (totalAmount * LINEAGE_SHARE) / BASIS_POINTS;
        uint256 platformAmount = (totalAmount * PLATFORM_SHARE) / BASIS_POINTS;
        uint256 daoAmount = (totalAmount * DAO_SHARE) / BASIS_POINTS;

        // Transfer from buyer
        virtualToken.safeTransferFrom(msg.sender, address(this), totalAmount);

        // Distribute
        virtualToken.safeTransfer(listing.seller, sellerAmount);

        if (listing.lineageAddresses.length > 0) {
            uint256 perLineage = lineageAmount / listing.lineageAddresses.length;
            for (uint256 i = 0; i < listing.lineageAddresses.length; i++) {
                virtualToken.safeTransfer(listing.lineageAddresses[i], perLineage);
            }
            uint256 remainder = lineageAmount - (perLineage * listing.lineageAddresses.length);
            if (remainder > 0) {
                virtualToken.safeTransfer(listing.lineageAddresses[0], remainder);
            }
        } else {
            platformAmount += lineageAmount;
        }

        virtualToken.safeTransfer(platformTreasury, platformAmount);
        virtualToken.safeTransfer(daoTreasury, daoAmount);

        listing.salesCount++;

        capsulePurchases[capsuleId].push(Purchase({
            buyer: msg.sender,
            amount: totalAmount,
            timestamp: block.timestamp,
            txId: keccak256(abi.encodePacked(msg.sender, capsuleId, block.timestamp, block.number))
        }));

        totalVolume += totalAmount;
        totalPurchases++;

        emit CapsulePurchased(
            capsuleId,
            msg.sender,
            listing.seller,
            totalAmount,
            sellerAmount,
            lineageAmount,
            platformAmount,
            daoAmount
        );
    }
}
