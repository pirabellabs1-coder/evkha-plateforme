/** Ce que l'espace a le droit de dire de l'ARRÊT d'un abonnement.
 *
 * Trois écrans en parlaient, et deux promettaient ce que le serveur refuse :
 *
 * - la page de paiement : « s'arrête depuis votre espace en un clic, sans
 *   préavis ni justification » — écrit juste au-dessus du bouton qui prélève ;
 * - la confirmation d'abonnement : « vous pouvez l'arrêter quand vous voulez
 *   depuis la page Abonnement » ;
 * - chaque carte de formule : « Arrêt possible à tout moment ».
 *
 * Or `arreter_l_abonnement` (`backend/organisations/vues_espace.py`) refuse
 * TOUJOURS : l'arrêt se fait sur demande auprès d'EVKHA, et l'engagement
 * minimum est de `MOIS_ENGAGEMENT` mois — décision de la cliente du
 * 07/08/2026. Seule la page Abonnement le disait. Quelqu'un qui s'abonnait
 * sur la foi des deux autres découvrait la règle en voulant partir.
 *
 * D'où ce module : les mots de l'arrêt vivent ICI, et les trois écrans les
 * lisent. Deux formulations d'une même règle finissent par ne plus dire la
 * même chose (règle 5) — c'est exactement ce qui s'était produit.
 *
 * ## Ce que ce module ne résout pas
 *
 * La durée est RECOPIÉE du serveur : `MOIS_ENGAGEMENT` n'est rendu par aucune
 * route de l'espace, et son commentaire demande précisément de ne pas le
 * recopier. Tant que l'API ne l'expose pas, c'est ici — et nulle part ailleurs
 * dans l'espace — qu'il faudra le changer le jour où l'engagement bouge.
 */

/** L'adresse à laquelle un abonné demande l'arrêt de son abonnement. */
export const CONTACT = "contact@evkha.fr";

/** L'engagement minimum, tel qu'il s'écrit dans une phrase. */
export const ENGAGEMENT_MINIMUM = "trois mois";

/** La règle en une ligne, pour la liste d'une carte de formule.
 *
 *  Dite AVANT le choix, comme l'était la promesse qu'elle remplace : quelqu'un
 *  qui hésite à s'engager a le droit de savoir à quoi, et pour combien de
 *  temps, avant de donner sa carte. */
export const ARRET_EN_UNE_LIGNE = `Engagement minimum de ${ENGAGEMENT_MINIMUM}, puis arrêt sur simple demande`;

/** La règle en une phrase, pour le pied d'une page de paiement. */
export const ARRET_EN_UNE_PHRASE =
  `L'abonnement se reconduit chaque mois, avec un engagement minimum de ` +
  `${ENGAGEMENT_MINIMUM} à compter de la souscription. Il ne s'arrête pas ` +
  `d'un clic : l'arrêt se fait sur demande, par e-mail à ${CONTACT}.`;
