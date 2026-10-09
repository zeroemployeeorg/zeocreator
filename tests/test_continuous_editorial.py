"""End-to-end invariants for the continuous editorial protocol."""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from zeo_core.contracts import CapabilityStatus
from zeo_core.tools import invoke_sync

from zeo_creator.capabilities._examples import REQUIREMENTS, publication
from zeo_creator.capabilities._newsroom_examples import NOW, WINDOW, agenda, dossier, observation
from zeo_creator.capabilities._specialization_examples import (
    article_draft,
    article_plan,
    commentary_draft,
    conversation,
    edition,
    newsletter_draft,
    newsletter_plan,
)
from zeo_creator.capabilities.commentary_workflows import ReviewCommentaryRequest
from zeo_creator.capabilities.create_content_brief import CreateContentBriefRequest
from zeo_creator.capabilities.extract_editorial_signals import ExtractEditorialSignalsRequest
from zeo_creator.capabilities.journalism_workflows import ReviewNewsArticleRequest
from zeo_creator.capabilities.plan_content_portfolio import PlanContentPortfolioRequest
from zeo_creator.capabilities.plan_editorial_agenda import PlanEditorialAgendaRequest
from zeo_creator.contracts.commentary import CommentaryDraft
from zeo_creator.contracts.editorial import (
    ContentRequirement,
    PortfolioConstraints,
    PublicationObjective,
)
from zeo_creator.contracts.journalism import HighRiskClassification, NewsArticlePlan
from zeo_creator.contracts.newsroom import (
    PublicationSlot,
    RiskLevel,
    SlotUrgency,
    SourceObservation,
)
from zeo_creator.registry import capability_registry
from zeo_creator.runtime import make_context


def _invoke(capability_id: str, request: Any) -> Any:
    capability = capability_registry().get(capability_id)
    return invoke_sync(
        capability,
        request,
        make_context(capability_name=capability_id),
    )


def test_common_kernel_runs_observation_to_edition() -> None:
    signal_result = _invoke(
        "creator.extract_editorial_signals@1.0.0",
        ExtractEditorialSignalsRequest(
            organization_id="org_example",
            publication_id="publication-a.example",
            observations=(observation(),),
            created_at=NOW,
        ),
    )
    assert signal_result.status is CapabilityStatus.success
    assert signal_result.data is not None
    signals = signal_result.data.signals
    story_result = _invoke(
        "creator.update_story_revisions@1.0.0",
        {
            "organization_id": "org_example",
            "publication_id": "publication-a.example",
            "signals": [item.model_dump(mode="json") for item in signals],
            "previous_revisions": [],
            "created_at": NOW.isoformat(),
        },
    )
    assert story_result.status is CapabilityStatus.success
    story = story_result.data.revisions[0]
    dossier_result = _invoke(
        "creator.build_story_dossier@1.0.0",
        {
            "story": story.model_dump(mode="json"),
            "audience_significance": "Readers need verified context.",
            "prior_coverage_refs": [],
            "created_at": NOW.isoformat(),
            "revision": 1,
        },
    )
    assert dossier_result.status is CapabilityStatus.success
    frozen = dossier_result.data.dossier
    slot = PublicationSlot(
        slot_id="slot_pipeline",
        publication_id=frozen.publication_id,
        desk_id="desk_general",
        content_kind="news.daily-briefing",
        purpose="Summarize the verified development",
        due_at=NOW + timedelta(hours=1),
        urgency=SlotUrgency.DAILY,
        target_channels=("website",),
        story_dossier_refs=(frozen.dossier_id,),
        desired_audience_action="Understand the change",
        risk_policy_ref="risk.general@1",
        approval_policy_ref="approval.editor@1",
    )
    agenda_result = _invoke(
        "creator.plan_editorial_agenda@1.0.0",
        PlanEditorialAgendaRequest(
            organization_id=frozen.organization_id,
            publication_id=frozen.publication_id,
            desk_id="desk_general",
            coverage_window=WINDOW,
            dossiers=(frozen,),
            slots=(slot,),
            created_at=NOW,
        ),
    )
    assert agenda_result.status is CapabilityStatus.success
    edition_result = _invoke(
        "creator.plan_edition@1.0.0",
        {
            "agenda": agenda_result.data.agenda.model_dump(mode="json"),
            "edition_kind": "website.living-day",
            "publication_window": WINDOW.model_dump(mode="json"),
            "update_policy_ref": "updates.living@1",
            "human_editor_requirements": ["desk-editor"],
            "created_at": NOW.isoformat(),
            "revision": 1,
        },
    )
    assert edition_result.status is CapabilityStatus.success
    assert edition_result.data.edition.lead_items[0].slot_ref == slot.slot_id


def test_same_topic_signals_in_one_batch_chain_into_one_story() -> None:
    first = observation()
    second = SourceObservation.model_validate(
        {
            **first.model_dump(mode="json", exclude={"content_digest"}),
            "observation_id": f"{first.observation_id}-second",
            "extracted_text": "A second development on the same story.",
        }
    )
    signals = _invoke(
        "creator.extract_editorial_signals@1.0.0",
        ExtractEditorialSignalsRequest(
            organization_id="org_example",
            publication_id="publication-a.example",
            observations=(first, second),
            created_at=NOW,
        ),
    ).data.signals
    assert len({item.topic for item in signals}) == 1
    result = _invoke(
        "creator.update_story_revisions@1.0.0",
        {
            "organization_id": "org_example",
            "publication_id": "publication-a.example",
            "signals": [item.model_dump(mode="json") for item in signals],
            "previous_revisions": [],
            "created_at": NOW.isoformat(),
        },
    )
    assert result.status is CapabilityStatus.success
    earlier, later = result.data.revisions
    assert earlier.story_id == later.story_id
    assert (earlier.revision, later.revision) == (1, 2)
    assert later.previous_revision_ref == earlier.story_revision_id


def test_publication_crossing_fails_closed() -> None:
    crossed = type(dossier()).model_validate(
        dossier().model_dump(mode="json")
        | {"publication_id": "publication-b.example", "content_digest": ""}
    )
    result = _invoke(
        "creator.plan_editorial_agenda@1.0.0",
        PlanEditorialAgendaRequest(
            organization_id="org_example",
            publication_id="publication-a.example",
            desk_id="desk_general",
            coverage_window=WINDOW,
            dossiers=(crossed,),
            created_at=NOW,
        ),
    )
    assert result.status is CapabilityStatus.error
    assert result.error is not None
    assert result.error.code == "ZEO_CREATOR_PUBLICATION_LEAKAGE"


def test_complete_observation_without_text_fails_closed() -> None:
    with pytest.raises(ValidationError):
        SourceObservation.model_validate(
            observation().model_dump(mode="json") | {"extracted_text": "", "content_digest": ""}
        )


def test_commentary_expires_and_still_requires_human_approval() -> None:
    expired = CommentaryDraft.model_validate(
        commentary_draft().model_dump(mode="json")
        | {"expires_at": (NOW - timedelta(seconds=1)).isoformat(), "content_digest": ""}
    )
    result = _invoke(
        "creator.review_commentary@1.0.0",
        ReviewCommentaryRequest(
            draft=expired,
            conversation=conversation(),
            persona_position_refs=("position_example",),
            approval_policy_ref="approval.human@1",
            created_at=NOW,
        ),
    )
    assert result.status is CapabilityStatus.success
    assert not result.data.review.ready_for_human_approval


def test_high_risk_article_requires_qualified_human_review() -> None:
    risky = NewsArticlePlan.model_validate(
        article_plan().model_dump(mode="json")
        | {
            "risk_level": RiskLevel.HIGH,
            "high_risk_classifications": [HighRiskClassification.PUBLIC_SAFETY],
            "content_digest": "",
        }
    )
    draft = article_draft().model_copy(
        update={
            "organization_id": risky.organization_id,
            "publication_id": risky.publication_id,
            "article_plan_ref": risky.article_plan_id,
        }
    )
    result = _invoke(
        "creator.review_news_article@1.0.0",
        ReviewNewsArticleRequest(plan=risky, draft=draft, created_at=NOW),
    )
    assert result.status is CapabilityStatus.success
    assert result.data.review.qualified_human_required
    assert not result.data.review.ready_for_approval


def test_newsletter_canary_has_html_plain_text_and_lineage() -> None:
    assert edition().edition_kind == "newsletter.issue"
    plan = newsletter_plan()
    draft = newsletter_draft()
    assert plan.sections
    assert draft.html_content.media_type == "text/html"
    assert draft.plain_text_content.media_type == "text/plain"
    assert draft.source_refs


def test_frozen_dossier_and_agenda_feed_the_existing_production_boundary() -> None:
    profile = publication()
    frozen = dossier()
    editorial_agenda = agenda()
    portfolio_result = _invoke(
        "creator.plan_content_portfolio@1.0.0",
        PlanContentPortfolioRequest(
            organization_id=profile.organization_id,
            profiles=(profile,),
            editorial_agendas=(editorial_agenda,),
            story_dossiers=(frozen,),
            objectives=(
                PublicationObjective(
                    publication_id=profile.publication_id,
                    objective="Explain the verified development",
                    desired_audience_action="Understand what changed",
                ),
            ),
            constraints=PortfolioConstraints(
                requirements=(ContentRequirement(content_kind="news.article", quantity=1),)
            ),
            planning_window=WINDOW,
            due_at=NOW + timedelta(hours=4),
            created_at=NOW,
        ),
    )
    assert portfolio_result.status is CapabilityStatus.success
    assignment = portfolio_result.data.plan.assignments[0]
    brief_result = _invoke(
        "creator.create_content_brief@1.0.0",
        CreateContentBriefRequest(
            assignment=assignment,
            publication=profile,
            dossier=frozen,
            creative_direction="Produce a concise verified explainer.",
            delivery_requirements=REQUIREMENTS,
            created_at=NOW,
        ),
    )
    assert brief_result.status is CapabilityStatus.success
    assert brief_result.data.brief.source_refs == frozen.verified_claims[0].evidence_refs
