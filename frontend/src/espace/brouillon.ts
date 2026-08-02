/** Brouillon du questionnaire de commande.
 *
 *  Le business plan compte **24 questions sur 11 sections**, majoritairement
 *  des zones de texte long. Les réponses ne vivaient que dans `useState` : ni
 *  sauvegarde, ni avertissement avant de quitter. Fermer l'onglet, recharger,
 *  ou simplement cliquer un lien de la barre latérale démontait le composant et
 *  effaçait tout, sans un mot.
 *
 *  Pire, un chemin de perte à **un seul clic** existait dans la page : le clic
 *  sur une carte de document exécutait `setReponses({})` — y compris en
 *  re-sélectionnant le document déjà choisi. Aller lire la description d'un
 *  autre type puis revenir suffisait à tout perdre.
 *
 *  ## Pourquoi le navigateur et pas le serveur
 *
 *  Un brouillon serveur demanderait une table, une route, une purge, et
 *  poserait la question de ce qu'on fait des saisies abandonnées — pour une
 *  donnée qui n'a de valeur que sur le poste où elle est tapée. Le navigateur
 *  suffit, et l'implémentation qui ne perd rien vaut mieux que celle qui
 *  perdrait moins.
 *
 *  Ce que cela ne couvre PAS, et il faut le savoir : changer d'ordinateur, ou
 *  vider ses données de navigation. Le brouillon est un filet contre
 *  l'accident, pas une sauvegarde.
 */

/** Une clé par type de document : commencer un business plan ne doit pas
 *  écraser l'étude de marché laissée en plan la veille. */
const CLE = (typeDocument: string) => `evkha.brouillon.${typeDocument}`;

/** Au-delà, on considère la saisie abandonnée.
 *
 *  Sept jours : assez pour reprendre après un week-end ou des congés courts,
 *  assez court pour ne pas ressortir un brouillon dont la personne a oublié
 *  jusqu'à l'existence — et qu'elle enverrait sans le relire. */
const DUREE_MS = 7 * 24 * 3600 * 1000;

type Brouillon = { reponses: Record<string, string>; ecrit_le: number };

export function enregistrerBrouillon(
  typeDocument: string,
  reponses: Record<string, string>,
): void {
  try {
    // Un brouillon vide n'en est pas un : le garder ferait « restaurer » du
    // néant par-dessus une saisie en cours après un rechargement.
    if (!Object.values(reponses).some((v) => v.trim())) {
      localStorage.removeItem(CLE(typeDocument));
      return;
    }
    const charge: Brouillon = { reponses, ecrit_le: Date.now() };
    localStorage.setItem(CLE(typeDocument), JSON.stringify(charge));
  } catch {
    // Stockage plein, mode privé, quota : perdre le brouillon est regrettable,
    // faire échouer la saisie en cours serait pire.
  }
}

export function lireBrouillon(typeDocument: string): Record<string, string> {
  try {
    const brut = localStorage.getItem(CLE(typeDocument));
    if (!brut) return {};
    const charge = JSON.parse(brut) as Brouillon;
    if (!charge?.reponses || Date.now() - charge.ecrit_le > DUREE_MS) {
      localStorage.removeItem(CLE(typeDocument));
      return {};
    }
    return charge.reponses;
  } catch {
    // JSON abîmé par une version précédente : on repart à vide plutôt que de
    // faire planter la page de commande.
    return {};
  }
}

export function oublierBrouillon(typeDocument: string): void {
  try {
    localStorage.removeItem(CLE(typeDocument));
  } catch {
    /* voir `enregistrerBrouillon` */
  }
}

/** Date du brouillon, pour le dire à la personne au lieu de le restaurer en
 *  douce. Restaurer sans prévenir ferait envoyer une saisie qu'elle croit
 *  neuve. */
export function dateDuBrouillon(typeDocument: string): Date | null {
  try {
    const brut = localStorage.getItem(CLE(typeDocument));
    if (!brut) return null;
    const charge = JSON.parse(brut) as Brouillon;
    return charge?.ecrit_le ? new Date(charge.ecrit_le) : null;
  } catch {
    return null;
  }
}
