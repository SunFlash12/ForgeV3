"""
Tests for FROWG Tipping Models.

This module tests the tipping models for the optional social tipping layer
using $FROWG tokens on Solana.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from forge.virtuals.models.tipping import (
    FROWG_DECIMALS,
    FROWG_TOKEN_MINT,
    Tip,
    TipCreate,
    TipLeaderboard,
    TipResponse,
    TipSummary,
    TipTargetType,
)


# ==================== Constants Tests ====================


class TestTippingConstants:
    """Tests for tipping constants."""

    def test_frowg_token_mint(self):
        """Test FROWG token mint address."""
        assert FROWG_TOKEN_MINT == "uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump"

    def test_frowg_decimals(self):
        """Test FROWG token decimals."""
        assert FROWG_DECIMALS == 9


# ==================== TipTargetType Tests ====================


class TestTipTargetType:
    """Tests for TipTargetType enum."""

    def test_all_target_types(self):
        """Test all target types exist."""
        assert TipTargetType.AGENT == "agent"
        assert TipTargetType.CAPSULE == "capsule"
        assert TipTargetType.USER == "user"

    def test_target_type_count(self):
        """Test number of target types."""
        assert len(TipTargetType) == 3


# ==================== Tip Tests ====================


class TestTip:
    """Tests for Tip model."""

    def test_tip_creation(self):
        """Test creating a tip."""
        tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=10.0,
        )

        assert tip.amount_frowg == 10.0
        assert tip.target_type == TipTargetType.AGENT
        assert tip.confirmed is False
        assert tip.id is not None

    def test_tip_with_message(self):
        """Test tip with message."""
        tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-456",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=5.0,
            message="Great knowledge capsule!",
        )

        assert tip.message == "Great knowledge capsule!"

    def test_tip_with_user_id(self):
        """Test tip with sender user ID."""
        tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            sender_user_id="user-789",
            target_type=TipTargetType.USER,
            target_id="user-target",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=20.0,
        )

        assert tip.sender_user_id == "user-789"

    def test_tip_confirmed(self):
        """Test confirmed tip."""
        tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=15.0,
            tx_signature="abc123signature",
            confirmed=True,
            confirmed_at=datetime.now(UTC),
        )

        assert tip.confirmed is True
        assert tip.tx_signature == "abc123signature"
        assert tip.confirmed_at is not None

    def test_tip_to_lamports(self):
        """Test conversion to lamports."""
        tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=1.0,  # 1 FROWG = 1_000_000_000 lamports (10^9)
        )

        lamports = tip.to_lamports()
        assert lamports == 1_000_000_000

    def test_tip_to_lamports_fractional(self):
        """Test conversion to lamports with fractional amount."""
        tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-123",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=0.5,
        )

        lamports = tip.to_lamports()
        assert lamports == 500_000_000

    def test_tip_amount_validation_positive(self):
        """Test that amount must be positive."""
        with pytest.raises(ValidationError):
            Tip(
                sender_wallet="7B8xLj" + "a" * 30,
                target_type=TipTargetType.AGENT,
                target_id="agent-123",
                recipient_wallet="9Y3kMn" + "b" * 30,
                amount_frowg=0.0,  # Must be > 0
            )

    def test_tip_message_max_length(self):
        """Test message max length (280 chars - tweet length)."""
        with pytest.raises(ValidationError):
            Tip(
                sender_wallet="7B8xLj" + "a" * 30,
                target_type=TipTargetType.AGENT,
                target_id="agent-123",
                recipient_wallet="9Y3kMn" + "b" * 30,
                amount_frowg=1.0,
                message="X" * 281,  # Exceeds 280 char limit
            )


# ==================== TipCreate Tests ====================


class TestTipCreate:
    """Tests for TipCreate model."""

    def test_tip_create_minimal(self):
        """Test creating tip request with minimal fields."""
        create = TipCreate(
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            amount_frowg=10.0,
        )

        assert create.target_type == TipTargetType.AGENT
        assert create.amount_frowg == 10.0
        assert create.message is None

    def test_tip_create_with_message(self):
        """Test creating tip request with message."""
        create = TipCreate(
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-456",
            amount_frowg=25.0,
            message="Thanks for the knowledge!",
        )

        assert create.message == "Thanks for the knowledge!"

    def test_tip_create_amount_minimum(self):
        """Test minimum amount validation."""
        with pytest.raises(ValidationError):
            TipCreate(
                target_type=TipTargetType.USER,
                target_id="user-123",
                amount_frowg=0.0,  # Must be > 0
            )

    def test_tip_create_amount_maximum(self):
        """Test maximum amount validation."""
        with pytest.raises(ValidationError):
            TipCreate(
                target_type=TipTargetType.USER,
                target_id="user-123",
                amount_frowg=1_000_001.0,  # Exceeds 1M limit
            )


# ==================== TipResponse Tests ====================


class TestTipResponse:
    """Tests for TipResponse model."""

    def test_tip_response_pending(self):
        """Test pending tip response."""
        response = TipResponse(
            tip_id="tip-123",
            status="pending",
            message="Tip is being processed",
        )

        assert response.tip_id == "tip-123"
        assert response.status == "pending"
        assert response.tx_signature is None

    def test_tip_response_confirmed(self):
        """Test confirmed tip response."""
        response = TipResponse(
            tip_id="tip-456",
            tx_signature="abc123sig",
            status="confirmed",
            message="Tip sent successfully",
        )

        assert response.status == "confirmed"
        assert response.tx_signature == "abc123sig"

    def test_tip_response_failed(self):
        """Test failed tip response."""
        response = TipResponse(
            tip_id="tip-789",
            status="failed",
            message="Insufficient balance",
        )

        assert response.status == "failed"


# ==================== TipSummary Tests ====================


class TestTipSummary:
    """Tests for TipSummary model."""

    def test_tip_summary_creation(self):
        """Test creating tip summary."""
        summary = TipSummary(
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            total_tips=50,
            total_frowg=1000.0,
            unique_tippers=25,
        )

        assert summary.total_tips == 50
        assert summary.total_frowg == 1000.0
        assert summary.unique_tippers == 25
        assert summary.recent_tips == []

    def test_tip_summary_with_recent_tips(self):
        """Test tip summary with recent tips."""
        recent_tip = Tip(
            sender_wallet="7B8xLj" + "a" * 30,
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            recipient_wallet="9Y3kMn" + "b" * 30,
            amount_frowg=10.0,
        )

        summary = TipSummary(
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            total_tips=1,
            total_frowg=10.0,
            unique_tippers=1,
            recent_tips=[recent_tip],
        )

        assert len(summary.recent_tips) == 1
        assert summary.recent_tips[0].amount_frowg == 10.0


# ==================== TipLeaderboard Tests ====================


class TestTipLeaderboard:
    """Tests for TipLeaderboard model."""

    def test_leaderboard_creation(self):
        """Test creating a leaderboard."""
        leaderboard = TipLeaderboard(
            target_type=TipTargetType.AGENT,
            period="all_time",
        )

        assert leaderboard.target_type == TipTargetType.AGENT
        assert leaderboard.period == "all_time"
        assert leaderboard.entries == []

    def test_leaderboard_with_entries(self):
        """Test leaderboard with entries."""
        entries = [
            {"target_id": "agent-1", "total_frowg": 5000.0, "tip_count": 100},
            {"target_id": "agent-2", "total_frowg": 3000.0, "tip_count": 75},
            {"target_id": "agent-3", "total_frowg": 1500.0, "tip_count": 50},
        ]

        leaderboard = TipLeaderboard(
            target_type=TipTargetType.AGENT,
            period="monthly",
            entries=entries,
        )

        assert len(leaderboard.entries) == 3
        assert leaderboard.entries[0]["total_frowg"] == 5000.0

    def test_leaderboard_weekly_period(self):
        """Test weekly leaderboard."""
        leaderboard = TipLeaderboard(
            target_type=TipTargetType.CAPSULE,
            period="weekly",
            entries=[{"target_id": "capsule-1", "total_frowg": 100.0, "tip_count": 10}],
        )

        assert leaderboard.period == "weekly"
        assert leaderboard.target_type == TipTargetType.CAPSULE
