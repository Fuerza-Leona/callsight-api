import typer
import subprocess

app = typer.Typer()


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Start the CallSight API server using uvicorn.
    """
    cmd = ["uvicorn", "app.main:app", f"--host={host}", f"--port={port}"]

    if reload:
        cmd.append("--reload")

    print(
        f"Starting server at http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
    )
    subprocess.run(cmd)


if __name__ == "__main__":
    app()
