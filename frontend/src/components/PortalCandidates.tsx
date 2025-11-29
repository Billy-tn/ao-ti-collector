import React, { useEffect, useMemo, useState } from "react";

type Candidate = {
  id: number;
  discovered_url: string;
  label: string;
  country: string;
  source_type: string;
  status: string;
  created_at: string;
};

export default function PortalCandidates({ token }: { token: string | null }) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<Candidate[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [discoveredUrl, setDiscoveredUrl] = useState("https://www.merx.com/");
  const [label, setLabel] = useState("MERX");
  const [country, setCountry] = useState("CA");
  const [sourceType, setSourceType] =
    useState<"html" | "rss" | "api" | "opendata" | "manual">("html");

  const canSubmit = useMemo(() => discoveredUrl.trim().length > 8, [discoveredUrl]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/portals/candidates");
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function add() {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const payload = {
        discovered_url: discoveredUrl.trim(),
        label: label.trim(),
        country: country.trim(),
        source_type: sourceType,
      };

      const res = await fetch("/api/portals/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(await res.text());
      await refresh();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div
      style={{
        marginTop: 14,
        padding: 14,
        borderRadius: 14,
        border: "1px solid rgba(255,255,255,.12)",
        background: "rgba(255,255,255,.06)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>Candidats portails (découverte)</div>
          <div style={{ opacity: 0.75, fontSize: 12 }}>
            Ajoute un portail à évaluer (MERX, etc.). Aucun scraping auto ici — juste un registre.
          </div>
        </div>
        <button onClick={refresh} disabled={loading} style={btn()}>
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 0.5fr 0.8fr auto",
          gap: 10,
          marginTop: 12,
        }}
      >
        <input
          value={discoveredUrl}
          onChange={(e) => setDiscoveredUrl(e.target.value)}
          placeholder="https://..."
          style={inp()}
        />
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label" style={inp()} />
        <input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="CA" style={inp()} />
        <select value={sourceType} onChange={(e) => setSourceType(e.target.value as any)} style={inp()}>
          <option value="html">html</option>
          <option value="rss">rss</option>
          <option value="api">api</option>
          <option value="opendata">opendata</option>
          <option value="manual">manual</option>
        </select>
        <button onClick={add} disabled={loading || !canSubmit} style={btn(true)}>
          Ajouter
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 10, color: "#ffb4b4", fontSize: 12, whiteSpace: "pre-wrap" }}>{error}</div>
      )}

      <div style={{ marginTop: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", opacity: 0.85 }}>
              <th style={th()}>ID</th>
              <th style={th()}>URL</th>
              <th style={th()}>Label</th>
              <th style={th()}>Pays</th>
              <th style={th()}>Type</th>
              <th style={th()}>Statut</th>
              <th style={th()}>Créé</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} style={{ borderTop: "1px solid rgba(255,255,255,.08)" }}>
                <td style={td()}>{c.id}</td>
                <td style={td()}>
                  <a href={c.discovered_url} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>
                    {c.discovered_url}
                  </a>
                </td>
                <td style={td()}>{c.label}</td>
                <td style={td()}>{c.country}</td>
                <td style={td()}>{c.source_type}</td>
                <td style={td()}>{c.status}</td>
                <td style={td()}>{c.created_at}</td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td style={td()} colSpan={7}>
                  Aucun candidat pour le moment.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {!token && (
        <div style={{ marginTop: 10, opacity: 0.7, fontSize: 12 }}>
          Note: ce panneau n’utilise pas le token (endpoints publics).
        </div>
      )}
    </div>
  );
}

function inp(): React.CSSProperties {
  return {
    padding: "10px 12px",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,.12)",
    outline: "none",
    background: "rgba(0,0,0,.25)",
    color: "rgba(255,255,255,.92)",
  };
}
function btn(primary = false): React.CSSProperties {
  return {
    padding: "10px 12px",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,.14)",
    background: primary ? "rgba(125, 211, 252, .18)" : "rgba(255,255,255,.06)",
    color: "rgba(255,255,255,.92)",
    cursor: "pointer",
    fontWeight: 700,
  };
}
function th(): React.CSSProperties {
  return { padding: "10px 8px" };
}
function td(): React.CSSProperties {
  return { padding: "10px 8px", opacity: 0.95 };
}
