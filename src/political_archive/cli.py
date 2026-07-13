"""Typer entry point for the Political Archive command line interface."""

import typer

from political_archive import __version__

app = typer.Typer(
    name="political-archive",
    help=(
        "Political Archive Crawler development CLI. "
        "M0 currently provides project foundations only."
    ),
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print the installed package version when requested."""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def cli_callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        help="Show the installed package version.",
    ),
) -> None:
    """Run the currently available foundation CLI."""
    del version


def main() -> None:
    """Run the Typer application."""
    app()
