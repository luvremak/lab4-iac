"""mywebapp — Simple Inventory web application (variant V3 = 3).

Business object ``item``:  id, name, quantity, created_at

Business endpoints:
  GET  /items          -> list of all items (id, name)
  POST /items          -> create a new item (name, quantity)
  GET  /items/{id}     -> full details of one item (id, name, quantity, created_at)

Service endpoints:
  GET  /health/alive   -> always 200 OK
  GET  /health/ready   -> 200 OK if the database is reachable, otherwise 500
  GET  /               -> text/html only; lists the business endpoints

Content negotiation:
  Business endpoints inspect the ``Accept`` request header. A client that
  asks for ``text/html`` receives a plain HTML page (tables for lists, no
  JavaScript, no CSS); a client that asks for ``application/json`` receives
  JSON. When the client expresses no preference, JSON is returned.
"""

from __future__ import annotations

import html
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import db
from .config import load_config

# ---------------------------------------------------------------------------
# Application lifespan: open the DB pool on start-up, close it on shutdown.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    db.init_pool(config)
    try:
        yield
    finally:
        db.close_pool()


app = FastAPI(title="mywebapp — Simple Inventory", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ItemIn(BaseModel):
    """Body of POST /items."""

    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=0)


# Description of the business endpoints, reused by the root endpoint.
BUSINESS_ENDPOINTS: list[tuple[str, str, str]] = [
    ("GET", "/items", "List all inventory items (id, name)"),
    ("POST", "/items", "Create a new inventory item (name, quantity)"),
    ("GET", "/items/{id}", "Show full details of one item (id, name, quantity, created_at)"),
]


# ---------------------------------------------------------------------------
# Content negotiation helpers
# ---------------------------------------------------------------------------


def wants_html(request: Request) -> bool:
    """True if the client prefers an HTML response.

    JSON wins when the client lists ``application/json`` explicitly or sends
    no/`*/*` preference (typical for API clients such as curl). HTML is
    returned when the client asks for ``text/html`` and not JSON (typical
    for web browsers).
    """
    accept = request.headers.get("accept", "").lower()
    if "application/json" in accept:
        return False
    if "text/html" in accept:
        return True
    return False


def accepts_html(request: Request) -> bool:
    """True if the client is willing to accept text/html (used by ``/``)."""
    accept = request.headers.get("accept", "").lower()
    if accept == "" or "*/*" in accept:
        return True
    return "text/html" in accept


# ---------------------------------------------------------------------------
# HTML rendering helpers (plain HTML, no JS, no CSS)
# ---------------------------------------------------------------------------


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>{html.escape(title)}</h1>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _render_items_list(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        f"<tr><td>{item['id']}</td><td>{html.escape(item['name'])}</td></tr>\n"
        for item in items
    )
    if not rows:
        rows = '<tr><td colspan="2">No items yet</td></tr>\n'
    return (
        '<table border="1">\n'
        "<thead><tr><th>id</th><th>name</th></tr></thead>\n"
        f"<tbody>\n{rows}</tbody>\n"
        "</table>"
    )


def _render_item(item: dict[str, Any]) -> str:
    return (
        '<table border="1">\n'
        "<tbody>\n"
        f"<tr><th>id</th><td>{item['id']}</td></tr>\n"
        f"<tr><th>name</th><td>{html.escape(str(item['name']))}</td></tr>\n"
        f"<tr><th>quantity</th><td>{item['quantity']}</td></tr>\n"
        f"<tr><th>created_at</th><td>{html.escape(str(item['created_at']))}</td></tr>\n"
        "</tbody>\n"
        "</table>"
    )


def _render_index() -> str:
    rows = "".join(
        f"<tr><td>{html.escape(method)}</td>"
        f"<td>{html.escape(path)}</td>"
        f"<td>{html.escape(description)}</td></tr>\n"
        for method, path, description in BUSINESS_ENDPOINTS
    )
    return (
        "<p>mywebapp — Simple Inventory service. Business endpoints:</p>\n"
        '<table border="1">\n'
        "<thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>\n"
        f"<tbody>\n{rows}</tbody>\n"
        "</table>"
    )


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a database row into a JSON-friendly dict."""
    created_at = row["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    return {
        "id": row["id"],
        "name": row["name"],
        "quantity": row["quantity"],
        "created_at": created_at,
    }


def fetch_items() -> list[dict[str, Any]]:
    with db.get_pool().connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM items ORDER BY id"
        ).fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def fetch_item(item_id: int) -> dict[str, Any] | None:
    with db.get_pool().connection() as conn:
        row = conn.execute(
            "SELECT id, name, quantity, created_at FROM items WHERE id = %s",
            (item_id,),
        ).fetchone()
    return _serialize(row) if row else None


def insert_item(name: str, quantity: int) -> dict[str, Any]:
    with db.get_pool().connection() as conn:
        row = conn.execute(
            "INSERT INTO items (name, quantity) VALUES (%s, %s) "
            "RETURNING id, name, quantity, created_at",
            (name, quantity),
        ).fetchone()
        conn.commit()
    return _serialize(row)


# ---------------------------------------------------------------------------
# Business endpoints
# ---------------------------------------------------------------------------


@app.get("/items")
def list_items(request: Request):
    items = fetch_items()
    if wants_html(request):
        return HTMLResponse(_page("Inventory items", _render_items_list(items)))
    return JSONResponse(items)


@app.post("/items", status_code=201)
def create_item(item: ItemIn, request: Request):
    created = insert_item(item.name, item.quantity)
    if wants_html(request):
        return HTMLResponse(
            _page("Item created", _render_item(created)), status_code=201
        )
    return JSONResponse(created, status_code=201)


@app.get("/items/{item_id}")
def get_item(item_id: int, request: Request):
    item = fetch_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if wants_html(request):
        return HTMLResponse(_page(f"Item {item_id}", _render_item(item)))
    return JSONResponse(item)


# ---------------------------------------------------------------------------
# Service endpoints
# ---------------------------------------------------------------------------


@app.get("/health/alive")
def health_alive():
    """Liveness probe — the process is running."""
    return PlainTextResponse("OK")


@app.get("/health/ready")
def health_ready():
    """Readiness probe — the service can reach its database.

    A short timeout is used so the probe fails fast (rather than blocking on
    the connection pool) when the database is unavailable.
    """
    try:
        with db.get_pool().connection(timeout=3.0) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
        return PlainTextResponse(
            f"not ready: database is unavailable ({exc})", status_code=500
        )
    return PlainTextResponse("OK")


@app.get("/")
def root(request: Request):
    """Root endpoint — consumes and produces text/html only."""
    if not accepts_html(request):
        raise HTTPException(
            status_code=406, detail="This endpoint serves text/html only"
        )
    return HTMLResponse(_page("mywebapp", _render_index()))
