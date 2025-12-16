from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from . import ai_tools, auth, pdf_tools
from pydantic import BaseModel
from backend.collect_ted import run as run_ted

# ----------------------------------------------------------------------
# Config / DB helpers
# ----------------------------------------------------------------------

DB_PATH = os.environ.get(
    "AO_DB",
    os.path.join(os.path.dirname(__file__), "..", "ao.db"),
)


def _dict_factory(cursor: sqlite3.Cursor, row: Tuple[Any, ...]) -> Dict[str, Any]:
    """Transforme un tuple SQLite en dict: {nom_colonne: valeur}"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = _dict_factory
    return con


def _ensure_search_logs_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            searched_at TEXT NOT NULL,
            country TEXT,
            portal_code TEXT,
            q TEXT,
            limit_requested INTEGER,
            results_count INTEGER
        )
        """
    )


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------

app = FastAPI(title="AO Collector", version="1.0")


def custom_openapi():
    # cache
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    # Déclare le "scheme" Bearer pour Swagger UI (bouton Authorize)
    components = schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    

    # Ajoute automatiquement la sécurité aux endpoints qui déclarent
    # un header "Authorization"
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            params = operation.get("parameters", []) or []
            has_auth_header = any(
                isinstance(p, dict)
                and p.get("in") == "header"
                and p.get("name", "").lower() == "authorization"
                for p in params
            )
            if has_auth_header:
                operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers sous /api
app.include_router(auth.router, prefix="/api")
app.include_router(pdf_tools.router, prefix="/api")
app.include_router(ai_tools.router, prefix="/api")

# ----------------------------------------------------------------------
# Root
# ----------------------------------------------------------------------


@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "ok", "app": "ao-collector"}


# ----------------------------------------------------------------------
# Portails
#  - /api/portals : registry (source_portals) -> affiche tous les portails même si 0 AO collecté
#  - /api/portals/observed : portails observés dans tenders.portal_name (debug)
# ----------------------------------------------------------------------


@app.get("/api/portals")
def list_portals(
    only_active: bool = Query(default=True),
    country: str = Query(default="ALL"),
):
    con = get_db()
    try:
        sql = """
            SELECT
                code AS code,
                name AS label,
                country AS country,
                region AS region,
                base_url AS base_url,
                api_type AS api_type,
                is_active AS is_active,
                notes AS notes
            FROM source_portals
            WHERE 1=1
        """
        params: List[Any] = []

        if only_active:
            sql += " AND is_active = 1"

        if country != "ALL":
            sql += " AND country = ?"
            params.append(country)

        sql += " ORDER BY country, region, code"
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


@app.get("/api/portals/observed")
def list_portals_observed(
    country: str = Query(default="ALL"),
):
    """Retourne les portails réellement présents dans tenders (collecte déjà faite)."""
    con = get_db()
    try:
        sql = """
            SELECT DISTINCT
                portal_name AS code,
                portal_name AS label,
                country AS country
            FROM tenders
            WHERE portal_name IS NOT NULL AND portal_name != ''
        """
        params: List[Any] = []
        if country != "ALL":
            sql += " AND country = ?"
            params.append(country)

        sql += " ORDER BY country, portal_name"
        return con.execute(sql, params).fetchall()
    finally:
        con.close()



class CollectRunRequest(BaseModel):
    portal: str
    limit: int = 100
    start_token: Optional[str] = None
    pd_days: int = 90
    terms: Optional[str] = None
    query: Optional[str] = None
    per_page: int = 100


@app.post("/api/collect/run")
def collect_run(
    payload: CollectRunRequest,
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    portal = (payload.portal or "").strip().upper()
    limit = int(payload.limit or 100)

    if limit < 1 or limit > 500:
        return {"error": "limit must be between 1 and 500"}

    if portal == "TED_EU":
        return run_ted(limit=limit)

    return {"error": f"Unsupported portal: {portal}"}


# ----------------------------------------------------------------------
# Tenders – protégé par token
# ----------------------------------------------------------------------


@app.get("/api/tenders")
def list_tenders(
    limit: int = Query(default=200, ge=1, le=5000),
    q: str | None = Query(default=None),
    country: str = Query(default="ALL"),
    portal: str = Query(default="ALL"),
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    con = get_db()
    try:
        _ensure_search_logs_table(con)

        sql = """
        SELECT *
        FROM tenders
        LIMIT ?
        """
        rows = con.execute(sql, [limit]).fetchall()

        con.execute(
            """
            INSERT INTO search_logs (searched_at, country, portal_code, q, limit_requested, results_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                country,
                None if portal == "ALL" else portal,
                q,
                limit,
                len(rows),
            ),
        )
        con.commit()

        return {"items": rows, "count": len(rows), "user": current_user.profile.dict()}
    finally:
        con.close()


# ----------------------------------------------------------------------
# Rapports (stub)
# ----------------------------------------------------------------------


@app.get("/api/report/categories")
def report_categories(
    q: str | None = Query(default=None),
    top_n: int = Query(default=5),
    max_rows: int = Query(default=5000),
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    return {"items": [], "total": 0}


@app.get("/api/report/keywords")
def report_keywords(
    q: str | None = Query(default=None),
    top_n: int = Query(default=5),
    max_rows: int = Query(default=5000),
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    return {"items": [], "total": 0}
