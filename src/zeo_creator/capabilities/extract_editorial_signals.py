"""`creator.extract_editorial_signals@1.0.0`."""

from datetime import datetime
from typing import cast

from pydantic import Field
from zeo_core.contracts import CapabilityExample, CapabilityResult, EffectKind
from zeo_core.tools import ToolContext, capability

from zeo_creator.capabilities._newsroom_examples import extract_request
from zeo_creator.capabilities.editorial_support import (
    require_bound_refs,
    require_scope,
    strategy,
)
from zeo_creator.contracts.common import CreatorModel
from zeo_creator.contracts.newsroom import EditorialSignal, SourceObservation
from zeo_creator.errors import CreatorDomainError
from zeo_creator.services.editorial_kernel import ResearchSynthesisStrategy


class ExtractEditorialSignalsRequest(CreatorModel):
    organization_id: str = Field(min_length=1)
    publication_id: str = Field(min_length=1)
    observations: tuple[SourceObservation, ...] = Field(min_length=1)
    created_at: datetime
    revision: int = Field(default=1, ge=1)


class ExtractEditorialSignalsResponse(CreatorModel):
    signals: tuple[EditorialSignal, ...]


@capability(
    id="creator.extract_editorial_signals@1.0.0",
    description="Extract publication-scoped editorial signals from normalized observations.",
    effects={EffectKind.READ},
    examples=(CapabilityExample(name="official-observation", request=extract_request()),),
    error_codes=("ZEO_CREATOR_SCOPE_MISMATCH", "ZEO_CREATOR_PUBLICATION_LEAKAGE"),
    tags=("creator", "editorial", "pure"),
    metadata={"strategy_service": "creator.research_synthesizer"},
    projection_name="creator_extract_editorial_signals",
)
def extract_editorial_signals(
    request: ExtractEditorialSignalsRequest, ctx: ToolContext
) -> CapabilityResult[ExtractEditorialSignalsResponse]:
    try:
        require_scope(request.organization_id, request.publication_id, *request.observations)
        implementation = cast(
            ResearchSynthesisStrategy, strategy(ctx, "creator.research_synthesizer")
        )
        signals = implementation.extract_signals(
            observations=request.observations,
            created_at=request.created_at,
            revision=request.revision,
        )
        require_scope(request.organization_id, request.publication_id, *signals)
        given = {item.observation_id for item in request.observations}
        for signal in signals:
            require_bound_refs(
                (*signal.source_refs, *signal.input_refs),
                given,
                "ZEO_CREATOR_PUBLICATION_LEAKAGE",
                f"signal {signal.signal_id}",
            )
    except CreatorDomainError as exc:
        return CapabilityResult.fail(msg=str(exc), code=exc.code, exception=exc)
    return CapabilityResult.ok(
        data=ExtractEditorialSignalsResponse(signals=signals),
        msg=f"Extracted {len(signals)} editorial signals",
    )
