/** Ce que l'écran de suivi a le DROIT d'annoncer sur le délai et sur la forme
 *  du parcours de production.
 *
 * Logique pure, hors de la page : elle se relit et se teste sans monter un
 * arbre React, et c'est elle qui porte la seule règle vraiment dangereuse de
 * cet écran.
 *
 * ## La règle : trois cas, et le troisième est le silence
 *
 * `backend/organisations/suivi.py` l'écrit en toutes lettres — « une estimation
 * fausse est pire que pas d'estimation », et son `fin_estimee` rend `null` dès
 * qu'il refuse d'extrapoler. Une interface qui comblerait ce `null` par une
 * moyenne, une règle de trois ou la fourchette maquillée en compte à rebours
 * annulerait ce refus : le serveur se serait tu pour rien.
 *
 * D'où trois sorties, et pas une de plus :
 *
 * 1. `fin_estimee` renseignée → un délai, avec sa provenance. `etudes_passees`
 *    est annoncé comme tel : c'est une médiane d'autres études, elle ignore la
 *    lenteur du jour, et le taire promettrait une précision qu'elle n'a pas ;
 * 2. sinon `duree_estimee_minutes` → la fourchette large, énoncée COMME une
 *    fourchette observée. Jamais « il reste » : ce n'est pas une mesure de
 *    cette étude-ci ;
 * 3. sinon `null` — l'appelant n'affiche rien du tout.
 *
 * L'écran d'avant écrivait « durée inconnue » dans ce troisième cas, une ligne
 * qui occupait la place sans rien apprendre à personne.
 */
import type { EtapeSuivi, Suivi } from "./api";

/** Un délai prêt à afficher : une phrase, et la réserve qui la nuance. */
export interface DelaiAnnonce {
  /** Phrase principale. Toujours renseignée quand l'objet existe. */
  texte: string;
  /** Ce qu'il faut savoir sur la valeur du chiffre. Vide s'il n'y a rien à
   *  nuancer — jamais une phrase de remplissage. */
  reserve: string;
}

/** Ce que porte le suivi côté délai. Un `Pick` plutôt que `Suivi` entier :
 *  la fonction ne doit rien pouvoir lire d'autre, et le test n'a pas à
 *  fabriquer un livrable complet pour vérifier une phrase. */
type SourceDuDelai = Pick<
  Suivi,
  "en_production" | "fin_estimee" | "duree_estimee_minutes"
>;

/** Au-delà de cette durée, le nombre de minutes cesse de se lire.
 *
 * « Prêt dans environ 312 minutes » demande une division mentale à quelqu'un
 * qui voulait juste savoir s'il a le temps de déjeuner. */
const MINUTES_AVANT_DE_PASSER_AUX_HEURES = 90;

/** Espace insécable : « 12 minutes » et « 2 h 15 » ne doivent jamais se couper
 *  en fin de ligne, le nombre se retrouverait seul au-dessus de son unité. */
const INSECABLE = " ";

function duree(minutes: number): string {
  if (minutes < MINUTES_AVANT_DE_PASSER_AUX_HEURES) {
    return `${minutes}${INSECABLE}minute${minutes > 1 ? "s" : ""}`;
  }
  const heures = Math.floor(minutes / 60);
  const reste = minutes % 60;
  if (reste === 0) return `${heures}${INSECABLE}heure${heures > 1 ? "s" : ""}`;
  return `${heures}${INSECABLE}h${INSECABLE}${String(reste).padStart(2, "0")}`;
}

export function delaiAnnonce(suivi: SourceDuDelai): DelaiAnnonce | null {
  // Hors production, un délai n'a plus d'objet : l'étude est livrée, annulée ou
  // arrêtée. Le serveur rend d'ailleurs déjà les deux champs à `null` dans ces
  // états — cette garde ne fait que refuser de les afficher si un jour il
  // change d'avis sans que cet écran soit relu.
  if (!suivi.en_production) return null;

  if (suivi.fin_estimee) {
    const { minutes_restantes, fondee_sur } = suivi.fin_estimee;
    return {
      texte: `Prêt dans environ ${duree(minutes_restantes)}`,
      reserve:
        fondee_sur === "etudes_passees"
          ? `Estimation fondée sur vos études précédentes du même type, pas ` +
            `encore sur celle-ci${INSECABLE}: elle est moins fiable et peut ` +
            `varier.`
          : `Estimation calculée sur l'avancement réel de cette étude.`,
    };
  }

  if (suivi.duree_estimee_minutes) {
    const [bas, haut] = suivi.duree_estimee_minutes;
    // L'unité ne se factorise que si les deux bornes la partagent : « entre 20
    // et 2 heures » est du charabia, et la fourchette du serveur peut changer.
    const memeUnite = haut < MINUTES_AVANT_DE_PASSER_AUX_HEURES;
    const bornes = memeUnite
      ? `${bas} et ${duree(haut)}`
      : `${duree(bas)} et ${duree(haut)}`;
    return {
      texte: `Habituellement entre ${bornes}`,
      reserve:
        `Fourchette observée sur les études de ce type. Ce n'est pas une ` +
        `estimation pour la vôtre${INSECABLE}: il est trop tôt pour en donner ` +
        `une.`,
    };
  }

  return null;
}

/** État du segment qui SORT d'un jalon, vers le jalon suivant.
 *
 * Il se déduit de l'étape amont et d'elle seule : le trait dit ce qu'il est
 * advenu du travail de cette étape-là. Plein quand elle est finie, en
 * circulation tant qu'elle occupe la production, vide sinon — un segment qui
 * se remplirait après un échec laisserait croire que la suite avance.
 *
 * Aucune donnée n'est extrapolée du `detail` (« 12 chapitres sur 22 »). Le
 * relire pour en tirer un pourcentage reviendrait à mesurer une phrase écrite
 * pour être lue, et à afficher un remplissage faux le jour où elle change.
 */
export type EtatLiaison = "plein" | "flux" | "vide";

export function liaison(etat: EtapeSuivi["etat"]): EtatLiaison {
  if (etat === "fait") return "plein";
  if (etat === "en_cours") return "flux";
  return "vide";
}

/** L'état d'une étape en toutes lettres.
 *
 * Affiché, et non caché derrière un `aria-label` : la couleur et la forme du
 * jalon ne suffisent ni à un daltonien, ni à une impression en noir et blanc,
 * ni à qui a désactivé les animations — pour qui l'anneau qui tourne ne tourne
 * plus.
 */
export const LIBELLE_ETAT: Record<EtapeSuivi["etat"], string> = {
  fait: "Terminé",
  en_cours: "En cours",
  attente: "À venir",
  echec: "Interrompu",
};
