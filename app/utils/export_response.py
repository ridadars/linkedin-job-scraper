"""Helpers to build downloadable CSV/JSON HTTP responses."""

import json

from fastapi import Response


def csv_response(content: str, filename: str) -> Response:
    """Return a UTF-8 CSV download response with a Content-Disposition header."""
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def json_download_response(payload: dict, filename: str) -> Response:
    """Return a JSON download response with a Content-Disposition header."""
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
