# CLI reference

The CLI is intentionally small. It supports discovery and diagnostics, not
production workflow orchestration.

## `zeo-creator capabilities`

List the complete capability catalog:

```console
zeo-creator capabilities
```

Emit canonical JSON:

```console
zeo-creator capabilities --json
```

Emit OpenAI-compatible function projections:

```console
zeo-creator capabilities --projection openai
```

## `zeo-creator runtime-provider`

Added in 0.5.4. Emit the complete installed inventory as
one canonical JSON document for trusted Runtime provisioning:

```console
zeo-creator runtime-provider
```

This performs no invocation or admission. Runtime supplies the verified
`environment_digest` and `generation` to form Core's `ProviderBinding`, then
uses the [shared host](../guides/runtime-host.md) for scoped discovery and calls.

## `zeo-creator doctor`

Check the interpreter, exact Zeocore version, manifest discovery, and projection
compatibility:

```console
zeo-creator doctor --json
```

## Contract schemas

List the stable contract catalog:

```console
zeo-creator contracts list --json
```

Export the schemas bundled in the installed wheel:

```console
zeo-creator contracts export --output=./schemas
```

Print one named contract version:

```console
zeo-creator contract-schema --name=content-brief --version=1
```

## `zeo-creator --version`

```console
zeo-creator --version
```

## Operating protocol

Other seats and tools operate the CLI through this fixed contract:

- `--help` on the root and on every command.
- Machine-readable output: `capabilities --json`, `contracts list --json` and
  `doctor --json` emit JSON when asked. `contracts export`, `contract-schema`
  and `runtime-provider` always emit JSON.
- Exit codes follow Zeocore's `cli_protocol` 1, so they mean the same in every
  ZEO tool:

| Code | Meaning |
|---|---|
| `0` | Done |
| `1` | Internal error: stdout is `{"ok": false, "outcome": "internal"}`, with no detail |
| `2` | Invalid input or command: an unknown command, option or contract |
| `20` | Refused: a check failed (`doctor` reports `"ok": false`) |

Codes 10 to 13 concern remote operations, which this CLI never performs.

## Install, upgrade and rollback

Install a published release as a tool, never a checkout, then check it:

```console
make install VERSION=0.5.4
```

This runs `uv tool install --force "zeocreator==0.5.4"` and then
`zeo-creator doctor --json`. To upgrade, or to roll back, run the same command
with the version you want.

## What is intentionally absent

There is no daily-run, schedule, approve, publish, OAuth, credential, or daemon
command. Those operations belong to Sovereign Agent, a ZEO runtime, or managed
connection infrastructure.
