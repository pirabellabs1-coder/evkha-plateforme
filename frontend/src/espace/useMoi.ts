/** Contexte de la personne connectée : identité, rôle, droits, solde, formule.
 *
 * Dans son propre fichier et non dans `Coquille.tsx` : un module qui exporte à
 * la fois un composant et un crochet casse le rafraîchissement à chaud de Vite.
 *
 * Un seul appel, mis en cache par TanStack Query et partagé par tous les
 * écrans. Chaque page qui redemanderait ces données finirait par en afficher
 * une version différente de sa voisine.
 */
import { useQuery } from "@tanstack/react-query";
import { espaceApi, type Moi } from "./api";

export const CLE_MOI = ["espace", "moi"] as const;

export function useMoi() {
  return useQuery<Moi>({
    queryKey: CLE_MOI,
    queryFn: espaceApi.moi,
    staleTime: 30_000,
  });
}

/** Ce rôle permet-il cette action ?
 *
 * La liste des droits vient du SERVEUR (`moi.utilisateur.droits`). L'interface
 * ne rejoue pas la matrice du §12 : la recopier ici la ferait diverger du
 * serveur au premier ajout d'action, et c'est le serveur qui décide.
 *
 * Masquer un bouton n'est d'ailleurs pas une mesure de sécurité — l'API refuse
 * de toute façon. C'est une commodité : proposer une action interdite pour
 * afficher ensuite une erreur est une mauvaise expérience.
 */
export function peut(moi: Moi | undefined, action: string): boolean {
  return moi?.utilisateur.droits.includes(action) ?? false;
}
