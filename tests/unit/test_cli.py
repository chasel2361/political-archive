from typer.testing import CliRunner

from political_archive.cli import app


def test_cli_help_is_available() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Political Archive Crawler" in result.stdout
    assert "--version" in result.stdout
