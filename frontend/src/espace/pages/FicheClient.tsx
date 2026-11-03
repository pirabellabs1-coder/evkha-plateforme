/** La fiche d'un client : ses marques ou projets, les études à lancer, et tout
 * ce qui a déjà été produit pour lui (03/11/2026).
 *
 * Chaque bouton de livrable ouvre le questionnaire POUR CE PROJET : le serveur
 * le pré-remplit de ce qui a déjà été répondu, et impose le nom du projet —
 * c'est lui qui relie un business plan à l'étude de marché qui l'a précédé.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ErreurApi, espaceApi, type ClientFinal } from "../api";
import * as f from "../format";
import { peut, useMoi } from "../useMoi";
import {
  Bandeau,
  Carte,
  Champ,
  ErreurDeChargement,
  Pastille,
  Squelette,
  Vide,
} from "../composants/Interface";
import { CelluleFichiers } from "../composants/EtatDesFichiers";

type Modifiable = Pick<
  ClientFinal,
  "raison_sociale" | "secteur" | "pays" | "ville" | "contact_email"
>;

export function FicheClient() {
  const { clientId } = useParams({ from: "/espace/clients/$clientId" });
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const [nomProjet, setNomProjet] = useState("");
  const [erreur, setErreur] = useState("");
  const [rattaches, setRattaches] = useState<{ nom: string; nombre: number } | null>(null);
  const [edition, setEdition] = useState<Modifiable | null>(null);

  const peutGerer = peut(moi, "gerer_clients_finaux");
  const peutCommander = peut(moi, "commander");

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["espace", "clients", clientId],
    queryFn: () => espaceApi.ficheClient(clientId),
  });
  const { data: catalogue } = useQuery({
    queryKey: ["espace", "catalogue"],
    queryFn: espaceApi.catalogue,
  });

  const rafraichir = () =>
    void cache.invalidateQueries({ queryKey: ["espace", "clients"] });

  const ajout = useMutation({
    mutationFn: () => espaceApi.creerProjet(clientId, nomProjet.trim()),
    onSuccess: (projet) => {
      setErreur("");
      setNomProjet("");
      setRattaches(
        projet.dossiers_rattaches > 0
          ? { nom: projet.nom, nombre: projet.dossiers_rattaches }
          : null,
      );
      rafraichir();
    },
    onError: (cause) =>
      setErreur(cause instanceof ErreurApi ? cause.message : "Ajout impossible."),
  });

  const modification = useMutation({
    mutationFn: (donnees: Modifiable) => espaceApi.modifierClient(clientId, donnees),
    onSuccess: () => {
      setErreur("");
      setEdition(null);
      rafraichir();
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Enregistrement impossible.",
      ),
  });

  if (isPending) return <Squelette lignes={6} />;
  if (isError || !data) {
    return <ErreurDeChargement quoi="la fiche de ce client" erreur={error} />;
  }

  const { client, projets, dossiers } = data;
  const actifs = projets.filter((p) => !p.archive);
  const documents = catalogue?.documents ?? [];

  return (
    <>
      <p className="carte-note">
        <Link to="/espace/clients" className="bandeau-lien">
          ← Tous les clients
        </Link>
      </p>

      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {rattaches && (
        <Bandeau ton="succes" titre={`« ${rattaches.nom} » ajouté`}>
          {rattaches.nombre === 1
            ? "Une étude déjà produite sous ce nom y a été rattachée."
            : `${rattaches.nombre} études déjà produites sous ce nom y ont été rattachées.`}
        </Bandeau>
      )}

      <Carte
        titre={client.raison_sociale}
        note={
          [client.secteur, [client.ville, client.pays].filter(Boolean).join(", ")]
            .filter(Boolean)
            .join(" · ") || "Aucune information complémentaire."
        }
        action={
          peutGerer && !edition ? (
            <button
              type="button"
              className="bouton bouton-contour bouton-sm"
              onClick={() =>
                setEdition({
                  raison_sociale: client.raison_sociale,
                  secteur: client.secteur,
                  pays: client.pays,
                  ville: client.ville,
                  contact_email: client.contact_email,
                })
              }
            >
              Modifier
            </button>
          ) : undefined
        }
      >
        {edition ? (
          <form
            className="questions"
            onSubmit={(evenement) => {
              evenement.preventDefault();
              modification.mutate(edition);
            }}
          >
            {(
              [
                ["raison_sociale", "Nom du client"],
                ["secteur", "Secteur d'activité"],
                ["pays", "Pays"],
                ["ville", "Ville ou zone"],
                ["contact_email", "Adresse e-mail du contact"],
              ] as const
            ).map(([cle, libelle]) => (
              <Champ
                key={cle}
                libelle={libelle}
                name={cle}
                type={cle === "contact_email" ? "email" : "text"}
                required={cle === "raison_sociale"}
                value={edition[cle]}
                onChange={(evenement) =>
                  setEdition({ ...edition, [cle]: evenement.target.value })
                }
              />
            ))}
            <div style={{ display: "flex", gap: "var(--e-4)" }}>
              <button
                type="submit"
                className="bouton bouton-principal"
                disabled={modification.isPending}
              >
                {modification.isPending ? "Enregistrement…" : "Enregistrer"}
              </button>
              <button
                type="button"
                className="bouton bouton-contour"
                onClick={() => setEdition(null)}
              >
                Annuler
              </button>
            </div>
          </form>
        ) : (
          <div className="grille-chiffres">
            <div>
              <div className="chiffre-libelle">Marques ou projets</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                {f.nombre(actifs.length)}
              </div>
            </div>
            <div>
              <div className="chiffre-libelle">Dossiers produits</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                {f.nombre(dossiers.length)}
              </div>
            </div>
            <div>
              <div className="chiffre-libelle">Contact</div>
              <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
                {client.contact_email || "—"}
              </div>
            </div>
          </div>
        )}
      </Carte>

      <Carte
        titre="Marques ou projets"
        note="Une étude lancée depuis un projet reprend ce que vous avez déjà répondu pour lui. Seules les questions propres à chaque étude restent à remplir."
      >
        {peutGerer && (
          <form
            onSubmit={(evenement) => {
              evenement.preventDefault();
              ajout.mutate();
            }}
            style={{
              display: "flex",
              gap: "var(--e-4)",
              alignItems: "flex-end",
              flexWrap: "wrap",
              marginBottom: "var(--e-5)",
            }}
          >
            <div style={{ flex: "1 1 260px" }}>
              <Champ
                libelle="Ajouter une marque ou un projet"
                aide="Le nom qui figurera sur ses études. Il relie entre elles les études d'un même projet."
                name="nom-projet"
                value={nomProjet}
                onChange={(evenement) => setNomProjet(evenement.target.value)}
              />
            </div>
            <button
              type="submit"
              className="bouton bouton-principal"
              disabled={ajout.isPending || !nomProjet.trim()}
            >
              {ajout.isPending ? "Ajout…" : "Ajouter"}
            </button>
          </form>
        )}

        {actifs.length === 0 ? (
          <Vide
            icone="◇"
            titre="Aucune marque ni projet"
            texte="Ajoutez-en un pour lancer sa première étude."
          />
        ) : (
          <ul className="liste-projets">
            {actifs.map((projet) => (
              <li key={projet.id} className="projet-ligne">
                <div>
                  <strong>{projet.nom}</strong>
                  <div className="carte-note">
                    {projet.nb_dossiers === 0
                      ? "Aucune étude pour l'instant"
                      : `${f.nombre(projet.nb_dossiers)} dossier${projet.nb_dossiers > 1 ? "s" : ""}`}
                  </div>
                </div>
                <div className="projet-actions">
                  {documents.map((doc) => {
                    const ouvert = peutCommander && doc.couvert;
                    return ouvert ? (
                      <Link
                        key={doc.type}
                        to="/espace/commander"
                        search={{ livrable: doc.type, projet: projet.id }}
                        className="bouton bouton-contour bouton-sm"
                      >
                        {doc.libelle}
                      </Link>
                    ) : (
                      // Un bouton fermé dit pourquoi au survol et à la lecture
                      // d'écran : grisé sans un mot, il se lit comme une panne.
                      <button
                        key={doc.type}
                        type="button"
                        className="bouton bouton-contour bouton-sm"
                        disabled
                        title={
                          peutCommander
                            ? "Aucun crédit disponible pour ce document"
                            : "Votre rôle ne permet pas de commander"
                        }
                      >
                        {doc.libelle}
                      </button>
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Carte>

      <Carte
        titre={`${dossiers.length} dossier${dossiers.length > 1 ? "s" : ""} produit${dossiers.length > 1 ? "s" : ""}`}
        note="Tout ce qui a été commandé pour ce client, du plus récent au plus ancien."
      >
        {dossiers.length === 0 ? (
          <Vide
            icone="▤"
            titre="Aucun dossier"
            texte="Les études lancées depuis cette fiche apparaîtront ici."
          />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Marque ou projet</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Créé le</th>
                  <th scope="col">Fichiers</th>
                </tr>
              </thead>
              <tbody>
                {dossiers.map((dossier) => (
                  <tr key={dossier.id}>
                    <td>
                      <Link
                        to="/espace/livrables/$jobId"
                        params={{ jobId: dossier.id }}
                        style={{ fontWeight: 600, color: "var(--texte-fort)" }}
                      >
                        {f.typeLivrable(dossier.type)}
                      </Link>
                    </td>
                    <td>{dossier.projet?.nom ?? "—"}</td>
                    <td>
                      <Pastille statut={dossier.statut} />
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>{f.date(dossier.cree_le)}</td>
                    <td>
                      <CelluleFichiers
                        livrable={dossier}
                        classeBouton="bouton bouton-contour bouton-sm"
                      />
                    </td>
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
