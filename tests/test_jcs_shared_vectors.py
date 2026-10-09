import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import rfc8785

from zeo_creator.contracts.common import canonical_digest

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "contracts" / "jcs-shared-vectors-v1.json").read_text(
        encoding="utf-8"
    )
)


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"non-JSON constant {name}")


def _refuse_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    names = [name for name, _ in pairs]
    if len(set(names)) != len(names):
        raise ValueError("duplicate member name")
    return dict(pairs)


def _canonical(text: str) -> bytes:
    value = json.loads(text, parse_constant=_refuse_constant, object_pairs_hook=_refuse_duplicates)
    return rfc8785.dumps(value)


@pytest.mark.parametrize("vector", FIXTURE["valid"], ids=lambda vector: vector["name"])
def test_valid_vector_reproduces_canonical_bytes(vector: dict[str, str]) -> None:
    canonical = _canonical(vector["input_json"])

    assert canonical.decode("utf-8") == vector["canonical_text"]
    assert hashlib.sha256(canonical).hexdigest() == vector["sha256"]


@pytest.mark.parametrize("vector", FIXTURE["invalid"], ids=lambda vector: vector["name"])
def test_invalid_vector_is_refused(vector: dict[str, str]) -> None:
    with pytest.raises((ValueError, rfc8785.CanonicalizationError, UnicodeEncodeError)):
        _canonical(vector["input_json"])


def test_creator_digest_uses_the_same_canonical_bytes() -> None:
    vector = next(v for v in FIXTURE["valid"] if v["name"] == "key-order-utf16-vs-codepoint")
    value = json.loads(vector["input_json"])

    assert canonical_digest(value) == f"sha256:{vector['sha256']}"
