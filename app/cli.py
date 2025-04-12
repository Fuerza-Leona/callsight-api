#!/usr/bin/env python3
import argparse
import uvicorn
import sys


def start_server(host: str, port: int, reload: bool) -> None:
    """Start the uvicorn server with the provided configuration."""
    print(f"Starting Callsight API server at {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload, log_level="info")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Callsight API server command line interface"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )

    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    try:
        start_server(args.host, args.port, args.reload)
    except KeyboardInterrupt:
        print("\nShutting down Callsight API server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting Callsight API server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
