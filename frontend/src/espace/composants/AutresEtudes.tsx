/** Les autres études à acheter, pour un client qui paie à l'unité.
 *
 * Un acheteur à l'unité n'a ni formule ni crédits à racheter : les deux blocs
 * qui servent aux abonnés lui sont fermés, côté serveur comme à l'affichage.
 * Sans ce composant, son espace ne lui proposait donc **rien** — alors que le
 * parcours le plus fréquent est justement d'en reprendre une : l'étude de
 * marché d'abord, le business plan au moment d'aller voir la banque.
 *
 * ## Ce qui est masqué, et ce qui ne l'est pas
 *
 * L'étude qu'il vient d'acheter reste dans la liste. Cela peut surprendre —
 * mais rien n'interdit d'en commander deux, sur deux projets différents, et
 * la retirer obligerait à deviner laquelle « il a déjà », ce qu'un crédit
 * dépensé ne dit pas. On propose tout, il choisit.
 *
 * ## Le prix vient du serveur
 *
 * Comme partout : la table `Offer` décide, l'espace et la page publique
 * l'affichent. Recopier « 149 € » ici ferait une troisième source pour un
 * même tarif.
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { espaceApi } from "../api";
import * as f from "../format";
import { Bandeau, Carte } from "./Interface";

export function AutresEtudes() {
  const { data, isPending } = useQuery({
    queryKey: ["espace", "etudes-a-l-unite"],
    queryFn: espaceApi.etudesALUnite,
  });
  // Le slug en cours d'ouverture, pour ne désactiver QUE son bouton : tout
  // désactiver ferait croire à une panne générale le temps de l'aller-retour.
  const [ouverture, setOuverture] = useState("");
  const [erreur, setErreur] = useState("");

  // `useMutation` et non un simple `async` dans le composant : c'est la forme
  // retenue partout dans l'espace pour un départ vers Stripe (voir l'achat de
  // crédits), et la redirection appartient à `onSuccess`, hors du rendu.
  const achat = useMutation({
    mutationFn: (slug: string) => espaceApi.acheterUneEtude(slug),
    onSuccess: (reponse) => {
      // Remplacement et non nouvel onglet : le paiement EST la suite du
      // parcours. Un onglet de plus laisse derrière soi une page morte à
      // laquelle la personne revient, et où elle recliquera.
      window.location.href = reponse.adresse;
    },
    onError: (cause: unknown) => {
      setOuverture("");
      setErreur(
        cause instanceof Error
          ? cause.message
          : "Le paiement n'a pas pu être ouvert. Réessayez dans un instant.",
      );
    },
  });

  const etudes = data?.etudes ?? [];
  if (isPending || etudes.length === 0) return null;

  function acheter(slug: string) {
    setOuverture(slug);
    setErreur("");
    achat.mutate(slug);
  }

  return (
    <Carte
      titre="Commander une autre étude"
      note="Paiement unique, sans abonnement. Le crédit arrive dans votre espace aussitôt."
    >
      {erreur && (
        <Bandeau ton="echec" titre="Paiement impossible">
          {erreur}
        </Bandeau>
      )}

      <ul className="autres-etudes">
        {etudes.map((etude) => (
          <li key={etude.slug}>
            <div>
              <p className="autres-etudes-nom">{etude.libelle}</p>
              <p className="carte-note">
                {f.montant(etude.prix_cents)} TTC · paiement unique
              </p>
            </div>
            <button
              type="button"
              className="bouton bouton-contour bouton-sm"
              onClick={() => acheter(etude.slug)}
              disabled={ouverture === etude.slug}
            >
              {ouverture === etude.slug ? "Ouverture…" : "Commander"}
            </button>
          </li>
        ))}
      </ul>
    </Carte>
  );
}
