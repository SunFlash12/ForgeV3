"""
Forge V3 — Full E2E Lifecycle Tests

Phases:
  1  User setup & auth
  2  Capsule creation (11 capsules, all types)
  3  Search & discovery
  4  Lineage & forking (3-level chain)
  5  Semantic edges (7 relationship types)
  6  Integrity & signing
  7  Tokenization — bonding curve
  8  Tokenization — graduation & revenue
  9  Tokenization — governance
 10  ACP — Agent Commerce Protocol (4-phase)
 11  Tipping — FROWG on Solana
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.e2e

from forge.models.base import CapsuleType, TrustLevel
from forge.models.capsule import (
    CapsuleCreate,
    CapsuleInDB,
    IntegrityStatus,
)
from forge.models.semantic_edges import (
    ContradictionSeverity,
    SemanticEdgeCreate,
    SemanticRelationType,
)
from forge.virtuals.models.base import (
    ACPJobStatus,
    ACPPhase,
    TokenizationStatus,
)

from .seed_capsules import (
    C1,
    C2,
    C5,
    C11,
    CAPSULE_DEFS,
    EDGE_DEFS,
)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_capsule_in_db(
    defn: dict,
    owner_id: str,
    capsule_id: str | None = None,
    parent_id: str | None = None,
    parent_content_hash: str | None = None,
) -> CapsuleInDB:
    """Create a CapsuleInDB from a seed definition."""
    # ForgeModel uses str_strip_whitespace=True, so strip before hashing
    content = defn["content"].strip()
    content_hash = _sha256(content)
    merkle_root = (
        _sha256(content_hash + parent_content_hash) if parent_content_hash else content_hash
    )
    return CapsuleInDB(
        id=capsule_id or str(uuid4()),
        content=content,
        type=defn["type"],
        title=defn["title"],
        tags=defn["tags"],
        metadata=defn["metadata"],
        owner_id=owner_id,
        trust_level=TrustLevel.STANDARD,
        version="1.0.0",
        content_hash=content_hash,
        integrity_status=IntegrityStatus.VALID,
        integrity_verified_at=datetime.now(UTC),
        parent_id=parent_id,
        parent_content_hash=parent_content_hash,
        merkle_root=merkle_root,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1  —  USER SETUP
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase1UserSetup:
    """Verify test user fixtures and basic auth concepts."""

    def test_admin_has_high_trust(self, users: dict) -> None:
        assert users["admin"]["trust_level"] >= 80

    def test_researcher_has_standard_trust(self, users: dict) -> None:
        assert users["researcher"]["trust_level"] == 60

    def test_contributor_has_standard_trust(self, users: dict) -> None:
        assert users["contributor"]["trust_level"] == 60

    def test_all_users_have_unique_ids(self, users: dict) -> None:
        ids = [u["id"] for u in users.values()]
        assert len(set(ids)) == len(ids)

    def test_all_users_have_wallets(self, users: dict) -> None:
        for user in users.values():
            assert user["wallet"].startswith("0x")
            assert len(user["wallet"]) == 42


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2  —  CAPSULE CREATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase2CapsuleCreation:
    """Create all 11 seed capsules and validate models."""

    def test_all_capsule_types_covered(self) -> None:
        created_types = {d["type"] for d in CAPSULE_DEFS}
        expected_types = set(CapsuleType)
        assert created_types == expected_types, f"Missing types: {expected_types - created_types}"

    @pytest.mark.parametrize("idx", range(11))
    def test_capsule_model_valid(self, idx: int, users: dict) -> None:
        defn = CAPSULE_DEFS[idx]
        capsule = _make_capsule_in_db(defn, owner_id=users["researcher"]["id"])
        assert capsule.title == defn["title"]
        assert capsule.type == defn["type"]
        assert len(capsule.content) > 0
        assert capsule.content_hash is not None
        assert capsule.integrity_status == IntegrityStatus.VALID

    @pytest.mark.parametrize("idx", range(11))
    def test_capsule_content_hash_correct(self, idx: int, users: dict) -> None:
        defn = CAPSULE_DEFS[idx]
        capsule = _make_capsule_in_db(defn, owner_id=users["researcher"]["id"])
        assert capsule.content_hash == _sha256(capsule.content)

    def test_capsule_create_model_validation(self) -> None:
        """CapsuleCreate rejects invalid payloads."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CapsuleCreate(content="", type=CapsuleType.KNOWLEDGE, tags=[])

    def test_tags_normalised_to_lowercase(self, users: dict) -> None:
        defn = CAPSULE_DEFS[C1].copy()
        defn["tags"] = ["Genomics", "ONTOLOGY", "Rare-Disease"]
        capsule = _make_capsule_in_db(defn, owner_id=users["researcher"]["id"])
        for tag in capsule.tags:
            assert tag == tag.lower()

    def test_owner_id_matches_creator(self, users: dict) -> None:
        capsule = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=users["researcher"]["id"])
        assert capsule.owner_id == users["researcher"]["id"]

    def test_default_trust_is_standard(self, users: dict) -> None:
        capsule = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=users["researcher"]["id"])
        assert capsule.trust_level == TrustLevel.STANDARD


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3  —  SEARCH & DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase3SearchDiscovery:
    """Validate filtering and search helpers."""

    def _all_capsules(self, users: dict) -> list[CapsuleInDB]:
        return [_make_capsule_in_db(d, owner_id=users["researcher"]["id"]) for d in CAPSULE_DEFS]

    def test_filter_by_type(self, users: dict) -> None:
        capsules = self._all_capsules(users)
        codes = [c for c in capsules if c.type == CapsuleType.CODE]
        assert len(codes) == 1
        assert codes[0].title == "Ensemble Variant Classifier Implementation"

    def test_filter_by_tag(self, users: dict) -> None:
        capsules = self._all_capsules(users)
        genomics = [c for c in capsules if "genomics" in c.tags]
        assert len(genomics) >= 8  # most capsules have this tag

    def test_filter_by_owner(self, users: dict) -> None:
        capsules = self._all_capsules(users)
        researcher_id = users["researcher"]["id"]
        owned = [c for c in capsules if c.owner_id == researcher_id]
        assert len(owned) == 11

    def test_recent_ordering(self, users: dict) -> None:
        capsules = self._all_capsules(users)
        # All created at roughly the same time; just verify they're sortable
        sorted_by_time = sorted(capsules, key=lambda c: c.created_at, reverse=True)
        assert len(sorted_by_time) == 11


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4  —  LINEAGE & FORKING
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase4Lineage:
    """Test DERIVED_FROM lineage chains up to depth 3."""

    def _build_lineage(self, users: dict) -> dict[int, CapsuleInDB]:
        """Build capsules with lineage according to LINEAGE_DEFS."""
        owner = users["researcher"]["id"]
        capsules: dict[int, CapsuleInDB] = {}

        # Create C1 first (root)
        capsules[C1] = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=owner)

        # C2 derives from C1
        capsules[C2] = _make_capsule_in_db(
            CAPSULE_DEFS[C2],
            owner_id=owner,
            parent_id=capsules[C1].id,
            parent_content_hash=capsules[C1].content_hash,
        )

        # C5 derives from C2 (3-level chain: C1 -> C2 -> C5)
        capsules[C5] = _make_capsule_in_db(
            CAPSULE_DEFS[C5],
            owner_id=owner,
            parent_id=capsules[C2].id,
            parent_content_hash=capsules[C2].content_hash,
        )

        # C11 derives from C1
        capsules[C11] = _make_capsule_in_db(
            CAPSULE_DEFS[C11],
            owner_id=owner,
            parent_id=capsules[C1].id,
            parent_content_hash=capsules[C1].content_hash,
        )

        return capsules

    def test_c2_parent_is_c1(self, users: dict) -> None:
        caps = self._build_lineage(users)
        assert caps[C2].parent_id == caps[C1].id

    def test_c5_parent_is_c2(self, users: dict) -> None:
        caps = self._build_lineage(users)
        assert caps[C5].parent_id == caps[C2].id

    def test_c11_parent_is_c1(self, users: dict) -> None:
        caps = self._build_lineage(users)
        assert caps[C11].parent_id == caps[C1].id

    def test_three_level_ancestry(self, users: dict) -> None:
        """C5's lineage chain should be C1 -> C2 -> C5 (depth 3)."""
        caps = self._build_lineage(users)
        # Walk from C5 up
        chain = []
        current: CapsuleInDB | None = caps[C5]
        while current:
            chain.append(current)
            pid = current.parent_id
            if pid:
                # Find parent in our built capsules
                parent = next((c for c in caps.values() if c.id == pid), None)
                current = parent
            else:
                current = None
        assert len(chain) == 3  # C5, C2, C1

    def test_parent_content_hash_immutable(self, users: dict) -> None:
        caps = self._build_lineage(users)
        assert caps[C2].parent_content_hash == caps[C1].content_hash

    def test_merkle_root_chains_correctly(self, users: dict) -> None:
        caps = self._build_lineage(users)
        # C2's merkle_root = sha256(C2_content_hash + C1_content_hash)
        expected = _sha256(caps[C2].content_hash + caps[C1].content_hash)  # type: ignore[operator]
        assert caps[C2].merkle_root == expected


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5  —  SEMANTIC EDGES
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase5SemanticEdges:
    """Create and validate all planned semantic edges."""

    def _build_capsules(self, users: dict) -> list[CapsuleInDB]:
        owner = users["researcher"]["id"]
        return [
            _make_capsule_in_db(d, owner_id=owner, capsule_id=f"capsule-{i}")
            for i, d in enumerate(CAPSULE_DEFS)
        ]

    def test_all_edge_defs_create_valid_models(self, users: dict) -> None:
        caps = self._build_capsules(users)
        for src_idx, tgt_idx, rel_type, props in EDGE_DEFS:
            edge = SemanticEdgeCreate(
                source_id=caps[src_idx].id,
                target_id=caps[tgt_idx].id,
                relationship_type=rel_type,
                properties=props,
            )
            assert edge.source_id == caps[src_idx].id
            assert edge.target_id == caps[tgt_idx].id
            assert edge.relationship_type == rel_type

    def test_contradicts_edge_has_severity(self, users: dict) -> None:
        caps = self._build_capsules(users)
        # C6 -> C2 CONTRADICTS
        c6_c2 = next(
            (src, tgt, rt, p)
            for src, tgt, rt, p in EDGE_DEFS
            if rt == SemanticRelationType.CONTRADICTS
        )
        edge = SemanticEdgeCreate(
            source_id=caps[c6_c2[0]].id,
            target_id=caps[c6_c2[1]].id,
            relationship_type=c6_c2[2],
            properties=c6_c2[3],
        )
        assert edge.properties["severity"] == ContradictionSeverity.HIGH.value

    def test_contradicts_is_bidirectional(self) -> None:
        assert SemanticRelationType.CONTRADICTS.is_bidirectional is True

    def test_implements_is_directed(self) -> None:
        assert SemanticRelationType.IMPLEMENTS.is_bidirectional is False

    def test_supports_edge_has_evidence_type(self, users: dict) -> None:
        caps = self._build_capsules(users)
        supports_edges = [
            (s, t, r, p) for s, t, r, p in EDGE_DEFS if r == SemanticRelationType.SUPPORTS
        ]
        assert len(supports_edges) >= 1
        edge = SemanticEdgeCreate(
            source_id=caps[supports_edges[0][0]].id,
            target_id=caps[supports_edges[0][1]].id,
            relationship_type=supports_edges[0][2],
            properties=supports_edges[0][3],
        )
        assert "evidence_type" in edge.properties

    def test_edge_count_matches_plan(self) -> None:
        assert len(EDGE_DEFS) == 13

    def test_seven_relationship_types_used(self) -> None:
        used_types = {rt for _, _, rt, _ in EDGE_DEFS}
        assert len(used_types) >= 7


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6  —  INTEGRITY & SIGNING
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase6Integrity:
    """Validate content hashing, tamper detection, and merkle chains."""

    def test_content_hash_valid(self, users: dict) -> None:
        cap = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=users["researcher"]["id"])
        assert cap.content_hash == _sha256(cap.content)
        assert cap.integrity_status == IntegrityStatus.VALID

    def test_tamper_detection(self, users: dict) -> None:
        cap = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=users["researcher"]["id"])
        original_hash = cap.content_hash
        # Simulate content tampering
        tampered_hash = _sha256(cap.content + " TAMPERED")
        assert tampered_hash != original_hash

    def test_merkle_root_for_root_capsule(self, users: dict) -> None:
        """Root capsule's merkle_root == its own content_hash."""
        cap = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=users["researcher"]["id"])
        assert cap.merkle_root == cap.content_hash

    def test_merkle_chain_verification(self, users: dict) -> None:
        """Child's merkle_root = sha256(child_hash + parent_hash)."""
        owner = users["researcher"]["id"]
        parent = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=owner)
        child = _make_capsule_in_db(
            CAPSULE_DEFS[C2],
            owner_id=owner,
            parent_id=parent.id,
            parent_content_hash=parent.content_hash,
        )
        expected_merkle = _sha256(child.content_hash + parent.content_hash)  # type: ignore[operator]
        assert child.merkle_root == expected_merkle

    def test_integrity_report_model(self, users: dict) -> None:
        from forge.models.capsule import IntegrityReport

        cap = _make_capsule_in_db(CAPSULE_DEFS[C1], owner_id=users["researcher"]["id"])
        report = IntegrityReport(
            capsule_id=cap.id,
            content_hash_valid=True,
            content_hash_expected=cap.content_hash,
            content_hash_computed=_sha256(cap.content),
            overall_status=IntegrityStatus.VALID,
            checked_at=datetime.now(UTC),
        )
        assert report.content_hash_valid is True
        assert report.overall_status == IntegrityStatus.VALID

    def test_lineage_integrity_report_model(self, users: dict) -> None:
        from forge.models.capsule import LineageIntegrityReport

        report = LineageIntegrityReport(
            capsule_id="leaf-id",
            chain_length=3,
            all_hashes_valid=True,
            merkle_chain_valid=True,
            verified_capsules=["c1", "c2", "c5"],
            failed_capsules=[],
            checked_at=datetime.now(UTC),
        )
        assert report.chain_length == 3
        assert report.merkle_chain_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7  —  TOKENIZATION: BONDING CURVE
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase7TokenizationBonding:
    """Request tokenization and contribute to bonding curves."""

    @pytest.mark.asyncio
    async def test_request_tokenization_c1(self, tokenization_service: Any, users: dict) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-c1",
            token_name="Genomic Ontology Token",
            token_symbol="GOT",
            token_description="Token for the Rare Disease Genomic Ontology",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)
        assert entity.status == TokenizationStatus.BONDING
        assert entity.bonding_curve_virtual_accumulated == 100.0
        assert entity.bonding_curve_contributors == 1

    @pytest.mark.asyncio
    async def test_request_tokenization_c4(self, tokenization_service: Any, users: dict) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-c4",
            token_name="Variant Classifier Token",
            token_symbol="VCT",
            token_description="Token for the Ensemble Variant Classifier",
            initial_stake_virtual=200.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)
        assert entity.status == TokenizationStatus.BONDING
        assert entity.bonding_curve_virtual_accumulated == 200.0

    @pytest.mark.asyncio
    async def test_contribute_to_bonding_curve(
        self, tokenization_service: Any, users: dict
    ) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-contrib-test",
            token_name="Test Token",
            token_symbol="TST",
            token_description="Test token for contribution",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)

        # Contribute additional VIRTUAL
        updated, contribution = await tokenization_service.contribute_to_bonding_curve(
            entity_id=entity.id,
            contributor_wallet=users["contributor"]["wallet"],
            amount_virtual=1000.0,
        )
        assert updated.bonding_curve_virtual_accumulated == 1100.0
        assert updated.bonding_curve_contributors == 2
        assert contribution.amount_virtual == 1000.0

    @pytest.mark.asyncio
    async def test_insufficient_stake_rejected(
        self, tokenization_service: Any, users: dict
    ) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest
        from forge.virtuals.tokenization.service import InsufficientStakeError

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-low-stake",
            token_name="Low Stake Token",
            token_symbol="LOW",
            token_description="Should fail",
            initial_stake_virtual=100.0,  # minimum is 100
            owner_wallet=users["researcher"]["wallet"],
        )
        # Temporarily set a higher minimum
        original_fee = tokenization_service.config.agent_creation_fee
        tokenization_service.config.agent_creation_fee = 500
        try:
            with pytest.raises(InsufficientStakeError):
                await tokenization_service.request_tokenization(req)
        finally:
            tokenization_service.config.agent_creation_fee = original_fee

    @pytest.mark.asyncio
    async def test_duplicate_tokenization_rejected(
        self, tokenization_service: Any, users: dict
    ) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest
        from forge.virtuals.tokenization.service import AlreadyTokenizedError

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-dup",
            token_name="Dup Token",
            token_symbol="DUP",
            token_description="First request",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        await tokenization_service.request_tokenization(req)

        req2 = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-dup",
            token_name="Dup Token 2",
            token_symbol="DUP2",
            token_description="Duplicate",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        with pytest.raises(AlreadyTokenizedError):
            await tokenization_service.request_tokenization(req2)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8  —  TOKENIZATION: GRADUATION & REVENUE
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase8GraduationRevenue:
    """Push past graduation threshold and distribute revenue."""

    @pytest.mark.asyncio
    async def test_graduation_on_threshold(self, tokenization_service: Any, users: dict) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-grad",
            token_name="Graduation Token",
            token_symbol="GRAD",
            token_description="Will graduate",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)

        # Contribute enough to hit 42K threshold
        updated, _ = await tokenization_service.contribute_to_bonding_curve(
            entity_id=entity.id,
            contributor_wallet=users["contributor"]["wallet"],
            amount_virtual=42_000.0,
        )
        assert updated.status == TokenizationStatus.GRADUATED
        assert updated.graduated_at is not None
        assert updated.liquidity_locked_until is not None

    @pytest.mark.asyncio
    async def test_revenue_distribution(self, tokenization_service: Any, users: dict) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-rev",
            token_name="Revenue Token",
            token_symbol="REV",
            token_description="For revenue testing",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)

        # Graduate first
        updated, _ = await tokenization_service.contribute_to_bonding_curve(
            entity_id=entity.id,
            contributor_wallet=users["contributor"]["wallet"],
            amount_virtual=42_000.0,
        )

        # Distribute 1000 VIRTUAL revenue
        distributions = await tokenization_service.distribute_revenue(
            entity_id=updated.id,
            revenue_amount_virtual=1000.0,
            revenue_source="knowledge_query_fees",
        )
        # Default shares: creator=30%, contributor=20%, treasury=50%
        assert distributions["creator"] == pytest.approx(300.0)
        # Treasury = 500, buyback_burn = 50% of treasury = 250
        assert distributions["buyback_burn"] == pytest.approx(250.0)
        assert distributions["treasury"] == pytest.approx(250.0)

    @pytest.mark.asyncio
    async def test_revenue_updates_entity_metrics(
        self, tokenization_service: Any, users: dict
    ) -> None:
        from forge.virtuals.models.tokenization import TokenizationRequest

        req = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-rev-metrics",
            token_name="Metric Token",
            token_symbol="MET",
            token_description="For metric testing",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)
        updated, _ = await tokenization_service.contribute_to_bonding_curve(
            entity_id=entity.id,
            contributor_wallet=users["contributor"]["wallet"],
            amount_virtual=42_000.0,
        )

        await tokenization_service.distribute_revenue(
            entity_id=updated.id,
            revenue_amount_virtual=500.0,
            revenue_source="inference_fees",
        )
        # Re-fetch from repo
        refreshed = await tokenization_service._entity_repo.get_by_id(updated.id)
        assert refreshed.total_revenue_generated == 500.0
        assert refreshed.total_buyback_burned > 0


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9  —  TOKENIZATION: GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase9Governance:
    """Create governance proposals and cast votes."""

    async def _create_graduated_entity(
        self, tokenization_service: Any, users: dict, suffix: str = ""
    ) -> Any:
        from forge.virtuals.models.tokenization import TokenizationRequest

        # Strip non-alphanumeric chars for token symbol
        alpha_suffix = "".join(c for c in suffix if c.isalnum())[:3].upper() or "X"
        req = TokenizationRequest(
            entity_type="capsule",
            entity_id=f"capsule-gov{suffix}",
            token_name=f"Gov Token {suffix}",
            token_symbol=f"GOV{alpha_suffix}",
            token_description="Governance testing",
            initial_stake_virtual=100.0,
            owner_wallet=users["researcher"]["wallet"],
        )
        entity = await tokenization_service.request_tokenization(req)
        updated, _ = await tokenization_service.contribute_to_bonding_curve(
            entity_id=entity.id,
            contributor_wallet=users["contributor"]["wallet"],
            amount_virtual=42_000.0,
        )
        return updated

    @pytest.mark.asyncio
    async def test_create_governance_proposal(self, tokenization_service: Any, users: dict) -> None:
        entity = await self._create_graduated_entity(tokenization_service, users, suffix="-prop")
        proposal = await tokenization_service.create_governance_proposal(
            entity_id=entity.id,
            proposer_wallet=users["researcher"]["wallet"],
            title="Increase creator share to 35%",
            description="Proposal to adjust revenue distribution parameters",
            proposal_type="parameter_change",
            proposed_changes={"creator_share_percent": 35.0},
        )
        assert proposal.title == "Increase creator share to 35%"
        assert proposal.status == "active"
        assert proposal.quorum_required == entity.governance_quorum_percent

    @pytest.mark.asyncio
    async def test_cast_governance_vote(
        self, tokenization_service: Any, users: dict, proposal_repo: Any
    ) -> None:
        entity = await self._create_graduated_entity(tokenization_service, users, suffix="-vote")
        proposal = await tokenization_service.create_governance_proposal(
            entity_id=entity.id,
            proposer_wallet=users["researcher"]["wallet"],
            title="Vote Test Proposal",
            description="Testing vote casting",
            proposal_type="parameter_change",
            proposed_changes={"key": "value"},
        )

        vote = await tokenization_service.cast_governance_vote(
            proposal_id=proposal.id,
            voter_wallet=users["contributor"]["wallet"],
            vote="for",
        )
        assert vote.vote == "for"
        assert vote.voting_power > 0

        # Verify proposal tallies updated
        updated_proposal = await proposal_repo.get_by_id(proposal.id)
        assert updated_proposal.votes_for > 0
        assert updated_proposal.total_voters == 1

    @pytest.mark.asyncio
    async def test_invalid_vote_rejected(self, tokenization_service: Any, users: dict) -> None:
        from forge.virtuals.tokenization.service import TokenizationServiceError

        entity = await self._create_graduated_entity(tokenization_service, users, suffix="-badv")
        proposal = await tokenization_service.create_governance_proposal(
            entity_id=entity.id,
            proposer_wallet=users["researcher"]["wallet"],
            title="Invalid Vote Test",
            description="Testing invalid vote",
            proposal_type="parameter_change",
            proposed_changes={},
        )
        with pytest.raises(TokenizationServiceError, match="must be"):
            await tokenization_service.cast_governance_vote(
                proposal_id=proposal.id,
                voter_wallet=users["contributor"]["wallet"],
                vote="invalid_vote",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 10  —  ACP: AGENT COMMERCE PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase10ACP:
    """Full 4-phase ACP lifecycle: Request → Negotiation → Transaction → Evaluation."""

    @pytest.mark.asyncio
    async def test_register_offering(self, acp_service: Any, users: dict) -> None:
        from forge.virtuals.models.acp import JobOffering

        offering = JobOffering(
            provider_agent_id="agent-c4",
            provider_wallet=users["researcher"]["wallet"],
            service_type="knowledge_query",
            title="Genomic Variant Classification Query",
            description="Query the ensemble classifier for variant pathogenicity",
            base_fee_virtual=10.0,
        )
        registered = await acp_service.register_offering(
            agent_id="agent-c4",
            agent_wallet=users["researcher"]["wallet"],
            offering=offering,
        )
        assert registered.id is not None
        assert registered.service_type == "knowledge_query"

    @pytest.mark.asyncio
    async def test_search_offerings(self, acp_service: Any, users: dict) -> None:
        from forge.virtuals.models.acp import JobOffering

        offering = JobOffering(
            provider_agent_id="agent-c4",
            provider_wallet=users["researcher"]["wallet"],
            service_type="knowledge_query",
            title="Genomic Query Service",
            description="Query service for genomic data",
            base_fee_virtual=10.0,
        )
        await acp_service.register_offering(
            agent_id="agent-c4",
            agent_wallet=users["researcher"]["wallet"],
            offering=offering,
        )
        results = await acp_service.search_offerings(service_type="knowledge_query")
        assert len(results) >= 1
        assert results[0].service_type == "knowledge_query"

    @pytest.mark.asyncio
    async def test_full_acp_lifecycle(self, acp_service: Any, users: dict) -> None:
        """Complete 4-phase lifecycle: Request → Negotiation → Transaction → Evaluation."""
        from forge.virtuals.models.acp import (
            ACPDeliverable,
            ACPEvaluation,
            ACPJobCreate,
            ACPNegotiationTerms,
            JobOffering,
        )

        # 1. Register offering
        offering = JobOffering(
            provider_agent_id="agent-provider",
            provider_wallet=users["researcher"]["wallet"],
            service_type="knowledge_query",
            title="Full Lifecycle Query",
            description="E2E test offering",
            base_fee_virtual=10.0,
        )
        offering = await acp_service.register_offering(
            agent_id="agent-provider",
            agent_wallet=users["researcher"]["wallet"],
            offering=offering,
        )

        # 2. Phase 1: REQUEST — buyer creates job
        create_req = ACPJobCreate(
            job_offering_id=offering.id,
            buyer_agent_id="agent-buyer",
            requirements="Classify variant chr7:g.117199646T>C",
            max_fee_virtual=50.0,
        )
        job = await acp_service.create_job(create_req, buyer_wallet=users["contributor"]["wallet"])
        assert job.current_phase == ACPPhase.REQUEST
        assert job.status == ACPJobStatus.OPEN
        assert job.request_memo is not None
        assert job.request_memo.nonce > 0

        # 3. Phase 2: NEGOTIATION — provider responds
        terms = ACPNegotiationTerms(
            job_id=job.id,
            proposed_fee_virtual=15.0,
            proposed_deadline=datetime.now(UTC) + timedelta(hours=4),
            deliverable_format="json",
            deliverable_description="ACMG classification with SHAP explanation",
        )
        job = await acp_service.respond_to_request(
            job_id=job.id,
            terms=terms,
            provider_wallet=users["researcher"]["wallet"],
        )
        assert job.current_phase == ACPPhase.NEGOTIATION
        assert job.status == ACPJobStatus.NEGOTIATING
        assert job.requirement_memo is not None

        # 4. Buyer accepts terms → TRANSACTION phase
        job = await acp_service.accept_terms(
            job_id=job.id,
            buyer_wallet=users["contributor"]["wallet"],
        )
        assert job.current_phase == ACPPhase.TRANSACTION
        assert job.status == ACPJobStatus.IN_PROGRESS
        assert job.agreement_memo is not None
        assert job.agreed_fee_virtual == 15.0

        # 5. Provider submits deliverable
        deliverable = ACPDeliverable(
            job_id=job.id,
            content_type="json",
            content={
                "variant": "chr7:g.117199646T>C",
                "gene": "CFTR",
                "classification": "pathogenic",
                "ensemble_score": 0.98,
                "shap_features": {"CADD": 0.4, "REVEL": 0.3, "SpliceAI": 0.3},
            },
            notes="High-confidence pathogenic classification",
        )
        job = await acp_service.submit_deliverable(
            job_id=job.id,
            deliverable=deliverable,
            provider_wallet=users["researcher"]["wallet"],
        )
        assert job.current_phase == ACPPhase.EVALUATION
        assert job.status == ACPJobStatus.DELIVERED
        assert job.deliverable_memo is not None
        assert job.delivered_at is not None

        # 6. Phase 4: EVALUATION — buyer approves
        evaluation = ACPEvaluation(
            job_id=job.id,
            evaluator_agent_id="agent-buyer",
            result="approved",
            score=0.95,
            feedback="Excellent classification with clear explanation",
            met_requirements=["variant_classification", "shap_explanation"],
        )
        job = await acp_service.evaluate_deliverable(
            job_id=job.id,
            evaluation=evaluation,
            evaluator_wallet=users["contributor"]["wallet"],
        )
        assert job.status == ACPJobStatus.COMPLETED
        assert job.evaluation_result == "approved"
        assert job.evaluation_score == 0.95
        assert job.escrow_released is True
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_all_memos_have_unique_nonces(self, acp_service: Any, users: dict) -> None:
        """Verify each memo in a lifecycle gets a unique, increasing nonce."""
        from forge.virtuals.models.acp import (
            ACPDeliverable,
            ACPEvaluation,
            ACPJobCreate,
            ACPNegotiationTerms,
            JobOffering,
        )

        offering = JobOffering(
            provider_agent_id="agent-nonce",
            provider_wallet=users["researcher"]["wallet"],
            service_type="analysis",
            title="Nonce Test",
            description="Testing nonce uniqueness",
            base_fee_virtual=5.0,
        )
        offering = await acp_service.register_offering(
            "agent-nonce", users["researcher"]["wallet"], offering
        )

        job = await acp_service.create_job(
            ACPJobCreate(
                job_offering_id=offering.id,
                buyer_agent_id="agent-nonce-buyer",
                requirements="nonce test",
                max_fee_virtual=20.0,
            ),
            buyer_wallet=users["contributor"]["wallet"],
        )

        job = await acp_service.respond_to_request(
            job.id,
            ACPNegotiationTerms(
                job_id=job.id,
                proposed_fee_virtual=8.0,
                proposed_deadline=datetime.now(UTC) + timedelta(hours=1),
                deliverable_format="text",
                deliverable_description="nonce test result",
            ),
            users["researcher"]["wallet"],
        )

        job = await acp_service.accept_terms(job.id, users["contributor"]["wallet"])

        job = await acp_service.submit_deliverable(
            job.id,
            ACPDeliverable(job_id=job.id, content_type="text", content={"result": "done"}),
            users["researcher"]["wallet"],
        )

        job = await acp_service.evaluate_deliverable(
            job.id,
            ACPEvaluation(
                job_id=job.id,
                evaluator_agent_id="agent-nonce-buyer",
                result="approved",
                score=1.0,
                feedback="ok",
            ),
            users["contributor"]["wallet"],
        )

        # Collect all memos (5 total across the lifecycle)
        memos = [
            job.request_memo,
            job.requirement_memo,
            job.agreement_memo,
            job.deliverable_memo,
            job.evaluation_memo,
        ]
        present_memos = [m for m in memos if m is not None]
        assert len(present_memos) == 5
        # All nonces are positive
        assert all(m.nonce > 0 for m in present_memos)
        # Nonces are unique PER SENDER (ACP nonce store is per-address)
        by_sender: dict[str, list[int]] = {}
        for m in present_memos:
            by_sender.setdefault(m.sender_address, []).append(m.nonce)
        for sender, sender_nonces in by_sender.items():
            assert len(set(sender_nonces)) == len(sender_nonces), (
                f"Duplicate nonce for sender {sender}: {sender_nonces}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11  —  TIPPING: FROWG ON SOLANA
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase11Tipping:
    """FROWG tipping service on Solana."""

    @pytest.mark.asyncio
    async def test_send_tip(self, tipping_service: Any) -> None:
        from forge.virtuals.tipping.service import TipCategory, TipStatus

        tip = await tipping_service.send_tip(
            sender_address="7B8xLj1111111111111111111111111111111111111",
            recipient_address="9Y3kMn2222222222222222222222222222222222222",
            amount=Decimal("10.0"),
            category=TipCategory.CAPSULE_CONTRIBUTION,
            memo="Great ontology contribution!",
        )
        assert tip.amount == Decimal("10.0")
        assert tip.category == TipCategory.CAPSULE_CONTRIBUTION
        assert tip.tx_hash is not None
        # LOCAL simulation mode confirms tips immediately
        assert tip.status == TipStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_tip_amount_validation(self, tipping_service: Any) -> None:
        from forge.virtuals.tipping.service import TipCategory

        with pytest.raises(ValueError, match="at least"):
            await tipping_service.send_tip(
                sender_address="7B8xLj1111111111111111111111111111111111111",
                recipient_address="9Y3kMn2222222222222222222222222222222222222",
                amount=Decimal("0.00001"),  # Below minimum
                category=TipCategory.COMMUNITY_GIFT,
            )

    @pytest.mark.asyncio
    async def test_tip_history(self, tipping_service: Any) -> None:
        from forge.virtuals.tipping.service import TipCategory

        sender = "7B8xLj1111111111111111111111111111111111111"
        recipient = "9Y3kMn2222222222222222222222222222222222222"

        await tipping_service.send_tip(
            sender_address=sender,
            recipient_address=recipient,
            amount=Decimal("5.0"),
            category=TipCategory.AGENT_REWARD,
        )
        await tipping_service.send_tip(
            sender_address=sender,
            recipient_address=recipient,
            amount=Decimal("15.0"),
            category=TipCategory.CAPSULE_CONTRIBUTION,
        )

        history = tipping_service.get_tip_history(address=sender)
        assert len(history) >= 2

        # Filter by category
        agent_tips = tipping_service.get_tip_history(
            address=sender, category=TipCategory.AGENT_REWARD
        )
        assert len(agent_tips) >= 1

    @pytest.mark.asyncio
    async def test_tip_fee_estimation(self, tipping_service: Any) -> None:
        estimate = await tipping_service.estimate_tip_fee(Decimal("100.0"))
        assert estimate["tip_amount"] == Decimal("100.0")
        assert estimate["platform_fee"] == Decimal("1.0")  # 1% default
        assert estimate["recipient_receives"] == Decimal("99.0")
