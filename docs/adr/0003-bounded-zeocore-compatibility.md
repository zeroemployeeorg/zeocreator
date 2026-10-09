# ADR 0003: Bounded, qualified Zeocore compatibility

- Status: Proposed; surface reviewed by the Zeocore seat; not in force until accepted (ADR 0002's exact pin governs until then)
- Date: 2026-10-09
- Decision owner: Creator seat, under the council's K4 direction of 2026-10-09
- Supersedes, once accepted: ADR 0002's exact dependency pin only

The council retained Creator's exact `zeocore[runtime-host]==0.11.0` pin until a
successor decision is reviewed. It also adopted bounded, qualified compatibility
as the direction. Applications lock exact environments; a library should not
demand one global Zeocore release. Creator has no hosted or Broker coupling, so
a Zeocore release made for hosted integrations should not force every Creator
consumer through a Creator release.

## Proposed decision

Creator declares a bounded Zeocore range, not one version. The lower bound is the
oldest release that Creator's gate has qualified. The upper bound excludes the
minor after the newest **qualified** minor (for example `>=0.11.0,<0.15` once
0.14.0 qualifies). Zeocore's 0.x minors may break and it has shipped no patch
releases, so a "below the next minor" bound would admit exactly one version.
The range is only a ceiling: a release inside it is admitted only when Creator's
gate has qualified it, and the qualified list is the admission rule.

Compatibility is also bounded by the runtime-host protocol version. Every
runtime-host message carries `protocol_version` (1 today), and Zeocore treats a
change to it as breaking. A Zeocore release whose protocol version differs from
the qualified one is not admitted, whatever its package version. The wheel does
not ship the protocol's schemas or canonical vectors, so their sha256 values are
pinned from the source tree at the qualified tag.

Qualification covers only the Zeocore surface Creator actually uses:

- `zeo_core.tools`: `ToolContext`, `capability`, `invoke_sync`,
  `BoundCapability`, `CapabilityRegistry`, `bound_capability_of`;
- `zeo_core.contracts`: `CapabilityExample`, `CapabilityResult`, `EffectKind`,
  `CapabilityId`, `CapabilityRequirements`, `NetworkRequirement`,
  `CapabilityManifest`;
- `zeo_core.contracts.runtime`: `InvocationRequest`, `ProviderBinding`;
- `zeo_core.adapters.runtime_host`: `host.prepare_request`,
  `catalogue.validate_inventory`, and `canonical.canonical_bytes`, `digest`,
  `manifest_inventory`, `parse_json`, `MAX_BYTES`, `InvalidRequestError` and
  `ProtocolError`;
- `zeo_core.adapters.llm_tools`: `OpenAIFunctionTool`, `project_openai_tool`.

Creator's tests also use a gate surface, which qualification covers too:
`catalogue.CandidateCatalogue`, `host.parse_result`,
`contracts.CapabilityStatus`, and `contracts.runtime.AttemptBinding` and
`LaunchContext`. The list is measured by parsing every `zeo_core` import in
`src/` and `tests/`, not by line matching, which misses multi-line imports.

The Zeocore seat reviewed this surface on 2026-10-09 (ZEOCORE-SOW-02), and
its tiers carry different risk:

- **Public (20 names):** in a package `__all__` and documented. These are all of
  `tools`, all of `contracts` plus `CapabilityStatus`, all of `contracts.runtime`,
  and `llm_tools`.
- **Documented, no `__all__` (1 name):** `host.parse_result` (test-only).
- **Internal (10 names):** `host.prepare_request`, `catalogue.validate_inventory`
  and `CandidateCatalogue`, and every `canonical` name above. Zeocore's policy
  lets internal names change in any release, including a patch, and 9 of them are
  in `provider.py`. Until Zeocore promotes them to a supported tier, which it has
  offered to do after 0.14.0, they are qualified per release, with the shared
  RFC 8785 vectors run against `canonical_bytes` from the installed wheel, and
  they are the first suspect when a qualification fails.

A Zeocore release qualifies when, installed in a clean environment, it passes:

- the full `make verify`;
- `make doctor`;
- the installed-wheel host conformance;
- an unchanged canonical provider inventory;
- an unchanged contract catalog, so every schema digest stays the same.

The CI matrix runs the gate at the range's lower bound and at the newest
qualified release. A newly published Zeocore is added to the matrix by a reviewed
change. The runtime check in `provider.py` and the doctor check accept a version
only if it is inside the declared range **and** in the qualified list. Neither
check simply compares against one string.

## What does not change

- Creator owns no credentials, authority, scheduling, effects or retries
  (ADR 0001).
- Package versions and contract versions stay separate. A qualified Zeocore
  never changes a public contract digest without a new contract major.
- Runtime still verifies the exact environment it admits. A range in Creator
  widens what can be installed. It does not change what Runtime accepts.

## Open before acceptance

- The range syntax, and whether the qualified list is packaged data or derived
  from the range plus CI evidence.
- How Creator reads the protocol version. Zeocore exports no constant today, and
  has offered `RUNTIME_HOST_PROTOCOL_VERSION` with the promotion of the internal
  tier.
- Zeocore's promotion of the internal tier, after 0.14.0. Until then, those names
  are qualified per release as described above.
