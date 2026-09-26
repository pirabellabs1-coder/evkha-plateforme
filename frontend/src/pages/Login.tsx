import { useState } from "react";
import { setToken } from "../auth";
import "./Login.css";

/** Où atterrit un administrateur qui vient de présenter son jeton.
 *
 * Cette page redirigeait vers `/`. C'était juste au temps où `/` servait le
 * tableau de bord ; depuis que la racine rend la page partenaires — publique —,
 * coller un jeton d'administration menait sur le site vitrine. Le jeton était
 * pourtant bien enregistré : rien n'échouait, on n'arrivait simplement jamais.
 *
 * La destination est nommée ici, à côté du geste qui l'emprunte, pour qu'un
 * futur changement de racine ne puisse plus la déplacer en silence.
 */
export const APRES_CONNEXION = "/admin";

/** La porte du tableau de bord : une carte de verre sur le maillage or et
 * crème.
 *
 * Elle était composée en Radix Themes (`Card`, `TextField`, `Button`) sur un
 * gris de Radix : la seule porte de la plateforme qui ne parlait pas la
 * charte. Radix reste dans l'application ; cette page lit désormais
 * `tokens.css`, et son champ et son bouton sont ceux de l'espace
 * (`.champ-saisie`, `.bouton .bouton-principal`) — voir `Login.css`.
 */
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
    // Rechargement complet et non navigation interne : la garde de route lit
    // le jeton au chargement, et l'application doit repartir avec.
    window.location.href = APRES_CONNEXION;
  }

  return (
    <main className="connexion-admin">
      <div className="connexion-admin-carte">
        <header className="connexion-admin-entete">
          <span className="connexion-admin-sceau" aria-hidden="true">
            ⬡
          </span>
          <div>
            <h1 className="connexion-admin-titre">EVKHA</h1>
            <p className="connexion-admin-sous-titre">
              Dashboard · accès administrateur
            </p>
          </div>
        </header>

        <form onSubmit={handleSubmit}>
          <div className="connexion-admin-champ">
            <label htmlFor="token" className="connexion-admin-libelle">
              Token d'accès
            </label>
            {/* Le message d'erreur est RELIÉ au champ (`aria-describedby`)
                et le champ se dit invalide : entendu au moment où il
                apparaît, et relu quand on revient sur le champ. */}
            <input
              id="token"
              className="champ-saisie"
              type="password"
              placeholder="Coller le token ici…"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError("");
              }}
              autoFocus
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "token-erreur" : undefined}
            />
            {error && (
              <p id="token-erreur" className="connexion-admin-erreur" role="alert">
                {error}
              </p>
            )}
          </div>

          <button
            type="submit"
            className="bouton bouton-principal connexion-admin-bouton"
            disabled={!value.trim()}
          >
            Accéder au dashboard
            <span className="bouton__icone" aria-hidden="true">
              ↗
            </span>
          </button>
        </form>

        <p className="connexion-admin-aide">
          Le token se trouve dans{" "}
          <code className="connexion-admin-code">EVKHA_DASHBOARD_TOKEN</code>{" "}
          (Coolify env vars).
        </p>
      </div>
    </main>
  );
}
