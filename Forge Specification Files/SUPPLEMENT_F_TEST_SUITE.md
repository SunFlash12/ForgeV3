# Forge V3 - Supplement: Test Suite Examples

**Purpose:** Provide test patterns for Phases 3-8 to help AI assistants understand the expected behavior and testing patterns.

---

## 1. Phase 3 Tests - Overlay System

```python
# tests/unit/test_overlay_service.py
"""
Unit tests for OverlayService.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from forge.core.overlays.service import OverlayService
from forge.core.overlays.repository import OverlayRepository
from forge.core.overlays.runtime import WasmRuntime
from forge.infrastructure.storage.client import ObjectStorageClient
from forge.models.overlay import (
    Overlay,
    OverlayCreate,
    OverlayManifest,
    OverlayCapability,
    OverlayInvocation,
    OverlayResult,
    OverlayState,
)
from forge.models.user import User
from forge.models.base import TrustLevel
from forge.exceptions import NotFoundError, AuthorizationError, ValidationError


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=OverlayRepository)


@pytest.fixture
def mock_runtime():
    runtime = AsyncMock(spec=WasmRuntime)
    runtime.compile_module = MagicMock()  # Sync method
    return runtime


@pytest.fixture
def mock_storage():
    return AsyncMock(spec=ObjectStorageClient)


@pytest.fixture
def overlay_service(mock_repository, mock_runtime, mock_storage):
    return OverlayService(mock_repository, mock_runtime, mock_storage)


@pytest.fixture
def test_user():
    return User(
        id=uuid4(),
        email="test@example.com",
        trust_level=TrustLevel.STANDARD,
        roles=["user"],
    )


@pytest.fixture
def admin_user():
    return User(
        id=uuid4(),
        email="admin@example.com",
        trust_level=TrustLevel.CORE,
        roles=["admin"],
    )


@pytest.fixture
def sample_overlay():
    return Overlay(
        id=uuid4(),
        name="test-overlay",
        version="1.0.0",
        description="Test overlay",
        author="Test Author",
        state=OverlayState.ACTIVE,
        trust_level=TrustLevel.STANDARD,
        capabilities=[OverlayCapability(name="capsule:read")],
        entry_points=["process", "analyze"],
        wasm_key="overlays/test-overlay/1.0.0/abc123.wasm",
        wasm_hash="abc123",
    )


class TestOverlayServiceRegister:
    """Tests for overlay registration."""
    
    async def test_register_basic_overlay(
        self, overlay_service, mock_repository, mock_runtime, mock_storage, test_user
    ):
        """Test registering an overlay with basic capabilities."""
        manifest = OverlayManifest(
            name="test-overlay",
            version="1.0.0",
            description="Test description",
            author="Test Author",
            capabilities=[OverlayCapability(name="capsule:read")],
            entry_points=["process"],
        )
        
        wasm_binary = b"\x00asm\x01\x00\x00\x00"  # Minimal WASM header
        
        data = OverlayCreate(
            manifest=manifest,
            wasm_binary=wasm_binary,
        )
        
        # Mock the repository create
        mock_repository.create.return_value = Overlay(
            id=uuid4(),
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            author=manifest.author,
            state=OverlayState.PENDING,
            trust_level=TrustLevel.SANDBOX,
            wasm_key="overlays/test-overlay/1.0.0/hash.wasm",
            wasm_hash="somehash",
        )
        
        result = await overlay_service.register(data, test_user)
        
        # Verify compilation was attempted (validates WASM)
        mock_runtime.compile_module.assert_called_once()
        
        # Verify storage upload
        mock_storage.put.assert_called_once()
        
        # Verify repository create
        mock_repository.create.assert_called_once()
        
        # New overlays start in PENDING
        assert result.state == OverlayState.PENDING
    
    async def test_register_overlay_with_privileged_capabilities_gets_sandbox(
        self, overlay_service, mock_repository, mock_runtime, mock_storage, test_user
    ):
        """Overlays requesting privileged capabilities start in sandbox."""
        manifest = OverlayManifest(
            name="privileged-overlay",
            version="1.0.0",
            description="Overlay with write capability",
            author="Test",
            capabilities=[OverlayCapability(name="capsule:write")],  # Privileged
        )
        
        data = OverlayCreate(
            manifest=manifest,
            wasm_binary=b"\x00asm\x01\x00\x00\x00",
        )
        
        mock_repository.create.return_value = Overlay(
            id=uuid4(),
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            author=manifest.author,
            state=OverlayState.PENDING,
            trust_level=TrustLevel.SANDBOX,
            wasm_key="key",
            wasm_hash="hash",
        )
        
        result = await overlay_service.register(data, test_user)
        
        # Check that create was called with SANDBOX trust level
        call_kwargs = mock_repository.create.call_args.kwargs
        assert call_kwargs["trust_level"] == TrustLevel.SANDBOX


class TestOverlayServiceInvoke:
    """Tests for overlay invocation."""
    
    async def test_invoke_active_overlay_succeeds(
        self, overlay_service, mock_repository, mock_runtime, mock_storage,
        test_user, sample_overlay
    ):
        """Test successful invocation of an active overlay."""
        mock_repository.get_by_id.return_value = sample_overlay
        mock_storage.get.return_value = b"\x00asm\x01\x00\x00\x00"
        mock_runtime.invoke.return_value = OverlayResult(
            success=True,
            result={"processed": True},
            execution_time_ms=50,
            fuel_consumed=1000,
        )
        
        invocation = OverlayInvocation(
            function="process",
            args={"input": "test"},
        )
        
        result = await overlay_service.invoke(sample_overlay.id, invocation, test_user)
        
        assert result.success is True
        assert result.result == {"processed": True}
        mock_repository.record_invocation.assert_called_once()
    
    async def test_invoke_inactive_overlay_fails(
        self, overlay_service, mock_repository, test_user
    ):
        """Test that invoking inactive overlay raises ValidationError."""
        inactive_overlay = Overlay(
            id=uuid4(),
            name="inactive",
            version="1.0.0",
            description="Inactive overlay",
            author="Test",
            state=OverlayState.PENDING,  # Not active!
            trust_level=TrustLevel.STANDARD,
            wasm_key="key",
            wasm_hash="hash",
        )
        mock_repository.get_by_id.return_value = inactive_overlay
        
        invocation = OverlayInvocation(function="process")
        
        with pytest.raises(ValidationError) as exc_info:
            await overlay_service.invoke(inactive_overlay.id, invocation, test_user)
        
        assert "not active" in str(exc_info.value).lower()
    
    async def test_invoke_with_insufficient_trust_fails(
        self, overlay_service, mock_repository, test_user
    ):
        """Test that user can't invoke overlay requiring higher trust."""
        high_trust_overlay = Overlay(
            id=uuid4(),
            name="high-trust",
            version="1.0.0",
            description="High trust overlay",
            author="Test",
            state=OverlayState.ACTIVE,
            trust_level=TrustLevel.CORE,  # Requires CORE
            wasm_key="key",
            wasm_hash="hash",
        )
        mock_repository.get_by_id.return_value = high_trust_overlay
        
        # User has STANDARD trust, overlay requires CORE
        invocation = OverlayInvocation(function="process")
        
        with pytest.raises(AuthorizationError):
            await overlay_service.invoke(high_trust_overlay.id, invocation, test_user)
    
    async def test_invoke_invalid_entry_point_fails(
        self, overlay_service, mock_repository, test_user, sample_overlay
    ):
        """Test that invoking non-existent entry point fails."""
        mock_repository.get_by_id.return_value = sample_overlay
        
        invocation = OverlayInvocation(
            function="nonexistent",  # Not in entry_points
        )
        
        with pytest.raises(ValidationError) as exc_info:
            await overlay_service.invoke(sample_overlay.id, invocation, test_user)
        
        assert "not a valid entry point" in str(exc_info.value)


class TestOverlayServiceActivate:
    """Tests for overlay activation."""
    
    async def test_admin_can_activate_pending_overlay(
        self, overlay_service, mock_repository, admin_user
    ):
        """Test that admin can activate a pending overlay."""
        pending_overlay = Overlay(
            id=uuid4(),
            name="pending",
            version="1.0.0",
            description="Pending",
            author="Test",
            state=OverlayState.PENDING,
            trust_level=TrustLevel.SANDBOX,
            wasm_key="key",
            wasm_hash="hash",
        )
        mock_repository.get_by_id.return_value = pending_overlay
        mock_repository.update_state.return_value = Overlay(
            **{**pending_overlay.model_dump(), "state": OverlayState.ACTIVE}
        )
        
        result = await overlay_service.activate(pending_overlay.id, admin_user)
        
        assert result.state == OverlayState.ACTIVE
        mock_repository.update_state.assert_called_once_with(
            pending_overlay.id, OverlayState.ACTIVE
        )
    
    async def test_non_admin_cannot_activate_overlay(
        self, overlay_service, mock_repository, test_user
    ):
        """Test that non-admin cannot activate overlays."""
        pending_overlay = Overlay(
            id=uuid4(),
            name="pending",
            version="1.0.0",
            description="Pending",
            author="Test",
            state=OverlayState.PENDING,
            trust_level=TrustLevel.SANDBOX,
            wasm_key="key",
            wasm_hash="hash",
        )
        mock_repository.get_by_id.return_value = pending_overlay
        
        with pytest.raises(AuthorizationError):
            await overlay_service.activate(pending_overlay.id, test_user)
```

---

## 2. Phase 4 Tests - Governance System

```python
# tests/unit/test_governance_service.py
"""
Unit tests for GovernanceService.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from forge.core.governance.service import GovernanceService, TRUST_VOTE_WEIGHTS
from forge.core.governance.repository import GovernanceRepository
from forge.core.users.repository import UserRepository
from forge.models.governance import (
    Proposal,
    ProposalCreate,
    Vote,
    VoteCreate,
    ProposalStatus,
    ProposalType,
)
from forge.models.user import User
from forge.models.base import TrustLevel, VoteDecision
from forge.exceptions import AuthorizationError, ValidationError


@pytest.fixture
def mock_gov_repository():
    return AsyncMock(spec=GovernanceRepository)


@pytest.fixture
def mock_user_repository():
    repo = AsyncMock(spec=UserRepository)
    # Default: return 3 users for eligible weight calculation
    repo.list_active.return_value = [
        User(id=uuid4(), email="a@test.com", trust_level=TrustLevel.STANDARD),
        User(id=uuid4(), email="b@test.com", trust_level=TrustLevel.TRUSTED),
        User(id=uuid4(), email="c@test.com", trust_level=TrustLevel.CORE),
    ]
    return repo


@pytest.fixture
def governance_service(mock_gov_repository, mock_user_repository):
    return GovernanceService(mock_gov_repository, mock_user_repository)


@pytest.fixture
def standard_user():
    return User(
        id=uuid4(),
        email="standard@test.com",
        trust_level=TrustLevel.STANDARD,
        roles=["user"],
    )


@pytest.fixture
def trusted_user():
    return User(
        id=uuid4(),
        email="trusted@test.com",
        trust_level=TrustLevel.TRUSTED,
        roles=["trusted"],
    )


@pytest.fixture
def sample_proposal():
    return Proposal(
        id=uuid4(),
        title="Test Proposal",
        description="Test description",
        type=ProposalType.CONFIGURATION,
        status=ProposalStatus.ACTIVE,
        proposer_id=uuid4(),
        voting_ends_at=datetime.now(timezone.utc) + timedelta(hours=24),
        quorum_percentage=0.3,
        approval_threshold=0.5,
        votes_for=0,
        votes_against=0,
        votes_abstain=0,
        total_eligible_weight=9.0,  # 1 + 3 + 5 = 9 (standard + trusted + core)
    )


class TestProposalCreation:
    """Tests for creating proposals."""
    
    async def test_trusted_user_can_create_config_proposal(
        self, governance_service, mock_gov_repository, trusted_user
    ):
        """Test that trusted users can create configuration proposals."""
        data = ProposalCreate(
            title="Change rate limit",
            description="Increase rate limit for trusted users",
            type=ProposalType.CONFIGURATION,
            payload={"config_key": "rate_limit", "new_value": "2000"},
        )
        
        mock_gov_repository.create_proposal.return_value = Proposal(
            id=uuid4(),
            title=data.title,
            description=data.description,
            type=data.type,
            status=ProposalStatus.DRAFT,
            proposer_id=trusted_user.id,
            voting_ends_at=datetime.now(timezone.utc) + timedelta(hours=72),
        )
        
        result = await governance_service.create_proposal(data, trusted_user)
        
        assert result.status == ProposalStatus.DRAFT
        mock_gov_repository.create_proposal.assert_called_once()
    
    async def test_standard_user_cannot_create_config_proposal(
        self, governance_service, standard_user
    ):
        """Test that standard users cannot create config proposals."""
        data = ProposalCreate(
            title="Change config",
            description="This should fail",
            type=ProposalType.CONFIGURATION,
        )
        
        with pytest.raises(AuthorizationError) as exc_info:
            await governance_service.create_proposal(data, standard_user)
        
        assert "trust level" in str(exc_info.value).lower()


class TestVoting:
    """Tests for casting votes."""
    
    async def test_cast_vote_calculates_correct_weight(
        self, governance_service, mock_gov_repository, trusted_user, sample_proposal
    ):
        """Test that vote weight is calculated correctly based on trust level."""
        mock_gov_repository.get_proposal.return_value = sample_proposal
        mock_gov_repository.get_vote.return_value = None  # No existing vote
        mock_gov_repository.create_vote.return_value = Vote(
            id=uuid4(),
            proposal_id=sample_proposal.id,
            voter_id=trusted_user.id,
            decision=VoteDecision.FOR,
            weight=TRUST_VOTE_WEIGHTS[TrustLevel.TRUSTED],
        )
        
        vote_data = VoteCreate(decision=VoteDecision.FOR)
        
        result = await governance_service.cast_vote(
            sample_proposal.id, vote_data, trusted_user
        )
        
        # TRUSTED users have weight of 3.0
        assert result.weight == 3.0
        mock_gov_repository.create_vote.assert_called_once()
    
    async def test_quarantined_user_cannot_vote(
        self, governance_service, mock_gov_repository, sample_proposal
    ):
        """Test that quarantined users cannot vote."""
        quarantined_user = User(
            id=uuid4(),
            email="quarantined@test.com",
            trust_level=TrustLevel.QUARANTINE,
            roles=["user"],
        )
        mock_gov_repository.get_proposal.return_value = sample_proposal
        
        vote_data = VoteCreate(decision=VoteDecision.FOR)
        
        with pytest.raises(AuthorizationError):
            await governance_service.cast_vote(
                sample_proposal.id, vote_data, quarantined_user
            )
    
    async def test_cannot_vote_on_closed_proposal(
        self, governance_service, mock_gov_repository, trusted_user
    ):
        """Test that voting on closed proposals fails."""
        closed_proposal = Proposal(
            id=uuid4(),
            title="Closed",
            description="Already closed",
            type=ProposalType.CONFIGURATION,
            status=ProposalStatus.CLOSED,  # Not ACTIVE
            proposer_id=uuid4(),
        )
        mock_gov_repository.get_proposal.return_value = closed_proposal
        
        vote_data = VoteCreate(decision=VoteDecision.FOR)
        
        with pytest.raises(ValidationError) as exc_info:
            await governance_service.cast_vote(
                closed_proposal.id, vote_data, trusted_user
            )
        
        assert "not open" in str(exc_info.value).lower()


class TestProposalClosure:
    """Tests for closing proposals and determining outcomes."""
    
    async def test_proposal_passes_with_quorum_and_majority(
        self, governance_service, mock_gov_repository
    ):
        """Test that proposal passes when quorum is met and majority votes for."""
        proposal = Proposal(
            id=uuid4(),
            title="Passing Proposal",
            description="Should pass",
            type=ProposalType.CONFIGURATION,
            status=ProposalStatus.ACTIVE,
            proposer_id=uuid4(),
            quorum_percentage=0.3,
            approval_threshold=0.5,
            votes_for=5.0,
            votes_against=1.0,
            votes_abstain=1.0,
            total_eligible_weight=10.0,
        )
        mock_gov_repository.get_proposal.return_value = proposal
        mock_gov_repository.close_proposal.return_value = Proposal(
            **{**proposal.model_dump(), "status": ProposalStatus.APPROVED}
        )
        
        result = await governance_service.close_voting(proposal.id)
        
        # Participation: 7/10 = 70% > 30% quorum
        # Approval: 5/6 = 83% > 50% threshold
        assert result.status == ProposalStatus.APPROVED
        mock_gov_repository.close_proposal.assert_called_with(
            proposal.id, ProposalStatus.APPROVED
        )
    
    async def test_proposal_fails_without_quorum(
        self, governance_service, mock_gov_repository
    ):
        """Test that proposal fails if quorum is not met."""
        proposal = Proposal(
            id=uuid4(),
            title="No Quorum",
            description="Insufficient participation",
            type=ProposalType.CONFIGURATION,
            status=ProposalStatus.ACTIVE,
            proposer_id=uuid4(),
            quorum_percentage=0.5,  # 50% quorum required
            approval_threshold=0.5,
            votes_for=2.0,
            votes_against=0.0,
            votes_abstain=0.0,
            total_eligible_weight=10.0,  # Only 2/10 = 20% participated
        )
        mock_gov_repository.get_proposal.return_value = proposal
        mock_gov_repository.close_proposal.return_value = Proposal(
            **{**proposal.model_dump(), "status": ProposalStatus.REJECTED}
        )
        
        result = await governance_service.close_voting(proposal.id)
        
        assert result.status == ProposalStatus.REJECTED
```

---

## 3. Phase 5 Tests - Security

```python
# tests/unit/test_auth_service.py
"""
Unit tests for AuthService.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from forge.security.auth import AuthService
from forge.models.user import User, UserCreate
from forge.models.base import TrustLevel
from forge.exceptions import AuthenticationError, ValidationError


@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def auth_service(mock_user_repo, mock_redis):
    return AuthService(mock_user_repo, mock_redis)


@pytest.fixture
def sample_user():
    return User(
        id=uuid4(),
        email="test@example.com",
        password_hash="$argon2id$...",  # Would be real hash
        trust_level=TrustLevel.STANDARD,
        is_active=True,
        failed_login_attempts=0,
    )


class TestPasswordHashing:
    """Tests for password hashing."""
    
    def test_hash_password_returns_argon2_hash(self, auth_service):
        """Test that password is hashed with Argon2id."""
        password = "SecurePassword123"
        
        hash_result = auth_service.hash_password(password)
        
        assert hash_result.startswith("$argon2id$")
        assert password not in hash_result
    
    def test_verify_password_succeeds_with_correct_password(self, auth_service):
        """Test password verification with correct password."""
        password = "SecurePassword123"
        hash_result = auth_service.hash_password(password)
        
        assert auth_service.verify_password(password, hash_result) is True
    
    def test_verify_password_fails_with_incorrect_password(self, auth_service):
        """Test password verification fails with wrong password."""
        password = "SecurePassword123"
        wrong_password = "WrongPassword456"
        hash_result = auth_service.hash_password(password)
        
        assert auth_service.verify_password(wrong_password, hash_result) is False


class TestAuthentication:
    """Tests for user authentication."""
    
    async def test_authenticate_success_returns_tokens(
        self, auth_service, mock_user_repo, mock_redis, sample_user
    ):
        """Test successful authentication returns user and tokens."""
        mock_user_repo.get_by_email.return_value = sample_user
        
        # Mock password verification
        with patch.object(auth_service, 'verify_password', return_value=True):
            user, access_token, refresh_token = await auth_service.authenticate(
                email="test@example.com",
                password="password",
                ip_address="127.0.0.1",
            )
        
        assert user.id == sample_user.id
        assert access_token is not None
        assert refresh_token is not None
        mock_user_repo.clear_failed_attempts.assert_called_once()
    
    async def test_authenticate_wrong_password_increments_failures(
        self, auth_service, mock_user_repo, sample_user
    ):
        """Test that wrong password increments failed attempts."""
        mock_user_repo.get_by_email.return_value = sample_user
        
        with patch.object(auth_service, 'verify_password', return_value=False):
            with pytest.raises(AuthenticationError):
                await auth_service.authenticate(
                    email="test@example.com",
                    password="wrong",
                    ip_address="127.0.0.1",
                )
        
        mock_user_repo.update_failed_attempts.assert_called_once()
    
    async def test_authenticate_locked_account_fails(
        self, auth_service, mock_user_repo
    ):
        """Test that locked accounts cannot authenticate."""
        locked_user = User(
            id=uuid4(),
            email="locked@example.com",
            password_hash="$argon2id$...",
            trust_level=TrustLevel.STANDARD,
            is_active=True,
            failed_login_attempts=5,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        mock_user_repo.get_by_email.return_value = locked_user
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate(
                email="locked@example.com",
                password="password",
                ip_address="127.0.0.1",
            )
        
        assert "locked" in str(exc_info.value).lower()


class TestPasswordValidation:
    """Tests for password strength validation."""
    
    def test_password_too_short_fails(self, auth_service):
        """Test that short passwords are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            auth_service._validate_password_strength("Short1")
        
        assert "at least 8" in str(exc_info.value)
    
    def test_password_without_uppercase_fails(self, auth_service):
        """Test that passwords without uppercase are rejected."""
        with pytest.raises(ValidationError):
            auth_service._validate_password_strength("lowercase123")
    
    def test_password_without_digit_fails(self, auth_service):
        """Test that passwords without digits are rejected."""
        with pytest.raises(ValidationError):
            auth_service._validate_password_strength("NoDigitsHere")
    
    def test_valid_password_passes(self, auth_service):
        """Test that valid passwords pass validation."""
        # Should not raise
        auth_service._validate_password_strength("ValidPass123")
```

---

## 4. Phase 6 Tests - API Routes

```python
# tests/integration/test_capsule_api.py
"""
Integration tests for capsule API endpoints.
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4

from forge.main import create_app


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Mock authentication headers."""
    # In real tests, you'd generate a valid JWT
    return {"Authorization": "Bearer test-token"}


class TestCapsuleEndpoints:
    """Tests for capsule API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_capsule_returns_201(self, client, auth_headers):
        """Test creating a capsule returns 201 and the capsule."""
        response = await client.post(
            "/api/v1/capsules",
            json={
                "content": "Test capsule content",
                "type": "knowledge",
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "data" in data
        assert data["data"]["content"] == "Test capsule content"
    
    @pytest.mark.asyncio
    async def test_get_capsule_returns_capsule(self, client, auth_headers):
        """Test getting a capsule by ID."""
        # First create a capsule
        create_response = await client.post(
            "/api/v1/capsules",
            json={"content": "Test", "type": "knowledge"},
            headers=auth_headers,
        )
        capsule_id = create_response.json()["data"]["id"]
        
        # Then retrieve it
        response = await client.get(
            f"/api/v1/capsules/{capsule_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert response.json()["data"]["id"] == capsule_id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_capsule_returns_404(self, client, auth_headers):
        """Test that getting a non-existent capsule returns 404."""
        fake_id = str(uuid4())
        
        response = await client.get(
            f"/api/v1/capsules/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_search_capsules_returns_results(self, client, auth_headers):
        """Test semantic search for capsules."""
        response = await client.post(
            "/api/v1/capsules/search",
            json={
                "query": "test query",
                "limit": 5,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
    
    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, client):
        """Test that requests without auth return 401."""
        response = await client.get("/api/v1/capsules")
        
        assert response.status_code == 401
```

---

## 5. Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=forge --cov-report=html

# Run specific test file
pytest tests/unit/test_capsule_service.py -v

# Run tests matching a pattern
pytest -k "test_create" -v

# Run with parallel execution
pytest tests/ -v -n auto
```
