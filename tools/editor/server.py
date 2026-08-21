"""Loopback-only HTTP server for the translation editor."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .application import EditorApplication

STATIC_ROOT = Path(__file__).resolve().parent / "static"
MAX_REQUEST_BYTES = 1_000_000
MAX_FONT_REQUEST_BYTES = 20_000_000


class EditorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        application: EditorApplication | None = None,
    ) -> None:
        self.application = application or EditorApplication()
        super().__init__(server_address, EditorRequestHandler)


class EditorRequestHandler(BaseHTTPRequestHandler):
    server: EditorHTTPServer

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        try:
            if request.path == "/health":
                self._json({"status": "ok"})
                return
            if request.path == "/api/entries":
                query = parse_qs(request.query)
                raw_limit = query.get("limit", ["250"])[0]
                try:
                    limit = max(1, min(500, int(raw_limit)))
                except ValueError:
                    raise ValueError("limit must be an integer") from None
                self._json(
                    self.server.application.catalog.list_entries(
                        query.get("q", [""])[0], limit
                    )
                )
                return
            if request.path == "/api/entry":
                query = parse_qs(request.query)
                self._json(
                    self.server.application.catalog.entry(
                        self._one(query, "id")
                    )
                )
                return
            if request.path == "/api/fonts":
                query = parse_qs(request.query)
                self._json(
                    self.server.application.fonts.inventory(
                        query.get("language", ["en"])[0]
                    )
                )
                return
            if request.path == "/api/font":
                query = parse_qs(request.query)
                try:
                    offset = int(query.get("offset", ["0"])[0])
                    limit = int(query.get("limit", ["200"])[0])
                except ValueError:
                    raise ValueError("glyph page values must be integers") from None
                self._json(
                    self.server.application.fonts.detail(
                        self._one(query, "id"),
                        query.get("language", ["en"])[0],
                        offset=offset,
                        limit=limit,
                        query=query.get("q", [""])[0],
                    )
                )
                return
            if request.path == "/api/font/update-plan":
                query = parse_qs(request.query)
                self._json(
                    self.server.application.fonts.update_plan(
                        self._one(query, "id"),
                        query.get("language", ["en"])[0],
                    )
                )
                return
            if request.path == "/api/languages":
                self._json(self.server.application.languages.list())
                return
            if request.path == "/api/language":
                query = parse_qs(request.query)
                self._json(
                    self.server.application.languages.detail(self._one(query, "id"))
                )
                return
            if request.path == "/":
                self._file(STATIC_ROOT / "index.html")
                return
            relative = request.path.removeprefix("/")
            if relative in {"app.js", "styles.css"}:
                self._file(STATIC_ROOT / relative)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except RuntimeError as error:
            self._json({"error": str(error)}, HTTPStatus.CONFLICT)
        except ValueError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - final request boundary
            self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        request = urlsplit(self.path)
        if request.path not in {
            "/api/evaluate",
            "/api/languages",
            "/api/font/import",
            "/api/font/update",
        }:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            if request.path == "/api/font/import":
                query = parse_qs(request.query)
                self._json(
                    self.server.application.fonts.import_typeface(
                        self._one(query, "language"),
                        self._one(query, "font"),
                        self._one(query, "filename"),
                        self._request_bytes(MAX_FONT_REQUEST_BYTES),
                    )
                )
                return
            payload = self._request_json()
            if request.path == "/api/font/update":
                self._json(
                    self.server.application.fonts.apply_update(
                        self._text(payload, "id"),
                        self._text(payload, "language"),
                        self._text(payload, "base_hash"),
                        confirm_required=payload.get("confirm_required") is True,
                    )
                )
                return
            if request.path == "/api/languages":
                self._json(
                    self.server.application.languages.create(
                        self._text(payload, "id"),
                        self._text(payload, "label"),
                        self._text(payload, "locale"),
                        self._text(payload, "characters"),
                    ),
                    HTTPStatus.CREATED,
                )
                return
            self._json(
                self.server.application.evaluate(
                    self._text(payload, "id"),
                    self._text(payload, "translation"),
                    payload.get("font8_alphabet"),
                )
            )
        except RuntimeError as error:
            self._json({"error": str(error)}, HTTPStatus.CONFLICT)
        except ValueError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - final request boundary
            self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PATCH(self) -> None:
        request = urlsplit(self.path)
        if request.path not in {
            "/api/entry",
            "/api/font",
            "/api/font/source",
            "/api/language",
        }:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._request_json()
            if request.path == "/api/language":
                self._json(
                    self.server.application.languages.update(
                        self._text(payload, "id"),
                        self._text(payload, "label"),
                        self._text(payload, "locale"),
                        self._text(payload, "characters"),
                        self._text(payload, "base_hash"),
                    )
                )
                return
            if request.path == "/api/font/source":
                self._json(
                    self.server.application.save_font_source(
                        self._text(payload, "id"),
                        self._integer(payload, "code"),
                        self._text(payload, "source_value"),
                        self._text(payload, "base_hash"),
                    )
                )
                return
            if request.path == "/api/font":
                self._json(
                    self.server.application.remap_font(
                        self._text(payload, "id"),
                        self._integer(payload, "code"),
                        self._text(payload, "replacement"),
                        self._text(payload, "base_hash"),
                        language_id=self._text(payload, "language"),
                        confirm_used=payload.get("confirm_used") is True,
                    )
                )
                return
            self._json(
                self.server.application.save(
                    self._text(payload, "id"),
                    self._text(payload, "translation"),
                    self._text(payload, "base_hash"),
                    payload.get("font8_alphabet"),
                )
            )
        except RuntimeError as error:
            self._json({"error": str(error)}, HTTPStatus.CONFLICT)
        except ValueError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - final request boundary
            self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    @staticmethod
    def _one(query: dict[str, list[str]], name: str) -> str:
        values = query.get(name)
        if values is None or len(values) != 1 or not values[0]:
            raise ValueError(f"query parameter {name!r} is required")
        return values[0]

    @staticmethod
    def _text(payload: dict[str, Any], name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str):
            raise ValueError(f"{name} must be text")
        return value

    @staticmethod
    def _integer(payload: dict[str, Any], name: str) -> int:
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
        return value

    def _request_json(self) -> dict[str, Any]:
        raw = self._request_bytes(MAX_REQUEST_BYTES)
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("request body must be valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _request_bytes(self, maximum: int) -> bytes:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "")
        except ValueError:
            raise ValueError("Content-Length is required") from None
        if not 0 < length <= maximum:
            raise ValueError("request body has an invalid size")
        return self.rfile.read(length)

    def _file(self, path: Path) -> None:
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._headers(content_type, len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(
        self, value: object, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self.send_response(status)
        self._headers("application/json; charset=utf-8", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _headers(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'",
        )

    def log_message(self, format: str, *args: Any) -> None:
        return
