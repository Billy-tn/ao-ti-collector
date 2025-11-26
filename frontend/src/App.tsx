import React, { useEffect, useMemo, useState } from "react";
import "./App.css";
import LoginPage from "./LoginPage";

// =======================
// Types
// =======================

const API_BASE = "/api";

interface RawTender {
  id: number;
  // nouveaux champs backend (anglais)
  title?: string;
  url?: string;
  published_at?: string;
  country?: string;
  region?: string;
  portal_name?: string;
  buyer?: string;
  categorie_principale?: string;
  est_ats?: number | boolean | string;

  // anciens champs (français) si jamais ils réapparaissent
  titre?: string;
  lien?: string;
  date_publication?: string;
  date_cloture?: string;
  pays?: string;
  portail?: string;
  [key: string]: any;
}

export interface Tender {
  id: number;
  titre: string;
  acheteur: string;
  pays: string;
  region: string;
  date_publication: string;
  date_cloture: string;
  portail: string;
  lien: string;
  est_ats: boolean;
}

interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  activity_type?: string;
  main_specialty?: string;
}

interface TendersResponse {
  items: RawTender[];
  count: number;
  user?: UserProfile;
}

// =======================
// Helpers
// =======================

const DEFAULT_LIMIT = 100;

function normalizeTender(raw: RawTender): Tender {
  const titre = raw.titre || raw.title || "";
  const acheteur = raw.acheteur || raw.buyer || "";
  const pays = raw.pays || raw.country || "";
  const region = raw.region || "";
  const date_publication = raw.date_publication || raw.published_at || "";
  const date_cloture = raw.date_cloture || ""; // pas toujours dispo côté backend
  const portail = raw.portail || raw.portal_name || raw.source || "";
  const lien = raw.lien || raw.url || "";

  const est_ats =
    typeof raw.est_ats === "boolean"
      ? raw.est_ats
      : raw.est_ats === 1 || raw.est_ats === "1";

  return {
    id: raw.id,
    titre,
    acheteur,
    pays,
    region,
    date_publication,
    date_cloture,
    portail,
    lien,
    est_ats: Boolean(est_ats),
  };
}

// =======================
// Composant principal
// =======================

const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // recherche : saisie vs requête effective
  const [searchText, setSearchText] = useState("");
  const [query, setQuery] = useState("");
  const [searchField, setSearchField] = useState<
    "title_buyer" | "title" | "buyer"
  >("title_buyer");
  const [atsOnly, setAtsOnly] = useState(false);

  const [selectedTenderId, setSelectedTenderId] = useState<number | null>(null);

  // Récupère token + user au démarrage
  useEffect(() => {
    const storedToken = localStorage.getItem("ao_token");
    const storedUser = localStorage.getItem("ao_user");

    if (storedToken) setToken(storedToken);
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        // ignore
      }
    }
  }, []);

  // Charge les AO quand token / filtres changent
  useEffect(() => {
    if (!token) return;

    const controller = new AbortController();

    async function fetchTenders() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams();
        params.set("limit", String(DEFAULT_LIMIT));

        if (query.trim()) params.set("q", query.trim());

        // champs supportés côté backend : title_buyer / title / buyer
        params.set("field", searchField);

        if (atsOnly) params.set("ats_only", "true");

        const res = await fetch(`${API_BASE}/tenders?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: controller.signal,
        });

        // Gestion token invalide ou expiré
        if (res.status === 401) {
          let detail = "Token invalide ou expiré.";
          try {
            const body = await res.json();
            if (body?.detail) detail = body.detail;
          } catch {
            /* ignore */
          }

          setError(detail);

          // on force le retour à l'écran de login
          setToken(null);
          setUser(null);
          setTenders([]);
          setSelectedTenderId(null);
          localStorage.removeItem("ao_token");
          localStorage.removeItem("ao_user");
          return;
        }

        if (!res.ok) {
          const body = await res.json().catch(() => null);
          const msg = body?.detail || "Erreur lors du chargement des AO.";
          throw new Error(msg);
        }

        const data = (await res.json()) as TendersResponse;
        const normalized = (data.items || []).map(normalizeTender);

        setTenders(normalized);

        if (!user && data.user) {
          setUser(data.user);
          localStorage.setItem("ao_user", JSON.stringify(data.user));
        }
      } catch (err: any) {
        if (err.name === "AbortError") return;
        console.error("Erreur fetch AO:", err);
        setError(
          err.message === "Failed to fetch"
            ? "Serveur injoignable. Vérifie que le backend tourne sur le port 8000."
            : err.message
        );
      } finally {
        setLoading(false);
      }
    }

    fetchTenders();
    return () => controller.abort();
  }, [token, query, searchField, atsOnly, user]);

  const selectedTender = useMemo(
    () => tenders.find((t) => t.id === selectedTenderId) || null,
    [tenders, selectedTenderId]
  );

  const stats = useMemo(() => {
    const total = tenders.length;
    const ats = tenders.filter((t) => t.est_ats).length;
    const caQc = tenders.filter(
      (t) =>
        t.pays === "CA" &&
        (t.region === "QC" ||
          t.region === "CA / QC" ||
          t.region === "CA/QC" ||
          t.region === "QC / CA")
    ).length;
    return { total, ats, caQc };
  }, [tenders]);

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setTenders([]);
    setSelectedTenderId(null);
    localStorage.removeItem("ao_token");
    localStorage.removeItem("ao_user");
  };

  // =======================
  // Si pas de token → Login
  // =======================

  if (!token) {
    return (
      <div className="app-root">
        <LoginPage
          onAuthenticated={(newToken, newUser) => {
            setToken(newToken);
            setUser(newUser);
            localStorage.setItem("ao_token", newToken);
            if (newUser) {
              localStorage.setItem("ao_user", JSON.stringify(newUser));
            }
          }}
        />
      </div>
    );
  }

  // =======================
  // Dashboard AO
  // =======================

  return (
    <div className="app-root">
      <header className="app-header">
        <div className="user-pill">
          <div className="avatar-circle">B</div>
          <div className="user-meta">
            <div className="user-line">
              <span className="status-dot" />
              <span>
                Connecté en tant que{" "}
                <strong>{user?.full_name || "Bilel — Stratège AO TI"}</strong>
              </span>
            </div>
            <div className="user-sub">
              {user?.activity_type || "Consultant TI / Intégrateur"} ·{" "}
              <span className="user-highlight">
                {user?.main_specialty || "Intégration ERP & IA"}
              </span>
            </div>
          </div>
        </div>

        <button className="logout-button" onClick={handleLogout}>
          Se déconnecter
        </button>
      </header>

      <main className="app-main">
        <h1 className="page-title">AO Collector — Recherche</h1>
        <p className="page-subtitle">
          Tableau de bord des appels d’offres TI (SEAO &amp; CanadaBuys) avec
          pré-filtrage ATS et préparation à l’analyse IA.
        </p>

        {/* KPIs */}
        <section className="kpi-row">
          <div className="kpi-card">
            <div className="kpi-label">AO chargés</div>
            <div className="kpi-value">{stats.total}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">AO ATS</div>
            <div className="kpi-value">{stats.ats}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">AO CA (QC) dans la fenêtre</div>
            <div className="kpi-value">
              {stats.caQc} <span className="kpi-suffix">/ {stats.total}</span>
            </div>
          </div>
        </section>

        {/* Bandeau filtre actif */}
        <section className="filter-banner">
          <span className="filter-icon">⚡</span>
          <span className="filter-text">
            {query
              ? `Filtre actif — "${query}" (${
                  searchField === "title_buyer"
                    ? "titre + acheteur"
                    : searchField === "title"
                    ? "titre"
                    : "acheteur"
                })`
              : "Aucun filtre spécifique — dernières AO chargées."}
          </span>
        </section>

        {/* Recherche */}
        <section className="search-row">
          <div className="search-main">
            <span className="search-icon">🔍</span>
            <input
              className="search-input"
              placeholder="Recherche intelligente (ex : crm, servicenow, odoo, cybersécurité...)"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  setQuery(searchText.trim());
                }
              }}
            />
          </div>
          <button
            className="primary-button"
            onClick={() => setQuery(searchText.trim())}
          >
            Rechercher
          </button>
        </section>

        {/* Options de recherche */}
        <section className="search-options">
          <div className="search-field-group">
            <span className="search-option-label">Champ :</span>
            <label className="radio-pill">
              <input
                type="radio"
                name="field"
                checked={searchField === "title_buyer"}
                onChange={() => setSearchField("title_buyer")}
              />
              <span>Titre + acheteur</span>
            </label>
            <label className="radio-pill">
              <input
                type="radio"
                name="field"
                checked={searchField === "title"}
                onChange={() => setSearchField("title")}
              />
              <span>Titre</span>
            </label>
            <label className="radio-pill">
              <input
                type="radio"
                name="field"
                checked={searchField === "buyer"}
                onChange={() => setSearchField("buyer")}
              />
              <span>Acheteur</span>
            </label>
          </div>

          <label className="checkbox-option">
            <input
              type="checkbox"
              checked={atsOnly}
              onChange={(e) => setAtsOnly(e.target.checked)}
            />
            <span>Filtrer sur AO ATS uniquement</span>
          </label>
        </section>

        {/* Erreur globale */}
        {error && <div className="alert error">{error}</div>}

        {/* Layout résultats + détail */}
        <section
          className={`results-layout ${
            selectedTender
              ? "results-layout--with-detail"
              : "results-layout--single"
          }`}
        >
          {/* Tableau des AO */}
          <div className="card table-card">
            <div className="card-header">
              <div>
                <h2>Liste des AO</h2>
                <p className="card-subtitle">
                  {stats.total} résultat(s)
                  {atsOnly ? " — filtrés ATS" : ""}
                </p>
              </div>
            </div>

            <div className="ao-table-wrapper">
              <table className="ao-table">
                <thead>
                  <tr>
                    <th>Titre</th>
                    <th>Acheteur</th>
                    <th>Lieu</th>
                    <th>Dates</th>
                    <th>Portail</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && (
                    <tr>
                      <td colSpan={5} className="table-loading">
                        Chargement des appels d’offres...
                      </td>
                    </tr>
                  )}
                  {!loading && tenders.length === 0 && (
                    <tr>
                      <td colSpan={5} className="table-empty">
                        Aucun résultat pour ces critères.
                      </td>
                    </tr>
                  )}
                  {!loading &&
                    tenders.map((t) => {
                      const isSelected = t.id === selectedTenderId;
                      return (
                        <tr
                          key={t.id}
                          className={isSelected ? "row-selected" : ""}
                          onClick={() =>
                            setSelectedTenderId(isSelected ? null : t.id)
                          }
                        >
                          <td>{t.titre || "—"}</td>
                          <td>{t.acheteur || "—"}</td>
                          <td>
                            {t.pays
                              ? `${t.pays}${t.region ? " / " + t.region : ""}`
                              : "—"}
                          </td>
                          <td>
                            {t.date_publication || "?"} →{" "}
                            {t.date_cloture || "?"}
                          </td>
                          <td>{t.portail || "—"}</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Panneau détail AO */}
          {selectedTender && (
            <div className="card detail-card detail-enter">
              <div className="detail-header">
                <div>
                  <div className="detail-label">Détail de l’AO</div>
                  <h2 className="detail-title">{selectedTender.titre}</h2>
                </div>
                <button
                  className="secondary-button"
                  onClick={() => setSelectedTenderId(null)}
                >
                  Fermer
                </button>
              </div>

              <div className="detail-grid">
                <div className="detail-row">
                  <span className="detail-key">Acheteur :</span>
                  <span className="detail-value">
                    {selectedTender.acheteur || "—"}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Pays / Région :</span>
                  <span className="detail-value">
                    {selectedTender.pays || "—"}{" "}
                    {selectedTender.region ? `(${selectedTender.region})` : ""}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Dates :</span>
                  <span className="detail-value">
                    {selectedTender.date_publication || "?"} →{" "}
                    {selectedTender.date_cloture || "?"}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Portail :</span>
                  <span className="detail-value">
                    {selectedTender.portail || "—"}
                  </span>
                </div>
              </div>

              <div className="detail-section">
                <h3>Analyse IA &amp; documents</h3>
                <p className="detail-description">
                  Téléverse le PDF officiel de l’AO ou des documents annexes
                  (Word, Excel, PDF…) pour préparer l’analyse IA de cette
                  opportunité.
                </p>
                <div className="detail-actions">
                  <button className="primary-button subtle">
                    PDF AO (portail)
                  </button>
                  <button className="secondary-button subtle">
                    Docs annexes
                  </button>
                </div>
              </div>

              <div className="detail-footer-link">
                {selectedTender.lien && (
                  <>
                    Lien officiel :{" "}
                    <a
                      href={selectedTender.lien}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Ouvrir l’AO
                    </a>
                  </>
                )}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default App;
