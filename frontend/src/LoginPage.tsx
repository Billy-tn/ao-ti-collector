import React, { useState } from "react";

type LoginResponse = {
  temp_token: string;
  message: string;
};

type VerifyResponse = {
  access_token: string;
  token_type: string;
  user: any;
};

interface LoginPageProps {
  onAuthenticated: (token: string, user: any) => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onAuthenticated }) => {
  const [step, setStep] = useState<"credentials" | "mfa">("credentials");
  const [email, setEmail] = useState("bilel@example.com");
  const [password, setPassword] = useState("password");
  const [mfaCode, setMfaCode] = useState("123456");
  const [tempToken, setTempToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmitCredentials(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const msg = body?.detail || body?.message || "Erreur de connexion";
        throw new Error(msg);
      }

      const data = (await res.json()) as LoginResponse;
      setTempToken(data.temp_token);
      setStep("mfa");
    } catch (err: any) {
      console.error("Login error:", err);
      setError(
        err.message === "Failed to fetch"
          ? "Serveur injoignable. Vérifie que le backend tourne sur le port 8000."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitMfa(e: React.FormEvent) {
    e.preventDefault();
    if (!tempToken) {
      setError("Session MFA invalide, recommence la connexion.");
      setStep("credentials");
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/verify-mfa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temp_token: tempToken, code: mfaCode }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const msg = body?.detail || body?.message || "Code MFA invalide";
        throw new Error(msg);
      }

      const data = (await res.json()) as VerifyResponse;
      localStorage.setItem("ao_token", data.access_token);
      localStorage.setItem("ao_user", JSON.stringify(data.user));
      onAuthenticated(data.access_token, data.user);
    } catch (err: any) {
      console.error("MFA error:", err);
      setError(
        err.message === "Failed to fetch"
          ? "Serveur injoignable. Vérifie que le backend tourne sur le port 8000."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  }

  const isCredentialsStep = step === "credentials";

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-badge">AO COLLECTOR</div>
        <h1 className="login-title">Connexion sécurisée</h1>
        <p className="login-subtitle">
          Accède à ton tableau de bord AO (SEAO &amp; CanadaBuys)
          <br />
          avec pré-filtrage ATS et IA.
        </p>

        <div className="login-steps">
          <button
            type="button"
            className={`login-step ${isCredentialsStep ? "active" : ""}`}
            onClick={() => setStep("credentials")}
          >
            1. Identifiants
          </button>
          <button
            type="button"
            className={`login-step ${!isCredentialsStep ? "active" : ""}`}
            disabled={!tempToken}
            onClick={() => tempToken && setStep("mfa")}
          >
            2. Code MFA
          </button>
        </div>

        {error && <div className="login-error">{error}</div>}

        {isCredentialsStep ? (
          <form onSubmit={handleSubmitCredentials} className="login-form">
            <label className="login-label">
              Email
              <input
                className="login-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </label>

            <label className="login-label">
              Mot de passe
              <input
                className="login-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>

            <button className="login-button" type="submit" disabled={loading}>
              {loading ? "Connexion..." : "Se connecter"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmitMfa} className="login-form">
            <label className="login-label">
              Code MFA (démo : 123456)
              <input
                className="login-input"
                type="text"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                maxLength={6}
              />
            </label>

            <button className="login-button" type="submit" disabled={loading}>
              {loading ? "Validation..." : "Valider le code"}
            </button>

            <button
              type="button"
              className="login-secondary-button"
              onClick={() => {
                setStep("credentials");
                setTempToken(null);
              }}
            >
              ← Revenir aux identifiants
            </button>
          </form>
        )}

        <p className="login-demo">
          Démo interne : <code>bilel@example.com</code> / <code>password</code>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
