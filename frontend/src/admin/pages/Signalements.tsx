/** Les signalements clients, et l'assistance qui va avec (§10.4).
 *
 * ## Ce que cet écran fait, et que l'e-mail ne faisait pas
 *
 * Un problème arrivait dans une boîte, sans numéro, sans statut, sans lien
 * avec le dossier. Ici il porte les trois, et l'écran ajoute le geste qui
 * manquait : ouvrir l'espace du client pour voir ce qu'il voit.
 *
 * ## L'assistance, et sa limite
 *
 * « Ouvrir l'espace » demande au serveur une **vraie session** sur le compte du
 * client, puis pose son jeton dans ce navigateur et va sur `/espace`. Une vue
 * en lecture seule aurait été plus confortable à décrire et n'aurait rien
 * permis de réparer.
 *
 * Ce qui la borne n'est pas dans ce fichier — et c'est le point. Le serveur
 * marque le jeton `assistance` et **refuse** deux familles de routes : celles
 * qui parlent d'argent au prestataire de paiement, et celles qui donnent ou
 * retirent un accès. Si le garde-fou vivait ici, il suffirait d'appeler la
 * route à la main pour souscrire avec la carte d'une cliente.
 *
 * Le compte exact n'est pas recopié ici : il vit dans le décorateur
 * `espace()`, et un test structurel le tient à jour. Une prose qui annonce
 * « les cinq routes » devient fausse le jour où il y en a six — c'est
 * précisément ce qu'un audit a trouvé le 04/09/2026.
 *
 * ## Un avertissement, quand même
 *
 * Poser le jeton d'assistance REMPLACE la session cliente éventuellement
 * ouverte dans ce navigateur. C'est dit avant, pas découvert après : quelqu'un
 * qui utilise aussi son propre espace depuis ce poste en serait déconnecté sans
 * comprendre pourquoi.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi, type SignalementAdmin, type StatutSignalement } from "../api";
import * as f from "../../espace/format";
import { jeton as jetonEspace } from "../../espace/api";
import {
  Bandeau,
  Carte,
  Pastille,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";

/** Le statut suivant, dans le sens où le travail avance.
 *
 *  Un menu déroulant obligerait à choisir à chaque fois ce que l'on fait neuf
 *  fois sur dix. Le bouton porte donc le geste suivant, et le déroulant reste
 *  pour les cas qui reviennent en arrière.
 */
const SUIVANT: Record<StatutSignalement, StatutSignalement | null> = {
  nouveau: "en_cours",
  en_cours: "traite",
  traite: null,
};

const LIBELLE_SUIVANT: Record<string, string> = {
  en_cours: "Prendre en charge",
  traite: "Marquer traité",
};

export function SignalementsAdmin() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [filtre, setFiltre] = useState<StatutSignalement | "">("");
  const [reponses, setReponses] = useState<Record<string, string>>({});

  const { data, isPending } = useQuery({
    queryKey: ["admin", "signalements"],
    queryFn: adminApi.signalements,
  });

  const { data: ouvertes } = useQuery({
    queryKey: ["admin", "assistances"],
    queryFn: adminApi.assistances,
  });

  const traiter = useMutation({
    mutationFn: ({
      id,
      corps,
    }: {
      id: string;
      corps: { statut?: StatutSignalement; reponse?: string };
    }) => adminApi.traiterSignalement(id, corps),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["admin", "signalements"] });
    },
    onError: () => setErreur("Le signalement n'a pas pu être mis à jour."),
  });

  const fermer = useMutation({
    mutationFn: (jetonId: string) => adminApi.fermerAssistance(jetonId),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["admin", "assistances"] });
    },
    onError: () => setErreur("Cette session d'assistance n'a pas pu être fermée."),
  });

  const assistance = useMutation({
    mutationFn: (organisationId: string) =>
      adminApi.ouvrirAssistance(organisationId),
    onSuccess: (retour) => {
      // Le jeton part dans le stockage de l'espace client, puis on y va. Une
      // navigation par `window.location` et non par le routeur : le jeton doit
      // être lu au chargement par la garde de `/espace`, et un changement de
      // route interne ne la rejoue pas.
      jetonEspace.ecrire(retour.jeton);
      window.location.href = "/espace";
    },
    onError: () =>
      setErreur(
        "Impossible d'ouvrir l'espace de ce client. A-t-il un compte de connexion actif ?",
      ),
  });

  function ouvrirLEspace(signalement: SignalementAdmin) {
    const confirme = window.confirm(
      `Ouvrir l'espace de ${signalement.organisation} ?\n\n` +
        "Vous arriverez dans son espace comme si vous étiez lui. Aucune " +
        "dépense n'y sera possible : le serveur refuse tout paiement depuis " +
        "une session d'assistance.\n\n" +
        "Votre propre session cliente sur ce navigateur, si vous en avez une, " +
        "sera remplacée.",
    );
    if (confirme) assistance.mutate(signalement.organisation_id);
  }

  const liste = (data?.signalements ?? []).filter(
    (signalement) => !filtre || signalement.statut === filtre,
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--e-5)" }}>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}

      {(ouvertes?.assistances.length ?? 0) > 0 && (
        <Carte
          titre="Sessions d'assistance ouvertes"
          note="Elles n'expirent pas d'elles-mêmes. Fermez celles dont vous n'avez plus besoin."
        >
          <ul className="signalements">
            {(ouvertes?.assistances ?? []).map((session) => (
              <li key={session.id} className="signalement">
                <div className="signalement-tete">
                  <span className="signalement-sujet">{session.compte}</span>
                  <span className="signalement-date">
                    ouverte le {f.dateHeure(session.ouvert_le)}
                    {session.derniere_utilisation
                      ? ` · vue ${f.dateHeure(session.derniere_utilisation)}`
                      : " · jamais utilisée"}
                  </span>
                  <button
                    type="button"
                    className="bouton bouton-discret bouton-sm"
                    onClick={() => fermer.mutate(session.id)}
                    disabled={fermer.isPending}
                  >
                    Fermer
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Carte>
      )}

      <Carte
        titre="Signalements"
        note={
          data
            ? `${data.a_traiter} à traiter sur ${data.signalements.length}.`
            : undefined
        }
        action={
          <label className="champ" style={{ minWidth: 200 }}>
            <span className="visuellement-cache">Filtrer par statut</span>
            <select
              className="champ-saisie"
              value={filtre}
              onChange={(evenement) =>
                setFiltre(evenement.target.value as StatutSignalement | "")
              }
            >
              <option value="">Tous les statuts</option>
              {(data?.statuts ?? []).map((statut) => (
                <option key={statut.code} value={statut.code}>
                  {statut.libelle}
                </option>
              ))}
            </select>
          </label>
        }
      >
        {isPending && <Squelette lignes={4} />}
        {!isPending && liste.length === 0 && (
          <Vide
            titre="Aucun signalement"
            texte="Rien n'est remonté des espaces clients pour ce filtre."
          />
        )}
        {!isPending && liste.length > 0 && (
          <ul className="signalements">
            {liste.map((signalement) => {
              const suivant = SUIVANT[signalement.statut];
              return (
                <li key={signalement.id} className="signalement">
                  <div className="signalement-tete">
                    <span className="signalement-sujet">
                      {signalement.organisation}
                    </span>
                    <Pastille
                      statut={signalement.statut}
                      texte={signalement.statut_libelle}
                    />
                    <span className="signalement-date">
                      {signalement.sujet_libelle} · {signalement.auteur} ·{" "}
                      {f.dateHeure(signalement.cree_le)}
                    </span>
                  </div>

                  <p className="signalement-message">{signalement.message}</p>

                  {signalement.livrable_id && (
                    <p className="signalement-date" style={{ marginTop: "var(--e-2)" }}>
                      Dossier concerné : <code>{signalement.livrable_id}</code>
                    </p>
                  )}

                  <div
                    style={{
                      display: "flex",
                      gap: "var(--e-2)",
                      flexWrap: "wrap",
                      marginTop: "var(--e-3)",
                    }}
                  >
                    {suivant && (
                      <button
                        type="button"
                        className="bouton bouton-sm"
                        disabled={traiter.isPending}
                        onClick={() =>
                          traiter.mutate({
                            id: signalement.id,
                            corps: {
                              statut: suivant,
                              // La réponse tapée part avec le changement de
                              // statut : deux clics pour un geste unique se
                              // solderaient par un « traité » sans réponse.
                              ...(reponses[signalement.id]
                                ? { reponse: reponses[signalement.id] }
                                : {}),
                            },
                          })
                        }
                      >
                        {LIBELLE_SUIVANT[suivant]}
                      </button>
                    )}
                    <button
                      type="button"
                      className="bouton bouton-contour bouton-sm"
                      onClick={() => ouvrirLEspace(signalement)}
                      disabled={assistance.isPending}
                    >
                      Ouvrir l'espace de ce client
                    </button>
                    {signalement.statut === "traite" && (
                      <button
                        type="button"
                        className="bouton bouton-discret bouton-sm"
                        disabled={traiter.isPending}
                        onClick={() =>
                          traiter.mutate({
                            id: signalement.id,
                            corps: { statut: "en_cours" },
                          })
                        }
                      >
                        Rouvrir
                      </button>
                    )}
                  </div>

                  <label className="champ" style={{ marginTop: "var(--e-3)" }}>
                    <span className="champ-libelle">
                      Réponse au client (visible dans son espace)
                    </span>
                    <textarea
                      className="champ-saisie"
                      rows={2}
                      value={reponses[signalement.id] ?? signalement.reponse}
                      placeholder="Ce que vous avez fait, en une ou deux phrases."
                      onChange={(evenement) =>
                        setReponses((etat) => ({
                          ...etat,
                          [signalement.id]: evenement.target.value,
                        }))
                      }
                      onBlur={(evenement) => {
                        const texte = evenement.target.value;
                        if (texte !== signalement.reponse) {
                          traiter.mutate({
                            id: signalement.id,
                            corps: { reponse: texte },
                          });
                        }
                      }}
                    />
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </Carte>
    </div>
  );
}
