"""
Forge Deployment Profiles
=========================

Predefined deployment configurations for different use cases:
- Lite: Basic persistence, minimal overhead
- Standard: Full features, single-tenant
- Enterprise: Multi-tenant, compliance, governance
"""

from forge.resilience.profiles.deployment import (
    DeploymentProfileManager,
    apply_profile,
    get_current_profile,
)

__all__ = [
    "DeploymentProfileManager",
    "apply_profile",
    "get_current_profile",
]
