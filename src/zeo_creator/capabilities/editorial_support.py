"""Strategy resolution and invariant helpers for editorial capabilities."""

from __future__ import annotations

from collections.abc import Iterable

from zeo_core.tools import ToolContext

from zeo_creator.errors import CreatorDomainError
from zeo_creator.services.editorial_kernel import DeterministicEditorialStrategy

REFERENCE_STRATEGY = DeterministicEditorialStrategy()


def strategy(ctx: ToolContext, service_name: str) -> object:
    """Use a runner-injected strategy or the deterministic public reference."""
    return ctx.get_service(service_name) or REFERENCE_STRATEGY


def require_scope(
    organization_id: str,
    publication_id: str,
    *artifacts: object,
) -> None:
    for artifact in artifacts:
        if getattr(artifact, "organization_id", None) != organization_id:
            raise CreatorDomainError("ZEO_CREATOR_SCOPE_MISMATCH", "organization scope mismatch")
        if getattr(artifact, "publication_id", None) != publication_id:
            raise CreatorDomainError(
                "ZEO_CREATOR_PUBLICATION_LEAKAGE", "publication scope mismatch"
            )


def require_bound_refs(refs: Iterable[str], allowed: set[str], code: str, what: str) -> None:
    """Refuse output that cites anything the strategy was not given.

    An injected strategy is trusted for judgement, never for scope: every reference
    it returns must resolve to an input of the same call.
    """
    unbound = sorted(set(refs) - allowed)
    if unbound:
        raise CreatorDomainError(code, f"{what} cites inputs it was not given: {unbound[:3]}")
