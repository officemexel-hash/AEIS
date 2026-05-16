"""AEIS Advisor — Role Resolver module.

Maps abstract roles (planner / worker / critic / governance / local_verifier)
to concrete LLM models.
"""

from sylion.aeis.advisor.role_resolver._models import ModelChoice, Role, RoutingEntry, RoutingPreview
from sylion.aeis.advisor.role_resolver.resolver import resolve_judge_model, resolve_role_model
from sylion.aeis.advisor.role_resolver.service import RoleResolverService, get_role_resolver_service
from sylion.aeis.advisor.role_resolver.verdicts import RoleVerdictDistribution, compute_distribution

__all__ = [
    "ModelChoice",
    "Role",
    "RoutingEntry",
    "RoutingPreview",
    "RoleVerdictDistribution",
    "compute_distribution",
    "resolve_judge_model",
    "resolve_role_model",
    "RoleResolverService",
    "get_role_resolver_service",
]
