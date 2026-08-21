"""Command-line entry point for the local translation editor."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from collections.abc import Sequence

from .server import EditorHTTPServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open the translation editor.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise SystemExit("--port must be between 0 and 65535")
    server = EditorHTTPServer(("127.0.0.1", args.port))
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Translation editor: {url}")
    if not args.no_browser:
        threading.Timer(0.25, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

