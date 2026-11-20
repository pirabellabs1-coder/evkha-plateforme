import { useState } from "react";
import { setToken } from "../auth";
import { Icone } from "../admin/icones";
import { CHEMINS } from "../public/contenuSite";
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

/** La porte de l'administration, au langage du site.
 *
 * Elle parlait encore le verre de l'ancien espace — maillage de halos, carte
 * translucide, hexagone tapé au clavier en guise de sceau — alors que le site
 * et ses écrans de connexion (`public/Portail.tsx`) sont passés au papier
 * crème, à l'or et à l'encre. Elle les rejoint : fond papier, carte blanche à
 * double bord, étiquette à pastille, mot d'accent en Fraunces italique,
 * bouton pilule.
 *
 * Ce qu'elle garde, parce que c'est ce qui la distingue : le SCEAU de
 * l'administration, noir sur or — le même que dans la barre de la coquille
 * (`admin/Coquille.tsx`). On sait, avant d'avoir lu un mot, que cette porte
 * n'est pas celle de l'espace client.
 *
 * Sa logique n'a pas bougé : une clé collée, enregistrée, puis un vrai
 * rechargement vers `APRES_CONNEXION`. Le champ et le bouton restent
 * `.champ-saisie` et `.bouton .bouton-principal` de `theme/espace.css`,
 * ajustés par `Login.css`.
 *
 * Le vocabulaire, lui, a changé : « token » et « dashboard » sont devenus
 * « clé d'accès » et « administration ». Le nom de la variable du serveur
 * reste écrit tel quel — c'est lui qu'on cherche quand on a perdu la clé.
 */
export function Login() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setError("La clé d'accès ne peut pas être vide.");
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
            E
          </span>
          <p className="connexion-admin-etiquette">EVKHA · Administration</p>
        </header>

        <h1 className="connexion-admin-titre">
          Votre espace de <em className="connexion-admin-accent">pilotage</em>
        </h1>
        <p className="connexion-admin-sous-titre">
          Ventes, clients, production et catalogue. Réservé à l'équipe EVKHA.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="connexion-admin-champ">
            <label htmlFor="token" className="connexion-admin-libelle">
              Clé d'accès
            </label>
            {/* Le message d'erreur est RELIÉ au champ (`aria-describedby`)
                et le champ se dit invalide : entendu au moment où il
                apparaît, et relu quand on revient sur le champ. */}
            <input
              id="token"
              className="champ-saisie"
              type="password"
              placeholder="Collez votre clé ici"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError("");
              }}
              autoFocus
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "token-erreur" : "token-aide"}
            />
            {error ? (
              <p id="token-erreur" className="connexion-admin-erreur" role="alert">
                {error}
              </p>
            ) : (
              <p id="token-aide" className="connexion-admin-aide">
                C'est la valeur de{" "}
                <code className="connexion-admin-code">EVKHA_DASHBOARD_TOKEN</code>, dans
                les variables du serveur.
              </p>
            )}
          </div>

          <button
            type="submit"
            className="bouton bouton-principal connexion-admin-bouton"
            disabled={!value.trim()}
          >
            Entrer dans l'administration
            <span className="connexion-admin-fleche" aria-hidden="true">
              <Icone nom="fleche" taille={18} />
            </span>
          </button>
        </form>

        <p className="connexion-admin-pied">
          {/* Les chemins du site ont une seule source (`contenuSite.ts`). Des
              liens ordinaires : le site et l'espace client sont d'autres
              morceaux de l'application. */}
          <a href={CHEMINS.accueil}>Retour au site</a>
          <span aria-hidden="true"> · </span>
          <a href={CHEMINS.espaceClient}>Espace client</a>
        </p>
      </div>
    </main>
  );
}
