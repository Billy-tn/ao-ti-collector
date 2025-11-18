// frontend/src/App.tsx
import React, { useEffect, useMemo, useState } from "react";
import "./App.css";

type Portal = {
  code: string;
  name: string;
  country: string;
  region?: string | null;
  base_url?: string | null;
  api_type?: string | null;
  is_active?: boolean | 0 | 1;
};

type Tender = {
  id: number;
  source: string;
  portal: string;
  country: string | null;
  region: string | null;
  buyer: string | null;
  title: string;
  url: string;
  published_at: string | null;
  closing_at: string | null;
  budget: number | null;
  category: string | null;
  matched_keywords: string | null;
  score: number | null;
};

type ColumnKey =
  | "id"
  | "title"
  | "portal"
  | "source"
  | "buyer"
  | "country"
  | "region"
  | "budget"
  | "published_at"
  | "closing_at"
  | "score";

type QuickField =
  | "title"
  | "buyer"
  | "portal"
  | "source"
  | "country"
  | "region"
  | "category"
  | "matched_keywords";

type SortState = {
  key: ColumnKey;
  direction: "asc" | "desc";
};

type CategoryReport = {
  total_tenders: number;
  distinct_categories: number;
  categories: { category: string; count: number }[];
};

type KeywordReport = {
  total_tenders: number;
  distinct_keywords: number;
  keywords: { keyword: string; count: number }[];
};

const API_BASE_URL =
  ((import.meta as any).env?.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/+$/,
    ""
  ) || "/api";

const ALL_COLUMNS: {
  key: ColumnKey;
  label: string;
  align?: "left" | "center" | "right";
  locked?: boolean;
}[] = [
  { key: "id", label: "ID", align: "left", locked: true },
  { key: "title", label: "Titre", align: "left", locked: true },
  { key: "portal", label: "Portail" },
  { key: "source", label: "Source" },
  { key: "buyer", label: "Acheteur" },
  { key: "country", label: "Pays", align: "center" },
  { key: "region", label: "Région", align: "center" },
  { key: "budget", label: "Budget", align: "right" },
  { key: "published_at", label: "Publiée", align: "center" },
  { key: "closing_at", label: "Fermeture", align: "center" },
  { key: "score", label: "Score", align: "right" },
];

const QUICK_FIELD_OPTIONS: { value: QuickField; label: string }[] = [
  { value: "title", label: "Titre" },
  { value: "buyer", label: "Acheteur" },
  { value: "portal", label: "Portail" },
  { value: "source", label: "Source" },
  { value: "country", label: "Pays" },
  { value: "region", label: "Région" },
  { value: "category", label: "Catégorie" },
  { value: "matched_keywords", label: "Mots-clés" },
];

const App: React.FC = () => {
  const [portals, setPortals] = useState<Portal[]>([]);
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filtres principaux
  const [countryFilter, setCountryFilter] = useState<string>("ALL");
  const [portalFilter, setPortalFilter] = useState<string>("ALL");
  const [query, setQuery] = useState<string>("");

  // 🔍 Un seul filtre rapide dynamique
  const [quickField, setQuickField] = useState<QuickField>("title");
  const [quickValue, setQuickValue] = useState<string>("");

  // Colonnes visibles
  const [visibleColumns, setVisibleColumns] = useState<Set<ColumnKey>>(
    () =>
      new Set<ColumnKey>([
        "id",
        "title",
        "portal",
        "source",
        "buyer",
        "country",
        "budget",
        "published_at",
      ])
  );

  // Tri
  const [sortState, setSortState] = useState<SortState>({
    key: "published_at",
    direction: "desc",
  });

  // Sélection pour panneau de détail (fermé par défaut)
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);

  // Rapports
  const [categoryReport, setCategoryReport] = useState<CategoryReport | null>(
    null
  );
  const [keywordReport, setKeywordReport] = useState<KeywordReport | null>(
    null
  );
  const [reportLoading, setReportLoading] = useState(false);

  // -------------------------------------------------------------------
  // Chargement des portails
  // -------------------------------------------------------------------

  useEffect(() => {
    const fetchPortals = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/portals?only_active=true&country=ALL`
        );
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setPortals(data);
      } catch (e: any) {
        console.error(e);
      }
    };
    fetchPortals();
  }, []);

  // -------------------------------------------------------------------
  // Chargement des AO + rapports
  // -------------------------------------------------------------------

  const fetchTenders = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.set("limit", "200");
      if (countryFilter && countryFilter !== "ALL") {
        params.set("country", countryFilter);
      }
      if (portalFilter && portalFilter !== "ALL") {
        params.set("portal", portalFilter);
      }
      if (query.trim()) {
        params.set("q", query.trim());
      }

      const res = await fetch(`${API_BASE_URL}/tenders?${params.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      const data: Tender[] = await res.json();
      setTenders(data);
      setSelectedTender(null);

      // --- Rapports (catégories + mots-clés) ---
      const reportParams = new URLSearchParams();
      if (countryFilter && countryFilter !== "ALL") {
        reportParams.set("country", countryFilter);
      }
      if (portalFilter && portalFilter !== "ALL") {
        reportParams.set("portal", portalFilter);
      }
      if (query.trim()) {
        reportParams.set("q", query.trim());
      }
      reportParams.set("top_n", "5");
      reportParams.set("max_rows", "5000");

      setReportLoading(true);
      try {
        const [catRes, keyRes] = await Promise.all([
          fetch(`${API_BASE_URL}/report/categories?${reportParams.toString()}`),
          fetch(`${API_BASE_URL}/report/keywords?${reportParams.toString()}`),
        ]);

        if (catRes.ok) {
          const catData: CategoryReport = await catRes.json();
          setCategoryReport(catData);
        } else {
          setCategoryReport(null);
        }

        if (keyRes.ok) {
          const keyData: KeywordReport = await keyRes.json();
          setKeywordReport(keyData);
        } else {
          setKeywordReport(null);
        }
      } catch (e) {
        console.error("Erreur rapports:", e);
        setCategoryReport(null);
        setKeywordReport(null);
      } finally {
        setReportLoading(false);
      }
    } catch (e: any) {
      console.error(e);
      setError("Erreur lors du chargement des appels d’offres.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -------------------------------------------------------------------
  // Gestion colonnes
  // -------------------------------------------------------------------

  const toggleColumn = (key: ColumnKey) => {
    const colMeta = ALL_COLUMNS.find((c) => c.key === key);
    if (colMeta?.locked) return;

    setVisibleColumns((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const isColumnVisible = (key: ColumnKey) => visibleColumns.has(key);

  // -------------------------------------------------------------------
  // Tri
  // -------------------------------------------------------------------

  const handleSort = (key: ColumnKey) => {
    setSortState((prev) => {
      if (prev.key === key) {
        return {
          key,
          direction: prev.direction === "asc" ? "desc" : "asc",
        };
      }
      return { key, direction: "asc" };
    });
  };

  const sortIcon = (key: ColumnKey) => {
    if (sortState.key !== key) return "↕";
    return sortState.direction === "asc" ? "↑" : "↓";
  };

  // -------------------------------------------------------------------
  // Filtres + Tri
  // -------------------------------------------------------------------

  const filteredTenders = useMemo(() => {
    let rows = [...tenders];

    // Filtres principaux
    if (countryFilter !== "ALL") {
      rows = rows.filter(
        (t) => (t.country || "").toUpperCase() === countryFilter.toUpperCase()
      );
    }
    if (portalFilter !== "ALL") {
      rows = rows.filter(
        (t) =>
          t.portal.toUpperCase() === portalFilter.toUpperCase() ||
          t.source.toUpperCase() === portalFilter.toUpperCase()
      );
    }
    if (query.trim()) {
      const terms = query
        .split(/\s+/)
        .map((t) => t.toLowerCase())
        .filter(Boolean);
      rows = rows.filter((t) =>
        terms.every((term) => {
          const title = (t.title || "").toLowerCase();
          const buyer = (t.buyer || "").toLowerCase();
          const source = (t.source || "").toLowerCase();
          const portal = (t.portal || "").toLowerCase();
          return (
            title.includes(term) ||
            buyer.includes(term) ||
            source.includes(term) ||
            portal.includes(term)
          );
        })
      );
    }

    // 🔍 Filtre rapide
    if (quickValue.trim()) {
      const v = quickValue.trim().toLowerCase();
      rows = rows.filter((t) => {
        const raw = ((t as any)[quickField] ?? "").toString().toLowerCase();
        return raw.includes(v);
      });
    }

    // Tri
    rows.sort((a, b) => {
      const { key, direction } = sortState;
      const dir = direction === "asc" ? 1 : -1;

      const va = (a as any)[key];
      const vb = (b as any)[key];

      if (key === "published_at" || key === "closing_at") {
        const sa = (va || "") as string;
        const sb = (vb || "") as string;
        if (sa === sb) return 0;
        return sa > sb ? dir : -dir;
      }

      if (key === "id" || key === "budget" || key === "score") {
        const na = va == null ? -Infinity : Number(va);
        const nb = vb == null ? -Infinity : Number(vb);
        if (na === nb) return 0;
        return na > nb ? dir : -dir;
      }

      const sa = (va || "").toString().toLowerCase();
      const sb = (vb || "").toString().toLowerCase();
      if (sa === sb) return 0;
      return sa > sb ? dir : -dir;
    });

    return rows;
  }, [tenders, countryFilter, portalFilter, query, quickField, quickValue, sortState]);

  // 🎁 Petit résumé en bas du tableau
  const summary = useMemo(() => {
    const total = filteredTenders.length;
    const portals = new Set(
      filteredTenders.map((t) => t.portal || t.source || "")
    ).size;
    const withScore = filteredTenders.filter((t) => t.score != null);
    const avgScore = withScore.length
      ? withScore.reduce((sum, t) => sum + (t.score || 0), 0) /
        withScore.length
      : null;

    return { total, portals, avgScore };
  }, [filteredTenders]);

  // -------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------

  const formatDate = (value: string | null) => {
    if (!value) return "—";
    return value;
  };

  const formatBudget = (value: number | null) => {
    if (value == null || isNaN(value)) return "—";
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)} M$`;
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(1)} k$`;
    }
    return `${value.toFixed(0)} $`;
  };

  const handleRowClick = (t: Tender) => {
    setSelectedTender(t);
  };

  const handleCloseDetail = () => {
    setSelectedTender(null);
  };

  // -------------------------------------------------------------------
  // Rendu
  // -------------------------------------------------------------------

  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-title">
          <h1>AO Collector — Recherche</h1>
          <p>
            Résultats chargés automatiquement. Ajuste les filtres et clique{" "}
            <strong>Rechercher</strong>.
          </p>
        </div>
        <div className="app-api-hint">
          API&nbsp;: <code>{API_BASE_URL}</code>
        </div>
      </header>

      <main className="app-main">
        {/* Carte filtres */}
        <section className="filters-card">
          <div className="filters-row">
            <div className="filter-group">
              <label>Pays</label>
              <select
                value={countryFilter}
                onChange={(e) => setCountryFilter(e.target.value)}
              >
                <option value="ALL">Tous</option>
                <option value="CA">Canada</option>
                <option value="QC">Québec (si codé)</option>
              </select>
            </div>

            <div className="filter-group">
              <label>Portail</label>
              <select
                value={portalFilter}
                onChange={(e) => setPortalFilter(e.target.value)}
              >
                <option value="ALL">Tous</option>
                {portals.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.code} — {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group filter-group-wide">
              <label>Mot-clé</label>
              <input
                placeholder="ex: crm, servicenow, odoo, oracle…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") fetchTenders();
                }}
              />
            </div>

            <div className="filter-group filter-group-button">
              <button onClick={fetchTenders} disabled={loading}>
                {loading ? "Chargement…" : "Rechercher"}
              </button>
            </div>
          </div>

          {/* Colonnes */}
          <div className="columns-toggle-bar">
            <span className="columns-label">Colonnes :</span>
            {ALL_COLUMNS.map((col) => {
              const checked = isColumnVisible(col.key);
              const locked = !!col.locked;
              return (
                <label
                  key={col.key}
                  className={
                    "column-chip" +
                    (checked ? " column-chip--active" : "") +
                    (locked ? " column-chip--locked" : "")
                  }
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={locked}
                    onChange={() => toggleColumn(col.key)}
                  />
                  {col.label}
                </label>
              );
            })}
          </div>

          {/* 🔍 Filtre rapide unique */}
          <div className="quick-filters-row">
            <div className="quick-filter">
              <label>Filtre rapide</label>
              <div className="quick-filter-inner">
                <select
                  value={quickField}
                  onChange={(e) => setQuickField(e.target.value as QuickField)}
                >
                  {QUICK_FIELD_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <input
                  placeholder="Contient…"
                  value={quickValue}
                  onChange={(e) => setQuickValue(e.target.value)}
                />
              </div>
            </div>
          </div>
        </section>

        {/* Rapport express */}
        {categoryReport && keywordReport && (
          <section className="report-card">
            <div className="report-header">
              <h2>Rapport express</h2>
              {reportLoading && (
                <span className="report-badge">Mise à jour…</span>
              )}
            </div>
            <div className="report-kpis">
              <div className="report-kpi">
                <span className="report-kpi-label">AO analysés</span>
                <span className="report-kpi-value">
                  {categoryReport.total_tenders}
                </span>
              </div>
              <div className="report-kpi">
                <span className="report-kpi-label">Catégories distinctes</span>
                <span className="report-kpi-value">
                  {categoryReport.distinct_categories}
                </span>
              </div>
              <div className="report-kpi">
                <span className="report-kpi-label">Mots-clés distincts</span>
                <span className="report-kpi-value">
                  {keywordReport.distinct_keywords}
                </span>
              </div>
            </div>

            <div className="report-columns">
              <div className="report-column">
                <h3>Top catégories</h3>
                {categoryReport.categories.length === 0 && (
                  <p className="report-empty">Aucune catégorie détectée.</p>
                )}
                <ul>
                  {categoryReport.categories.slice(0, 5).map((c) => (
                    <li key={c.category}>
                      <span className="report-item-label">{c.category}</span>
                      <span className="report-item-count">{c.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="report-column">
                <h3>Top mots-clés</h3>
                {keywordReport.keywords.length === 0 && (
                  <p className="report-empty">Aucun mot-clé détecté.</p>
                )}
                <ul>
                  {keywordReport.keywords.slice(0, 5).map((k) => (
                    <li key={k.keyword}>
                      <span className="report-item-label">{k.keyword}</span>
                      <span className="report-item-count">{k.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        )}

        {error && <div className="error-banner">{error}</div>}

        {/* Tableau + panneau detail */}
        <section
          className={
            selectedTender
              ? "results-layout"
              : "results-layout results-layout--single"
          }
        >
          {/* Tableau */}
          <div className="table-wrapper">
            <table className="tenders-table">
              <thead>
                <tr>
                  {ALL_COLUMNS.filter((c) => isColumnVisible(c.key)).map(
                    (col) => (
                      <th
                        key={col.key}
                        onClick={() => handleSort(col.key)}
                        className={
                          (col.align === "center"
                            ? "col-center "
                            : col.align === "right"
                            ? "col-right "
                            : "col-left ") + "th-sortable"
                        }
                      >
                        <span className="th-label">
                          {col.label}
                          <span className="th-sort-icon">
                            {sortIcon(col.key)}
                          </span>
                        </span>
                      </th>
                    )
                  )}
                  <th className="col-center">
                    <span className="th-label">Lien</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredTenders.length === 0 && (
                  <tr>
                    <td colSpan={ALL_COLUMNS.length + 1} className="empty-row">
                      Aucun résultat pour ces critères.
                    </td>
                  </tr>
                )}

                {filteredTenders.map((t) => (
                  <tr
                    key={t.id}
                    className={selectedTender?.id === t.id ? "row--selected" : ""}
                    onClick={() => handleRowClick(t)}
                  >
                    {ALL_COLUMNS.filter((c) => isColumnVisible(c.key)).map(
                      (col) => {
                        let value: React.ReactNode = (t as any)[col.key];

                        if (
                          col.key === "published_at" ||
                          col.key === "closing_at"
                        ) {
                          value = formatDate(value as string | null);
                        } else if (col.key === "budget") {
                          value = formatBudget(value as number | null);
                        } else if (value == null || value === "") {
                          value = "—";
                        }

                        const className =
                          col.align === "center"
                            ? "col-center"
                            : col.align === "right"
                            ? "col-right"
                            : "col-left";

                        return (
                          <td key={col.key} className={className}>
                            {value}
                          </td>
                        );
                      }
                    )}

                    <td className="col-center">
                      {t.url ? (
                        <button
                          className="link-button"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(t.url, "_blank");
                          }}
                        >
                          Ouvrir
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="table-footer">
              <span>{summary.total} lignes affichées (max 200)</span>
              <span className="table-footer-sep">•</span>
              <span>{summary.portals} portails</span>
              {summary.avgScore != null && (
                <>
                  <span className="table-footer-sep">•</span>
                  <span>Score moyen {summary.avgScore.toFixed(1)}</span>
                </>
              )}
            </div>
          </div>

          {/* Panneau de détail */}
          {selectedTender && (
            <aside className="detail-panel">
              <div className="detail-header">
                <div>
                  <h2>{selectedTender.title}</h2>
                  <div className="detail-id">
                    #{selectedTender.id} · {selectedTender.portal} ·{" "}
                    {selectedTender.source}
                  </div>
                </div>
                <button className="detail-close" onClick={handleCloseDetail}>
                  Fermer
                </button>
              </div>

              <dl className="detail-grid">
                <div>
                  <dt>Acheteur</dt>
                  <dd>{selectedTender.buyer || "—"}</dd>
                </div>
                <div>
                  <dt>Pays</dt>
                  <dd>{selectedTender.country || "—"}</dd>
                </div>
                <div>
                  <dt>Région</dt>
                  <dd>{selectedTender.region || "—"}</dd>
                </div>
                <div>
                  <dt>Budget</dt>
                  <dd>{formatBudget(selectedTender.budget)}</dd>
                </div>
                <div>
                  <dt>Publiée</dt>
                  <dd>{formatDate(selectedTender.published_at)}</dd>
                </div>
                <div>
                  <dt>Fermeture</dt>
                  <dd>{formatDate(selectedTender.closing_at)}</dd>
                </div>
                <div>
                  <dt>Catégorie</dt>
                  <dd>{selectedTender.category || "—"}</dd>
                </div>
                <div>
                  <dt>Mots-clés détectés</dt>
                  <dd>{selectedTender.matched_keywords || "—"}</dd>
                </div>
                <div>
                  <dt>Score</dt>
                  <dd>
                    {selectedTender.score != null
                      ? selectedTender.score.toFixed(2)
                      : "—"}
                  </dd>
                </div>
              </dl>

              <div className="detail-actions">
                {selectedTender.url && (
                  <button
                    className="primary"
                    onClick={() => window.open(selectedTender.url, "_blank")}
                  >
                    Ouvrir l’appel d’offres
                  </button>
                )}
              </div>
            </aside>
          )}
        </section>
      </main>
    </div>
  );
};

export default App;
