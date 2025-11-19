// src/LoginPage.tsx
import React, { useState } from "react";

const API_URL = "http://localhost:8000"; // adapte selon ton setup

type Step = "login" | "mfa" | "done";

interface TenderWin {
  ao_id: string;
  title: string;
  specialty: string;
  date_awarded: string;
}

interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  activity_type: string;
  main_specialty: string;
  mfa_code?: string; // on pourrait le masquer côté backend plus tard
  history: TenderWin[];
}

interface UserReports {
  main_specialty: string;
  ao_count_in_specialty: number;
  seniority_score: number;
  wins_by_year: Record<string, number>;
}

interface VerifyMfaResponse {
  access_token: string;
  user: UserProfile;
  reports: UserReports;
}

const LoginPage: React.FC = () => {
  const [step, setStep] = useState<Step>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("password"); // POC
  const [mfaCode, setMfaCode] = useState("");
  const [tempToken, setTempToken] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [reports, setReports] = useState<UserReports | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Erreur de connexion");
      }

      const data = await res.json();
      setTempToken(data.temp_token);
      setStep("mfa");
    } catch (e: any) {
      setError(e.message || "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyMfa = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/verify-mfa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temp_token: tempToken, code: mfaCode }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Erreur MFA");
      }

      const data: VerifyMfaResponse = await res.json();
      setAccessToken(data.access_token);
      setUser(data.user);
      setReports(data.reports);
      setStep("done");
    } catch (e: any) {
      setError(e.message || "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  if (step === "done" && user && reports) {
    return (
      <div style={{ maxWidth: 900, margin: "40px auto", fontFamily: "sans-serif" }}>
        <h1>AO Collector – Tableau de bord utilisateur</h1>
        <p>Bonjour <strong>{user.full_name}</strong> 👋</p>
        <p>
          Activité : <strong>{user.activity_type}</strong>
          <br />
          Spécialité principale : <strong>{user.main_specialty}</strong>
        </p>

        <h2>Rapport rapide</h2>
        <ul>
          <li>
            Nombre d&apos;AO gagnés dans la spécialité principale :{" "}
            <strong>{reports.ao_count_in_specialty}</strong>
          </li>
          <li>
            Score d&apos;ancienneté dans cette spécialité :{" "}
            <strong>{reports.seniority_score.toFixed(1)}</strong>
          </li>
        </ul>

        <h3>Répartition des gains par année (spécialité principale)</h3>
        <ul>
          {Object.entries(reports.wins_by_year).map(([year, count]) => (
            <li key={year}>
              {year} : {count} AO gagnés
            </li>
          ))}
          {Object.keys(reports.wins_by_year).length === 0 && (
            <li>Aucun gain dans la spécialité principale pour l&apos;instant.</li>
          )}
        </ul>

        <h2>Historique complet des AO gagnés</h2>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ borderBottom: "1px solid #ccc", textAlign: "left" }}>Référence</th>
              <th style={{ borderBottom: "1px solid #ccc", textAlign: "left" }}>Titre</th>
              <th style={{ borderBottom: "1px solid #ccc", textAlign: "left" }}>Spécialité</th>
              <th style={{ borderBottom: "1px solid #ccc", textAlign: "left" }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {user.history.map((h) => (
              <tr key={h.ao_id}>
                <td style={{ borderBottom: "1px solid #eee" }}>{h.ao_id}</td>
                <td style={{ borderBottom: "1px solid #eee" }}>{h.title}</td>
                <td style={{ borderBottom: "1px solid #eee" }}>{h.specialty}</td>
                <td style={{ borderBottom: "1px solid #eee" }}>{h.date_awarded}</td>
              </tr>
            ))}
            {user.history.length === 0 && (
              <tr>
                <td colSpan={4}>Pas encore d&apos;AO gagnés.</td>
              </tr>
            )}
          </tbody>
        </table>

        <p style={{ marginTop: 24, fontSize: 12, color: "#666" }}>
          Token (pour tests API):<br />
          <code>{accessToken}</code>
        </p>
      </div>
    );
  }

  // Step login / MFA
  return (
    <div style={{ maxWidth: 400, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h1>AO Collector – Connexion</h1>

      {step === "login" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%", padding: 8, marginTop: 4 }}
              placeholder="bilel@example.com"
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label>Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: 8, marginTop: 4 }}
            />
          </div>
          <button onClick={handleLogin} disabled={loading} style={{ padding: "8px 16px" }}>
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </>
      )}

      {step === "mfa" && (
        <>
          <p>
            Un code MFA a été généré pour <strong>{email}</strong> (dans le POC, utilise le code
            statique du profil, ex: <code>123456</code>).
          </p>
          <div style={{ marginBottom: 12 }}>
            <label>Code MFA</label>
            <input
              type="text"
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              style={{ width: "100%", padding: 8, marginTop: 4 }}
              placeholder="123456"
            />
          </div>
          <button onClick={handleVerifyMfa} disabled={loading} style={{ padding: "8px 16px" }}>
            {loading ? "Validation..." : "Valider le code"}
          </button>
        </>
      )}

      {error && (
        <p style={{ color: "red", marginTop: 12 }}>
          {error}
        </p>
      )}
    </div>
  );
};

export default LoginPage;
