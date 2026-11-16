"""CLI entry point for Agentica Server.

Usage:
    # Start server (default port 8765)
    uv run python -m scripts.agentica.server

    # Custom port
    uv run python -m scripts.agentica.server --port 8000

    # With reload for development
    uv run python -m scripts.agentica.server --reload
"""

import argparse
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Agentica Server - Stateful agent hosting"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run server on (default: 8765)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Install with: uv pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    print(f"Starting Agentica Server on {args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    print(f"Health: http://{args.host}:{args.port}/health")

    uvicorn.run(
        "scripts.agentica.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
