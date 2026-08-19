/** Page publique des études vendues à l'unité — reprise de
 *  `evkha.fr/etudedemarche`.
 *
 * Jumelle de `Partenaires` : même menu, même charte, même partage des rôles.
 * L'une s'adresse aux professionnels qui s'abonnent, l'autre aux porteurs de
 * projet qui achètent une étude. Elles se répondent — chacune renvoie vers
 * l'autre en bas de page, parce qu'un visiteur arrive rarement sur la bonne du
 * premier coup.
 *
 * ## Deux principes de construction, repris à l'identique
 *
 * 1. **Le prix vient du serveur.** Il est lu dans `/api/public/livrables/`,
 *    qui le tient de la table `Offer`. Écrire « 149 € » dans ce fichier en
 *    ferait une seconde source, qui contredirait le paiement au premier
 *    changement de tarif (règle 5). Le texte éditorial, lui, vit dans
 *    `contenu.ts` — y compris le nombre de chapitres ANNONCÉ, qui n'est pas
 *    celui du plan de production et n'a pas à l'être : voir `ArgumentaireEtude`.
 *
 * 2. **Aucun tarif n'est affiché tant qu'il n'est pas chargé.** Un prix de
 *    repli en attendant l'API afficherait un prix faux à qui a une connexion
 *    lente. Sur une page de vente, c'est inacceptable.
 *
 * ## Où mènent les boutons
 *
 * Vers la création de compte, pas vers la connexion : le visiteur qui clique
 * n'a par définition pas encore de compte, et lui présenter un écran de
 * connexion est le meilleur moyen de le perdre. L'étude choisie voyage dans
 * l'adresse (`/inscription?livrable=etude-marche`), exactement comme la
 * formule sur la page partenaires. C'est l'inscription qui enchaîne ensuite
 * sur le paiement.
 */
import { useEffect, useState } from "react";

import { CONTACT_EMAIL, ETUDES, ETUDES_PAGE } from "./contenu";
import { chargerLivrables, euros, type LivrablePublic } from "./donnees";
import { MenuSite } from "./MenuSite";
import "./Partenaires.css";
import "./NosEtudes.css";

/** Destination du bouton « Commander ».
 *
 * Le slug voyage dans l'adresse. La page d'inscription le lit, rappelle ce
 * qu'on achète avec son prix, puis ouvre le paiement une fois le compte créé.
 */
function lienCommande(slug: string): string {
  return `/inscription?livrable=${encodeURIComponent(slug)}`;
}

/** Puce à coche dorée, comme sur la page partenaires. La coche est décorative :
 *  elle double une information déjà portée par le texte, et un lecteur d'écran
 *  qui l'annoncerait dirait « coche » avant chaque ligne sans rien apporter. */
function Puce({ children }: { children: React.ReactNode }) {
  return (
    <li>
      <span className="pp-coche" aria-hidden="true">
        ✓
      </span>
      <span>{children}</span>
    </li>
  );
}

/** L'ordre de la page de vente, et non celui du serveur.
 *
 * L'API trie par prix croissant — un ordre juste pour un catalogue, faux pour
 * une page de vente : il mettait l'étude de concurrence à 89 € en tête, quand
 * `evkha.fr` ouvre sur l'étude de marché. La première carte n'est pas la moins
 * chère, c'est le produit d'appel.
 *
 * L'ordre est celui de `ETUDES`, qui reprend la page de la cliente. Une offre
 * sans argumentaire passe à la fin plutôt que de disparaître : une étude
 * invisible parce qu'un texte manque serait un défaut bien pire qu'un ordre
 * imparfait.
 */
function ordonnees(etudes: LivrablePublic[]): LivrablePublic[] {
  const rang = Object.keys(ETUDES);
  const place = (slug: string) => {
    const index = rang.indexOf(slug);
    return index === -1 ? rang.length : index;
  };
  return [...etudes].sort((a, b) => place(a.slug) - place(b.slug));
}

function Carte({ etude }: { etude: LivrablePublic }) {
  const texte = ETUDES[etude.slug];

  return (
    <article className="ne-carte">
      {texte && <div className="ne-surtitre">{texte.surtitre}</div>}

      <h3>{etude.libelle}</h3>
      <div className="ne-prix">
        {euros(etude.prix_cents)} <span>TTC · paiement unique</span>
      </div>

      <div className="ne-quoi">Ce que vous obtenez :</div>
      <ul className="ne-points">
        <Puce>
          <b>
            {texte
              ? `${texte.chapitres} ${texte.chapeau}`
              : "Un document complet, en Word et en PDF"}
          </b>
        </Puce>
        {(texte?.details ?? []).map((detail) => (
          <li key={detail} className="ne-detail">
            <span className="pp-coche" aria-hidden="true">
              ✓
            </span>
            <span>{detail}</span>
          </li>
        ))}
      </ul>

      {texte && <p className="ne-pied">{texte.pied}</p>}

      {/* Poussé en bas de carte par `margin-top: auto` : quatre cartes de
          hauteurs différentes alignent quand même leurs boutons, et l'œil les
          balaie d'un seul mouvement. */}
      <a className="ne-bouton" href={lienCommande(etude.slug)}>
        {texte?.bouton ?? `Commander ${etude.libelle.toLowerCase()}`}
      </a>
    </article>
  );
}

export function NosEtudes() {
  const [etudes, setEtudes] = useState<LivrablePublic[] | null>(null);
  const [erreur, setErreur] = useState("");

  // Le gabarit HTML annonce « EVKHA — Espace client » : juste pour les deux
  // espaces connectés, faux pour une page publique que l'on partage par lien
  // et que les moteurs indexent.
  useEffect(() => {
    const precedent = document.title;
    document.title = "Nos études et livrables — EVKHA";
    return () => {
      document.title = precedent;
    };
  }, []);

  useEffect(() => {
    let vivant = true;
    chargerLivrables()
      .then((liste) => {
        if (vivant) setEtudes(liste);
      })
      .catch(() => {
        if (vivant) setErreur("Le catalogue est momentanément indisponible.");
      });
    return () => {
      vivant = false;
    };
  }, []);

  return (
    <div className="pp ne">
      <MenuSite />

      <header className="pp-large ne-entete">
        <p className="ne-eyebrow">{ETUDES_PAGE.surtitre}</p>
        <h1>{ETUDES_PAGE.titre}</h1>
        <p className="ne-chapeau">{ETUDES_PAGE.chapeau}</p>
      </header>

      <main className="pp-large">
        {erreur && (
          <p className="ne-erreur" role="alert">
            {erreur} Écrivez-nous à{" "}
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
          </p>
        )}

        {etudes === null && !erreur && (
          <p className="ne-attente">Chargement du catalogue…</p>
        )}

        {etudes !== null && (
          <div className="ne-grille">
            {ordonnees(etudes).map((etude) => (
              <Carte key={etude.slug} etude={etude} />
            ))}
          </div>
        )}

        <section className="ne-etapes" aria-labelledby="ne-etapes-titre">
          <h2 id="ne-etapes-titre">Comment ça se passe</h2>
          <ol>
            {ETUDES_PAGE.etapes.map((etape) => (
              <li key={etape}>{etape}</li>
            ))}
          </ol>
        </section>

        <section className="ne-appel">
          <h2>{ETUDES_PAGE.appel.titre}</h2>
          <p>{ETUDES_PAGE.appel.corps}</p>
          <a href="/partenaires">{ETUDES_PAGE.appel.lien}</a>
        </section>
      </main>
    </div>
  );
}
