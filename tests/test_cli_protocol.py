"""Other seats operate the CLI through documented verbs, JSON and fixed exit codes."""

import json
import sys

import pytest
from typer.testing import CliRunner

import zeo_creator.cli as cli
from zeo_creator.cli import app

runner = CliRunner()


def test_every_command_has_help() -> None:
    for args in (
        [],
        ["capabilities"],
        ["contracts", "list"],
        ["contracts", "export"],
        ["contract-schema"],
        ["doctor"],
        ["runtime-provider"],
    ):
        result = runner.invoke(app, [*args, "--help"])
        assert result.exit_code == 0, args


def test_json_verbs_emit_json() -> None:
    for args in (
        ["capabilities", "--json"],
        ["contracts", "list", "--json"],
        ["doctor", "--json"],
        ["runtime-provider"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, args
        json.loads(result.stdout)


def test_bad_input_exits_two() -> None:
    assert runner.invoke(app, ["no-such-command"]).exit_code == 2
    assert runner.invoke(app, ["capabilities", "--no-such-option"]).exit_code == 2
    unknown = runner.invoke(
        app, ["contract-schema", "--name", "no-such-contract", "--version", "1"]
    )
    assert unknown.exit_code == 2


def test_a_failed_check_is_refused_with_twenty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "capability_manifests", lambda: ())
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 20
    assert json.loads(result.stdout)["ok"] is False


def test_an_internal_error_exits_one_without_detail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> None:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(cli, "capability_manifests", broken)
    monkeypatch.setattr(sys, "argv", ["zeo-creator", "capabilities", "--json"])
    with pytest.raises(SystemExit) as exited:
        cli.main()
    assert exited.value.code == 1
    out = capsys.readouterr().out
    assert json.loads(out) == {"ok": False, "outcome": "internal"}
    assert "secret detail" not in out
