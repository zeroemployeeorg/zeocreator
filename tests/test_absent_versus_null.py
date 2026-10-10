"""Wire rule 7: a digest covers the fully materialized contract, never a sparse one."""

from zeo_creator.capabilities._newsroom_examples import observation
from zeo_creator.contracts.common import canonical_digest
from zeo_creator.contracts.newsroom import SourceObservation


def test_sparse_and_full_forms_differ_on_the_wire_but_validate_to_one_digest() -> None:
    full = observation()
    dumped = full.model_dump(exclude={"content_digest"})
    sparse = full.model_dump(exclude={"content_digest"}, exclude_none=True)
    omitted = set(dumped) - set(sparse)
    assert omitted, "the example must have an unset optional field"
    assert all(dumped[key] is None for key in omitted)
    assert canonical_digest(dumped) == full.content_digest
    assert canonical_digest(sparse) != full.content_digest
    wire = full.model_dump(mode="json", exclude={"content_digest"}, exclude_none=True)
    assert SourceObservation.model_validate(wire).content_digest == full.content_digest
