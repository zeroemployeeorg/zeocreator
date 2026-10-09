"""`creator.update_story_revisions@1.0.0`."""

from datetime import datetime
from typing import cast

from pydantic import Field
from zeo_core.contracts import CapabilityExample, CapabilityResult, EffectKind
from zeo_core.tools import ToolContext, capability

from zeo_creator.capabilities._newsroom_examples import update_request
from zeo_creator.capabilities.editorial_support import (
    require_bound_refs,
    require_scope,
    strategy,
)
from zeo_creator.contracts.common import CreatorModel
from zeo_creator.contracts.newsroom import EditorialSignal, StoryRevision
from zeo_creator.errors import CreatorDomainError
from zeo_creator.services.editorial_kernel import StoryRevisionStrategy


class UpdateStoryRevisionsRequest(CreatorModel):
    organization_id: str = Field(min_length=1)
    publication_id: str = Field(min_length=1)
    signals: tuple[EditorialSignal, ...] = Field(min_length=1)
    previous_revisions: tuple[StoryRevision, ...] = ()
    created_at: datetime


class UpdateStoryRevisionsResponse(CreatorModel):
    revisions: tuple[StoryRevision, ...]


@capability(
    id="creator.update_story_revisions@1.0.0",
    description="Create immutable story revisions from new editorial signals and prior revisions.",
    effects={EffectKind.READ},
    examples=(CapabilityExample(name="first-revision", request=update_request()),),
    error_codes=("ZEO_CREATOR_SCOPE_MISMATCH", "ZEO_CREATOR_PUBLICATION_LEAKAGE"),
    tags=("creator", "story", "pure"),
    metadata={"strategy_service": "creator.story_revision_strategy"},
    projection_name="creator_update_story_revisions",
)
def update_story_revisions(
    request: UpdateStoryRevisionsRequest, ctx: ToolContext
) -> CapabilityResult[UpdateStoryRevisionsResponse]:
    try:
        require_scope(
            request.organization_id,
            request.publication_id,
            *request.signals,
            *request.previous_revisions,
        )
        implementation = cast(
            StoryRevisionStrategy, strategy(ctx, "creator.story_revision_strategy")
        )
        revisions = implementation.update_revisions(
            signals=request.signals,
            previous_revisions=request.previous_revisions,
            created_at=request.created_at,
        )
        require_scope(request.organization_id, request.publication_id, *revisions)
        signal_ids = {item.signal_id for item in request.signals}
        previous_ids = {item.story_revision_id for item in request.previous_revisions}
        sources = {ref for item in request.signals for ref in item.source_refs} | {
            ref
            for item in request.previous_revisions
            for ref in (*item.primary_source_refs, *item.secondary_source_refs)
        }
        produced: set[str] = set()
        for revision in revisions:
            what = f"story revision {revision.story_revision_id}"
            code = "ZEO_CREATOR_PUBLICATION_LEAKAGE"
            require_bound_refs(revision.signal_refs, signal_ids, code, what)
            if revision.previous_revision_ref is not None:
                require_bound_refs(
                    (revision.previous_revision_ref,), previous_ids | produced, code, what
                )
            require_bound_refs(
                (
                    *revision.primary_source_refs,
                    *revision.secondary_source_refs,
                    *(
                        ref
                        for claim in (*revision.verified_claims, *revision.disputed_claims)
                        for ref in claim.evidence_refs
                    ),
                    *(ref for item in revision.material_developments for ref in item.source_refs),
                ),
                sources,
                code,
                what,
            )
            produced.add(revision.story_revision_id)
    except CreatorDomainError as exc:
        return CapabilityResult.fail(msg=str(exc), code=exc.code, exception=exc)
    return CapabilityResult.ok(
        data=UpdateStoryRevisionsResponse(revisions=revisions),
        msg=f"Produced {len(revisions)} story revisions",
    )
