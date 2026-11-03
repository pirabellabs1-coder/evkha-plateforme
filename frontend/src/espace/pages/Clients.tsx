/** Les clients de l'abonnée, une fiche chacun (03/11/2026).
 *
 * Une consultante travaille pour plusieurs personnes. Elle remplissait un
 * questionnaire par étude et, pour chaque nouvelle étude d'une même personne,
 * effaçait ou retapait les champs. Elle part désormais de la personne : « Ajouter
 * un client », puis, depuis sa fiche, ses marques ou projets et chaque livrable.
 *
 * La liste dit pour chaque client combien de projets sont ouverts et combien de
 * dossiers ont été produits : les deux nombres viennent du serveur, qui seul
 * voit les dossiers d'un projet archivé.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ErreurApi, espaceApi } from "../api";
import * as f from "../format";
import { peut, useMoi } from "../useMoi";
import {
  Bandeau,
  Carte,
  Champ,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../composants/Interface";

const VIDE = { raison_sociale: "", secteur: "", pays: "", ville: "" };

export function Clients() {
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const naviguer = useNavigate();
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState(VIDE);
  const [erreur, setErreur] = useState("");

  const peutGerer = peut(moi, "gerer_clients_finaux");

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["espace", "clients"],
    queryFn: () => espaceApi.clientsFinaux(),
  });

  const creation = useMutation({
    mutationFn: () =>
      espaceApi.creerClientFinal({
        raison_sociale: saisie.raison_sociale.trim(),
        secteur: saisie.secteur.trim(),
        pays: saisie.pays.trim(),
        ville: saisie.ville.trim(),
      }),
    onSuccess: (client) => {
      setErreur("");
      setSaisie(VIDE);
      void cache.invalidateQueries({ queryKey: ["espace", "clients"] });
      // On arrive sur la fiche : c'est là qu'on ajoute la première marque et
      // qu'on lance la première étude. Rester sur la liste ferait chercher le
      // client qu'on vient de créer.
      void naviguer({
        to: "/espace/clients/$clientId",
        params: { clientId: client.id },
      });
    },
    onError: (cause) =>
      setErreur(cause instanceof ErreurApi ? cause.message : "Création impossible."),
  });

  const clients = data?.clients ?? [];

  const champ = (cle: keyof typeof VIDE) => ({
    name: cle,
    value: saisie[cle],
    onChange: (evenement: React.ChangeEvent<HTMLInputElement>) =>
      setSaisie((avant) => ({ ...avant, [cle]: evenement.target.value })),
  });

  return (
    <>
      {isError && <ErreurDeChargement quoi="vos clients" erreur={error} />}

      <Carte
        titre={`${clients.length} client${clients.length > 1 ? "s" : ""}`}
        note="Chaque fiche garde ses marques ou projets, et chaque étude commandée depuis elle reprend ce que vous avez déjà répondu."
        action={
          peutGerer && !ouvert ? (
            <button
              type="button"
              className="bouton bouton-principal bouton-sm"
              onClick={() => setOuvert(true)}
            >
              Ajouter un client
            </button>
          ) : undefined
        }
      >
        {ouvert && (
          <form
            className="questions"
            style={{ marginBottom: "var(--e-5)" }}
            onSubmit={(evenement) => {
              evenement.preventDefault();
              creation.mutate();
            }}
          >
            {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
            <Champ
              libelle="Nom du client"
              aide="La personne ou l'entreprise pour qui vous produisez les études."
              required
              autoFocus
              {...champ("raison_sociale")}
            />
            <Champ
              libelle="Secteur d'activité"
              aide="Repris dans chaque questionnaire, modifiable étude par étude."
              {...champ("secteur")}
            />
            <Champ libelle="Pays" {...champ("pays")} />
            <Champ libelle="Ville ou zone" {...champ("ville")} />
            <div style={{ display: "flex", gap: "var(--e-4)" }}>
              <button
                type="submit"
                className={
                  creation.isPending
                    ? "bouton bouton-principal bouton-chargement"
                    : "bouton bouton-principal"
                }
                disabled={creation.isPending || !saisie.raison_sociale.trim()}
              >
                {creation.isPending ? "Création…" : "Créer la fiche"}
              </button>
              <button
                type="button"
                className="bouton bouton-contour"
                onClick={() => {
                  setOuvert(false);
                  setErreur("");
                }}
              >
                Annuler
              </button>
            </div>
          </form>
        )}

        {isPending ? (
          <Squelette lignes={4} />
        ) : clients.length === 0 ? (
          !isError && (
            <Vide
              icone="◇"
              titre="Aucun client pour l'instant"
              texte="Ajoutez la personne pour qui vous travaillez : vous lancerez ses études depuis sa fiche, sans retaper son projet à chaque fois."
            />
          )
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Client</th>
                  <th scope="col">Secteur</th>
                  <th scope="col">Lieu</th>
                  <th scope="col">Marques ou projets</th>
                  <th scope="col">Dossiers</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr key={client.id}>
                    <td>
                      <Link
                        to="/espace/clients/$clientId"
                        params={{ clientId: client.id }}
                        style={{ fontWeight: 600, color: "var(--texte-fort)" }}
                      >
                        {client.raison_sociale}
                      </Link>
                    </td>
                    <td>{client.secteur || "—"}</td>
                    <td>
                      {[client.ville, client.pays].filter(Boolean).join(", ") || "—"}
                    </td>
                    <td className="nombre">{f.nombre(client.nb_projets ?? 0)}</td>
                    <td className="nombre">{f.nombre(client.nb_dossiers ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>
    </>
  );
}
