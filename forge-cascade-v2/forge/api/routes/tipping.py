"""
FROWG Tipping API Routes

Optional social tipping layer using $FROWG tokens on Solana.
Tips are purely for social recognition - no functional impact on Forge.

All endpoints are public and optional - tipping doesn't gate any features.
"""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query

from forge.services.tipping_service import get_tipping_service

logger = structlog.get_logger(__name__)
from forge.virtuals.models.tipping import (
    FROWG_TOKEN_MINT,
    Tip,
    TipCreate,
    TipLeaderboard,
    TipResponse,
    TipSummary,
    TipTargetType,
)

router = APIRouter(prefix="/tips", tags=["Tipping"])


@router.get("/info")
async def get_tipping_info() -> dict[str, Any]:
    """
    Get information about the FROWG tipping system.

    Returns token address and basic info about tipping.
    """
    return {
        "token": "FROWG",
        "name": "Rise of Frowg",
        "chain": "solana",
        "mint_address": FROWG_TOKEN_MINT,
        "description": "Optional social tipping for Forge. Tips are purely for recognition - they don't affect any functionality.",
        "tip_targets": [t.value for t in TipTargetType],
    }


@router.post("", response_model=TipResponse)
async def create_tip(
    request: TipCreate,
    sender_wallet: str = Query(..., description="Your Solana wallet address"),
    recipient_wallet: str = Query(..., description="Recipient's Solana wallet address"),
    tx_signature: str | None = Query(
        None, description="Solana transaction signature if already sent"
    ),
) -> TipResponse:
    """
    Record a FROWG tip.

    Tips are optional social recognition. You can either:
    1. Send the tip on-chain first, then record it here with tx_signature
    2. Record intent here, then send on-chain and confirm later

    Tips have NO functional impact - they're purely social.
    """
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    try:
        tip = await service.create_tip(
            sender_wallet=sender_wallet,
            target_type=request.target_type,
            target_id=request.target_id,
            recipient_wallet=recipient_wallet,
            amount_frowg=request.amount_frowg,
            message=request.message,
            tx_signature=tx_signature,
        )

        return TipResponse(
            tip_id=tip.id,
            tx_signature=tx_signature,
            status="confirmed" if tx_signature else "pending",
            message=f"Tip of {request.amount_frowg} $FROWG recorded successfully!",
        )
    except (ValueError, ConnectionError, TimeoutError, OSError) as e:
        logger.error(f"Tip creation failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to process tip")


@router.post("/{tip_id}/confirm", response_model=TipResponse)
async def confirm_tip(
    tip_id: str,
    tx_signature: str = Query(..., description="Solana transaction signature"),
) -> TipResponse:
    """
    Confirm a tip with its on-chain transaction signature.

    Call this after sending the FROWG transfer on Solana.
    """
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    success = await service.confirm_tip(tip_id, tx_signature)
    if not success:
        raise HTTPException(status_code=404, detail="Tip not found")

    return TipResponse(
        tip_id=tip_id,
        tx_signature=tx_signature,
        status="confirmed",
        message="Tip confirmed on-chain!",
    )


@router.get("/{tip_id}", response_model=Tip)
async def get_tip(tip_id: str) -> Tip:
    """Get a specific tip by ID."""
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    tip = await service.get_tip(tip_id)
    if not tip:
        raise HTTPException(status_code=404, detail="Tip not found")

    return tip


@router.get("/target/{target_type}/{target_id}", response_model=list[Tip])
async def get_tips_for_target(
    target_type: TipTargetType,
    target_id: str,
    limit: int = Query(50, ge=1, le=100),
    confirmed_only: bool = Query(True),
) -> list[Tip]:
    """
    Get all tips for a specific target (agent, capsule, or user).

    Returns tips sorted by most recent first.
    """
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    return await service.get_tips_for_target(
        target_type=target_type,
        target_id=target_id,
        limit=limit,
        confirmed_only=confirmed_only,
    )


@router.get("/target/{target_type}/{target_id}/summary", response_model=TipSummary)
async def get_tip_summary(
    target_type: TipTargetType,
    target_id: str,
) -> TipSummary:
    """
    Get aggregated tip statistics for a target.

    Returns total tips, total FROWG, unique tippers, and recent tips.
    """
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    return await service.get_tip_summary(target_type, target_id)


@router.get("/sender/{sender_wallet}", response_model=list[Tip])
async def get_tips_by_sender(
    sender_wallet: str,
    limit: int = Query(50, ge=1, le=100),
) -> list[Tip]:
    """Get all tips sent by a specific wallet."""
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    return await service.get_tips_by_sender(sender_wallet, limit)


@router.get("/leaderboard/{target_type}", response_model=TipLeaderboard)
async def get_leaderboard(
    target_type: TipTargetType,
    limit: int = Query(10, ge=1, le=50),
) -> TipLeaderboard:
    """
    Get the top tipped targets of a given type.

    Returns targets sorted by total FROWG received.
    """
    service = get_tipping_service()
    if not service:
        raise HTTPException(status_code=503, detail="Tipping service not available")

    return await service.get_leaderboard(target_type, limit)
