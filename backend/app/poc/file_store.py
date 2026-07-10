"""File-based Quick PoC loader.

Drop files under data/poc-files/ and they become live routes:

- data/poc-files/xss.html -> /p/xss
- data/poc-files/probe.js -> /p/probe
- data/poc-files/kit/index.html -> /p/kit
- data/poc-files/kit/payload.js -> /p/kit/payload.js
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from .base import PocMeta, PocRequest, PocResponse


PROJECT_ROOT = Path(__file__).resolve().parents[3]
POC_FILE_DIR = PROJECT_ROOT / "data" / "poc-files"

SUPPORTED_SUFFIXES = {
    ".html",
    ".htm",
    ".js",
    ".mjs",
    ".txt",
    ".json",
    ".xml",
    ".svg",
    ".css",
    ".sh",
    ".py",
    ".ps1",
    ".php",
}

CONTENT_TYPE_OVERRIDES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".sh": "text/plain",
    ".py": "text/plain",
    ".ps1": "text/plain",
    ".php": "application/x-httpd-php",
}

_runtime_file_pocs: dict[str, PocMeta] = {}


def _guess_content_type(path: Path) -> str:
    content_type = CONTENT_TYPE_OVERRIDES.get(path.suffix.lower())
    if content_type:
        return content_type
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _default_usage(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix in {".js", ".mjs"}:
        return '<script src="{url}"></script>'
    if suffix in {".html", ".htm"}:
        return '{url}'
    return None


def _safe_resolve(base_dir: Path, relative_path: str) -> Optional[Path]:
    target = (base_dir / relative_path).resolve()
    try:
        target.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return target


def _find_index_file(dir_path: Path) -> Optional[Path]:
    for suffix in SUPPORTED_SUFFIXES:
        candidate = dir_path / f"index{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _read_file_response(path: Path) -> PocResponse:
    content_type = _guess_content_type(path)
    raw = path.read_bytes()

    if content_type.startswith("text/") or content_type in {
        "application/json",
        "application/xml",
        "application/x-httpd-php",
    }:
        body: str | bytes = raw.decode("utf-8", errors="replace")
    else:
        body = raw

    return PocResponse(body=body, content_type=content_type)


def _build_handler(route_name: str, entry_path: Path):
    async def _handler(req: PocRequest) -> PocResponse:
        if entry_path.is_file():
            if req.path:
                return PocResponse(body="PoC Path Not Found", status_code=404, content_type="text/plain")
            return _read_file_response(entry_path)

        sub_path = req.path.strip("/")
        if not sub_path:
            index_file = _find_index_file(entry_path)
            if not index_file:
                return PocResponse(body="PoC Index Not Found", status_code=404, content_type="text/plain")
            return _read_file_response(index_file)

        target = _safe_resolve(entry_path, sub_path)
        if not target or not target.is_file():
            return PocResponse(body="PoC File Not Found", status_code=404, content_type="text/plain")

        return _read_file_response(target)

    return _handler


def _build_meta(route_name: str, entry_path: Path, existing: Optional[PocMeta]) -> PocMeta:
    if entry_path.is_file():
        sample_path = entry_path
    else:
        sample_path = _find_index_file(entry_path) or entry_path

    return PocMeta(
        name=route_name,
        description=f"File response from {entry_path.relative_to(PROJECT_ROOT)}",
        category="custom",
        content_type=_guess_content_type(sample_path) if sample_path.is_file() else "text/plain",
        record=True,
        usage=_default_usage(sample_path) if sample_path.is_file() else '{url}',
        handler=_build_handler(route_name, entry_path),
        hit_count=existing.hit_count if existing else 0,
        response_body=None,
        status_code=200,
        redirect_url=None,
        enable_variables=False,
        filename=sample_path.name if sample_path.is_file() else None,
    )


def _discover_entries() -> dict[str, Path]:
    entries: dict[str, Path] = {}
    if not POC_FILE_DIR.exists():
        return entries

    for child in sorted(POC_FILE_DIR.iterdir()):
        if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
            entries.setdefault(child.stem, child)
        elif child.is_dir():
            entries.setdefault(child.name, child)
    return entries


def refresh_file_pocs() -> dict[str, PocMeta]:
    entries = _discover_entries()
    current_names = set(entries.keys())

    for name in list(_runtime_file_pocs.keys()):
        if name not in current_names:
            del _runtime_file_pocs[name]

    for name, entry_path in entries.items():
        existing = _runtime_file_pocs.get(name)
        _runtime_file_pocs[name] = _build_meta(name, entry_path, existing)

    return dict(_runtime_file_pocs)


def get_file_poc(name: str) -> Optional[PocMeta]:
    return refresh_file_pocs().get(name)


def get_all_file_pocs() -> list[PocMeta]:
    return list(refresh_file_pocs().values())
