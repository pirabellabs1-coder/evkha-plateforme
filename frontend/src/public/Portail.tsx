/** Coquille commune à la connexion et à l'inscription.
 *
 * Les deux pages étaient étrangères l'une à l'autre : l'une dans la charte du
 * site, l'autre dans celle de l'application. Quelqu'un qui passe de « Créer
 * mon compte » à « Se connecter » changeait d'univers visuel en un clic, et
 * doutait d'être au bon endroit.
 *
 * Elles partagent donc **une seule** coquille : formulaire à gauche, visuel et
 * argumentaire à droite. Deux mises en page jumelles finiraient par diverger
 * au premier ajustement (règle 5) — ici, corriger l'une corrige l'autre.
 */
import { useEffect } from "react";
import "./Partenaires.css";
import "./Portail.css";

export function Portail({
  titre,
  sousTitre,
  onglet,
  enfants,
  panneau,
}: {
  titre: string;
  sousTitre?: React.ReactNode;
  /** Onglet actif. Les deux pages restent visibles l'une de l'autre : cacher
   *  le chemin qu'on n'a pas pris oblige à chercher. */
  onglet: "connexion" | "inscription";
  enfants: React.ReactNode;
  panneau: { image: string; alt: string; titre: string; arguments: string[] };
}) {
  useEffect(() => {
    const precedent = document.title;
    document.title = `${titre} — EVKHA`;
    return () => {
      document.title = precedent;
    };
  }, [titre]);

  return (
    <div className="pp prt">
      <div className="prt-grille">
        {/* ── Le formulaire ─────────────────────────────────────────── */}
        {/* Premier dans le HTML, affiché à droite : voir `Portail.css`. Le
            côté est une décision de mise en page, l'ordre du HTML une
            décision d'accessibilité — les mélanger obligerait à choisir. */}
        <section className="prt-formulaire">
          <div className="prt-contenu">
            <a className="prt-logo" href="/partenaires">
              Evkha
              <small>ÉTUDES &amp; STRATÉGIES</small>
            </a>

            <nav className="prt-onglets" aria-label="Accès à votre espace">
              <a
                href="/inscription"
                className={onglet === "inscription" ? "prt-actif" : ""}
                aria-current={onglet === "inscription" ? "page" : undefined}
              >
                Créer un compte
              </a>
              <a
                href="/espace/connexion"
                className={onglet === "connexion" ? "prt-actif" : ""}
                aria-current={onglet === "connexion" ? "page" : undefined}
              >
                Se connecter
              </a>
            </nav>

            <h1>{titre}</h1>
            {sousTitre}

            {enfants}
          </div>
        </section>

        {/* ── Le visuel et son argumentaire ─────────────────────────── */}
        <aside className="prt-visuel" aria-hidden="true">
          <img src={panneau.image} alt={panneau.alt} loading="lazy" />
          <div className="prt-voile" />
          <div className="prt-panneau">
            <h2>{panneau.titre}</h2>
            <ul>
              {panneau.arguments.map((argument) => (
                <li key={argument}>
                  <span className="pp-coche">✓</span>
                  <span>{argument}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
