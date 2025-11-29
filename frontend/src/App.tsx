import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import LoginPage from "./LoginPage";
import PortalCandidates from "./components/PortalCandidates";


const API_BASE = "/api";
const DEFAULT_LIMIT = 100;

type TabKey = "ao" | "ai" | "reports" | "portals" | "others";
type SearchField = "title_buyer" | "title" | "buyer";

interface RawTender {
  id: number;

  // backend (anglais)
  title?: string;
  url?: string;
  published_at?: string;
  country?: string;
  region?: string;
  portal_name?: string;
  buyer?: string;
  categorie_principale?: string;
  est_ats?: number | boolean | string;
  source?: string;

  // fallback (français)
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
  history?: Array<{
    ao_id: string;
    title: string;
    specialty: string;
    date_awarded: string;
  }>;
}

interface TendersResponse {
  items: RawTender[];
  count: number;
  user?: UserProfile;
}

// -----------------------
// Helpers
// -----------------------
function normalizeTender(raw: RawTender): Tender {
  const titre = raw.titre || raw.title || "";
  const acheteur = (raw as any).acheteur || raw.buyer || "";
  const pays = raw.pays || raw.country || "";
  const region = raw.region || "";
  const date_publication = raw.date_publication || raw.published_at || "";
  const date_cloture = raw.date_cloture || "";
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

function safeJsonParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function isProbablyPdf(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function formatBytes(bytes: number) {
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function summarizeFiles(files: File[]) {
  if (!files.length) return "Aucun fichier";
  const total = files.reduce((acc, f) => acc + (f.size || 0), 0);
  return `${files.length} fichier(s) • ${formatBytes(total)}`;
}

function fmtDate(s: string) {
  if (!s) return "";
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
  return s;
}

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function clamp01(n: number) {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

function confidenceTone(c: number): "bad" | "warn" | "info" | "good" {
  const v = clamp01(c);
  if (v < 0.35) return "bad";
  if (v < 0.6) return "warn";
  if (v < 0.8) return "info";
  return "good";
}

function pick(obj: any, path: string[]) {
  let cur = obj;
  for (const p of path) {
    if (cur == null) return undefined;
    cur = cur[p];
  }
  return cur;
}

// -----------------------
// Small UI bits (no deps)
// -----------------------
function Pill({
  children,
  tone = "neutral",
  title,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "good" | "bad" | "info" | "warn";
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cx(
        "ao-pill",
        tone === "good" && "ao-pill-good",
        tone === "bad" && "ao-pill-bad",
        tone === "info" && "ao-pill-info",
        tone === "warn" && "ao-pill-warn"
      )}
    >
      {children}
    </span>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <span className="ao-kbd">{children}</span>;
}

function SectionTitle({
  title,
  right,
}: {
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="ao-section-title">
      <div className="ao-section-title__left">{title}</div>
      {right ? <div className="ao-section-title__right">{right}</div> : null}
    </div>
  );
}

function PrettyJson({ value }: { value: any }) {
  return <pre className="ao-pre">{JSON.stringify(value, null, 2)}</pre>;
}

function AutoTableOrJson({ value }: { value: any }) {
  if (!value) return <div className="ao-small">Aucune donnée.</div>;

  if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object" && value[0] != null) {
    const keys = Object.keys(value[0]).slice(0, 6);
    return (
      <div style={{ overflow: "auto" }}>
        <table className="ao-table">
          <thead>
            <tr>
              {keys.map((k) => (
                <th className="ao-th" key={k}>
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.slice(0, 50).map((row: any, idx: number) => (
              <tr key={idx}>
                {keys.map((k) => (
                  <td className="ao-td" key={k}>
                    {typeof row[k] === "object" ? JSON.stringify(row[k]) : String(row[k] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {value.length > 50 ? (
          <div className="ao-small" style={{ marginTop: 8 }}>
            Affiché: 50/{value.length}
          </div>
        ) : null}
      </div>
    );
  }

  return <PrettyJson value={value} />;
}

// -----------------------
// Analysis Summary Card (future-proof)
// -----------------------
function AnalysisSummary({ analysis }: { analysis: any }) {
  const status = analysis?.status ?? "—";
  const createdAt = analysis?.created_at ?? "";
  const result = analysis?.result ?? {};

  const summary: string = result?.summary ?? "";
  const nextActions: string[] = Array.isArray(result?.next_actions) ? result.next_actions : [];
  const confidence: number = typeof result?.confidence === "number" ? result.confidence : 0;

  const extracted = result?.extracted_fields ?? {};
  const closing = extracted?.closing_date ?? null;
  const buyer = extracted?.buyer ?? null;
  const value = extracted?.estimated_value ?? null;

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div className="ao-banner" style={{ marginTop: 0 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <Pill tone={status === "ok" ? "good" : "warn"} title="Status">
            status: {String(status)}
          </Pill>
          {createdAt ? <Pill tone="neutral">created: {String(createdAt).replace("T", " ").replace("Z", "")}</Pill> : null}
          <Pill tone={confidenceTone(confidence)} title="Confiance (0..1)">
            confidence: {clamp01(confidence).toFixed(2)}
          </Pill>
        </div>

        {summary ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontWeight: 900, marginBottom: 4 }}>Résumé</div>
            <div className="ao-small" style={{ color: "rgba(255,255,255,.82)" }}>
              {summary}
            </div>
          </div>
        ) : null}
      </div>

      <div className="ao-card" style={{ boxShadow: "none" }}>
        <SectionTitle title="Champs extraits (prévu pour la vraie extraction)" />
        <div className="ao-card__body">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Pill tone={buyer ? "info" : "warn"} title="Acheteur">
              buyer: {buyer ? String(buyer) : "—"}
            </Pill>
            <Pill tone={closing ? "info" : "warn"} title="Date de clôture">
              closing: {closing ? String(closing) : "—"}
            </Pill>
            <Pill tone={value ? "info" : "warn"} title="Valeur estimée">
              value: {value ? String(value) : "—"}
            </Pill>
          </div>

          {nextActions.length > 0 ? (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 900, marginBottom: 6 }}>Prochaines actions</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {nextActions.slice(0, 8).map((a, i) => (
                  <li key={i} className="ao-small" style={{ color: "rgba(255,255,255,.85)" }}>
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// -----------------------
// AnalyzeBox
// -----------------------
function AnalyzeBox({
  tender,
  analyzing,
  analysis,
  files,
  notes,
  onPickFiles,
  onClearFiles,
  onNotes,
  onAnalyze,
}: {
  tender: Tender;
  analyzing: boolean;
  analysis: any;
  files: File[];
  notes: string;
  onPickFiles: (files: File[]) => void;
  onClearFiles: () => void;
  onNotes: (v: string) => void;
  onAnalyze: () => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const allPdf = files.length > 0 && files.every(isProbablyPdf);

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div
        className="ao-drop"
        style={{
          borderColor: isDragging ? "rgba(99,102,241,.55)" : undefined,
          background: isDragging ? "rgba(99,102,241,.14)" : undefined,
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setIsDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const picked = Array.from(e.dataTransfer.files || []);
          if (picked.length) onPickFiles(picked);
        }}
      >
        <div>
          <strong>PDF à analyser</strong>
          <div className="ao-small" style={{ marginTop: 4 }}>
            Glisse-dépose ici, ou sélectionne un fichier.{" "}
            <span style={{ opacity: 0.7 }}>({summarizeFiles(files)})</span>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {files.length > 0 ? (
            <Pill tone={allPdf ? "good" : "bad"} title={allPdf ? "Tout est en PDF" : "Au moins un fichier n’est pas PDF"}>
              {allPdf ? "PDF ✅" : "PDF ❌"}
            </Pill>
          ) : (
            <Pill tone="warn">PDF requis</Pill>
          )}

          <label className="ao-btn ao-btn-good" style={{ cursor: "pointer" }}>
            Choisir
            <input
              type="file"
              multiple
              accept=".pdf,application/pdf"
              style={{ display: "none" }}
              onChange={(e) => onPickFiles(Array.from(e.target.files || []))}
            />
          </label>

          <button className="ao-btn" disabled={files.length === 0 || analyzing} onClick={onClearFiles}>
            Clear
          </button>
        </div>
      </div>

      {files.length > 0 && (
        <div className="ao-banner" style={{ marginTop: 0 }}>
          <div style={{ fontWeight: 900, marginBottom: 6 }}>Fichiers sélectionnés</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {files.map((f, idx) => (
              <li key={idx} className="ao-small" style={{ color: "rgba(255,255,255,.85)" }}>
                {f.name} — {formatBytes(f.size)} {!isProbablyPdf(f) ? " (pas PDF?)" : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        <div className="ao-small" style={{ fontWeight: 900, opacity: 0.9 }}>
          Notes (optionnel)
        </div>
        <input
          className="ao-input"
          value={notes}
          onChange={(e) => onNotes(e.target.value)}
          placeholder="Ex: prioriser TI, sécurité, ERP, ServiceNow…"
        />
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <button
          className="ao-btn ao-btn-primary"
          disabled={analyzing || files.length === 0}
          onClick={onAnalyze}
          title={files.length === 0 ? "Ajoute un PDF d’abord" : `Analyser AO #${tender.id}`}
        >
          {analyzing ? "Analyse..." : "Lancer l’analyse IA"}
        </button>

        <Pill tone="info" title="Endpoint">
          POST /api/ai/analyze
        </Pill>

        <Pill tone="neutral">tender_id={tender.id}</Pill>
      </div>

      {analysis ? (
        <div className="ao-card" style={{ boxShadow: "none" }}>
          <SectionTitle title="Analyse (résumé)" right={<Pill tone={confidenceTone(pick(analysis, ["result", "confidence"]) ?? 0)}>IA</Pill>} />
          <div className="ao-card__body">
            <AnalysisSummary analysis={analysis} />
            <div style={{ height: 10 }} />
            <SectionTitle title="Analyse (JSON brut)" />
            <div className="ao-card__body">
              <PrettyJson value={analysis} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// -----------------------
// App
// -----------------------
const App: React.FC = () => {
  // Auth/session
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  // Tabs
  const [tab, setTab] = useState<TabKey>("ao");

  // Data
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loadingTenders, setLoadingTenders] = useState(false);

  // Selection
  const [selectedTenderId, setSelectedTenderId] = useState<number | null>(null);

  // Search/filter
  const [searchText, setSearchText] = useState("");
  const [query, setQuery] = useState("");
  const [searchField, setSearchField] = useState<SearchField>("title_buyer");
  const [atsOnly, setAtsOnly] = useState(false);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);

  // Filters (robust)
  const [portalFilter, setPortalFilter] = useState<string>("ALL");
  const [countryFilter, setCountryFilter] = useState<string>("ALL");

  // Global messages
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // IA Analyze
  const [analysisById, setAnalysisById] = useState<Record<number, any>>({});
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const [selectedFilesById, setSelectedFilesById] = useState<Record<number, File[]>>({});
  const [notesById, setNotesById] = useState<Record<number, string>>({});

  // Portals & reports
  const [portals, setPortals] = useState<any[] | null>(null);
  const [loadingPortals, setLoadingPortals] = useState(false);

  const [reportKeywords, setReportKeywords] = useState<any>(null);
  const [reportCategories, setReportCategories] = useState<any>(null);
  const [loadingReports, setLoadingReports] = useState(false);

  // Refs
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // -----------------------
  // CSS injection (FIX WHITE SELECT + LIST VISIBILITY)
  // -----------------------
  const injectedCss = useMemo(
    () => `
    :root{
      --ao-bg0:#0b1020;
      --ao-bg1:#0f172a;
      --ao-border:rgba(255,255,255,.10);
      --ao-text:rgba(255,255,255,.92);
      --ao-dim:rgba(255,255,255,.68);
      --ao-shadow: 0 20px 60px rgba(0,0,0,.35);
      --ao-radius: 18px;
    }

    .ao-shell{
      min-height: 100vh;
      background:
        radial-gradient(900px 500px at 15% 0%, rgba(99,102,241,.22), transparent 60%),
        radial-gradient(900px 500px at 85% 0%, rgba(34,197,94,.16), transparent 65%),
        linear-gradient(180deg, var(--ao-bg0), var(--ao-bg1) 55%, #070a13);
      color: var(--ao-text);
      padding: 18px;
    }

    .ao-topbar{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:14px;
      padding: 14px 16px;
      border-radius: var(--ao-radius);
      background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.03));
      border: 1px solid var(--ao-border);
      box-shadow: var(--ao-shadow);
    }

    .ao-brand{ display:flex; align-items:center; gap:12px; }
    .ao-logo{
      width: 38px; height:38px;
      border-radius: 12px;
      background: radial-gradient(circle at 30% 20%, rgba(99,102,241,1), rgba(34,197,94,.6));
      box-shadow: 0 10px 30px rgba(99,102,241,.25);
    }
    .ao-title{ font-size: 16px; font-weight: 900; letter-spacing: .2px; line-height: 1.2; }
    .ao-subtitle{ margin-top: 2px; font-size: 12px; color: var(--ao-dim); }

    .ao-actions{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }

    .ao-btn{
      background: rgba(255,255,255,.06);
      border: 1px solid var(--ao-border);
      color: var(--ao-text);
      padding: 9px 12px;
      border-radius: 12px;
      cursor: pointer;
      transition: transform .12s ease, background .12s ease, border-color .12s ease;
      user-select:none;
    }
    .ao-btn:hover{ transform: translateY(-1px); background: rgba(255,255,255,.09); border-color: rgba(255,255,255,.16); }
    .ao-btn:disabled{ opacity:.55; cursor:not-allowed; transform:none; }
    .ao-btn-primary{ background: rgba(99,102,241,.22); border-color: rgba(99,102,241,.35); }
    .ao-btn-primary:hover{ background: rgba(99,102,241,.28); }
    .ao-btn-good{ background: rgba(34,197,94,.18); border-color: rgba(34,197,94,.28); }

    .ao-card{
      border-radius: var(--ao-radius);
      border: 1px solid var(--ao-border);
      background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02));
      box-shadow: var(--ao-shadow);
      overflow:hidden;
    }
    .ao-card__body{ padding: 14px; }
    .ao-card__body-tight{ padding: 12px; }

    .ao-tabs{ display:flex; gap:8px; flex-wrap:wrap; }
    .ao-tab{
      padding: 8px 10px;
      border-radius: 12px;
      border: 1px solid var(--ao-border);
      background: rgba(255,255,255,.04);
      cursor:pointer;
      color: var(--ao-dim);
      transition: background .12s ease, transform .12s ease, color .12s ease;
      user-select:none;
      font-size: 13px;
    }
    .ao-tab:hover{ transform: translateY(-1px); background: rgba(255,255,255,.06); color: var(--ao-text); }
    .ao-tab--active{ color: var(--ao-text); background: rgba(99,102,241,.22); border-color: rgba(99,102,241,.35); }

    .ao-section-title{
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:center;
      padding: 12px 14px;
      border-bottom: 1px solid var(--ao-border);
      background: rgba(0,0,0,.10);
    }
    .ao-section-title__left{ font-weight: 900; letter-spacing: .2px; }
    .ao-section-title__right{ display:flex; gap:8px; align-items:center; color: var(--ao-dim); font-size: 12px; }

    /* ---- INPUTS / SELECTS (FIX "WHITE" look) ---- */
    .ao-input, .ao-select{
      background: rgba(15,23,42,.88);
      border: 1px solid rgba(255,255,255,.16);
      color: rgba(255,255,255,.92);
      padding: 9px 10px;
      border-radius: 12px;
      outline: none;
      min-width: 180px;
    }
    .ao-input::placeholder{ color: rgba(255,255,255,.45); }
    .ao-select{ min-width: 170px; color-scheme: dark; }
    .ao-select option{
      background: #0f172a;
      color: rgba(255,255,255,.92);
    }

    .ao-row{
      display:flex; gap:10px; flex-wrap:wrap; align-items:center;
      padding: 12px 14px;
      border-bottom: 1px solid var(--ao-border);
    }

    .ao-pill{
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--ao-border);
      background: rgba(255,255,255,.05);
      color: var(--ao-dim);
      user-select:none;
    }
    .ao-pill-good{ background: rgba(34,197,94,.16); border-color: rgba(34,197,94,.28); color: rgba(255,255,255,.88); }
    .ao-pill-bad{ background: rgba(239,68,68,.16); border-color: rgba(239,68,68,.28); color: rgba(255,255,255,.88); }
    .ao-pill-info{ background: rgba(99,102,241,.16); border-color: rgba(99,102,241,.28); color: rgba(255,255,255,.88); }
    .ao-pill-warn{ background: rgba(245,158,11,.16); border-color: rgba(245,158,11,.28); color: rgba(255,255,255,.88); }

    .ao-kbd{
      font-size: 11px;
      padding: 2px 7px;
      border-radius: 10px;
      background: rgba(255,255,255,.06);
      border: 1px solid var(--ao-border);
      color: var(--ao-dim);
    }

    .ao-list{ display:flex; flex-direction:column; gap:10px; padding: 12px 14px; }

    /* ---- LIST ITEMS: visible without hover (FIX) ---- */
    .ao-tender{
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.06);
      padding: 12px;
      cursor:pointer;
      transition: transform .12s ease, border-color .12s ease, background .12s ease;
    }
    .ao-tender:hover{ transform: translateY(-1px); border-color: rgba(255,255,255,.20); background: rgba(255,255,255,.08); }
    .ao-tender--active{
      border-color: rgba(99,102,241,.55);
      background: rgba(99,102,241,.14);
      box-shadow: 0 12px 40px rgba(99,102,241,.12);
    }
    .ao-tender__title{ font-weight: 900; letter-spacing: .15px; line-height: 1.2; color: rgba(255,255,255,.95); }
    .ao-tender__meta{ margin-top: 6px; font-size: 12px; color: var(--ao-dim); display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .ao-tender__link a{ color: rgba(255,255,255,.9); text-decoration: none; border-bottom: 1px dashed rgba(255,255,255,.25); }
    .ao-tender__link a:hover{ border-bottom-color: rgba(255,255,255,.5); }

    .ao-pre{
      margin: 0;
      padding: 12px;
      border-radius: 14px;
      border: 1px solid var(--ao-border);
      background: rgba(0,0,0,.22);
      overflow:auto;
      max-height: 420px;
      font-size: 12px;
      color: rgba(255,255,255,.85);
    }

    .ao-banner{
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: var(--ao-radius);
      border: 1px solid var(--ao-border);
      background: rgba(0,0,0,.10);
    }
    .ao-banner--err{ border-color: rgba(239,68,68,.35); background: rgba(239,68,68,.10); }
    .ao-banner--ok{ border-color: rgba(34,197,94,.35); background: rgba(34,197,94,.10); }

    .ao-drop{
      border: 1px dashed rgba(255,255,255,.18);
      background: rgba(255,255,255,.04);
      border-radius: 16px;
      padding: 12px;
      display:flex;
      gap:10px;
      align-items:center;
      justify-content:space-between;
      flex-wrap:wrap;
    }
    .ao-small{ font-size: 12px; color: var(--ao-dim); }

    .ao-table{ width: 100%; border-collapse: collapse; font-size: 13px; }
    .ao-th, .ao-td{ padding: 10px 10px; border-bottom: 1px solid rgba(255,255,255,.08); text-align:left; vertical-align: top; color: rgba(255,255,255,.86); }
    .ao-th{ color: rgba(255,255,255,.70); font-weight: 800; }

    @media (max-width: 980px){
      .ao-grid{ grid-template-columns: 1fr !important; }
    }
  `,
    []
  );

  // -----------------------
  // Local storage init
  // -----------------------
  useEffect(() => {
    const storedToken = localStorage.getItem("ao_token");
    const storedUser = localStorage.getItem("ao_user");
    if (storedToken) setToken(storedToken);
    if (storedUser) setUser(safeJsonParse<UserProfile>(storedUser));
  }, []);

  // -----------------------
  // Logout
  // -----------------------
  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setTenders([]);
    setSelectedTenderId(null);
    setAnalysisById({});
    setSelectedFilesById({});
    setNotesById({});
    setPortals(null);
    setReportKeywords(null);
    setReportCategories(null);
    localStorage.removeItem("ao_token");
    localStorage.removeItem("ao_user");
  }, []);

  // -----------------------
  // API fetch helper
  // -----------------------
  const apiFetchJson = useCallback(
    async (path: string, init?: RequestInit) => {
      if (!token) throw new Error("Non connecté");

      const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          ...(init?.headers || {}),
          Authorization: `Bearer ${token}`,
        },
      });

      const text = await res.text();
      const data = text ? safeJsonParse<any>(text) : null;

      if (res.status === 401) {
        logout();
        throw new Error("Session expirée. Reconnecte-toi.");
      }
      if (!res.ok) {
        const detail = data?.detail || `Erreur ${res.status}`;
        throw new Error(detail);
      }
      return data;
    },
    [token, logout]
  );

  // -----------------------
  // Token + user setter
  // -----------------------
  const acceptToken = useCallback((newToken: string, newUser?: UserProfile) => {
    setToken(newToken);
    localStorage.setItem("ao_token", newToken);
    if (newUser) {
      setUser(newUser);
      localStorage.setItem("ao_user", JSON.stringify(newUser));
    }
    setNotice("Connexion OK ✅");
    setTimeout(() => setNotice(null), 2000);
  }, []);

  // ✅ Robust callback to match ANY LoginPage signature
  const handleAuthCallback = useCallback(
    (...args: any[]) => {
      let foundToken: string | null = null;
      let foundUser: UserProfile | undefined = undefined;

      for (const a of args) {
        if (typeof a === "string" && (a.startsWith("acc_") || a.startsWith("tmp_"))) foundToken = a;
        if (a && typeof a === "object") {
          if (typeof a.access_token === "string") foundToken = a.access_token;
          if (a.user && typeof a.user === "object") foundUser = a.user as UserProfile;
          if (typeof (a as any).email === "string" && typeof (a as any).id === "string") foundUser = a as UserProfile;
        }
      }

      if (!foundToken) {
        const s = args.find((x: any) => typeof x === "string" && String(x).length > 20);
        if (typeof s === "string") foundToken = s;
      }

      if (!foundToken) throw new Error("Login: token introuvable (callback mismatch)");
      acceptToken(foundToken, foundUser);
    },
    [acceptToken]
  );

  const LoginPageAny = LoginPage as any;

  // -----------------------
  // Fetch tenders (backend) — with safe override
  // -----------------------
  const fetchTenders = useCallback(
    async (opts?: { q?: string }) => {
      if (!token) return;
      setError(null);
      setLoadingTenders(true);

      try {
        const effectiveQ = (opts?.q ?? query).trim();

        const params = new URLSearchParams();
        params.set("limit", String(limit));
        params.set("country", countryFilter);
        params.set("portal", portalFilter);

        // send to backend if supported
        if (effectiveQ) {
          params.set("q", effectiveQ);
          params.set("search_field", searchField);
        }
        if (atsOnly) params.set("ats_only", "1");

        const data = (await apiFetchJson(`/tenders?${params.toString()}`)) as TendersResponse;

        const normalized = (data.items || []).map(normalizeTender);
        normalized.sort((a, b) => (b.date_publication || "").localeCompare(a.date_publication || ""));
        setTenders(normalized);

        if (data.user) {
          setUser(data.user);
          localStorage.setItem("ao_user", JSON.stringify(data.user));
        }
      } catch (e: any) {
        setError(e?.message || "Erreur inconnue");
      } finally {
        setLoadingTenders(false);
      }
    },
    [token, query, limit, portalFilter, countryFilter, searchField, atsOnly, apiFetchJson]
  );

  useEffect(() => {
    if (!token) return;
    fetchTenders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // -----------------------
  // Portal/Country options derived from data (prevents mismatch)
  // -----------------------
  const portalOptions = useMemo(() => {
    const set = new Set<string>();
    for (const t of tenders) {
      const p = (t.portail || "").trim();
      if (p) set.add(p);
    }
    const arr = Array.from(set).sort((a, b) => a.localeCompare(b));
    return ["ALL", ...arr];
  }, [tenders]);

  const countryOptions = useMemo(() => {
    const set = new Set<string>();
    for (const t of tenders) {
      const c = (t.pays || "").trim();
      if (c) set.add(c);
    }
    const arr = Array.from(set).sort((a, b) => a.localeCompare(b));
    return ["ALL", ...arr];
  }, [tenders]);

  // -----------------------
  // Fallback filtering (frontend) => always works
  // -----------------------
  const visibleTenders = useMemo(() => {
    let list = [...tenders];

    if (portalFilter !== "ALL") {
      list = list.filter((t) => (t.portail || "").trim() === portalFilter);
    }

    if (countryFilter !== "ALL") {
      list = list.filter((t) => (t.pays || "").trim() === countryFilter);
    }

    if (atsOnly) list = list.filter((t) => t.est_ats);

    const q = query.trim().toLowerCase();
    if (!q) return list;

    const hit = (s: string) => (s || "").toLowerCase().includes(q);

    return list.filter((t) => {
      if (searchField === "title") return hit(t.titre);
      if (searchField === "buyer") return hit(t.acheteur);
      return hit(t.titre) || hit(t.acheteur);
    });
  }, [tenders, portalFilter, countryFilter, atsOnly, query, searchField]);

  // -----------------------
  // Fetch portals & reports (on demand)
  // -----------------------
  const fetchPortals = useCallback(async () => {
    if (!token) return;
    setError(null);
    setLoadingPortals(true);
    try {
      const data = await apiFetchJson("/portals");
      setPortals(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || "Erreur portails");
    } finally {
      setLoadingPortals(false);
    }
  }, [token, apiFetchJson]);

  const fetchReports = useCallback(async () => {
    if (!token) return;
    setError(null);
    setLoadingReports(true);
    try {
      const [kw, cat] = await Promise.allSettled([
        apiFetchJson("/report/keywords"),
        apiFetchJson("/report/categories"),
      ]);

      setReportKeywords(kw.status === "fulfilled" ? kw.value : { error: kw.reason?.message || "Erreur keywords" });
      setReportCategories(cat.status === "fulfilled" ? cat.value : { error: cat.reason?.message || "Erreur categories" });
    } catch (e: any) {
      setError(e?.message || "Erreur reports");
    } finally {
      setLoadingReports(false);
    }
  }, [token, apiFetchJson]);

  useEffect(() => {
    if (!token) return;
    if (tab === "portals" && portals == null) fetchPortals();
    if (tab === "reports" && reportKeywords == null && reportCategories == null) fetchReports();
  }, [token, tab, portals, reportKeywords, reportCategories, fetchPortals, fetchReports]);

  // -----------------------
  // Tender selection
  // -----------------------
  const selectedTender = useMemo(() => {
    if (selectedTenderId == null) return null;
    return (
      visibleTenders.find((t) => t.id === selectedTenderId) ||
      tenders.find((t) => t.id === selectedTenderId) ||
      null
    );
  }, [selectedTenderId, visibleTenders, tenders]);

  // -----------------------
  // Analyze tender
  // -----------------------
  const analyzeTender = useCallback(
    async (t: Tender) => {
      if (!token) throw new Error("Non connecté");

      const files = selectedFilesById[t.id] || [];
      if (files.length === 0) throw new Error("Ajoute au moins un PDF avant d’analyser.");

      const nonPdf = files.find((f) => !isProbablyPdf(f));
      if (nonPdf) throw new Error(`Fichier non-PDF détecté: "${nonPdf.name}"`);

      const fd = new FormData();
      fd.append("tender_id", String(t.id));

      const notes = (notesById[t.id] || "").trim();
      if (notes) fd.append("notes", notes);

      for (const f of files) fd.append("files", f);

      const res = await fetch(`${API_BASE}/ai/analyze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });

      const text = await res.text();
      const data = text ? safeJsonParse<any>(text) : null;

      if (res.status === 401) {
        logout();
        throw new Error("Session expirée. Reconnecte-toi.");
      }
      if (!res.ok) throw new Error(data?.detail || `Analyse échouée (${res.status})`);
      return data;
    },
    [token, selectedFilesById, notesById, logout]
  );

  // -----------------------
  // Keyboard shortcuts
  // -----------------------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!token) return;

      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "r") {
        e.preventDefault();
        fetchTenders();
        return;
      }

      if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === "1") setTab("ao");
        if (e.key === "2") setTab("ai");
        if (e.key === "3") setTab("reports");
        if (e.key === "4") setTab("portals");
        if (e.key === "5") setTab("others");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [token, fetchTenders]);

  // -----------------------
  // UI helpers
  // -----------------------
  const tabBtn = (k: TabKey, label: string, hotkey: string) => (
    <div
      className={cx("ao-tab", tab === k && "ao-tab--active")}
      onClick={() => setTab(k)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" ? setTab(k) : null)}
      title={`Raccourci: ${hotkey}`}
    >
      {label} <span style={{ opacity: 0.6 }}>({hotkey})</span>
    </div>
  );

  const applySearch = useCallback(() => {
    const q = searchText.trim();
    setQuery(q);
    fetchTenders({ q });
  }, [searchText, fetchTenders]);

  const resetSearch = useCallback(() => {
    setSearchText("");
    setQuery("");
    fetchTenders({ q: "" });
  }, [fetchTenders]);

  // -----------------------
  // Login render
  // -----------------------
  if (!token) {
    return (
      <div className="ao-shell">
        <style>{injectedCss}</style>

        <div className="ao-topbar" style={{ marginBottom: 14 }}>
          <div className="ao-brand">
            <div className="ao-logo" />
            <div>
              <div className="ao-title">AO Collector</div>
              <div className="ao-subtitle">
                Login requis • Astuce: <Kbd>bilel@example.com</Kbd> / <Kbd>password</Kbd>
              </div>
            </div>
          </div>
        </div>

        <div className="ao-card">
          <div className="ao-card__body">
            <LoginPageAny
              onAuthenticated={handleAuthCallback}
              onLogin={handleAuthCallback}
              onSuccess={handleAuthCallback}
              setToken={handleAuthCallback}
            />
          </div>
        </div>

        {error && (
          <div className="ao-banner ao-banner--err">
            <b>Erreur:</b> {error}
          </div>
        )}
      </div>
    );
  }

  // -----------------------
  // Main render
  // -----------------------
  return (
    <div className="ao-shell">
      <style>{injectedCss}</style>

      <div className="ao-topbar">
        <div className="ao-brand">
          <div className="ao-logo" />
          <div>
            <div className="ao-title">AO Collector</div>
            <div className="ao-subtitle">
              Connecté: <b>{user?.full_name || user?.email || "Utilisateur"}</b>
              {" • "}
              <span style={{ opacity: 0.85 }}>{user?.activity_type || "Profil"}</span>
              {" • "}
              <span style={{ opacity: 0.85 }}>{user?.main_specialty || "Spécialité"}</span>
            </div>
          </div>
        </div>

        <div className="ao-actions">
          <button className="ao-btn ao-btn-primary" onClick={() => fetchTenders()} disabled={loadingTenders}>
            {loadingTenders ? "Chargement..." : "Rafraîchir"}
          </button>
          <button
            className="ao-btn"
            onClick={() => {
              setError(null);
              setNotice(null);
            }}
          >
            Clear messages
          </button>
          <button className="ao-btn" onClick={() => logout()}>
            Déconnexion
          </button>
        </div>
      </div>

      <div className="ao-card" style={{ marginTop: 14 }}>
        <div className="ao-card__body-tight">
          <div className="ao-tabs">
            {tabBtn("ao", "AO", "1")}
            {tabBtn("ai", "Analyses IA", "2")}
            {tabBtn("reports", "Rapports", "3")}
            {tabBtn("portals", "Portails", "4")}
            {tabBtn("others", "Autres portails", "5")}
            

          </div>
        </div>
      </div>

      {error && (
        <div className="ao-banner ao-banner--err">
          <b>Erreur:</b> {error}
        </div>
      )}
      {notice && <div className="ao-banner ao-banner--ok">{notice}</div>}

      {tab === "ao" && (
        <div
          className="ao-grid"
          style={{ display: "grid", gridTemplateColumns: "1.2fr .8fr", gap: 14, marginTop: 14 }}
        >
          {/* Left */}
          <div className="ao-card">
            <SectionTitle
              title="Appels d’offres"
              right={
                <div>
                  <span style={{ marginRight: 8 }}>{visibleTenders.length} résultats</span>
                  <span className="ao-small">
                    <Kbd>/</Kbd> search • <Kbd>Ctrl</Kbd>+<Kbd>R</Kbd> refresh
                  </span>
                </div>
              }
            />

            <div className="ao-row">
              <input
                ref={searchInputRef}
                className="ao-input"
                style={{ minWidth: 260 }}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") applySearch();
                }}
                placeholder="Rechercher (titre/acheteur)…"
              />

              <select
                className="ao-select"
                value={searchField}
                onChange={(e) => setSearchField(e.target.value as SearchField)}
              >
                <option value="title_buyer">Titre + Acheteur</option>
                <option value="title">Titre</option>
                <option value="buyer">Acheteur</option>
              </select>

              <select className="ao-select" value={portalFilter} onChange={(e) => setPortalFilter(e.target.value)}>
                {portalOptions.map((p) => (
                  <option key={p} value={p}>
                    {p === "ALL" ? "Tous portails" : p}
                  </option>
                ))}
              </select>

              <select className="ao-select" value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)}>
                {countryOptions.map((c) => (
                  <option key={c} value={c}>
                    {c === "ALL" ? "Tous pays" : c}
                  </option>
                ))}
              </select>

              <label className="ao-small" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={atsOnly} onChange={(e) => setAtsOnly(e.target.checked)} />
                ATS seulement
              </label>

              <label className="ao-small" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                Limite
                <input
                  className="ao-input"
                  style={{ width: 100, minWidth: 100 }}
                  type="number"
                  min={1}
                  max={500}
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value) || DEFAULT_LIMIT)}
                />
              </label>

              <button className="ao-btn ao-btn-primary" disabled={loadingTenders} onClick={applySearch}>
                Chercher
              </button>

              <button className="ao-btn" disabled={loadingTenders} onClick={resetSearch}>
                Reset
              </button>

              <Pill tone={query ? "info" : "neutral"} title="Recherche active">
                {query ? `Filtre: ${query}` : "Aucun filtre"}
              </Pill>
            </div>

            <div className="ao-list">
              {visibleTenders.map((t) => {
                const isActive = t.id === selectedTenderId;
                return (
                  <div
                    key={t.id}
                    className={cx("ao-tender", isActive && "ao-tender--active")}
                    onClick={() => setSelectedTenderId(t.id)}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                      <div className="ao-tender__title">{t.titre || "(Sans titre)"}</div>
                      <div className="ao-small">{fmtDate(t.date_publication)}</div>
                    </div>

                    <div className="ao-tender__meta">
                      <Pill tone="info">{t.portail || "Portail"}</Pill>
                      {t.acheteur ? <Pill>{t.acheteur}</Pill> : null}
                      {t.est_ats ? <Pill tone="warn">ATS</Pill> : null}
                      {t.pays ? <Pill tone="neutral">{t.pays}</Pill> : null}
                    </div>

                    {t.lien && (
                      <div className="ao-tender__link" style={{ marginTop: 8 }}>
                        <a href={t.lien} target="_blank" rel="noreferrer">
                          Ouvrir le lien officiel
                        </a>
                      </div>
                    )}
                  </div>
                );
              })}

              {visibleTenders.length === 0 && !loadingTenders && (
                <div className="ao-small">
                  Aucun résultat. Essaie <Kbd>/</Kbd> puis tape un mot-clé.
                </div>
              )}
            </div>
          </div>

          {/* Right */}
          <div className="ao-card">
            <SectionTitle
              title="Détails + IA"
              right={
                selectedTender ? (
                  <span className="ao-small">
                    ID: <b>{selectedTender.id}</b>
                  </span>
                ) : (
                  <span className="ao-small">Sélectionne un AO</span>
                )
              }
            />

            <div className="ao-card__body">
              {!selectedTender ? (
                <div className="ao-drop">
                  <div>
                    <strong>Choisis un appel d’offres</strong>
                    <div className="ao-small" style={{ marginTop: 4 }}>
                      Astuce: utilise <Kbd>/</Kbd> pour chercher vite.
                    </div>
                  </div>
                  <Pill tone="info">AO → Analyse</Pill>
                </div>
              ) : (
                <>
                  <div style={{ display: "grid", gap: 8 }}>
                    <div style={{ fontSize: 16, fontWeight: 900, letterSpacing: 0.2 }}>
                      {selectedTender.titre || "(Sans titre)"}
                    </div>

                    <div className="ao-small">
                      <span style={{ marginRight: 8 }}>
                        <b>{selectedTender.portail}</b>
                      </span>
                      {selectedTender.acheteur ? <span>• {selectedTender.acheteur}</span> : null}
                      {selectedTender.est_ats ? (
                        <span>
                          {" "}
                          • <b>ATS</b>
                        </span>
                      ) : null}
                      {selectedTender.date_publication ? <span> • {fmtDate(selectedTender.date_publication)}</span> : null}
                      {selectedTender.pays ? <span> • {selectedTender.pays}</span> : null}
                    </div>

                    {selectedTender.lien ? (
                      <div className="ao-small">
                        Lien:{" "}
                        <a
                          href={selectedTender.lien}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "rgba(255,255,255,.9)", textDecoration: "underline" }}
                        >
                          {selectedTender.lien}
                        </a>
                      </div>
                    ) : null}
                  </div>

                  <div style={{ height: 12 }} />

                  <AnalyzeBox
                    tender={selectedTender}
                    analyzing={analyzingId === selectedTender.id}
                    analysis={analysisById[selectedTender.id]}
                    files={selectedFilesById[selectedTender.id] || []}
                    notes={notesById[selectedTender.id] || ""}
                    onPickFiles={(files) =>
                      setSelectedFilesById((prev) => ({ ...prev, [selectedTender.id]: files }))
                    }
                    onClearFiles={() => setSelectedFilesById((prev) => ({ ...prev, [selectedTender.id]: [] }))}
                    onNotes={(v) => setNotesById((prev) => ({ ...prev, [selectedTender.id]: v }))}
                    onAnalyze={async () => {
                      try {
                        setError(null);
                        setNotice(null);
                        setAnalyzingId(selectedTender.id);
                        const out = await analyzeTender(selectedTender);
                        setAnalysisById((prev) => ({ ...prev, [selectedTender.id]: out }));
                        setNotice("Analyse terminée ✅");
                        setTimeout(() => setNotice(null), 2500);
                        setTab("ai");
                      } catch (e: any) {
                        setError(e?.message || "Erreur analyse");
                      } finally {
                        setAnalyzingId(null);
                      }
                    }}
                  />
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === "ai" && (
        <div className="ao-card" style={{ marginTop: 14 }}>
          <SectionTitle
            title="Analyses IA"
            right={<span className="ao-small">{Object.keys(analysisById).length} analyse(s)</span>}
          />
          <div className="ao-card__body">
            {Object.keys(analysisById).length === 0 ? (
              <div className="ao-drop">
                <div>
                  <strong>Aucune analyse encore</strong>
                  <div className="ao-small" style={{ marginTop: 4 }}>
                    Va dans <Kbd>AO (1)</Kbd>, sélectionne un item, ajoute un PDF, puis “Analyser”.
                  </div>
                </div>
                <Pill tone="warn">Analyse = PDF requis</Pill>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {Object.entries(analysisById)
                  .sort((a, b) => Number(b[0]) - Number(a[0]))
                  .map(([idStr, analysis]) => {
                    const id = Number(idStr);
                    const t = tenders.find((x) => x.id === id);
                    const conf = pick(analysis, ["result", "confidence"]) ?? 0;
                    return (
                      <div key={id} className="ao-card" style={{ boxShadow: "none" }}>
                        <SectionTitle
                          title={`AO #${id} — ${t?.titre || "Titre inconnu"}`}
                          right={
                            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                              <Pill tone={confidenceTone(typeof conf === "number" ? conf : 0)}>
                                conf {clamp01(typeof conf === "number" ? conf : 0).toFixed(2)}
                              </Pill>
                              <button
                                className="ao-btn"
                                onClick={() => {
                                  setSelectedTenderId(id);
                                  setTab("ao");
                                }}
                              >
                                Ouvrir
                              </button>
                            </div>
                          }
                        />
                        <div className="ao-card__body">
                          <AnalysisSummary analysis={analysis} />
                          <div style={{ height: 10 }} />
                          <PrettyJson value={analysis} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "reports" && (
        <div className="ao-card" style={{ marginTop: 14 }}>
          <SectionTitle
            title="Rapports (backend)"
            right={
              <div className="ao-actions">
                <button className="ao-btn ao-btn-primary" onClick={fetchReports} disabled={loadingReports}>
                  {loadingReports ? "Chargement..." : "Rafraîchir"}
                </button>
              </div>
            }
          />
          <div className="ao-card__body">
            <div className="ao-small" style={{ marginBottom: 10 }}>
              Endpoints: <Kbd>/api/report/keywords</Kbd> & <Kbd>/api/report/categories</Kbd>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="ao-card" style={{ boxShadow: "none" }}>
                <SectionTitle title="Keywords" />
                <div className="ao-card__body">
                  <AutoTableOrJson value={reportKeywords} />
                </div>
              </div>

              <div className="ao-card" style={{ boxShadow: "none" }}>
                <SectionTitle title="Catégories" />
                <div className="ao-card__body">
                  <AutoTableOrJson value={reportCategories} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "portals" && (
        <div className="ao-card" style={{ marginTop: 14 }}>
          <SectionTitle
            title="Portails"
            right={
              <div className="ao-actions">
                <button className="ao-btn ao-btn-primary" onClick={fetchPortals} disabled={loadingPortals}>
                  {loadingPortals ? "Chargement..." : "Rafraîchir"}
                </button>
              </div>
            }
          />
          <div className="ao-card__body">
            {portals == null ? (
              <div className="ao-small">Clique “Rafraîchir” pour charger.</div>
            ) : portals.length === 0 ? (
              <div className="ao-small">Aucun portail.</div>
            ) : (
              <table className="ao-table">
                <thead>
                  <tr>
                    <th className="ao-th">Code</th>
                    <th className="ao-th">Label</th>
                    <th className="ao-th">Country</th>
                  </tr>
                </thead>
                <tbody>
                  {portals.map((p, idx) => (
                    <tr key={idx}>
                      <td className="ao-td">
                        <Pill tone="info">{p.code ?? "-"}</Pill>
                      </td>
                      <td className="ao-td">{p.label ?? "-"}</td>
                      <td className="ao-td">{p.country ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

  {tab === "others" && (
  <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 14 }}>
    {/* Section: candidats (MERX etc.) */}
    <div className="ao-card">
      <SectionTitle title="Candidats (à valider)" right={<Pill tone="info">Registry</Pill>} />
      <div className="ao-card__body">
        <PortalCandidates token={token} />
      </div>
    </div>

    {/* Section: roadmap (ce que tu avais déjà) */}
    <div className="ao-card">
      <SectionTitle title="Autres portails (roadmap)" right={<Pill tone="warn">Placeholder</Pill>} />
      <div className="ao-card__body">
        <div className="ao-drop">
          <div>
            <strong>MERX • Bids &amp; Tenders • BC Bid • Alberta Purchasing</strong>
            <div className="ao-small" style={{ marginTop: 4 }}>
              Ici on liste les portails à ajouter + la stratégie d’ingestion.
            </div>
          </div>
          <Pill tone="info">Next sprint</Pill>
        </div>
      </div>
    </div>
  </div>
)}


      <div className="ao-banner" style={{ marginTop: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div className="ao-small">
            Raccourcis: <Kbd>1</Kbd> AO • <Kbd>2</Kbd> IA • <Kbd>3</Kbd> Rapports • <Kbd>4</Kbd> Portails • <Kbd>5</Kbd>{" "}
            Autres • <Kbd>/</Kbd> recherche • <Kbd>Ctrl</Kbd>+<Kbd>R</Kbd> refresh
          </div>
          <div className="ao-small" style={{ opacity: 0.7 }}>
            Token in-memory → si tu redémarres le backend, reconnecte-toi.
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
