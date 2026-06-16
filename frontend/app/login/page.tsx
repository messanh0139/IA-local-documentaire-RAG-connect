"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result =
        mode === "login"
          ? await api.login(email, password)
          : await api.register(email, password, displayName || undefined);

      localStorage.setItem("docmind_token", result.access_token);
      localStorage.setItem(
        "docmind_user",
        JSON.stringify({ email: result.email, display_name: result.display_name })
      );
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-icon">
            <Sparkles size={20} />
          </div>
          <div className="brand-text">
            <strong>DocMind</strong>
            <span>Deep Bleue IA</span>
          </div>
        </div>

        <h1 className="auth-title">
          {mode === "login" ? "Connexion" : "Créer un compte"}
        </h1>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "register" && (
            <label>
              Nom d&apos;affichage
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Jean Dupont"
                autoComplete="name"
              />
            </label>
          )}

          <label>
            Adresse email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@exemple.com"
              required
              autoComplete="email"
              autoFocus
            />
          </label>

          <label>
            Mot de passe
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>

          <button className="auth-submit-btn" type="submit" disabled={busy}>
            {busy ? (
              <Loader2 size={16} className="spin" />
            ) : mode === "login" ? (
              "Se connecter"
            ) : (
              "Créer le compte"
            )}
          </button>
        </form>

        <button
          className="auth-switch"
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login"
            ? "Pas encore de compte ? Créer un compte"
            : "Déjà un compte ? Se connecter"}
        </button>
      </div>
    </div>
  );
}
