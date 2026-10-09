"""An injected editorial strategy is trusted for judgement, never for scope."""

from typing import Any

from zeo_core.contracts import CapabilityStatus
from zeo_core.tools import invoke_sync

from zeo_creator.capabilities._newsroom_examples import (
    NOW,
    observation,
    signal,
    story,
)
from zeo_creator.contracts.newsroom import StoryDossier, StoryRevision
from zeo_creator.registry import capability_registry
from zeo_creator.runtime import make_context
from zeo_creator.services.editorial_kernel import DeterministicEditorialStrategy

REFERENCE = DeterministicEditorialStrategy()


def _rebuilt[ModelT: Any](model: ModelT, **changes: Any) -> ModelT:
    payload = model.model_dump(mode="json", exclude={"content_digest"})
    return type(model).model_validate({**payload, **changes})


class _ForeignSignals:
    def extract_signals(self, **kwargs: Any) -> tuple[Any, ...]:
        produced = REFERENCE.extract_signals(**kwargs)
        return tuple(
            _rebuilt(
                item,
                source_refs=["observation_from_elsewhere"],
                input_refs=["observation_from_elsewhere"],
                candidate_claims=[
                    {
                        **claim.model_dump(mode="json"),
                        "evidence_refs": ["observation_from_elsewhere"],
                    }
                    for claim in item.candidate_claims
                ],
            )
            for item in produced
        )


class _ForeignRevisions:
    def __init__(self, **changes: Any) -> None:
        self.changes = changes

    def update_revisions(self, **kwargs: Any) -> tuple[StoryRevision, ...]:
        return tuple(
            _rebuilt(item, **self.changes) for item in REFERENCE.update_revisions(**kwargs)
        )


class _ForeignDossier:
    def __init__(self, **changes: Any) -> None:
        self.changes = changes

    def build_dossier(self, **kwargs: Any) -> StoryDossier:
        return _rebuilt(REFERENCE.build_dossier(**kwargs), **self.changes)


def _invoke(capability_id: str, request: dict[str, Any], services: dict[str, Any]) -> Any:
    return invoke_sync(
        capability_registry().get(capability_id),
        request,
        make_context(capability_name=capability_id, services=services),
    )


def _extract(services: dict[str, Any]) -> Any:
    item = observation()
    return _invoke(
        "creator.extract_editorial_signals@1.0.0",
        {
            "organization_id": item.organization_id,
            "publication_id": item.publication_id,
            "observations": [item.model_dump(mode="json")],
            "created_at": NOW.isoformat(),
        },
        services,
    )


def _update(services: dict[str, Any]) -> Any:
    item = signal()
    return _invoke(
        "creator.update_story_revisions@1.0.0",
        {
            "organization_id": item.organization_id,
            "publication_id": item.publication_id,
            "signals": [item.model_dump(mode="json")],
            "previous_revisions": [],
            "created_at": NOW.isoformat(),
        },
        services,
    )


def _dossier(services: dict[str, Any]) -> Any:
    return _invoke(
        "creator.build_story_dossier@1.0.0",
        {
            "story": story().model_dump(mode="json"),
            "audience_significance": "Readers need verified context.",
            "created_at": NOW.isoformat(),
        },
        services,
    )


def _refused(result: Any, code: str) -> None:
    assert result.status is CapabilityStatus.error
    assert result.error is not None
    assert (
        result.error.get("code") if isinstance(result.error, dict) else result.error.code
    ) == code


def test_reference_strategies_still_pass_the_binding_checks() -> None:
    assert _extract({}).status is CapabilityStatus.success
    assert _update({}).status is CapabilityStatus.success
    assert _dossier({}).status is CapabilityStatus.success


def test_signals_citing_observations_not_given_are_refused() -> None:
    result = _extract({"creator.research_synthesizer": _ForeignSignals()})
    _refused(result, "ZEO_CREATOR_PUBLICATION_LEAKAGE")


def test_signals_for_another_publication_are_refused() -> None:
    class _OtherPublication:
        def extract_signals(self, **kwargs: Any) -> tuple[Any, ...]:
            return tuple(
                _rebuilt(item, publication_id="publication-b.example")
                for item in REFERENCE.extract_signals(**kwargs)
            )

    result = _extract({"creator.research_synthesizer": _OtherPublication()})
    _refused(result, "ZEO_CREATOR_PUBLICATION_LEAKAGE")


def test_revisions_citing_signals_or_sources_not_given_are_refused() -> None:
    for changes in (
        {"signal_refs": ["signal_from_elsewhere"]},
        {"primary_source_refs": ["observation_from_elsewhere"]},
        {
            "revision": 2,
            "previous_revision_ref": "story_revision_from_elsewhere",
            "status": "DEVELOPING",
        },
    ):
        result = _update({"creator.story_revision_strategy": _ForeignRevisions(**changes)})
        _refused(result, "ZEO_CREATOR_PUBLICATION_LEAKAGE")


def test_dossiers_not_bound_to_their_story_are_refused() -> None:
    for changes in (
        {"publication_id": "publication-b.example"},
        {"story_revision_ref": "story_revision_from_elsewhere"},
        {"evidence_lineage": ["observation_from_elsewhere"], "verified_claims": []},
    ):
        result = _dossier({"creator.story_dossier_strategy": _ForeignDossier(**changes)})
        _refused(result, "ZEO_CREATOR_SCOPE_MISMATCH")
