# ADR 0003: Bounded, qualified Zeocore compatibility

- Status: Proposed; not in force until reviewed (ADR 0002's exact pin governs until then)
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
next Zeocore minor release, because Zeocore is still in 0.x. A release inside the
range is admitted only when Creator's gate has qualified it.

Qualification covers only the Zeocore surface Creator actually uses:

- `zeo_core.tools`: `ToolContext`, `capability`, `invoke_sync`,
  `BoundCapability`, `CapabilityRegistry`, `bound_capability_of`;
- `zeo_core.contracts`: `CapabilityExample`, `CapabilityResult`, `EffectKind`,
  `CapabilityId`, `CapabilityRequirements`, `NetworkRequirement`,
  `CapabilityManifest`;
- `zeo_core.contracts.runtime`: `InvocationRequest`, `ProviderBinding`;
- `zeo_core.adapters.runtime_host`: `host.prepare_request`,
  `catalogue.validate_inventory`, and `canonical.canonical_bytes`, `MAX_BYTES`,
  `InvalidRequestError` and `ProtocolError`;
- `zeo_core.adapters.llm_tools`: `OpenAIFunctionTool`, `project_openai_tool`.

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
- Whether the runtime-host protocol version, once Zeocore publishes one, should
  bound compatibility alongside the package version.
- Review by the Zeocore seat of the surface listed above.
