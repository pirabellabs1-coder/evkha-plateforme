/** Les chiffres que le serveur tient, posés dans le texte de la cliente.
 *
 * Le texte des formations et des packs CITE des chiffres que le serveur
 * possède : la durée d'une formation, ses heures de coaching, son nombre de
 * modules, son prix. Écrits dans les phrases, ils faisaient une seconde source
 * (règle 5) : la gérante changeait une durée dans l'administration, et la page
 * continuait d'annoncer l'ancienne.
 *
 * Les phrases restent celles de la cliente, mot pour mot ; seul le chiffre y
 * est remplacé par une MARQUE, que la page remplit avec ce que le serveur
 * rend :
 *
 *     "La formation P.O.P[[ en {heures} heures]] est une expérience…"
 *
 * - `{heures}` : une marque. Elle porte le nom d'un chiffre.
 * - `[[ … ]]` : un passage FACULTATIF. Si l'un de ses chiffres est inconnu —
 *   la réponse n'est pas arrivée, l'appel a échoué, la formation n'est pas en
 *   ligne —, le passage entier disparaît, avec ses mots de liaison : il ne
 *   reste ni « en  heures », ni parenthèse vide.
 * - Une marque HORS de tout passage facultatif rend la phrase entière
 *   dépendante de son chiffre : inconnu, la phrase vaut `""` et
 *   `composerTout` la retire de sa liste.
 *
 * Une marque dont le nom n'est pas déclaré LÈVE une erreur : une faute de
 * frappe (`{heure}`) s'afficherait sinon telle quelle, accolades comprises
 * (règle 1).
 *
 * Pas de composant ni de crochet ici : des fonctions pures, que les fichiers
 * de contenu, les pages et leurs tests partagent.
 */

/** Les chiffres connus, par nom de marque. `null` : inconnu — et non zéro. */
export type Chiffres = Record<string, string | number | null>;

const PASSAGE_FACULTATIF = /\[\[([\s\S]*?)\]\]/g;
const MARQUE = /\{(\w+)\}/g;

/** Remplit les marques d'un morceau. `null` si l'un de ses chiffres manque. */
function remplir(morceau: string, chiffres: Chiffres): string | null {
  let complet = true;
  const rempli = morceau.replace(MARQUE, (_trouve: string, nom: string) => {
    if (!Object.prototype.hasOwnProperty.call(chiffres, nom)) {
      throw new Error(
        `chiffres : la marque « {${nom}} » ne correspond à aucun chiffre déclaré`,
      );
    }
    const valeur = chiffres[nom];
    if (valeur === null) {
      complet = false;
      return "";
    }
    return String(valeur);
  });
  return complet ? rempli : null;
}

/** La phrase telle qu'elle s'affiche, avec les chiffres connus.
 *
 *  Une phrase sans marque est rendue telle quelle. Quand le passage facultatif
 *  qui OUVRAIT la phrase disparaît, la majuscule est rétablie (« 18h de
 *  formation digitale » devient « Formation digitale »). */
export function composer(texte: string, chiffres: Chiffres): string {
  if (!texte.includes("{") && !texte.includes("[[")) return texte;

  let teteRetiree = false;
  const sansLesPassages = texte.replace(
    PASSAGE_FACULTATIF,
    (_trouve: string, morceau: string, place: number) => {
      const rempli = remplir(morceau, chiffres);
      if (rempli === null && place === 0) teteRetiree = true;
      return rempli ?? "";
    },
  );
  const rempli = remplir(sansLesPassages, chiffres);
  if (rempli === null) return "";

  const net = rempli.trim();
  return teteRetiree && net !== ""
    ? net.charAt(0).toLocaleUpperCase("fr") + net.slice(1)
    : net;
}

/** Tout un bloc de contenu, composé d'un coup : chaque chaîne passe par
 *  `composer`, les objets et les listes gardent leur forme.
 *
 *  Dans une liste de PHRASES, celle que son chiffre manquant a vidée est
 *  retirée : une pastille « 18h de formation » sans son chiffre n'a plus rien
 *  à dire, et une puce vide serait un trou dans la page. */
export function composerTout<T>(valeur: T, chiffres: Chiffres): T {
  if (typeof valeur === "string") {
    return composer(valeur, chiffres) as T;
  }
  if (Array.isArray(valeur)) {
    const composes: unknown[] = [];
    for (const element of valeur as unknown[]) {
      const compose = composerTout(element, chiffres);
      const videe =
        typeof element === "string" && element !== "" && compose === "";
      if (!videe) composes.push(compose);
    }
    return composes as T;
  }
  if (valeur !== null && typeof valeur === "object") {
    return Object.fromEntries(
      Object.entries(valeur).map(([cle, contenu]) => [
        cle,
        composerTout(contenu as unknown, chiffres),
      ]),
    ) as T;
  }
  return valeur;
}
