// frontend/src/App.tsx
import React, { useEffect, useMemo, useState } from "react";
import "./App.css";

type Tender = {
  id: number | string;
  title: string;
  portal: string;
  source: string;
  buyer: string;
  country: string;
  region?: string | null;
  budget?: number | string | null;
  published?: string | null;
  closing?: string | null;
  link?: string | null;
};

type UserProfile = {
  id: string;
  email: string;
  full_name: string;
  activity_type: string;
  main_specialty: string;
};

type LoginStep = "credentials" | "mfa" | "done";

type AoAnalysisResult = {
  filename: string;
  size_bytes: number;
  summary: string;
  main_requirements: string[];
  risks: string[];
};

const API_BASE_URL =
  ((import.meta as any).env?.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/+$/,
    ""
  ) || "/api";

const App: React.FC = () => {
  // Auth
  const [authStep, setAuthStep] = useState<LoginStep>("credentials");
  const [loginEmail, setLoginEmail] = useState("bilel@example.com");
  const [loginPassword, setLoginPassword] = useState("password");
  const [mfaCode, setMfaCode] = useState("");
  const [tempToken, setTempToken] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // AO list
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);
  const [q, setQ] = useState("");
  const [loadingTenders, setLoadingTenders] = useState(false);
  const [tendersError, setTendersError] = useState<string | null>(null);

  // Analyse IA
  const [analysis, setAnalysis] = useState<AoAnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const isAuthenticated = useMemo(() => !!accessToken, [accessToken]);

  // -------------------------------------------------------------------
  // Auth
  // -------------------------------------------------------------------

  const handleLogin = async () => {
    setAuthError(null);
    setAuthLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginEmail,
          password: loginPassword,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Erreur de connexion");
      }

      const data = await res.json();
      setTempToken(data.temp_token);
      setAuthStep("mfa");
    } catch (e: any) {
      setAuthError(e.message || "Erreur inconnue");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyMfa = async () => {
    if (!tempToken) return;
    setAuthError(null);
    setAuthLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/verify-mfa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          temp_token: tempToken,
          code: mfaCode,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Erreur MFA");
      }

      const data = await res.json();
      setAccessToken(data.access_token);
      setCurrentUser(data.user);
      setAuthStep("done");
    } catch (e: any) {
      setAuthError(e.message || "Erreur inconnue");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setAccessToken(null);
    setCurrentUser(null);
    setAuthStep("credentials");
    setTenders([]);
    setSelectedTender(null);
  };

  // -------------------------------------------------------------------
  // Fetch AO
  // -------------------------------------------------------------------

  const fetchTenders = async () => {
    if (!accessToken) return;
    setLoadingTenders(true);
    setTendersError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (q.trim()) params.set("q", q.trim());

      const res = await fetch(`${API_BASE_URL}/tenders?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Erreur de chargement des AO");
      }

      const data = await res.json();
      setTenders(data.items || data);
      setSelectedTender((prev) => prev ?? (data.items || data)[0] ?? null);
    } catch (e: any) {
      setTendersError(e.message || "Erreur inconnue");
    } finally {
      setLoadingTenders(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchTenders();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  // -------------------------------------------------------------------
  // Analyse IA / upload
  // -------------------------------------------------------------------

  const handleUploadAoFile = async (file: File) => {
    if (!accessToken) return;
    setAnalysis(null);
    setAnalysisError(null);
    setAnalysisLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE_URL}/tools/analyze-ao`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Erreur lors de l'analyse");
      }

      const data: AoAnalysisResult = await res.json();
      setAnalysis(data);
    } catch (e: any) {
      setAnalysisError(e.message || "Erreur inconnue");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const onFileInputChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      void handleUploadAoFile(file);
      e.target.value = "";
    }
  };

  // -------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------

  if (!isAuthenticated) {
    return (
      <div className="app-root">
        <div className="login-card glass-card">
          <h1 className="app-title">AO Collector</h1>
          <p className="app-subtitle">Connexion avec MFA et profils métiers.</p>

          {authStep === "credentials" && (
            <>
              <label className="field-label">
                Email
                <input
                  className="text-input"
                  type="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                />
              </label>
              <label className="field-label">
                Mot de passe
                <input
                  className="text-input"
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                />
              </label>

              <button
                className="primary-btn"
                onClick={handleLogin}
                disabled={authLoading}
              >
                {authLoading ? "Connexion..." : "Se connecter"}
              </button>
            </>
          )}

          {authStep === "mfa" && (
            <>
              <p className="hint">
                Entrez le code MFA correspondant à l&apos;email choisi (voir
                dessous).
              </p>
              <label className="field-label">
                Code MFA
                <input
                  className="text-input"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  placeholder="123456, 654321, 999999..."
                />
              </label>
              <button
                className="primary-btn"
                onClick={handleVerifyMfa}
                disabled={authLoading}
              >
                {authLoading ? "Vérification..." : "Valider le code"}
              </button>
            </>
          )}

          {authError && <div className="error-banner">{authError}</div>}

          <div className="test-profiles">
            <div>Profils de test :</div>
            <ul>
              <li>bilel@example.com / MFA 123456</li>
              <li>cloud.consultant@example.com / MFA 654321</li>
              <li>odoo.partner@example.com / MFA 999999</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------
  // Ecran principal
  // -------------------------------------------------------------------

  return (
    <div className="app-root">
      <header className="top-bar">
        <div>
          <div className="top-title">AO Collector — Recherche</div>
          {currentUser && (
            <div className="top-subtitle">
              Bonjour{" "}
              <strong className="accent">{currentUser.full_name}</strong> ·{" "}
              {currentUser.activity_type} · Spécialité :{" "}
              <span className="accent">{currentUser.main_specialty}</span>
            </div>
          )}
        </div>
        <div className="top-right">
          <button className="ghost-btn" onClick={handleLogout}>
            Se déconnecter
          </button>
        </div>
      </header>

      <main className="layout">
        <section className="search-panel glass-card">
          <div className="search-row">
            <label className="field-label small">
              Mot-clé
              <input
                className="text-input"
                placeholder="ex: crm, servicenow, odoo..."
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </label>
            <button
              className="primary-btn"
              onClick={fetchTenders}
              disabled={loadingTenders}
            >
              {loadingTenders ? "Recherche..." : "Rechercher"}
            </button>
          </div>
          {tendersError && <div className="error-banner">{tendersError}</div>}
        </section>

        <section className="results-layout">
          <div className="tenders-table glass-card">
            <div className="table-header">
              <span>ID</span>
              <span>Titre</span>
              <span>Portail</span>
              <span>Acheteur</span>
              <span>Pays</span>
              <span>Publiée</span>
              <span>Fermeture</span>
            </div>
            <div className="table-body">
              {tenders.map((t) => (
                <button
                  key={t.id}
                  className={
                    "table-row" +
                    (selectedTender && selectedTender.id === t.id
                      ? " row-selected"
                      : "")
                  }
                  onClick={() => setSelectedTender(t)}
                >
                  <span>{t.id}</span>
                  <span>{t.title}</span>
                  <span>{t.portal}</span>
                  <span>{t.buyer}</span>
                  <span>{t.country}</span>
                  <span>{t.published || "—"}</span>
                  <span>{t.closing || "—"}</span>
                </button>
              ))}
              {tenders.length === 0 && !loadingTenders && (
                <div className="empty-state">Aucun résultat pour ces critères.</div>
              )}
            </div>
          </div>

          <div className="detail-panel glass-card">
            {selectedTender ? (
              <>
                <h2 className="detail-title">{selectedTender.title}</h2>
                <div className="detail-grid">
                  <div>
                    <div className="detail-label">Portail</div>
                    <div>{selectedTender.portal}</div>
                  </div>
                  <div>
                    <div className="detail-label">Source</div>
                    <div>{selectedTender.source}</div>
                  </div>
                  <div>
                    <div className="detail-label">Acheteur</div>
                    <div>{selectedTender.buyer}</div>
                  </div>
                  <div>
                    <div className="detail-label">Pays</div>
                    <div>{selectedTender.country}</div>
                  </div>
                  <div>
                    <div className="detail-label">Budget</div>
                    <div>{selectedTender.budget ?? "—"}</div>
                  </div>
                  <div>
                    <div className="detail-label">Publiée</div>
                    <div>{selectedTender.published ?? "—"}</div>
                  </div>
                  <div>
                    <div className="detail-label">Fermeture</div>
                    <div>{selectedTender.closing ?? "—"}</div>
                  </div>
                </div>

                <div className="detail-actions">
                  {selectedTender.link && (
                    <a
                      className="ghost-btn"
                      href={selectedTender.link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Ouvrir l&apos;appel d&apos;offres
                    </a>
                  )}

                  <label className="primary-btn file-btn">
                    Analyser l&apos;AO (IA)
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx,.xlsx,.xls"
                      onChange={onFileInputChange}
                      style={{ display: "none" }}
                    />
                  </label>
                </div>

                <div className="analysis-panel">
                  {analysisLoading && (
                    <div className="hint">Analyse en cours...</div>
                  )}
                  {analysisError && (
                    <div className="error-banner">{analysisError}</div>
                  )}
                  {analysis && (
                    <>
                      <div className="analysis-header">
                        <div>Fichier : {analysis.filename}</div>
                        <div>Taille : {analysis.size_bytes} octets</div>
                      </div>
                      <p className="analysis-summary">{analysis.summary}</p>
                      <div className="analysis-columns">
                        <div>
                          <div className="detail-label">
                            Exigences principales
                          </div>
                          <ul>
                            {analysis.main_requirements.map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <div className="detail-label">Risques identifiés</div>
                          <ul>
                            {analysis.risks.map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </>
            ) : (
              <div className="empty-state">
                Sélectionne un appel d&apos;offres dans la liste.
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

export default App;
