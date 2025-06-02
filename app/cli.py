import typer
import subprocess

app = typer.Typer()


@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    dev: bool = typer.Option(
        False, "--dev", is_flag=True, help="Enable development mode (auto-reload)"
    ),
    log_level: str = "info",
):
    """
    Start the CallSight API server using uvicorn.
    """
    if dev:
        reload = True

    cmd = [
        "uvicorn",
        "app.main:app",
        f"--host={host}",
        f"--port={port}",
        f"--log-level={log_level}",
    ]

    if reload:
        cmd.append("--reload")

    print(
        f"Starting server at http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
    )
    subprocess.run(cmd)


if __name__ == "__main__":
    app()
