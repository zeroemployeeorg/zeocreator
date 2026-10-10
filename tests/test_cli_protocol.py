"""Other seats operate the CLI through documented verbs, JSON and fixed exit codes."""

import json

from typer.testing import CliRunner

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
