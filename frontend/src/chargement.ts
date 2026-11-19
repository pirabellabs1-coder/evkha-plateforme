/** Charger un écran à la demande, et dire clairement quand il ne vient pas.
 *
 * Jusqu'au 19/11/2026, `router.tsx` importait tous les écrans : le visiteur de
 * la page d'accueil téléchargeait l'administration, l'espace client et les
 * vingt-deux pages publiques — un seul fichier de 957 Ko. Chaque écran hors de
 * l'accueil est désormais importé quand sa route est demandée.
 *
 * ## La forme retenue : `lazyRouteComponent`
 *
 * TanStack Router (1.170) offre deux formes : `createRoute(…).lazy(…)`, qui
 * déplace les OPTIONS de la route dans un second fichier, et
 * `lazyRouteComponent(importer, nomDeLExport)`, qui ne diffère que le
 * composant. La seconde est retenue parce qu'elle ne change pas la forme des
 * routes : `component:` reste défini sur chacune, ce que lisent
 * `chaque-lien-du-site-a-sa-route` (« une route qui rend une page a un
 * composant ») et `atterrissage-apres-connexion` (le texte de `router.tsx`).
 *
 * Les gardes d'accès ne bougent pas : `beforeLoad` s'exécute pour toute la
 * chaîne des routes AVANT que le routeur ne demande un seul composant
 * (`loadMatches`, `router-core`). Un visiteur sans session est renvoyé à la
 * connexion sans avoir téléchargé l'espace.
 *
 * ## Un échec n'est pas rechargé d'office
 *
 * Laissé à lui-même, `lazyRouteComponent` recharge la page UNE fois, sans rien
 * dire, quand un import échoue. Réseau coupé, le visiteur tombait alors sur la
 * page d'erreur de son navigateur, en anglais sur bien des postes, sans savoir
 * ce qui s'était passé. L'échec est donc rendu sous un type à nous
 * (`EchecDeChargement`), que le routeur ne reconnaît pas comme « module
 * introuvable » : il le remet à l'écran d'échec (`EtatsDuRouteur.tsx`), qui
 * l'explique en français et propose « Recharger la page ». C'est le visiteur
 * qui décide.
 *
 * Pas de composant dans ce fichier : le rechargement à chaud de Vite garde
 * l'état des pages.
 */
import { lazyRouteComponent } from "@tanstack/react-router";

/** Un morceau de l'application n'a pas pu être téléchargé : réseau coupé, ou
 *  mise en ligne survenue entre-temps — les fichiers de l'ancienne version ne
 *  sont plus sur le serveur. */
export class EchecDeChargement extends Error {
  /** L'erreur d'origine, pour qui lit la console. */
  readonly origine: unknown;

  // Affectations explicites : `erasableSyntaxOnly` interdit les propriétés de
  // paramètre de constructeur, qui ne s'effacent pas à la compilation.
  constructor(origine: unknown) {
    super("Un morceau de l'application n'a pas pu être chargé.");
    this.name = "EchecDeChargement";
    this.origine = origine;
  }
}

/** Un écran chargé à la demande : `importer` désigne son fichier, `nom` son
 *  export. Le résultat se pose tel quel dans `component:` d'une route.
 *
 *  Plusieurs écrans peuvent partager un `importer` (les pages d'un même
 *  fichier, tout un espace) : le navigateur ne télécharge le morceau qu'une
 *  fois. */
export function ecranDiffere<
  T extends Record<string, unknown>,
  K extends keyof T & string,
>(importer: () => Promise<T>, nom: K) {
  return lazyRouteComponent(
    () =>
      importer().catch((cause: unknown) => {
        throw new EchecDeChargement(cause);
      }),
    nom,
  );
}
