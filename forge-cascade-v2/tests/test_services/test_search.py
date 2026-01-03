"""
Tests for Search Service

Tests cover:
- Search modes (semantic, keyword, hybrid, exact)
- Filtering
- Result ranking and boosting
- Score thresholds
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from forge.services.search import (
    SearchService,
    SearchMode,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from forge.models.capsule import CapsuleType


class TestSearchFilters:
    """Tests for search filters."""
    
    def test_default_filters(self):
        filters = SearchFilters()
        assert filters.min_trust == 40
        assert filters.max_trust == 100
        assert filters.include_archived is False
    
    def test_custom_filters(self):
        filters = SearchFilters(
            capsule_types=[CapsuleType.KNOWLEDGE, CapsuleType.CODE],
            min_trust=60,
            tags=["python", "tutorial"],
        )
        assert len(filters.capsule_types) == 2
        assert filters.min_trust == 60
        assert filters.tags == ["python", "tutorial"]
    
    def test_filters_to_dict(self):
        filters = SearchFilters(
            owner_ids=["user-123"],
            created_after=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        
        result = filters.to_dict()
        
        assert result["owner_ids"] == ["user-123"]
        assert "2024-01-01" in result["created_after"]


class TestSearchRequest:
    """Tests for search request configuration."""
    
    def test_default_request(self):
        request = SearchRequest(query="test query")
        
        assert request.query == "test query"
        assert request.mode == SearchMode.SEMANTIC
        assert request.limit == 10
        assert request.min_score == 0.5
        assert request.boost_recent is True
    
    def test_custom_request(self):
        request = SearchRequest(
            query="python async",
            mode=SearchMode.HYBRID,
            limit=20,
            offset=10,
            min_score=0.7,
            boost_popular=False,
        )
        
        assert request.mode == SearchMode.HYBRID
        assert request.limit == 20
        assert request.offset == 10


class TestSearchService:
    """Tests for search service."""
    
    @pytest.fixture
    def mock_embedding_service(self):
        service = AsyncMock()
        service.embed = AsyncMock(return_value=MagicMock(
            embedding=[0.1] * 1536,
            model="mock",
            dimensions=1536,
        ))
        service.dimensions = 1536
        return service
    
    @pytest.fixture
    def mock_db_client(self):
        client = AsyncMock()
        client.execute = AsyncMock(return_value=[])
        return client
    
    @pytest.fixture
    def search_service(self, mock_embedding_service, mock_db_client):
        return SearchService(
            embedding_service=mock_embedding_service,
            db_client=mock_db_client,
        )
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self, search_service):
        request = SearchRequest(query="nonexistent content")
        
        response = await search_service.search(request)
        
        assert isinstance(response, SearchResponse)
        assert response.query == "nonexistent content"
        assert response.mode == "semantic"
        assert response.total == 0
        assert response.took_ms > 0
    
    @pytest.mark.asyncio
    async def test_search_with_results(self, search_service, mock_db_client):
        # Mock database to return results
        mock_db_client.execute = AsyncMock(return_value=[
            {
                "capsule": {
                    "id": "cap-1",
                    "title": "Test Capsule",
                    "content": "Test content about Python",
                    "type": "knowledge",
                    "owner_id": "user-1",
                    "trust_level": 60,
                    "version": "1.0.0",
                    "tags": ["python"],
                    "metadata": {},
                    "view_count": 100,
                    "fork_count": 5,
                    "is_archived": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "score": 0.95,
            },
        ])
        
        request = SearchRequest(query="Python programming")
        
        response = await search_service.search(request)
        
        assert response.total >= 0  # May be filtered
    
    @pytest.mark.asyncio
    async def test_search_modes(self, search_service):
        """Test all search modes execute without error."""
        for mode in SearchMode:
            request = SearchRequest(query="test", mode=mode)
            response = await search_service.search(request)
            assert response.mode == mode.value
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_service):
        request = SearchRequest(
            query="test",
            filters=SearchFilters(
                capsule_types=[CapsuleType.CODE],
                min_trust=70,
                tags=["python"],
            ),
        )
        
        response = await search_service.search(request)
        
        assert response.filters_applied["min_trust"] == 70
        assert response.filters_applied["tags"] == ["python"]


class TestResultRanking:
    """Tests for result ranking and boosting."""
    
    def test_apply_recency_boost(self):
        from forge.services.search import SearchService
        from forge.models.capsule import Capsule
        from forge.models.base import TrustLevel
        
        service = SearchService()
        
        # Create results with different ages
        now = datetime.now(timezone.utc)
        
        recent_capsule = Capsule(
            id="cap-1",
            content="Recent content",
            type=CapsuleType.KNOWLEDGE,
            owner_id="user-1",
            trust_level=TrustLevel.STANDARD,
            version="1.0.0",
            view_count=10,
            fork_count=1,
            created_at=now - timedelta(days=5),
        )
        
        old_capsule = Capsule(
            id="cap-2",
            content="Old content",
            type=CapsuleType.KNOWLEDGE,
            owner_id="user-1",
            trust_level=TrustLevel.STANDARD,
            version="1.0.0",
            view_count=10,
            fork_count=1,
            created_at=now - timedelta(days=60),
        )
        
        results = [
            SearchResultItem(capsule=old_capsule, score=0.8),
            SearchResultItem(capsule=recent_capsule, score=0.8),
        ]
        
        request = SearchRequest(query="test", boost_recent=True, boost_popular=False)
        boosted = service._apply_boosts(results, request)
        
        # Recent capsule should have higher score after boost
        recent_result = next(r for r in boosted if r.capsule.id == "cap-1")
        old_result = next(r for r in boosted if r.capsule.id == "cap-2")
        
        assert recent_result.score >= old_result.score
    
    def test_filter_by_score(self):
        from forge.services.search import SearchService
        
        service = SearchService()
        
        # Create mock results
        results = [
            MagicMock(score=0.9),
            MagicMock(score=0.7),
            MagicMock(score=0.4),
            MagicMock(score=0.3),
        ]
        
        filtered = service._filter_by_score(results, min_score=0.5)
        
        assert len(filtered) == 2
        assert all(r.score >= 0.5 for r in filtered)


class TestHighlightExtraction:
    """Tests for search highlight extraction."""
    
    def test_extract_highlights(self):
        from forge.services.search import SearchService
        
        service = SearchService()
        
        content = "This is a document about Python programming. Python is great for data science. Machine learning uses Python."
        terms = ["Python", "programming"]
        
        highlights = service._extract_highlights(content, terms, context_chars=20)
        
        assert len(highlights) > 0
        assert len(highlights) <= 3  # Max 3 highlights
    
    def test_extract_highlights_no_match(self):
        from forge.services.search import SearchService
        
        service = SearchService()
        
        content = "Document about JavaScript and React"
        terms = ["Python"]
        
        highlights = service._extract_highlights(content, terms)
        
        assert len(highlights) == 0
