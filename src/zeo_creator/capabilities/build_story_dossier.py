"""`creator.build_story_dossier@1.0.0`."""

from datetime import datetime
from typing import cast

from pydantic import Field
from zeo_core.contracts import CapabilityExample, CapabilityResult, EffectKind
from zeo_core.tools import ToolContext, capability

from zeo_creator.capabilities._newsroom_examples import dossier_request
from zeo_creator.capabilities.editorial_support import (
    require_bound_refs,
    strategy,
)
from zeo_creator.contracts.common import CreatorModel
from zeo_creator.contracts.newsroom import StoryDossier, StoryRevision
from zeo_creator.errors import CreatorDomainError
from zeo_creator.services.editorial_kernel import StoryDossierStrategy


class BuildStoryDossierRequest(CreatorModel):
    story: StoryRevision
    audience_significance: str = Field(min_length=1)
    prior_coverage_refs: tuple[str, ...] = ()
    created_at: datetime
    revision: int = Field(default=1, ge=1)


class BuildStoryDossierResponse(CreatorModel):
    dossier: StoryDossier


@capability(
    id="creator.build_story_dossier@1.0.0",
    description="Freeze one publication-scoped story revision into a reusable editorial dossier.",
    effects={EffectKind.READ},
    examples=(CapabilityExample(name="verified-story", request=dossier_request()),),
    error_codes=("ZEO_CREATOR_SCOPE_MISMATCH", "ZEO_CREATOR_STALE_INPUT"),
    tags=("creator", "story", "pure"),
    metadata={"strategy_service": "creator.story_dossier_strategy"},
    projection_name="creator_build_story_dossier",
)
def build_story_dossier(
    request: BuildStoryDossierRequest, ctx: ToolContext
) -> CapabilityResult[BuildStoryDossierResponse]:
    story = request.story
    implementation = cast(StoryDossierStrategy, strategy(ctx, "creator.story_dossier_strategy"))
    dossier = implementation.build_dossier(
        story=story,
        audience_significance=request.audience_significance,
        prior_coverage_refs=request.prior_coverage_refs,
        created_at=request.created_at,
        revision=request.revision,
    )
    try:
        what = f"dossier {dossier.dossier_id}"
        code = "ZEO_CREATOR_SCOPE_MISMATCH"
        require_bound_refs(
            (dossier.organization_id, dossier.publication_id),
            {story.organization_id, story.publication_id},
            code,
            what,
        )
        require_bound_refs(
            (dossier.story_id, dossier.story_revision_ref),
            {story.story_id, story.story_revision_id},
            code,
            what,
        )
        require_bound_refs(
            dossier.evidence_lineage,
            {
                *story.primary_source_refs,
                *story.secondary_source_refs,
                *story.signal_refs,
                *(
                    ref
                    for claim in (*story.verified_claims, *story.disputed_claims)
                    for ref in claim.evidence_refs
                ),
            },
            code,
            what,
        )
    except CreatorDomainError as exc:
        return CapabilityResult.fail(msg=str(exc), code=exc.code, exception=exc)
    return CapabilityResult.ok(
        data=BuildStoryDossierResponse(dossier=dossier), msg="Built frozen story dossier"
    )
