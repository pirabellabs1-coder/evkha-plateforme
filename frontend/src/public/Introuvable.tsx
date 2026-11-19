/** La page « Page introuvable » : ce que le site affiche à une adresse qu'il
 * ne connaît pas.
 *
 * Le routeur n'avait pas de page pour ce cas : une adresse inconnue affichait
 * le « Not Found » nu de TanStack Router — ni barre, ni pied, ni retour. Cette
 * page est branchée en `defaultNotFoundComponent` (`router.tsx`).
 *
 * Elle reprend le gabarit d'« article introuvable » (`Blog.tsx`) : le cadre
 * commun (`CadreDePage` : barre, contenu principal, pied), un titre en deux
 * temps, une phrase, et des portes — l'accueil d'abord, puis les études, la
 * boutique et le contact. Son texte est dans `contenuSite.PAGE_INTROUVABLE` :
 * rien n'est écrit ici (règle 5).
 *
 * Elle demande aux moteurs de ne pas l'indexer (`useSansIndexation`) :
 * l'application répond 200 à toute adresse, et la page d'erreur ne doit pas
 * entrer dans un index à l'adresse fautive. La vraie réponse 404 se pose au
 * serveur.
 *
 * Rien ne boucle et rien ne se charge : ni bouton de pause, ni région
 * d'alerte, ni bloc à révéler.
 */
import { useRef } from "react";

import { PAGE_INTROUVABLE } from "./contenuSite";
import { Bouton } from "./PiecesSite";
import { CadreDePage, TitreDOuverture } from "./Ressources";
import {
  titreDOnglet,
  useAimants,
  useSansIndexation,
  useTitreDePage,
  variables,
} from "./site";
// Le socle d'abord, la feuille du gabarit ensuite.
import "./Site.css";
import "./Ressources.css";

export function Introuvable() {
  const page = useRef<HTMLDivElement>(null);
  const i = PAGE_INTROUVABLE;

  useAimants(page);
  useTitreDePage(titreDOnglet(i.titreOnglet), i.description);
  useSansIndexation();

  return (
    <CadreDePage racine={page} classe="res-introuvable">
      <div className="res-ouverture res-ouverture-centree">
        <div className="acc-w">
          <span className="acc-tag acc-entre">{i.surtitre}</span>
          <TitreDOuverture titre={i.titre} />
          <p className="res-chapeau acc-entre" style={variables({ "--i": 1 })}>
            {i.corps}
          </p>
          {/* L'accueil d'abord, en bouton plein ; les trois portes ensuite, en
              boutons clairs. Un groupe nommé : un lecteur d'écran sait que
              ces liens vont ensemble. */}
          <div
            className="res-appels acc-entre"
            role="group"
            aria-label={i.nomDesPortes}
            style={variables({ "--i": 2 })}
          >
            <Bouton lien={i.accueil.lien} aspect="noir">
              {i.accueil.libelle}
            </Bouton>
            {i.portes.map((porte) => (
              <Bouton key={porte.lien} lien={porte.lien} aspect="clair">
                {porte.libelle}
              </Bouton>
            ))}
          </div>
        </div>
      </div>
    </CadreDePage>
  );
}
