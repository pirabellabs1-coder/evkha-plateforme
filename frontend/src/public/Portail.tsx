/** Coquille commune à la connexion et à l'inscription.
 *
 * Les deux pages étaient étrangères l'une à l'autre : l'une dans la charte du
 * site, l'autre dans celle de l'application. Quelqu'un qui passe de « Créer
 * mon compte » à « Se connecter » changeait d'univers visuel en un clic, et
 * doutait d'être au bon endroit.
 *
 * Elles partagent donc **une seule** coquille : le formulaire d'un côté, le
 * visuel et son argumentaire de l'autre. Deux mises en page jumelles
 * finiraient par diverger au premier ajustement (règle 5) — ici, corriger
 * l'une corrige l'autre.
 *
 * ## Au langage du site (19/11/2026)
 *
 * La coquille portait l'ancienne charte des pages publiques (`.pp`, verre
 * dépoli) : celui qui cliquait « Espace client » depuis l'accueil refondu
 * changeait de site sous ses yeux. Elle est maintenant une page du socle
 * (`.acc`, `Site.css`) : papier crème, carte à double bord, bouton-pilule,
 * étiquette à pastille, mot d'accent en Fraunces dans le titre.
 *
 * Son en-tête est celui d'un TUNNEL, pas celui du site : le logo, qui ramène
 * à l'accueil, et « Retour au site ». Ni méga-menu, ni menu plein écran, ni
 * pied — rien qui éloigne du formulaire. Il est écrit ici, avec les classes de
 * la barre du socle (`.acc-barre`, `.acc-logo`), et non dans `EnTeteSite` :
 * cette barre-là n'a ni rubrique ni état.
 *
 * Aucune logique n'a changé : la coquille ne fait qu'habiller ce que chaque
 * page lui passe.
 */
import { useEffect } from "react";

import { ACCUEIL, BARRE, EVITEMENT, ID_DU_CONTENU } from "./contenuSite";
import { variables } from "./site";
// Le socle d'abord, la feuille de la coquille ensuite.
import "./Site.css";
import "./Portail.css";

/** Le texte propre à la coquille. Aucun prix, aucune promesse : des repères. */
const TEXTES = {
  retour: "Retour au site",
  etiquette: "Espace client",
  nomDesOnglets: "Accès à votre espace",
  inscription: "Créer un compte",
  connexion: "Se connecter",
};

/** Le titre, avec son mot d'accent en Fraunces italique (`.acc-s`), comme les
 *  titres du site. `accent` est un morceau du titre lui-même : s'il n'y est
 *  pas (titre reformulé sans lui), le titre s'affiche entier, sans accent —
 *  jamais un mot en double ni un mot perdu. */
function Titre({ titre, accent }: { titre: string; accent?: string }) {
  const debut = accent ? titre.lastIndexOf(accent) : -1;
  if (!accent || debut === -1) return <>{titre}</>;
  return (
    <>
      {titre.slice(0, debut)}
      <span className="acc-s">{accent}</span>
      {titre.slice(debut + accent.length)}
    </>
  );
}

export function Portail({
  titre,
  accent,
  sousTitre,
  onglet,
  enfants,
  panneau,
}: {
  titre: string;
  /** Le morceau du titre mis en accent. Facultatif. */
  accent?: string;
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
    <div className="acc prt">
      <a className="acc-saut" href={`#${ID_DU_CONTENU}`}>
        {EVITEMENT}
      </a>

      {/* ── L'en-tête du tunnel ───────────────────────────────────────── */}
      <header className="acc-entete prt-entete">
        <div className="acc-w acc-barre">
          <a className="acc-logo" href={ACCUEIL} aria-label={BARRE.nomDuLogo}>
            {BARRE.logo}
            <span className="acc-logo-etoile" aria-hidden="true" />
          </a>
          <a className="prt-retour" href={ACCUEIL}>
            <span aria-hidden="true">←{"\u00a0"}</span>
            {TEXTES.retour}
          </a>
        </div>
      </header>

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus. */}
      <main id={ID_DU_CONTENU} className="acc-w prt-grille" tabIndex={-1}>
        {/* ── Le formulaire ─────────────────────────────────────────── */}
        {/* Premier dans le HTML, affiché à droite : voir `Portail.css`. Le
            côté est une décision de mise en page, l'ordre du HTML une
            décision d'accessibilité — les mélanger obligerait à choisir. */}
        <section className="prt-formulaire acc-entre">
          <span className="acc-tag">{TEXTES.etiquette}</span>

          <nav className="prt-onglets" aria-label={TEXTES.nomDesOnglets}>
            <a
              href="/inscription"
              className={onglet === "inscription" ? "prt-actif" : ""}
              aria-current={onglet === "inscription" ? "page" : undefined}
            >
              {TEXTES.inscription}
            </a>
            <a
              href="/espace/connexion"
              className={onglet === "connexion" ? "prt-actif" : ""}
              aria-current={onglet === "connexion" ? "page" : undefined}
            >
              {TEXTES.connexion}
            </a>
          </nav>

          <h1>
            <Titre titre={titre} accent={accent} />
          </h1>
          {sousTitre}

          {enfants}
        </section>

        {/* ── Le visuel et son argumentaire ─────────────────────────── */}
        <aside
          className="prt-visuel acc-entre"
          aria-hidden="true"
          style={variables({ "--i": 1 })}
        >
          <img
            className="prt-photo"
            src={panneau.image}
            alt={panneau.alt}
            width="1500"
            height="1001"
            loading="lazy"
          />
          <div className="prt-voile" />
          <div className="prt-panneau">
            <h2>{panneau.titre}</h2>
            <ul>
              {panneau.arguments.map((argument) => (
                <li key={argument}>
                  <span className="prt-coche">✓</span>
                  <span>{argument}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </main>
    </div>
  );
}

/** La flèche d'un bouton d'envoi : celle des boutons-pilules du socle, dans
 *  son disque. Décorative — le libellé dit déjà ce que fait le bouton. */
export function FlecheDEnvoi() {
  return (
    <span className="acc-btn-fleche" aria-hidden="true">
      →
    </span>
  );
}
