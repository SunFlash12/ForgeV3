"""
Forge Cascade Repositories

Data access layer providing CRUD operations and specialized queries
for all domain entities.
"""

from forge.repositories.audit_repository import AuditRepository
from forge.repositories.base import BaseRepository
from forge.repositories.capsule_repository import CapsuleRepository
from forge.repositories.cascade_repository import CascadeRepository, get_cascade_repository
from forge.repositories.governance_repository import GovernanceRepository
from forge.repositories.graph_repository import GraphRepository
from forge.repositories.marketplace_repository import (
    CartRepository,
    LicenseRepository,
    ListingRepository,
    MarketplaceRepository,
    PurchaseRepository,
)
from forge.repositories.overlay_repository import OverlayRepository
from forge.repositories.temporal_repository import TemporalRepository
from forge.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "CapsuleRepository",
    "CascadeRepository",
    "get_cascade_repository",
    "UserRepository",
    "OverlayRepository",
    "GovernanceRepository",
    "AuditRepository",
    "GraphRepository",
    "TemporalRepository",
    # Marketplace repositories
    "MarketplaceRepository",
    "ListingRepository",
    "PurchaseRepository",
    "CartRepository",
    "LicenseRepository",
]
