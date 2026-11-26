/** L'audience du site : les adresses récoltées par les ressources gratuites
 * et par l'inscription à la lettre (demande de la cliente du 24/11/2026).
 *
 * Trois gestes, pas plus :
 * - LIRE qui a pris quoi, et qui accepte la lettre ;
 * - EXPORTER en fichier pour un tableur : les SEULS inscrits à la lettre —
 *   le fichier à importer dans l'outil d'envoi —, ou toutes les adresses ;
 * - DÉSINSCRIRE une personne qui le demande. L'historique reste : on ne perd
 *   pas la trace de ce qu'elle a téléchargé ;
 * - EFFACER une personne qui le demande (RGPD) : l'adresse et ses demandes
 *   disparaissent, sans retour.
 *
 * Rien ne s'envoie d'ici. Ces lignes portent des adresses personnelles :
 * aucune n'est gardée par le navigateur (`no-store` côté serveur).
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi, type ContactDeLAudience } from "../api";
import { Icone } from "../icones";
import * as f from "../../espace/format";
import {
  Bandeau,
  Carte,
  Chiffre,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";
import "./Audience.css";

/** Remet un fichier reçu au navigateur, qui l'enregistre. */
function enregistrerLeFichier(blob: Blob, nom: string): void {
  const adresse = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = adresse;
  lien.download = nom;
  lien.hidden = true;
  document.body.append(lien);
  lien.click();
  lien.remove();
  window.setTimeout(() => URL.revokeObjectURL(adresse), 10_000);
}

function message(cause: unknown, repli: string): string {
  return cause instanceof Error && cause.message ? cause.message : repli;
}

export function AudienceAdmin() {
  const cache = useQueryClient();
  const [recherche, setRecherche] = useState("");
  const [erreur, setErreur] = useState("");
  const [annonce, setAnnonce] = useState("");

  const lecture = useQuery({ queryKey: ["admin", "audience"], queryFn: adminApi.audience });

  const exportation = useMutation({
    networkMode: "always",
    mutationFn: (lettre: boolean) => adminApi.exporterLAudience(lettre),
    onSuccess: (fichier) => {
      enregistrerLeFichier(fichier.blob, fichier.nom);
      setErreur("");
      setAnnonce(
        `Le fichier « ${fichier.nom} » est prêt : votre navigateur l'enregistre dans vos téléchargements.`,
      );
    },
    onError: (cause) => {
      setAnnonce("");
      setErreur(message(cause, "Le fichier n'a pas pu être préparé. Réessayez."));
    },
  });

  const desinscription = useMutation({
    mutationFn: (contact: ContactDeLAudience) => adminApi.desinscrireDeLaLettre(contact.id),
    onSuccess: (_, contact) => {
      setErreur("");
      setAnnonce(`${contact.email} ne recevra plus la newsletter.`);
      void cache.invalidateQueries({ queryKey: ["admin", "audience"] });
    },
    onError: (cause) => {
      setAnnonce("");
      setErreur(message(cause, "La désinscription n'a pas abouti. Réessayez."));
    },
  });

  const effacement = useMutation({
    mutationFn: (contact: ContactDeLAudience) => adminApi.effacerUnContact(contact.id),
    onSuccess: (_, contact) => {
      setErreur("");
      setAnnonce(`${contact.email} est effacée, avec son historique.`);
      void cache.invalidateQueries({ queryKey: ["admin", "audience"] });
    },
    onError: (cause) => {
      setAnnonce("");
      setErreur(message(cause, "L'effacement n'a pas abouti. Réessayez."));
    },
  });

  function effacer(contact: ContactDeLAudience) {
    if (
      window.confirm(
        `Effacer définitivement ${contact.email} et tout son historique ? À faire seulement si la personne le demande. Cette action est irréversible.`,
      )
    ) {
      effacement.mutate(contact);
    }
  }

  function desinscrire(contact: ContactDeLAudience) {
    if (window.confirm(`Retirer ${contact.email} de la newsletter ? Son historique reste visible.`)) {
      desinscription.mutate(contact);
    }
  }

  const data = lecture.data;
  const filtre = recherche.trim().toLowerCase();
  const contacts = (data?.contacts ?? []).filter(
    (contact) => filtre === "" || contact.email.includes(filtre),
  );

  return (
    <>
      {lecture.isError && (
        <ErreurDeChargement
          quoi="l'audience"
          erreur={lecture.error}
          perimees={lecture.isRefetchError}
        />
      )}
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {annonce && <Bandeau ton="succes">{annonce}</Bandeau>}

      {data && (
        <div className="grille-chiffres">
          <Chiffre
            libelle="Adresses récoltées"
            valeur={f.nombre(data.total)}
            detail="Ressources gratuites et newsletter"
            accent
          />
          <Chiffre
            libelle="Inscrites à la newsletter"
            valeur={f.nombre(data.inscrits_a_la_lettre)}
            detail="Ont confirmé leur adresse par courriel"
          />
        </div>
      )}

      <Carte
        titre="Les contacts"
        note="Les nouvelles adresses d'abord. Les fichiers s'ouvrent dans Excel ou Google Sheets ; l'envoi se fait depuis l'écran Newsletter."
        action={
          <div className="aud-exports">
            <button
              type="button"
              className="bouton bouton-principal bouton-sm"
              onClick={() => exportation.mutate(true)}
              disabled={exportation.isPending || !data || data.inscrits_a_la_lettre === 0}
            >
              <Icone nom="telecharger" taille={16} />
              Inscrits à la newsletter
            </button>
            <button
              type="button"
              className="bouton bouton-contour bouton-sm"
              onClick={() => exportation.mutate(false)}
              disabled={exportation.isPending || !data || data.total === 0}
            >
              <Icone nom="telecharger" taille={16} />
              Toutes les adresses
            </button>
          </div>
        }
      >
        <label className="champ">
          <span className="champ-libelle">Chercher une adresse</span>
          <input
            className="champ-saisie"
            type="search"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            autoComplete="off"
          />
        </label>

        {lecture.isPending ? (
          <Squelette lignes={4} />
        ) : contacts.length === 0 ? (
          data &&
          !lecture.isError && (
            <Vide
              icone={<Icone nom="audience" />}
              titre={filtre ? "Aucune adresse ne correspond" : "Aucune adresse pour l'instant"}
              texte="Les personnes qui téléchargent une ressource gratuite ou s'abonnent à la newsletter apparaîtront ici."
            />
          )
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Adresse e-mail</th>
                  <th scope="col">Ressources et inscriptions</th>
                  <th scope="col">Newsletter</th>
                  <th scope="col">Dernière demande</th>
                  <th scope="col">
                    <span className="visuellement-cache">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => (
                  <tr key={contact.id}>
                    <td>
                      <strong>{contact.email}</strong>
                    </td>
                    <td>{contact.demandes.join(", ")}</td>
                    <td>
                      {contact.inscrit_a_la_lettre ? (
                        <>
                          Oui
                          <div className="carte-note">depuis le {f.date(contact.lettre_le)}</div>
                        </>
                      ) : contact.desinscrit_le ? (
                        <>
                          Non
                          <div className="carte-note">désinscrite le {f.date(contact.desinscrit_le)}</div>
                        </>
                      ) : (
                        "Non"
                      )}
                    </td>
                    <td className="console-tabulaire">{f.dateHeure(contact.derniere_demande_le)}</td>
                    <td>
                      <div className="aud-actions">
                        {contact.inscrit_a_la_lettre && (
                          <button
                            type="button"
                            className="bouton bouton-contour bouton-sm"
                            onClick={() => desinscrire(contact)}
                            disabled={desinscription.isPending}
                            aria-label={`Désinscrire ${contact.email} de la newsletter`}
                          >
                            Désinscrire
                          </button>
                        )}
                        <button
                          type="button"
                          className="bouton bouton-contour bouton-sm"
                          onClick={() => effacer(contact)}
                          disabled={effacement.isPending}
                          aria-label={`Effacer ${contact.email} et son historique`}
                        >
                          Effacer
                        </button>
                      </div>
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
