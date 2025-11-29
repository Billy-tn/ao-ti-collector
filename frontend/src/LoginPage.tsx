import React, { useState } from "react";

type Step = "credentials" | "mfa";

interface LoginResponse {
  message: string;
  mfa_required: boolean;
  temp_token?: string | null;
  access_token?: string | null;
  token_type?: string;
  user?: any;
}

interface VerifyMfaResponse {
  access_token: string;
  token_type: string;
  user: any;
}

export default function LoginPage({
  onAuthenticated,
}: {
  onAuthenticated: (token: string, user: any) => void;
}) {
  const [step, setStep] = useState<Step>("credentials");

  const [email, setEmail] = useState("bilel@example.com");
  const [password, setPassword] = useState("password");

  const [tempToken, setTempToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("123456");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogin() {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = (await res.json().catch(() => null)) as LoginResponse | null;

      if (!res.ok) {
        throw new Error((data as any)?.detail || "Erreur de connexion.");
      }

      // ✅ MFA OFF: on reçoit directement access_token + user
      if (data && data.mfa_required === false && data.access_token) {
        localStorage.setItem("ao_token", data.access_token);
        if (data.user) localStorage.setItem("ao_user", JSON.stringify(data.user));
        onAuthenticated(data.access_token, data.user);
        return;
      }

      // ✅ MFA ON: temp_token puis écran MFA
      if (data?.temp_token) {
        setTempToken(data.temp_token);
        setStep("mfa");
        return;
      }

      throw new Error("Réponse login inattendue (pas de token).");
    } catch (e: any) {
      setError(e?.message || "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyMfa() {
    if (!tempToken) {
      setError("Token MFA manquant. Recommence la connexion.");
      setStep("credentials");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/verify-mfa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temp_token: tempToken, code: mfaCode }),
      });

      const data = (await res.json().catch(() => null)) as VerifyMfaResponse | null;

      if (!res.ok) {
        throw new Error((data as any)?.detail || "Code MFA invalide.");
      }

      if (!data?.access_token) {
        throw new Error("Réponse MFA inattendue (pas de access_token).");
      }

      localStorage.setItem("ao_token", data.access_token);
      localStorage.setItem("ao_user", JSON.stringify(data.user));
      onAuthenticated(data.access_token, data.user);
    } catch (e: any) {
      setError(e?.message || "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: "40px auto", padding: 16 }}>
      <h1 style={{ marginBottom: 6 }}>AO Collector</h1>
      <p style={{ marginTop: 0, opacity: 0.8 }}>
        Connecte-toi pour accéder au tableau des appels d’offres.
      </p>

      {error && (
        <div
          style={{
            background: "#3b0d0d",
            color: "#ffd6d6",
            padding: 12,
            borderRadius: 10,
            margin: "12px 0",
          }}
        >
          {error}
        </div>
      )}

      {step === "credentials" && (
        <div style={{ display: "grid", gap: 10 }}>
          <label>
            Email
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%", padding: 10, borderRadius: 10, marginTop: 6 }}
            />
          </label>

          <label>
            Mot de passe
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: 10, borderRadius: 10, marginTop: 6 }}
            />
          </label>

          <button
            onClick={handleLogin}
            disabled={loading}
            style={{
              padding: 12,
              borderRadius: 12,
              border: "none",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            {loading ? "Connexion..." : "Se connecter"}
          </button>

          <div style={{ fontSize: 12, opacity: 0.75 }}>
            Astuce: si MFA est activé, tu passeras à l’étape code (verify-mfa).
          </div>
        </div>
      )}

      {step === "mfa" && (
        <div style={{ display: "grid", gap: 10 }}>
          <div style={{ opacity: 0.85 }}>
            Code MFA (factice). Temp token: <code>{tempToken}</code>
          </div>

          <label>
            Code
            <input
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              style={{ width: "100%", padding: 10, borderRadius: 10, marginTop: 6 }}
            />
          </label>

          <button
            onClick={handleVerifyMfa}
            disabled={loading}
            style={{
              padding: 12,
              borderRadius: 12,
              border: "none",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            {loading ? "Vérification..." : "Valider le code"}
          </button>

          <button
            onClick={() => {
              setStep("credentials");
              setTempToken(null);
              setError(null);
            }}
            style={{
              padding: 12,
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.2)",
              background: "transparent",
              cursor: "pointer",
            }}
          >
            Retour
          </button>
        </div>
      )}
    </div>
  );
}
