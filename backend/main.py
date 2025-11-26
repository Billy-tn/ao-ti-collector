# backend/main.py
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Tuple
from datetime import datetime

from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from fastapi.openapi.utils import get_openapi
from . import auth, pdf_tools

# ----------------------------------------------------------------------
# Config / DB helpers
# ----------------------------------------------------------------------

DB_PATH = os.environ.get(
    "AO_DB",
    os.path.join(os.path.dirname(__file__), "..", "ao.db"),
)


def _dict_factory(cursor: sqlite3.Cursor, row: Tuple[Any, ...]) -> Dict[str, Any]:
    """
    Transforme un tuple SQLite en dict: {nom_colonne: valeur}
    """
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
    # un header "Authorization" (généré par Header(...) dans auth.py)
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

# on monte les routers sous /api
app.include_router(auth.router, prefix="/api")
app.include_router(pdf_tools.router, prefix="/api")


# ----------------------------------------------------------------------
# Root / health
# ----------------------------------------------------------------------


@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "ok", "app": "ao-collector"}


# ----------------------------------------------------------------------
# Portails (liste déroulante)
# ----------------------------------------------------------------------


@app.get("/api/portals")
def list_portals(
    only_active: bool = Query(default=True),
    country: str = Query(default="ALL"),
):
    con = get_db()
    sql = """
        SELECT DISTINCT
            portal_code AS code,
            portal_label AS label,
            country
        FROM tenders
        WHERE 1=1
    """
    params: List[Any] = []

    if country != "ALL":
        sql += " AND country = ?"
        params.append(country)

    sql += " ORDER BY country, portal_label"

    rows = con.execute(sql, params).fetchall()
    return rows


# ----------------------------------------------------------------------
# Tenders (tableau principal) – protégé par token
# ----------------------------------------------------------------------


@app.get("/api/tenders")
def list_tenders(
    limit: int = Query(default=200, ge=1, le=5000),
    q: str | None = Query(default=None),          # pour l'instant on ne filtre pas dessus
    country: str = Query(default="ALL"),          # idem
    portal: str = Query(default="ALL"),           # idem
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    """
    Version ultra-sécurisée : on ne référence *aucun* nom de colonne.
    On renvoie simplement toutes les colonnes de la table `tenders`
    (la row_factory transforme en dict automatiquement).
    """

    con = get_db()
    _ensure_search_logs_table(con)

    # 🔹 Requête *très* simple : pas de WHERE, pas de colonnes nommées
    sql = """
        SELECT *
        FROM tenders
        LIMIT ?
    """
    params: list[Any] = [limit]

    rows = con.execute(sql, params).fetchall()

    # 🔹 On log quand même la recherche pour garder l’historique
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

    return {
        "items": rows,                 # contient toutes les colonnes existantes
        "count": len(rows),
        "user": current_user.profile.dict(),
    }



# ----------------------------------------------------------------------
# Rapports (stub pour ne pas casser le front)
# ----------------------------------------------------------------------


@app.get("/api/report/categories")
def report_categories(
    q: str | None = Query(default=None),
    top_n: int = Query(default=5),
    max_rows: int = Query(default=5000),
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    # On renvoie un rapport vide (pas de calcul SQL compliqué pour l'instant)
    return {"items": [], "total": 0}


@app.get("/api/report/keywords")
def report_keywords(
    q: str | None = Query(default=None),
    top_n: int = Query(default=5),
    max_rows: int = Query(default=5000),
    current_user: auth.AuthenticatedUser = Depends(auth.get_current_user),
):
    return {"items": [], "total": 0}
