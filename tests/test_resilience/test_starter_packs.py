"""
Tests for Starter Packs System
==============================

Tests for forge/resilience/cold_start/starter_packs.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.cold_start.starter_packs import (
    PackCategory,
    PackCapsule,
    PackDependency,
    PackInstallation,
    PackOverlay,
    PackStatus,
    StarterPack,
    StarterPackManager,
    get_pack_manager,
)


class TestPackCategory:
    """Tests for PackCategory enum."""

    def test_category_values(self):
        """Test all category values."""
        assert PackCategory.DEVELOPMENT.value == "development"
        assert PackCategory.BUSINESS.value == "business"
        assert PackCategory.RESEARCH.value == "research"
        assert PackCategory.PERSONAL.value == "personal"
        assert PackCategory.COMPLIANCE.value == "compliance"
        assert PackCategory.OPERATIONS.value == "operations"


class TestPackStatus:
    """Tests for PackStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert PackStatus.DRAFT.value == "draft"
        assert PackStatus.PUBLISHED.value == "published"
        assert PackStatus.DEPRECATED.value == "deprecated"
        assert PackStatus.ARCHIVED.value == "archived"


class TestPackCapsule:
    """Tests for PackCapsule dataclass."""

    def test_capsule_creation(self):
        """Test creating a pack capsule."""
        capsule = PackCapsule(
            template_id="template_123",
            title="Test Capsule",
            content="Test content",
            capsule_type="KNOWLEDGE",
            tags=["test", "example"],
        )

        assert capsule.template_id == "template_123"
        assert capsule.title == "Test Capsule"
        assert capsule.content == "Test content"
        assert capsule.capsule_type == "KNOWLEDGE"
        assert capsule.tags == ["test", "example"]
        assert capsule.metadata == {}


class TestPackOverlay:
    """Tests for PackOverlay dataclass."""

    def test_overlay_creation(self):
        """Test creating a pack overlay."""
        overlay = PackOverlay(
            overlay_id="overlay_123",
            name="Test Overlay",
            overlay_type="GOVERNANCE",
            config={"require_approval": True},
        )

        assert overlay.overlay_id == "overlay_123"
        assert overlay.name == "Test Overlay"
        assert overlay.overlay_type == "GOVERNANCE"
        assert overlay.config == {"require_approval": True}


class TestPackDependency:
    """Tests for PackDependency dataclass."""

    def test_dependency_creation(self):
        """Test creating a pack dependency."""
        dep = PackDependency(
            pack_id="base-pack",
            version="1.0.0",
            optional=False,
        )

        assert dep.pack_id == "base-pack"
        assert dep.version == "1.0.0"
        assert dep.optional is False


class TestStarterPack:
    """Tests for StarterPack dataclass."""

    def test_pack_creation(self):
        """Test creating a starter pack."""
        pack = StarterPack(
            pack_id="test-pack",
            name="Test Pack",
            description="A test pack",
            category=PackCategory.DEVELOPMENT,
        )

        assert pack.pack_id == "test-pack"
        assert pack.name == "Test Pack"
        assert pack.description == "A test pack"
        assert pack.category == PackCategory.DEVELOPMENT
        assert pack.version == "1.0.0"
        assert pack.status == PackStatus.PUBLISHED
        assert pack.capsules == []
        assert pack.overlays == []
        assert pack.dependencies == []

    def test_pack_to_dict(self):
        """Test converting pack to dict."""
        pack = StarterPack(
            pack_id="test-pack",
            name="Test Pack",
            description="A test pack",
            category=PackCategory.DEVELOPMENT,
            capsules=[
                PackCapsule(
                    template_id="t1",
                    title="C1",
                    content="Content",
                    capsule_type="KNOWLEDGE",
                )
            ],
            overlays=[
                PackOverlay(
                    overlay_id="o1",
                    name="O1",
                    overlay_type="GOVERNANCE",
                )
            ],
            tags=["test"],
        )

        result = pack.to_dict()

        assert result["pack_id"] == "test-pack"
        assert result["name"] == "Test Pack"
        assert result["category"] == "development"
        assert result["capsule_count"] == 1
        assert result["overlay_count"] == 1
        assert result["tags"] == ["test"]

    def test_pack_from_dict(self):
        """Test creating pack from dict."""
        data = {
            "pack_id": "test-pack",
            "name": "Test Pack",
            "description": "A test pack",
            "category": "development",
            "version": "2.0.0",
            "author": "Test Author",
            "status": "published",
            "capsules": [
                {
                    "template_id": "t1",
                    "title": "C1",
                    "content": "Content",
                    "capsule_type": "KNOWLEDGE",
                    "tags": [],
                    "metadata": {},
                }
            ],
            "overlays": [],
            "dependencies": [],
            "tags": ["test"],
        }

        pack = StarterPack.from_dict(data)

        assert pack.pack_id == "test-pack"
        assert pack.version == "2.0.0"
        assert pack.author == "Test Author"
        assert len(pack.capsules) == 1


class TestPackInstallation:
    """Tests for PackInstallation dataclass."""

    def test_installation_creation(self):
        """Test creating an installation record."""
        installation = PackInstallation(
            installation_id="inst_123",
            pack_id="test-pack",
            pack_version="1.0.0",
            installed_by="user_456",
        )

        assert installation.installation_id == "inst_123"
        assert installation.pack_id == "test-pack"
        assert installation.pack_version == "1.0.0"
        assert installation.installed_by == "user_456"
        assert installation.status == "completed"


class TestStarterPackManager:
    """Tests for StarterPackManager class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.auto_import_dependencies = True
        return config

    @pytest.fixture
    def manager(self, mock_config):
        """Create a manager instance."""
        with patch("forge.resilience.cold_start.starter_packs.get_resilience_config") as mock:
            mock.return_value.starter_packs = mock_config
            manager = StarterPackManager()
            manager.initialize()
            return manager

    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager._initialized is True
        assert len(manager._packs) > 0  # Default packs registered

    def test_manager_initialize_disabled(self, mock_config):
        """Test manager initialization when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.cold_start.starter_packs.get_resilience_config") as mock:
            mock.return_value.starter_packs = mock_config
            manager = StarterPackManager()
            manager.initialize()

            assert manager._initialized is False

    def test_register_pack(self, manager):
        """Test registering a new pack."""
        pack = StarterPack(
            pack_id="custom-pack",
            name="Custom Pack",
            description="A custom pack",
            category=PackCategory.PERSONAL,
        )

        manager.register_pack(pack)

        assert "custom-pack" in manager._packs

    def test_get_pack(self, manager):
        """Test getting a pack by ID."""
        pack = manager.get_pack("forge-essentials")

        assert pack is not None
        assert pack.name == "Forge Essentials"

    def test_get_pack_not_found(self, manager):
        """Test getting nonexistent pack."""
        pack = manager.get_pack("nonexistent")

        assert pack is None

    def test_list_packs(self, manager):
        """Test listing all packs."""
        packs = manager.list_packs()

        assert len(packs) > 0
        # Should only include published packs
        for pack in packs:
            assert pack.status == PackStatus.PUBLISHED

    def test_list_packs_by_category(self, manager):
        """Test listing packs by category."""
        packs = manager.list_packs(category=PackCategory.DEVELOPMENT)

        assert len(packs) >= 1
        for pack in packs:
            assert pack.category == PackCategory.DEVELOPMENT

    def test_list_packs_by_tags(self, manager):
        """Test listing packs by tags."""
        packs = manager.list_packs(tags=["getting-started"])

        assert len(packs) >= 1
        for pack in packs:
            assert any(t in pack.tags for t in ["getting-started"])

    def test_search_packs(self, manager):
        """Test searching packs."""
        results = manager.search_packs("essentials")

        assert len(results) >= 1
        assert any("Essential" in p.name for p in results)

    def test_search_packs_by_description(self, manager):
        """Test searching packs by description."""
        results = manager.search_packs("development")

        assert len(results) >= 1

    def test_set_callbacks(self, manager):
        """Test setting callbacks."""
        capsule_callback = AsyncMock()
        overlay_callback = AsyncMock()

        manager.set_capsule_callback(capsule_callback)
        manager.set_overlay_callback(overlay_callback)

        assert manager._create_capsule_callback == capsule_callback
        assert manager._activate_overlay_callback == overlay_callback

    @pytest.mark.asyncio
    async def test_install_pack(self, manager):
        """Test installing a pack."""
        installation = await manager.install_pack(
            pack_id="forge-essentials",
            user_id="user_123",
            skip_dependencies=True,
        )

        assert installation.pack_id == "forge-essentials"
        assert installation.installed_by == "user_123"
        assert installation.status == "completed"
        assert "user_123" in manager._installations

    @pytest.mark.asyncio
    async def test_install_pack_not_found(self, manager):
        """Test installing nonexistent pack."""
        with pytest.raises(ValueError, match="Pack not found"):
            await manager.install_pack("nonexistent", "user_123")

    @pytest.mark.asyncio
    async def test_install_pack_already_installed(self, manager):
        """Test installing already installed pack."""
        await manager.install_pack("forge-essentials", "user_123", skip_dependencies=True)

        with pytest.raises(ValueError, match="already installed"):
            await manager.install_pack("forge-essentials", "user_123")

    @pytest.mark.asyncio
    async def test_install_pack_with_dependencies(self, manager):
        """Test installing pack with dependencies."""
        # software-development depends on forge-essentials
        installation = await manager.install_pack(
            pack_id="software-development",
            user_id="user_456",
        )

        # Should have installed both packs
        installations = manager.get_installations("user_456")
        assert len(installations) == 2

    @pytest.mark.asyncio
    async def test_install_pack_creates_capsules(self, manager):
        """Test that installation creates capsules via callback."""
        capsule_callback = AsyncMock(return_value="cap_123")
        manager.set_capsule_callback(capsule_callback)

        installation = await manager.install_pack(
            pack_id="forge-essentials",
            user_id="user_789",
            skip_dependencies=True,
        )

        assert capsule_callback.called
        assert len(installation.capsules_created) > 0

    @pytest.mark.asyncio
    async def test_install_pack_activates_overlays(self, manager):
        """Test that installation activates overlays via callback."""
        overlay_callback = AsyncMock(return_value="overlay_123")
        manager.set_overlay_callback(overlay_callback)

        installation = await manager.install_pack(
            pack_id="forge-essentials",
            user_id="user_101",
            skip_dependencies=True,
        )

        assert overlay_callback.called
        assert len(installation.overlays_activated) > 0

    def test_get_installations(self, manager):
        """Test getting installations for user."""
        # No installations yet
        installations = manager.get_installations("new_user")

        assert installations == []

    @pytest.mark.asyncio
    async def test_uninstall_pack(self, manager):
        """Test uninstalling a pack."""
        await manager.install_pack("forge-essentials", "user_123", skip_dependencies=True)

        result = await manager.uninstall_pack("forge-essentials", "user_123")

        assert result is True
        assert len(manager.get_installations("user_123")) == 0

    @pytest.mark.asyncio
    async def test_uninstall_pack_not_found(self, manager):
        """Test uninstalling pack that's not installed."""
        result = await manager.uninstall_pack("forge-essentials", "user_999")

        assert result is False

    def test_validate_pack_content_valid(self, manager):
        """Test validating valid content."""
        content = "This is normal content with no malicious patterns."

        result = manager._validate_pack_content(content)

        assert result == content

    def test_validate_pack_content_xss(self, manager):
        """Test validating content with XSS."""
        content = '<script>alert("xss")</script>'

        result = manager._validate_pack_content(content)

        assert result is None

    def test_validate_pack_content_javascript(self, manager):
        """Test validating content with javascript: URL."""
        content = 'Click <a href="javascript:alert(1)">here</a>'

        result = manager._validate_pack_content(content)

        assert result is None

    def test_validate_pack_content_sql_injection(self, manager):
        """Test validating content with SQL injection."""
        content = "'; DROP TABLE users; --"

        result = manager._validate_pack_content(content)

        assert result is None

    def test_validate_pack_content_too_large(self, manager):
        """Test validating content that's too large."""
        content = "x" * 200000  # 200KB

        result = manager._validate_pack_content(content)

        assert result is None

    def test_validate_pack_content_empty(self, manager):
        """Test validating empty content."""
        result = manager._validate_pack_content("")

        assert result == ""

    def test_validate_pack_content_sanitizes_script(self, manager):
        """Test that script tags are sanitized."""
        content = "Hello <SCRIPT>evil</SCRIPT> world"

        result = manager._validate_pack_content(content)

        # Should be rejected due to script tag pattern
        assert result is None


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_pack_manager(self):
        """Test getting global pack manager."""
        with patch("forge.resilience.cold_start.starter_packs._pack_manager", None):
            with patch("forge.resilience.cold_start.starter_packs.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.starter_packs.enabled = True
                mock.return_value = mock_config

                manager = get_pack_manager()

                assert isinstance(manager, StarterPackManager)
