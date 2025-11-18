# backend/main.py
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Tuple
from datetime import datetime
from collections import Counter
import re

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ----------------------------------------------------------------------
# Config / DB helpers
# ----------------------------------------------------------------------

DB_PATH = os.environ.get(
    "AO_DB",
    os.path.join(os.path.dirname(__file__), "..", "ao.db")
)


def _dict_factory(cursor: sqlite3.Cursor, row: Tuple[Any, ...]) -> Dict[str, Any]:
  return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_db() -> sqlite3.Connection:
  con = sqlite3.connect(DB_PATH)
  con.row_factory = _dict_factory
  return con


def _ensure_search_logs_table(con: sqlite3.Connection) -> None:
  """
  Crée la table search_logs si elle n'existe pas encore.
  Cette table sert à journaliser chaque appel à /api/tenders.
  """
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

# CORS: on autorise le front Codespaces/Vite
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],        # Codespaces/preview → origin dynamique
  allow_credentials=False,
  allow_methods=["*"],
  allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Root / health
# ----------------------------------------------------------------------


@app.get("/")
def root():
  return {
      "app": "AO Collector",
      "message": "API en ligne. Utilise /api/portals, /api/tenders, /api/search-logs et /api/report/*.",
  }


@app.get("/health")
def health():
  try:
      with get_db() as con:
          con.execute("SELECT 1")
      return {"ok": True}
  except Exception as e:
      return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# ----------------------------------------------------------------------
# /api/portals
# ----------------------------------------------------------------------


@app.get("/api/portals")
def list_portals(
  only_active: bool = Query(False, description="Limiter aux portails actifs"),
  country: str | None = Query(
      None, description="Filtrer par code pays (CA, US, EU, etc.)"
  ),
):
  """
  Retourne le catalogue des portails (table source_portals).

  On suppose que la table source_portals contient au minimum:
    - code
    - name
    - country
    - region
    - base_url
    - api_type
    - is_active
  """
  sql = """
      SELECT code, name, country, region, base_url, api_type, is_active
      FROM source_portals
  """
  where: List[str] = []
  params: List[Any] = []

  if only_active:
      where.append("is_active = 1")
  if country and country.strip() and country.upper() not in ("ALL", "TOUS"):
      where.append("UPPER(country) = UPPER(?)")
      params.append(country.strip())

  if where:
      sql += " WHERE " + " AND ".join(where)

  sql += " ORDER BY CASE WHEN is_active=1 THEN 0 ELSE 1 END, UPPER(name)"

  with get_db() as con:
      rows = con.execute(sql, params).fetchall()
  return rows

# ----------------------------------------------------------------------
# /api/tenders
# ----------------------------------------------------------------------


def _like(term: str) -> str:
  return f"%{term.lower()}%"


def _build_tenders_sql_and_params(
  country: str | None,
  portal_code: str | None,
  q: str | None,
  limit: int | None = None,
) -> Tuple[str, List[Any]]:
  """
  Construit la requête SQL et la liste de paramètres pour interroger la table tenders.
  Réutilisée par /api/tenders et /api/report/* pour garder la même logique de filtre.
  """
  base_sql = """
      SELECT *
      FROM tenders
      WHERE
          title <> '' AND url <> ''
  """

  where: List[str] = []
  params: List[Any] = []

  # Filtre pays -> colonne "country"
  if country and country.strip() and country.upper() not in ("ALL", "TOUS"):
      where.append("UPPER(country) = UPPER(?)")
      params.append(country.strip())

  # Filtre portail -> "source" ou "portal_name"
  if portal_code and portal_code.strip() and portal_code.upper() not in ("ALL", "TOUS"):
      where.append(
          "("
          "UPPER(source) = UPPER(?) "
          "OR INSTR(UPPER(portal_name), UPPER(?)) > 0"
          ")"
      )
      params.extend([portal_code.strip(), portal_code.strip()])

  # Recherche plein-texte simple sur les colonnes historiques
  if q and q.strip():
      terms = [t for t in q.split() if t.strip()]
      for t in terms:
          where.append(
              "("
              "LOWER(title)       LIKE ? OR "
              "LOWER(buyer)       LIKE ? OR "
              "LOWER(source)      LIKE ? OR "
              "LOWER(portal_name) LIKE ?"
              ")"
          )
          like = _like(t)
          params.extend([like, like, like, like])

  sql = base_sql
  if where:
      sql += " AND " + " AND ".join(where)

  # Tri: published_at si présent, puis id desc
  sql += """
      ORDER BY
          CASE
              WHEN published_at IS NOT NULL AND published_at <> ''
              THEN published_at
          END DESC,
          id DESC
  """

  if limit is not None:
      sql += " LIMIT ?"
      params.append(limit)

  return sql, params


@app.get("/api/tenders")
def list_tenders(
  country: str | None = Query(
      None, alias="country", description="Code pays (CA, US, EU, etc.)"
  ),
  country_code: str | None = Query(None, alias="country_code"),
  portal_code: str | None = Query(
      None, alias="portal_code", description="Code portail (SEAO, CANADABUYS, …)"
  ),
  portal: str | None = Query(None, alias="portal"),
  q: str | None = Query(
      None,
      description="Mots-clés (séparés par espace) sur titre/acheteur/source/portail",
  ),
  limit: int = Query(
      200,
      ge=1,
      le=1000,
      description="Nombre max de lignes",
  ),
):
  """
  Liste des AO depuis la table tenders, avec filtres légers.

  Schéma BD (version historique) :
    - id, source, portal_name, buyer, title, url,
      published_at, country, region, ...
  + colonnes ajoutées pour l'analyse :
    - categorie_principale, score_pertinence, budget,
      mots_cles_detectes, etc.

  JSON renvoyé au frontend :
    - id, source, portal, country, region, buyer, title, url,
      published_at, closing_at, budget, category,
      matched_keywords, score
  """
  # Harmoniser alias
  if not portal_code and portal:
      portal_code = portal
  if not country and country_code:
      country = country_code

  sql, params = _build_tenders_sql_and_params(country, portal_code, q, limit)

  with get_db() as con:
      rows = con.execute(sql, params).fetchall()

      # --- Journalisation de la recherche dans search_logs ---
      try:
          _ensure_search_logs_table(con)
          con.execute(
              """
              INSERT INTO search_logs (
                  searched_at,
                  country,
                  portal_code,
                  q,
                  limit_requested,
                  results_count
              )
              VALUES (?, ?, ?, ?, ?, ?)
              """,
              (
                  datetime.utcnow().isoformat(timespec="seconds"),
                  country.strip() if isinstance(country, str) and country.strip() else None,
                  portal_code.strip() if isinstance(portal_code, str) and portal_code.strip() else None,
                  q.strip() if isinstance(q, str) and q.strip() else None,
                  limit,
                  len(rows),
              ),
          )
          # le commit sera fait par le context manager "with"
      except Exception:
          # On ne casse pas l'API si la journalisation échoue
          pass

  # Mapping colonnes BD -> JSON propre pour le frontend
  mapped: List[Dict[str, Any]] = []
  for row in rows:
      mapped.append(
          {
              "id": row.get("id"),

              # Source brute (code, plateforme...)
              "source": row.get("source") or row.get("plateforme"),

              # Portail lisible / code
              "portal": row.get("portal") or row.get("portal_name") or row.get("portail"),

              # Pays / région
              "country": row.get("country") or row.get("pays"),
              "region": row.get("region"),

              # Acheteur
              "buyer": row.get("buyer") or row.get("acheteur"),

              # Titre + lien
              "title": row.get("title") or row.get("titre"),
              "url": row.get("url") or row.get("lien"),

              # Dates
              "published_at": row.get("published_at") or row.get("date_publication"),
              "closing_at": row.get("closing_at") or row.get("date_cloture"),

              # Budget
              "budget": row.get("budget"),

              # Catégorie lisible
              "category": (
                  row.get("category")
                  or row.get("categorie_principale")
                  or row.get("categories_unspsc")
              ),

              # Mots-clés détectés
              "matched_keywords": row.get("matched_keywords")
              or row.get("mots_cles_detectes"),

              # Score de pertinence
              "score": row.get("score")
              or row.get("score_pertinence"),
          }
      )

  return mapped

# ----------------------------------------------------------------------
# /api/search-logs – journal des recherches
# ----------------------------------------------------------------------


@app.get("/api/search-logs")
def list_search_logs(
  limit: int = Query(
      50,
      ge=1,
      le=1000,
      description="Nombre max de recherches renvoyées (ordre décroissant)",
  )
):
  """
  Retourne les recherches effectuées récemment sur /api/tenders.
  Utile pour diagnostiquer, et aussi base pour des rapports.
  """
  with get_db() as con:
      _ensure_search_logs_table(con)
      rows = con.execute(
          """
          SELECT
              id,
              searched_at,
              country,
              portal_code,
              q,
              limit_requested,
              results_count
          FROM search_logs
          ORDER BY searched_at DESC, id DESC
          LIMIT ?
          """,
          (limit,),
      ).fetchall()

  return rows

# ----------------------------------------------------------------------
# /api/report/categories – rapport par catégories
# ----------------------------------------------------------------------


@app.get("/api/report/categories")
def report_by_categories(
  country: str | None = Query(
      None, alias="country", description="Code pays (CA, US, EU, etc.)"
  ),
  country_code: str | None = Query(None, alias="country_code"),
  portal_code: str | None = Query(
      None, alias="portal_code", description="Code portail (SEAO, CANADABUYS, …)"
  ),
  portal: str | None = Query(None, alias="portal"),
  q: str | None = Query(
      None,
      description="Mots-clés (séparés par espace) sur titre/acheteur/source/portail",
  ),
  max_rows: int = Query(
      5000,
      ge=100,
      le=20000,
      description="Nombre max de lignes sources analysées",
  ),
  top_n: int = Query(
      50,
      ge=1,
      le=200,
      description="Nombre de catégories renvoyées (top N)",
  ),
):
  """
  Rapport simple: distribution des AO par catégorie.

  Utilise les mêmes filtres que /api/tenders, puis agrège:
    - category / categorie_principale / categories_unspsc
  """
  if not portal_code and portal:
      portal_code = portal
  if not country and country_code:
      country = country_code

  sql, params = _build_tenders_sql_and_params(country, portal_code, q, limit=max_rows)

  with get_db() as con:
      rows = con.execute(sql, params).fetchall()

  counter: Counter[str] = Counter()
  for row in rows:
      raw = (
          row.get("category")
          or row.get("categorie_principale")
          or row.get("categories_unspsc")
      )
      if not raw:
          continue

      # On découpe sur ; , |
      parts = re.split(r"[;,|]", str(raw))
      for part in parts:
          name = part.strip()
          if not name:
              continue
          counter[name] += 1

  total_tenders = len(rows)
  top_categories = [
      {"category": name, "count": count}
      for name, count in counter.most_common(top_n)
  ]

  return {
      "total_tenders": total_tenders,
      "distinct_categories": len(counter),
      "categories": top_categories,
  }

# ----------------------------------------------------------------------
# /api/report/keywords – rapport par mots-clés détectés
# ----------------------------------------------------------------------


@app.get("/api/report/keywords")
def report_by_keywords(
  country: str | None = Query(
      None, alias="country", description="Code pays (CA, US, EU, etc.)"
  ),
  country_code: str | None = Query(None, alias="country_code"),
  portal_code: str | None = Query(
      None, alias="portal_code", description="Code portail (SEAO, CANADABUYS, …)"
  ),
  portal: str | None = Query(None, alias="portal"),
  q: str | None = Query(
      None,
      description="Mots-clés (séparés par espace) sur titre/acheteur/source/portail",
  ),
  max_rows: int = Query(
      5000,
      ge=100,
      le=20000,
      description="Nombre max de lignes sources analysées",
  ),
  top_n: int = Query(
      50,
      ge=1,
      le=200,
      description="Nombre de mots-clés renvoyés (top N)",
  ),
):
  """
  Rapport simple: distribution des AO par mots-clés détectés.

  Utilise les mêmes filtres que /api/tenders, puis agrège:
    - matched_keywords / mots_cles_detectes
  """
  if not portal_code and portal:
      portal_code = portal
  if not country and country_code:
      country = country_code

  sql, params = _build_tenders_sql_and_params(country, portal_code, q, limit=max_rows)

  with get_db() as con:
      rows = con.execute(sql, params).fetchall()

  counter: Counter[str] = Counter()
  for row in rows:
      raw = row.get("matched_keywords") or row.get("mots_cles_detectes")
      if not raw:
          continue

      parts = re.split(r"[;,|]", str(raw))
      for part in parts:
          term = part.strip()
          if not term:
              continue
          counter[term] += 1

  total_tenders = len(rows)
  top_keywords = [
      {"keyword": term, "count": count}
      for term, count in counter.most_common(top_n)
  ]

  return {
      "total_tenders": total_tenders,
      "distinct_keywords": len(counter),
      "keywords": top_keywords,
  }
