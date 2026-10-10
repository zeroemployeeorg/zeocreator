"""Deterministic reference strategies for the continuous editorial kernel."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from zeo_creator.contracts.common import canonical_digest, stable_id
from zeo_creator.contracts.evidence import EvidenceClaim, ResearchWindow
from zeo_creator.contracts.newsroom import (
    AgendaSelection,
    EditionItem,
    EditionPlan,
    EditorialAgenda,
    EditorialSignal,
    GenerationTrace,
    PublicationSlot,
    RiskLevel,
    SignalType,
    SlotUrgency,
    SourceObservation,
    StoryDossier,
    StoryRevision,
    StoryStatus,
    StoryTimelineEntry,
)


def _trace(name: str, inputs: Sequence[object], findings: tuple[str, ...] = ()) -> GenerationTrace:
    return GenerationTrace(
        strategy_ref=f"zeo-creator.reference.{name}",
        strategy_version="1.0.0",
        policy_version="1.0.0",
        input_digests=tuple(canonical_digest(item) for item in inputs),
        evaluator_findings=findings,
    )


class ResearchSynthesisStrategy(Protocol):
    """Extract publication-scoped signals from normalized observations."""

    def extract_signals(
        self,
        *,
        observations: Sequence[SourceObservation],
        created_at: datetime,
        revision: int,
    ) -> tuple[EditorialSignal, ...]: ...


class PortfolioPlanningStrategy(Protocol):
    """Plan a publication agenda from frozen dossiers and requested slots."""

    def plan_agenda(
        self,
        *,
        organization_id: str,
        publication_id: str,
        desk_id: str,
        coverage_window: ResearchWindow,
        dossiers: Sequence[StoryDossier],
        slots: Sequence[PublicationSlot],
        created_at: datetime,
        revision: int,
    ) -> EditorialAgenda: ...


class BriefCompositionStrategy(Protocol):
    """Marker protocol for model-backed brief composition implementations."""


class PerformanceInterpretationStrategy(Protocol):
    """Marker protocol for model-backed performance interpretation implementations."""


class StoryRevisionStrategy(Protocol):
    def update_revisions(
        self,
        *,
        signals: Sequence[EditorialSignal],
        previous_revisions: Sequence[StoryRevision],
        created_at: datetime,
    ) -> tuple[StoryRevision, ...]: ...


class StoryDossierStrategy(Protocol):
    def build_dossier(
        self,
        *,
        story: StoryRevision,
        audience_significance: str,
        prior_coverage_refs: Sequence[str],
        created_at: datetime,
        revision: int,
    ) -> StoryDossier: ...


class EditionPlanningStrategy(Protocol):
    def plan_edition(
        self,
        *,
        agenda: EditorialAgenda,
        edition_kind: str,
        publication_window: ResearchWindow,
        update_policy_ref: str,
        human_editor_requirements: Sequence[str],
        created_at: datetime,
        revision: int,
    ) -> EditionPlan: ...


class DeterministicEditorialStrategy(
    ResearchSynthesisStrategy,
    PortfolioPlanningStrategy,
    StoryRevisionStrategy,
    StoryDossierStrategy,
    EditionPlanningStrategy,
):
    """Credential-free reference behavior for examples, tests and conformance."""

    def extract_signals(
        self,
        *,
        observations: Sequence[SourceObservation],
        created_at: datetime,
        revision: int,
    ) -> tuple[EditorialSignal, ...]:
        results: list[EditorialSignal] = []
        for observation in sorted(observations, key=lambda item: item.observation_id):
            if not observation.extracted_text:
                continue
            summary = observation.extracted_text.strip().splitlines()[0][:240]
            claim = EvidenceClaim(
                claim_id=stable_id("claim", observation.observation_id, summary),
                text=summary,
                evidence_refs=(observation.observation_id,),
            )
            results.append(
                EditorialSignal(
                    signal_id=stable_id(
                        "signal", observation.publication_id, observation.observation_id
                    ),
                    created_at=created_at,
                    organization_id=observation.organization_id,
                    publication_id=observation.publication_id,
                    input_refs=(observation.observation_id,),
                    revision=revision,
                    topic=observation.source_kind,
                    entities=(),
                    candidate_claims=(claim,),
                    signal_type=SignalType.DEVELOPMENT,
                    novelty=0.5,
                    relevance=0.5,
                    geography=observation.geography,
                    urgency=SlotUrgency.DAILY,
                    confidence=0.5 if observation.completeness.value == "PARTIAL" else 0.8,
                    source_refs=(observation.observation_id,),
                    why_it_matters=f"New {observation.source_kind} observation for this publication.",
                    generation=_trace("signal-extraction", (observation,)),
                )
            )
        return tuple(results)

    def update_revisions(
        self,
        *,
        signals: Sequence[EditorialSignal],
        previous_revisions: Sequence[StoryRevision],
        created_at: datetime,
    ) -> tuple[StoryRevision, ...]:
        previous_by_title: dict[str, StoryRevision] = {}
        for item in previous_revisions:
            key = item.title.casefold()
            current = previous_by_title.get(key)
            if current is None or item.revision > current.revision:
                previous_by_title[key] = item
        results: list[StoryRevision] = []
        for signal in sorted(signals, key=lambda item: item.signal_id):
            previous = previous_by_title.get(signal.topic.casefold())
            number = 1 if previous is None else previous.revision + 1
            story_id = stable_id(
                "story", signal.organization_id, signal.publication_id, signal.topic
            )
            source_refs = tuple(dict.fromkeys((*signal.source_refs,)))
            results.append(
                StoryRevision(
                    story_id=story_id,
                    story_revision_id=stable_id(
                        "story_revision", story_id, str(number), signal.content_digest
                    ),
                    previous_revision_ref=None if previous is None else previous.story_revision_id,
                    created_at=created_at,
                    organization_id=signal.organization_id,
                    publication_id=signal.publication_id,
                    input_refs=(signal.signal_id,)
                    if previous is None
                    else (previous.story_revision_id, signal.signal_id),
                    revision=number,
                    status=StoryStatus.DETECTED if previous is None else StoryStatus.DEVELOPING,
                    title=signal.topic,
                    verified_claims=() if signal.confidence < 0.75 else signal.candidate_claims,
                    disputed_claims=() if signal.confidence >= 0.5 else signal.candidate_claims,
                    primary_source_refs=source_refs,
                    freshness_at=created_at,
                    editorial_risk=RiskLevel.MEDIUM,
                    signal_refs=(signal.signal_id,),
                    geography=signal.geography,
                    generation=_trace(
                        "story-revision",
                        (signal,) if previous is None else (previous, signal),
                    ),
                )
            )
            # A later signal on the same topic in this batch develops this revision, so a
            # story never gets two revisions with the same number.
            previous_by_title[signal.topic.casefold()] = results[-1]
        return tuple(results)

    def build_dossier(
        self,
        *,
        story: StoryRevision,
        audience_significance: str,
        prior_coverage_refs: Sequence[str],
        created_at: datetime,
        revision: int,
    ) -> StoryDossier:
        evidence = tuple(
            dict.fromkeys(
                ref
                for claim in (*story.verified_claims, *story.disputed_claims)
                for ref in claim.evidence_refs
            )
        ) or tuple(dict.fromkeys((*story.primary_source_refs, *story.secondary_source_refs)))
        if not evidence:
            evidence = story.signal_refs
        return StoryDossier(
            dossier_id=stable_id("dossier", story.story_revision_id, story.publication_id),
            story_id=story.story_id,
            story_revision_ref=story.story_revision_id,
            created_at=created_at,
            organization_id=story.organization_id,
            publication_id=story.publication_id,
            input_refs=(story.story_revision_id, *prior_coverage_refs),
            revision=revision,
            verified_claims=story.verified_claims,
            evidence_lineage=evidence,
            contradictions=tuple(claim.text for claim in story.disputed_claims),
            unknowns=story.unknowns,
            timeline=tuple(
                StoryTimelineEntry(
                    occurred_at=item.occurred_at,
                    summary=item.summary,
                    source_refs=item.source_refs,
                )
                for item in story.material_developments
            ),
            audience_significance=audience_significance,
            possible_angles=(story.title,),
            recommended_framing=f"Explain {story.title} using verified evidence.",
            rejected_framings=("Treat observed popularity as verification.",),
            risk_level=story.editorial_risk,
            prior_coverage_refs=tuple(prior_coverage_refs),
            community_conversation_refs=story.community_reaction_refs,
            suggested_follow_up=story.unknowns,
            frozen_at=created_at,
            generation=_trace("story-dossier", (story,)),
        )

    def plan_agenda(
        self,
        *,
        organization_id: str,
        publication_id: str,
        desk_id: str,
        coverage_window: ResearchWindow,
        dossiers: Sequence[StoryDossier],
        slots: Sequence[PublicationSlot],
        created_at: datetime,
        revision: int,
    ) -> EditorialAgenda:
        ordered = sorted(dossiers, key=lambda item: (item.risk_level.value, item.dossier_id))
        selected = [
            AgendaSelection(dossier_ref=item.dossier_id, rationale=item.audience_significance)
            for item in ordered
        ]
        return EditorialAgenda(
            agenda_id=stable_id(
                "agenda",
                organization_id,
                publication_id,
                desk_id,
                coverage_window.ends_at.isoformat(),
            ),
            created_at=created_at,
            organization_id=organization_id,
            publication_id=publication_id,
            input_refs=tuple(item.dossier_id for item in dossiers),
            revision=revision,
            desk_id=desk_id,
            coverage_window=coverage_window,
            lead_stories=tuple(selected[:1]),
            secondary_stories=tuple(selected[1:]),
            publication_slots=tuple(slots),
            coverage_gaps=() if dossiers else ("No dossiers supplied.",),
            generation=_trace("agenda-planning", tuple(dossiers)),
        )

    def plan_edition(
        self,
        *,
        agenda: EditorialAgenda,
        edition_kind: str,
        publication_window: ResearchWindow,
        update_policy_ref: str,
        human_editor_requirements: Sequence[str],
        created_at: datetime,
        revision: int,
    ) -> EditionPlan:
        dossier_refs = tuple(
            item.dossier_ref for item in (*agenda.lead_stories, *agenda.secondary_stories)
        )
        items = tuple(
            EditionItem(
                slot_ref=slot.slot_id,
                dossier_refs=slot.story_dossier_refs or dossier_refs[:1],
                prominence=index,
                required_content_kinds=(slot.content_kind,),
            )
            for index, slot in enumerate(agenda.publication_slots, start=1)
        )
        return EditionPlan(
            edition_id=stable_id(
                "edition", agenda.agenda_id, edition_kind, publication_window.ends_at.isoformat()
            ),
            created_at=created_at,
            organization_id=agenda.organization_id,
            publication_id=agenda.publication_id,
            input_refs=(agenda.agenda_id,),
            revision=revision,
            agenda_ref=agenda.agenda_id,
            edition_kind=edition_kind,
            publication_window=publication_window,
            lead_items=items[:1],
            supporting_items=items[1:],
            update_policy_ref=update_policy_ref,
            human_editor_requirements=tuple(human_editor_requirements),
            generation=_trace("edition-planning", (agenda,)),
        )
