# backend/portal_registry.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "ao.db"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_portal_registry(conn: Optional[sqlite3.Connection] = None) -> None:
    close = False
    if conn is None:
        conn = get_conn()
        close = True

    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portals (
                portal_code   TEXT PRIMARY KEY,
                label         TEXT NOT NULL,
                country       TEXT DEFAULT '',
                source_type   TEXT DEFAULT 'html',  -- html|rss|api|opendata|manual
                base_url      TEXT DEFAULT '',
                rss_url       TEXT DEFAULT '',
                enabled       INTEGER DEFAULT 1,
                trust_score   REAL DEFAULT 0.70,
                notes         TEXT DEFAULT '',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_candidates (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                discovered_url TEXT NOT NULL,
                label          TEXT DEFAULT '',
                country        TEXT DEFAULT '',
                source_type    TEXT DEFAULT 'html',
                evidence_json  TEXT DEFAULT '',
                status         TEXT DEFAULT 'new',  -- new|review|approved|rejected
                created_at     TEXT NOT NULL
            );
            """
        )

        now = _utc_now_iso()
        seeds = [
            {
                "portal_code": "SEAO",
                "label": "SEAO",
                "country": "",
                "source_type": "html",
                "base_url": "https://seao.gouv.qc.ca/",
                "rss_url": "",
                "trust_score": 0.95,
                "notes": "Portail officiel Québec",
            },
            {
                "portal_code": "CanadaBuys",
                "label": "CanadaBuys",
                "country": "",
                "source_type": "html",
                "base_url": "https://canadabuys.canada.ca/",
                "rss_url": "",
                "trust_score": 0.95,
                "notes": "Portail officiel fédéral",
            },
        ]

        for s in seeds:
            cur.execute(
                """
                INSERT INTO portals (
                    portal_code, label, country, source_type, base_url, rss_url,
                    enabled, trust_score, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(portal_code) DO UPDATE SET
                    label=excluded.label,
                    country=excluded.country,
                    source_type=excluded.source_type,
                    base_url=excluded.base_url,
                    rss_url=excluded.rss_url,
                    trust_score=excluded.trust_score,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at;
                """,
                (
                    s["portal_code"],
                    s["label"],
                    s.get("country", ""),
                    s.get("source_type", "html"),
                    s.get("base_url", ""),
                    s.get("rss_url", ""),
                    float(s.get("trust_score", 0.70)),
                    s.get("notes", ""),
                    now,
                    now,
                ),
            )

        conn.commit()
    finally:
        if close:
            conn.close()


def list_portals(enabled_only: bool = True) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        ensure_portal_registry(conn)
        cur = conn.cursor()

        if enabled_only:
            cur.execute(
                """
                SELECT portal_code, label, country, source_type, base_url, rss_url, enabled, trust_score
                FROM portals
                WHERE enabled = 1
                ORDER BY portal_code ASC;
                """
            )
        else:
            cur.execute(
                """
                SELECT portal_code, label, country, source_type, base_url, rss_url, enabled, trust_score
                FROM portals
                ORDER BY portal_code ASC;
                """
            )

        rows = cur.fetchall()
        return [
            {
                "code": r["portal_code"],
                "label": r["label"],
                "country": r["country"] or "",
                "source_type": r["source_type"] or "html",
                "base_url": r["base_url"] or "",
                "rss_url": r["rss_url"] or "",
                "enabled": bool(r["enabled"]),
                "trust_score": float(r["trust_score"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def add_candidate(
    discovered_url: str,
    label: str = "",
    country: str = "",
    source_type: str = "html",
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    conn = get_conn()
    try:
        ensure_portal_registry(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO portal_candidates (
                discovered_url, label, country, source_type, evidence_json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'new', ?);
            """,
            (
                discovered_url.strip(),
                label.strip(),
                country.strip(),
                source_type.strip(),
                json.dumps(evidence or {}, ensure_ascii=False),
                _utc_now_iso(),
            ),
        )
        conn.commit()
        return {"id": cur.lastrowid, "status": "new", "discovered_url": discovered_url}
    finally:
        conn.close()
