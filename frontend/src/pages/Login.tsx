import { useState } from "react";
import { setToken } from "../auth";

export function Login() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Le token ne peut pas être vide.");
      return;
    }
    setToken(trimmed);
    window.location.href = "/";
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <span className="logo">⬡</span>
          <div>
            <strong>EVKHA</strong>
            <small>Dashboard · accès administrateur</small>
          </div>
        </div>
        <form onSubmit={handleSubmit}>
          <label htmlFor="token" className="login-label">
            Token d'accès
          </label>
          <input
            id="token"
            type="password"
            className="login-input"
            placeholder="Coller le token ici…"
            value={value}
            onChange={(e) => { setValue(e.target.value); setError(""); }}
            autoFocus
          />
          {error && <p className="login-error">{error}</p>}
          <button type="submit" className="login-btn">
            Accéder au dashboard
          </button>
        </form>
        <p className="login-hint">
          Le token se trouve dans <code>EVKHA_DASHBOARD_TOKEN</code> (Coolify env vars).
        </p>
      </div>
    </div>
  );
}
