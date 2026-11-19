/** Ce que l'application affiche ENTRE deux pages : l'attente, et l'échec.
 *
 * Depuis que les écrans se chargent à la demande (`chargement.ts`), il existe
 * un moment où la route est connue et son écran pas encore là — et un cas où
 * il ne viendra pas. Le routeur avait pour le premier un écran blanc, et pour
 * le second son propre message, en anglais (« Something went wrong! »). Les
 * deux sont branchés une fois, pour toutes les routes (`router.tsx`,
 * `defaultPendingComponent` et `defaultErrorComponent`).
 *
 * ## L'attente : une page vide, dans la charte
 *
 * Le papier crème du site, et rien d'autre : ni tourniquet, ni squelette — le
 * routeur ne la montre qu'après une seconde d'attente, et un morceau arrive en
 * général bien avant. Elle n'est pas muette pour autant : un lecteur d'écran
 * entend « Chargement de la page… ».
 *
 * ## L'échec : dire ce qui se passe, et offrir la sortie
 *
 * Deux causes à un morceau qui ne vient pas : le réseau est coupé, ou le site
 * a été mis à jour pendant la visite — les fichiers de l'ancienne version ne
 * sont plus sur le serveur. Dans les deux cas le remède est le même, et c'est
 * le visiteur qui l'actionne : « Recharger la page ».
 *
 * Cet écran reçoit aussi toute erreur survenue à l'affichage d'une page. Il
 * ne prétend pas alors que le réseau est en cause : il dit qu'un incident est
 * survenu, et donne l'adresse où écrire.
 *
 * Il se tient sous `.acc`, avec les pièces du socle (`Site.css`) : la page
 * d'accueil les a déjà chargées, cet écran n'a donc besoin d'aucun morceau
 * de plus pour s'afficher — ce qui tombe bien, puisqu'il s'affiche quand un
 * morceau manque.
 */
import type { ErrorComponentProps } from "@tanstack/react-router";

import { EchecDeChargement } from "./chargement";
import { CONTACT_EMAIL } from "./public/contenu";
import { ACCUEIL } from "./public/contenuSite";
// Le socle d'abord, la feuille de ces deux écrans ensuite.
import "./public/Site.css";
import "./EtatsDuRouteur.css";

const TEXTES = {
  attente: "Chargement de la page…",
  etiquette: "Page indisponible",
  morceau: {
    avant: "Cette page n'a pas pu être",
    fin: "chargée.",
    corps:
      "Votre connexion a peut-être été coupée, ou le site vient d'être mis à jour. Rechargez la page pour repartir sur la bonne version.",
  },
  incident: {
    avant: "Un incident est",
    fin: "survenu.",
    corps:
      "Cette page a rencontré un problème à l'affichage. Rechargez-la ; si cela persiste, écrivez-nous à",
  },
  recharger: "Recharger la page",
  accueil: "Revenir à l'accueil",
};

/** L'écran d'attente : le fond du site, et une phrase pour qui ne voit pas
 *  l'écran. `.visuellement-cache` vient de `index.css`. */
export function PageEnAttente() {
  return (
    <div className="etat-attente" role="status">
      <span className="visuellement-cache">{TEXTES.attente}</span>
    </div>
  );
}

/** L'écran d'échec. `error` est ce que le routeur a attrapé : un morceau qui
 *  n'est pas venu (`EchecDeChargement`), ou toute autre erreur d'affichage. */
export function PageEnEchec({ error }: ErrorComponentProps) {
  const morceau = error instanceof EchecDeChargement;
  const texte = morceau ? TEXTES.morceau : TEXTES.incident;

  return (
    <div className="acc etat-echec">
      <main className="acc-w etat-echec-corps">
        <div className="etat-echec-carte">
          <span className="acc-tag">{TEXTES.etiquette}</span>
          <h1>
            {texte.avant} <span className="acc-s">{texte.fin}</span>
          </h1>
          <p role="alert">
            {texte.corps}
            {!morceau && (
              <>
                {" "}
                <a className="etat-echec-lien" href={`mailto:${CONTACT_EMAIL}`}>
                  {CONTACT_EMAIL}
                </a>
                .
              </>
            )}
          </p>
          <div className="etat-echec-actions">
            {/* Un rechargement COMPLET, pas une navigation du routeur : c'est
                lui qui va rechercher le gabarit HTML et, avec lui, les noms
                des morceaux de la version en ligne. */}
            <button
              type="button"
              className="acc-btn acc-btn-noir"
              onClick={() => window.location.reload()}
            >
              {TEXTES.recharger}
              <span className="acc-btn-fleche" aria-hidden="true">
                →
              </span>
            </button>
            {/* Un lien ordinaire, pour la même raison : il recharge tout. */}
            <a className="etat-echec-lien" href={ACCUEIL}>
              {TEXTES.accueil}
            </a>
          </div>
        </div>
      </main>
    </div>
  );
}
