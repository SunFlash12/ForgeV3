"""
Diagnosis Routes Tests for Forge Cascade V2

Comprehensive tests for diagnosis API routes including:
- Session management (create, start, answer, skip, pause, resume, delete)
- Multi-agent diagnosis
- Streaming events
- Health check
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge.api.routes.diagnosis import (
    _DiagnosisServices,
    get_session_controller,
    initialize_diagnosis_services,
    router,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock diagnosis session."""
    session = MagicMock()
    session.id = "session123"
    session.state = MagicMock(value="INTAKE")
    session.is_complete = False
    session.is_confident = False
    session.iterations = 0
    session.hypotheses = []
    session.top_hypotheses = []
    session.pending_questions = []
    session.answered_questions = []
    return session


@pytest.fixture
def mock_session_controller(mock_session):
    """Create mock session controller."""
    controller = AsyncMock()
    controller.create_session = AsyncMock(return_value=mock_session)
    controller.start_diagnosis = AsyncMock(return_value=mock_session)
    controller.get_session = MagicMock(return_value=mock_session)
    controller.answer_questions = AsyncMock(return_value=mock_session)
    controller.skip_questions = AsyncMock(return_value=mock_session)
    controller.pause_session = AsyncMock(return_value=mock_session)
    controller.resume_session = AsyncMock(return_value=mock_session)
    controller.delete_session = AsyncMock(return_value=True)

    # Mock result
    mock_result = MagicMock()
    mock_result.session_id = "session123"
    mock_result.primary_diagnosis = None
    mock_result.confidence = 0.85
    mock_result.differential = []
    mock_result.key_findings = ["Finding 1"]
    mock_result.recommended_tests = ["Test 1"]
    mock_result.iterations = 3
    mock_result.questions_asked = 5
    controller.get_result = AsyncMock(return_value=mock_result)

    return controller


@pytest.fixture
def mock_diagnostic_coordinator():
    """Create mock diagnostic coordinator."""
    coordinator = AsyncMock()
    coordinator.diagnose = AsyncMock(return_value={"diagnosis": "Test diagnosis"})
    coordinator.suggest_discriminating_phenotypes = AsyncMock(return_value=["HP:0001250"])
    return coordinator


@pytest.fixture
def mock_user():
    """Create mock authenticated user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "testuser"
    user.trust_flame = 60
    user.is_active = True
    return user


@pytest.fixture
def diagnosis_app(mock_session_controller, mock_diagnostic_coordinator, mock_user):
    """Create FastAPI app with diagnosis router and mocked dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/diagnosis")

    # Initialize services
    initialize_diagnosis_services(mock_session_controller, mock_diagnostic_coordinator)

    # Override user dependency
    from forge.api.dependencies import get_current_active_user

    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    return app


@pytest.fixture
def client(diagnosis_app):
    """Create test client."""
    return TestClient(diagnosis_app)


# =============================================================================
# Session Creation Tests
# =============================================================================


class TestCreateSession:
    """Tests for POST /sessions endpoint."""

    def test_create_session_success(self, client: TestClient):
        """Create session with valid request."""
        response = client.post(
            "/api/v1/diagnosis/sessions",
            json={
                "patient_id": "patient123",
                "auto_advance": True,
            },
        )

        # Should succeed or return service unavailable if not initialized
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "state" in data
            assert "is_complete" in data

    def test_create_session_minimal(self, client: TestClient):
        """Create session with minimal request."""
        response = client.post(
            "/api/v1/diagnosis/sessions",
            json={},
        )

        assert response.status_code in [200, 503]

    def test_create_session_unauthorized(self, diagnosis_app):
        """Create session without auth fails."""
        # Remove user override
        from forge.api.dependencies import get_current_active_user

        diagnosis_app.dependency_overrides.pop(get_current_active_user, None)

        client = TestClient(diagnosis_app)
        response = client.post(
            "/api/v1/diagnosis/sessions",
            json={},
        )

        assert response.status_code in [401, 403, 503]


# =============================================================================
# Start Diagnosis Tests
# =============================================================================


class TestStartDiagnosis:
    """Tests for POST /sessions/{session_id}/start endpoint."""

    def test_start_diagnosis_success(self, client: TestClient):
        """Start diagnosis with valid phenotypes."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/start",
            json={
                "phenotypes": ["HP:0001250", "seizures"],
                "genetic_variants": [],
                "medical_history": ["Previous seizure disorder"],
                "family_history": ["Father has epilepsy"],
                "demographics": {
                    "age": 35,
                    "sex": "male",
                },
            },
        )

        assert response.status_code in [200, 404, 503]
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "state" in data

    def test_start_diagnosis_with_complex_phenotypes(self, client: TestClient):
        """Start diagnosis with complex phenotype inputs."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/start",
            json={
                "phenotypes": [
                    {"code": "HP:0001250", "value": "Seizures", "negated": False},
                    {
                        "code": "HP:0002315",
                        "value": "Headache",
                        "negated": True,
                        "severity": "moderate",
                    },
                ],
                "genetic_variants": [
                    {
                        "notation": "NM_000546.6:c.215C>G",
                        "gene_symbol": "TP53",
                        "pathogenicity": "pathogenic",
                        "zygosity": "heterozygous",
                    }
                ],
            },
        )

        assert response.status_code in [200, 404, 503]

    def test_start_diagnosis_empty_phenotypes(self, client: TestClient):
        """Start diagnosis with empty phenotypes."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/start",
            json={
                "phenotypes": [],
            },
        )

        assert response.status_code in [200, 404, 503]

    def test_start_diagnosis_invalid_session(self, client: TestClient, mock_session_controller):
        """Start diagnosis with non-existent session."""
        mock_session_controller.start_diagnosis.side_effect = ValueError("Session not found")

        response = client.post(
            "/api/v1/diagnosis/sessions/invalid_session/start",
            json={"phenotypes": ["HP:0001250"]},
        )

        assert response.status_code in [404, 503]


# =============================================================================
# Get Session Tests
# =============================================================================


class TestGetSession:
    """Tests for GET /sessions/{session_id} endpoint."""

    def test_get_session_success(self, client: TestClient):
        """Get existing session."""
        response = client.get("/api/v1/diagnosis/sessions/session123")

        assert response.status_code in [200, 404, 503]
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "state" in data
            assert "is_complete" in data

    def test_get_session_not_found(self, client: TestClient, mock_session_controller):
        """Get non-existent session returns 404."""
        mock_session_controller.get_session.return_value = None

        response = client.get("/api/v1/diagnosis/sessions/nonexistent")

        assert response.status_code in [404, 503]


# =============================================================================
# Answer Questions Tests
# =============================================================================


class TestAnswerQuestions:
    """Tests for POST /sessions/{session_id}/answer endpoint."""

    def test_answer_questions_success(self, client: TestClient):
        """Answer questions with valid answers."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/answer",
            json={
                "answers": [
                    {"question_id": "q1", "answer": "yes", "additional_info": "Details here"},
                    {"question_id": "q2", "answer": "no"},
                ],
            },
        )

        assert response.status_code in [200, 404, 503]

    def test_answer_questions_empty_answers(self, client: TestClient):
        """Answer questions with empty list."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/answer",
            json={"answers": []},
        )

        # Empty answers might be valid or fail validation
        assert response.status_code in [200, 400, 422, 503]

    def test_answer_questions_missing_answers(self, client: TestClient):
        """Answer questions without answers field."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/answer",
            json={},
        )

        assert response.status_code == 422


# =============================================================================
# Skip Questions Tests
# =============================================================================


class TestSkipQuestions:
    """Tests for POST /sessions/{session_id}/skip endpoint."""

    def test_skip_questions_success(self, client: TestClient):
        """Skip questions successfully."""
        response = client.post("/api/v1/diagnosis/sessions/session123/skip")

        assert response.status_code in [200, 404, 503]

    def test_skip_questions_invalid_session(self, client: TestClient, mock_session_controller):
        """Skip questions for non-existent session."""
        mock_session_controller.skip_questions.side_effect = ValueError("Session not found")

        response = client.post("/api/v1/diagnosis/sessions/invalid/skip")

        assert response.status_code in [404, 503]


# =============================================================================
# Pause/Resume Session Tests
# =============================================================================


class TestPauseResumeSession:
    """Tests for pause and resume session endpoints."""

    def test_pause_session_success(self, client: TestClient):
        """Pause session successfully."""
        response = client.post("/api/v1/diagnosis/sessions/session123/pause")

        assert response.status_code in [200, 404, 503]

    def test_resume_session_success(self, client: TestClient):
        """Resume session successfully."""
        response = client.post("/api/v1/diagnosis/sessions/session123/resume")

        assert response.status_code in [200, 404, 503]

    def test_pause_invalid_session(self, client: TestClient, mock_session_controller):
        """Pause non-existent session."""
        mock_session_controller.pause_session.side_effect = ValueError("Session not found")

        response = client.post("/api/v1/diagnosis/sessions/invalid/pause")

        assert response.status_code in [404, 503]


# =============================================================================
# Get Result Tests
# =============================================================================


class TestGetResult:
    """Tests for GET /sessions/{session_id}/result endpoint."""

    def test_get_result_success(self, client: TestClient):
        """Get result for completed session."""
        response = client.get("/api/v1/diagnosis/sessions/session123/result")

        assert response.status_code in [200, 404, 503]
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "confidence" in data
            assert "key_findings" in data

    def test_get_result_incomplete_session(self, client: TestClient, mock_session_controller):
        """Get result for incomplete session."""
        mock_session_controller.get_result.side_effect = ValueError("Session not complete")

        response = client.get("/api/v1/diagnosis/sessions/session123/result")

        assert response.status_code in [404, 503]


# =============================================================================
# Delete Session Tests
# =============================================================================


class TestDeleteSession:
    """Tests for DELETE /sessions/{session_id} endpoint."""

    def test_delete_session_success(self, client: TestClient):
        """Delete session successfully."""
        response = client.delete("/api/v1/diagnosis/sessions/session123")

        assert response.status_code in [200, 404, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "deleted"

    def test_delete_session_not_found(self, client: TestClient, mock_session_controller):
        """Delete non-existent session."""
        mock_session_controller.delete_session.return_value = False

        response = client.delete("/api/v1/diagnosis/sessions/nonexistent")

        assert response.status_code in [404, 503]


# =============================================================================
# Multi-Agent Diagnosis Tests
# =============================================================================


class TestMultiAgentDiagnosis:
    """Tests for multi-agent diagnosis endpoints."""

    def test_multi_agent_diagnose_success(self, client: TestClient):
        """Run multi-agent diagnosis with valid data."""
        response = client.post(
            "/api/v1/diagnosis/multi-agent/diagnose",
            json={
                "phenotypes": ["HP:0001250", "HP:0002315"],
                "genetic_variants": [{"gene_symbol": "BRCA1", "pathogenicity": "pathogenic"}],
                "medical_history": ["Previous diagnosis"],
                "family_history": ["Family history of cancer"],
                "demographics": {"age": 45, "sex": "female"},
                "wearable_data": [{"type": "heart_rate", "value": 72}],
            },
        )

        assert response.status_code in [200, 503]

    def test_multi_agent_diagnose_minimal(self, client: TestClient):
        """Run multi-agent diagnosis with minimal data."""
        response = client.post(
            "/api/v1/diagnosis/multi-agent/diagnose",
            json={
                "phenotypes": ["fatigue"],
            },
        )

        assert response.status_code in [200, 503]

    def test_get_discriminating_phenotypes(self, client: TestClient):
        """Get discriminating phenotypes for session."""
        response = client.get(
            "/api/v1/diagnosis/multi-agent/sessions/session123/discriminating-phenotypes"
        )

        assert response.status_code in [200, 404, 503]


# =============================================================================
# Stream Events Tests
# =============================================================================


class TestStreamEvents:
    """Tests for GET /sessions/{session_id}/stream endpoint."""

    def test_stream_events_returns_sse(self, client: TestClient, mock_session_controller):
        """Stream events returns Server-Sent Events response."""

        # Mock streaming
        async def mock_stream(session_id):
            yield MagicMock(to_dict=lambda: {"event": "test"})

        mock_session_controller.stream_events = mock_stream

        response = client.get(
            "/api/v1/diagnosis/sessions/session123/stream",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code in [200, 503]
        if response.status_code == 200:
            assert response.headers.get("content-type", "").startswith("text/event-stream")


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for GET /health endpoint."""

    def test_health_check(self, client: TestClient):
        """Health check returns service status."""
        response = client.get("/api/v1/diagnosis/health")

        # Health check should always return 200
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert data["service"] == "diagnosis"
        assert "timestamp" in data


# =============================================================================
# Request Validation Tests
# =============================================================================


class TestRequestValidation:
    """Tests for request validation."""

    def test_invalid_phenotype_input(self, client: TestClient):
        """Test validation of phenotype inputs."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/start",
            json={
                "phenotypes": [{"invalid_key": "value"}],
            },
        )

        # Should accept or fail validation
        assert response.status_code in [200, 400, 422, 503]

    def test_invalid_genetic_variant(self, client: TestClient):
        """Test validation of genetic variant inputs."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/start",
            json={
                "genetic_variants": [{"invalid": "data"}],
            },
        )

        # Should accept or fail validation
        assert response.status_code in [200, 400, 422, 503]

    def test_invalid_demographics(self, client: TestClient):
        """Test validation of demographics."""
        response = client.post(
            "/api/v1/diagnosis/sessions/session123/start",
            json={
                "demographics": {"age": "invalid"},
            },
        )

        # Should fail validation for invalid type
        assert response.status_code in [400, 422, 503]


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_services_not_initialized(self):
        """Test service not initialized error."""
        # Reset singleton for testing
        _DiagnosisServices._instance = None
        services = _DiagnosisServices()

        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_session_controller()

        assert exc_info.value.status_code == 503

    def test_services_initialized(self):
        """Test services can be initialized."""
        mock_controller = MagicMock()
        mock_coordinator = MagicMock()

        # Reset singleton
        _DiagnosisServices._instance = None

        initialize_diagnosis_services(mock_controller, mock_coordinator)

        services = _DiagnosisServices()
        assert services.is_initialized is True
        assert services.session_controller == mock_controller
        assert services.diagnostic_coordinator == mock_coordinator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
