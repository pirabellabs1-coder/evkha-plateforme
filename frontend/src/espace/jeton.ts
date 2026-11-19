/** Le jeton de session de l'espace client, dans le stockage du navigateur.
 *
 * Il vivait dans `api.ts`. Il en est sorti le 19/11/2026, tel quel : la garde
 * d'accès de l'espace (`routes.tsx`) n'a besoin que de lui, et l'importer
 * depuis `api.ts` faisait télécharger tout le client d'API de l'espace au
 * visiteur de la page d'accueil. `api.ts` le réexporte : pour tout le reste
 * de l'application, `jeton` se lit toujours là-bas.
 *
 * Aucune dépendance : ce fichier ne doit rien importer.
 */

const CLE_JETON = "evkha_espace_jeton";

export const jeton = {
  lire: (): string => localStorage.getItem(CLE_JETON) ?? "",
  /** N'écrit qu'un VRAI jeton.
   *
   *  Une valeur vide ou nulle n'est pas une session, et l'écrire en détruit
   *  une. Audit du 19/11/2026 : les retours de paiement rendent désormais
   *  `"jeton": null` quand le compte existait déjà. L'un des deux écrans
   *  écrivait alors la chaîne vide — la personne déjà connectée ne l'était
   *  plus —, l'autre écrivait `null`, que le stockage garde sous la forme
   *  « null » : `present()` répondait vrai sur une session qui n'existait pas.
   *
   *  Le refus vit ICI et non chez chaque appelant : un appelant qui l'oublie
   *  ne doit pas pouvoir fermer la session de quelqu'un (règle 4). */
  ecrire: (valeur: string): void => {
    if (typeof valeur !== "string" || valeur.length === 0) return;
    localStorage.setItem(CLE_JETON, valeur);
  },
  effacer: (): void => localStorage.removeItem(CLE_JETON),
  present: (): boolean => (localStorage.getItem(CLE_JETON) ?? "").length > 0,
};
