/** Les annonces : rédiger un message, le relire, l'envoyer à tous les clients.
 *
 * « Le business plan arrive le mois prochain », « l'étude de concurrence est
 * disponible » : ce sont des nouvelles que la cliente annonce elle-même, quand
 * elle le décide. Elle écrit le texte, ici, et il part par deux chemins à la
 * fois — le courriel et l'espace client.
 *
 * ## Pourquoi la rédaction et l'envoi sont deux gestes
 *
 * Une annonce touche TOUT le monde d'un coup, et ne se rattrape pas : le
 * courriel est parti. Elle se rédige donc en brouillon — invisible pour tous,
 * modifiable autant qu'on veut — et l'envoi est un second geste, confirmé, qui
 * dit combien de personnes le recevront avant de le faire.
 *
 * Une annonce envoyée ne se modifie plus. Il y aurait sinon deux versions du
 * même message, dont une déjà dans des boîtes aux lettres.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi, type Annonce } from "../api";
import { ActionsDePage } from "../ActionsDePage";
import { Icone } from "../icones";
import {
  Bandeau,
  Carte,
  Chiffre,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";
import "./Annonces.css";

function quand(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function Redaction({
  annonce,
  destinations,
  destinataires,
  onFini,
  onAnnuler,
}: {
  annonce?: Annonce;
  destinations: { cible: string; libelle: string }[];
  destinataires: number;
  onFini: () => void;
  onAnnuler: () => void;
}) {
  const [titre, setTitre] = useState(annonce?.titre ?? "");
  const [message, setMessage] = useState(annonce?.message ?? "");
  const [libelle, setLibelle] = useState(annonce?.lien_libelle ?? "");
  const [cible, setCible] = useState(annonce?.lien_cible ?? "");
  const [erreur, setErreur] = useState("");

  const enregistrement = useMutation({
    mutationFn: () => {
      const charge = {
        titre: titre.trim(),
        message: message.trim(),
        lien_libelle: libelle.trim(),
        lien_cible: cible,
      };
      return annonce
        ? adminApi.modifierUneAnnonce(annonce.id, charge)
        : adminApi.redigerUneAnnonce(charge);
    },
    onSuccess: () => {
      setErreur("");
      onFini();
    },
    onError: (cause: unknown) =>
      setErreur(cause instanceof Error ? cause.message : "Enregistrement impossible."),
  });

  return (
    <form
      className="carte console-formulaire"
      aria-labelledby="annonce-redaction-titre"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        if (!titre.trim()) {
          setErreur("Donnez un titre : c'est l'objet du courriel.");
          return;
        }
        if (!message.trim()) {
          setErreur("Écrivez le message à annoncer.");
          return;
        }
        enregistrement.mutate();
      }}
    >
      <header className="carte-entete">
        <h2 className="carte-titre" id="annonce-redaction-titre">
          {annonce ? "Modifier l'annonce" : "Rédiger une annonce"}
        </h2>
        <button
          type="button"
          className="console-bouton-icone"
          onClick={onAnnuler}
          aria-label="Fermer la rédaction"
        >
          <Icone nom="fermer" />
        </button>
      </header>

      {erreur && (
        <p className="bandeau bandeau-echec" role="alert">
          {erreur}
        </p>
      )}

      {/* Chaque champ a son libellé visible, et son aide lui est reliée
          (`aria-describedby`) : elle est lue en arrivant sur le champ. */}
      <label className="champ">
        <span className="champ-libelle">Titre</span>
        <input
          className="champ-saisie"
          value={titre}
          onChange={(e) => setTitre(e.currentTarget.value)}
          placeholder="Le business plan arrive en octobre"
          maxLength={160}
          autoFocus
          aria-describedby="annonce-titre-aide"
        />
        <span className="champ-aide" id="annonce-titre-aide">
          C'est aussi l'objet du courriel. {160 - titre.length} caractères restants.
        </span>
      </label>

      <label className="champ">
        <span className="champ-libelle">Message</span>
        <textarea
          className="champ-saisie champ-zone"
          rows={7}
          value={message}
          onChange={(e) => setMessage(e.currentTarget.value)}
          placeholder={
            "Écrivez votre annonce.\n\nLaissez une ligne vide entre deux paragraphes : ils seront séparés à l'affichage comme dans le courriel."
          }
          aria-describedby="annonce-message-aide"
        />
        <span className="champ-aide" id="annonce-message-aide">
          {message.split(/\n\s*\n/).filter((p) => p.trim()).length} paragraphe(s).
        </span>
      </label>

      <div className="console-champs">
        <label className="champ">
          <span className="champ-libelle">Texte du bouton</span>
          <input
            className="champ-saisie"
            value={libelle}
            onChange={(e) => setLibelle(e.currentTarget.value)}
            placeholder="Voir les livrables"
            maxLength={60}
            aria-describedby="annonce-bouton-aide"
          />
          <span className="champ-aide" id="annonce-bouton-aide">
            Laissez vide pour une annonce sans bouton.
          </span>
        </label>
        <label className="champ">
          <span className="champ-libelle">Le bouton mène à</span>
          <select
            className="champ-saisie"
            value={cible}
            onChange={(e) => setCible(e.currentTarget.value)}
            aria-describedby="annonce-cible-aide"
          >
            <option value="">Aucune destination</option>
            {destinations.map((d) => (
              <option key={d.cible} value={d.cible}>
                {d.libelle}
              </option>
            ))}
          </select>
          <span className="champ-aide" id="annonce-cible-aide">
            Les pages de l'espace client, et elles seules.
          </span>
        </label>
      </div>

      {/* L'aperçu montre ce que le client verra. Sans lui, on écrit à
          l'aveugle un message qui part chez tout le monde. */}
      <div className="ann-apercu">
        <p className="ann-apercu-mention">Aperçu — ce que verront vos clients</p>
        <div className="ann-apercu-fenetre">
          <p className="ann-apercu-titre">{titre || "Titre de l'annonce"}</p>
          {(message || "Votre message apparaîtra ici.")
            .split(/\n\s*\n/)
            .filter((p) => p.trim())
            .map((paragraphe) => (
              <p key={paragraphe.slice(0, 30)} className="ann-apercu-texte">
                {paragraphe}
              </p>
            ))}
          {libelle && cible && <span className="ann-apercu-bouton">{libelle}</span>}
        </div>
      </div>

      <footer className="console-formulaire-pied">
        <p className="carte-note">
          Une fois envoyée, elle partira à <b>{destinataires}</b>{" "}
          {destinataires > 1 ? "personnes" : "personne"}.
        </p>
        <button type="button" className="bouton bouton-discret" onClick={onAnnuler}>
          Annuler
        </button>
        <button
          type="submit"
          className="bouton bouton-principal"
          disabled={enregistrement.isPending}
        >
          {enregistrement.isPending ? "Enregistrement…" : "Enregistrer le brouillon"}
        </button>
      </footer>
    </form>
  );
}

export function Annonces() {
  const cache = useQueryClient();
  const { data, isPending, isError, isRefetchError, error } = useQuery({
    queryKey: ["admin", "annonces"],
    queryFn: adminApi.annonces,
  });
  const [redige, setRedige] = useState<Annonce | null>(null);
  const [ouvre, setOuvre] = useState(false);
  const [confirme, setConfirme] = useState<Annonce | null>(null);
  const [erreur, setErreur] = useState("");
  const [succes, setSucces] = useState("");

  const rafraichir = () => {
    void cache.invalidateQueries({ queryKey: ["admin", "annonces"] });
    setRedige(null);
    setOuvre(false);
  };

  const envoi = useMutation({
    mutationFn: (id: string) => adminApi.envoyerUneAnnonce(id),
    onSuccess: (reponse) => {
      setErreur("");
      setConfirme(null);
      setSucces(
        `Annonce envoyée : ${reponse.courriels_envoyes} courriel(s) partis sur ` +
          `${reponse.destinataires} destinataire(s). Elle s'affichera dans les ` +
          `espaces clients à leur prochaine connexion.`,
      );
      void cache.invalidateQueries({ queryKey: ["admin", "annonces"] });
    },
    onError: (cause: unknown) => {
      setConfirme(null);
      setErreur(cause instanceof Error ? cause.message : "Envoi impossible.");
    },
  });

  const suppression = useMutation({
    mutationFn: (id: string) => adminApi.supprimerUneAnnonce(id),
    onSuccess: rafraichir,
    onError: (cause: unknown) =>
      setErreur(cause instanceof Error ? cause.message : "Suppression impossible."),
  });

  if (isPending) return <Squelette lignes={4} />;
  // Rien reçu : on le dit, et on s'arrête là. L'écran affichait « 0 annonce »,
  // « 0 destinataire », et ouvrait quand même la rédaction — dont la
  // confirmation d'envoi aurait annoncé « à 0 personne » un message qui part
  // chez tous les clients (audit du 19/11/2026).
  if (!data) return <ErreurDeChargement quoi="les annonces" erreur={error} />;

  const annonces = data.annonces ?? [];
  const destinations = data.destinations ?? [];
  const destinataires = data.destinataires ?? 0;
  const brouillons = annonces.filter((a) => !a.envoyee).length;

  return (
    <>
      {isError && (
        <ErreurDeChargement quoi="les annonces" erreur={error} perimees={isRefetchError} />
      )}

      {/* Le geste principal de l'écran vit dans l'en-tête de la page. */}
      {!ouvre && !redige && (
        <ActionsDePage>
          <button
            type="button"
            className="bouton bouton-principal"
            onClick={() => {
              setErreur("");
              setSucces("");
              setOuvre(true);
            }}
          >
            <Icone nom="plus" taille={16} />
            Rédiger une annonce
          </button>
        </ActionsDePage>
      )}

      <div className="grille-chiffres">
        <Chiffre libelle="Annonces" valeur={annonces.length} detail="Brouillons et envoyées" />
        <Chiffre libelle="Brouillons" valeur={brouillons} detail="Invisibles pour vos clients" />
        <Chiffre
          libelle="Destinataires"
          valeur={destinataires}
          detail="Recevront la prochaine annonce"
          accent
        />
      </div>

      {erreur && (
        <p className="bandeau bandeau-echec" role="alert">
          {erreur}
        </p>
      )}
      {succes && <Bandeau ton="succes">{succes}</Bandeau>}

      {(ouvre || redige) && (
        <Redaction
          key={redige?.id ?? "nouvelle"}
          annonce={redige ?? undefined}
          destinations={destinations}
          destinataires={destinataires}
          onFini={rafraichir}
          onAnnuler={() => {
            setRedige(null);
            setOuvre(false);
          }}
        />
      )}

      {/* La confirmation d'envoi n'est pas une politesse : le geste est
          irréversible et touche tout le monde. Elle rappelle le titre exact et
          le nombre de personnes. */}
      {confirme && (
        <div
          className="console-confirmation"
          role="alertdialog"
          aria-label="Confirmer l'envoi"
        >
          <p>
            Envoyer <b>« {confirme.titre} »</b> à <b>{destinataires}</b>{" "}
            {destinataires > 1 ? "personnes" : "personne"} ?
          </p>
          <p className="carte-note">
            Le courriel part immédiatement et l'annonce s'affichera dans les
            espaces clients. C'est irréversible : une annonce envoyée ne se
            modifie plus.
          </p>
          <div className="console-gestes">
            <button
              type="button"
              className="bouton bouton-discret"
              onClick={() => setConfirme(null)}
            >
              Annuler
            </button>
            <button
              type="button"
              className="bouton bouton-principal"
              disabled={envoi.isPending}
              onClick={() => envoi.mutate(confirme.id)}
            >
              {envoi.isPending ? "Envoi en cours…" : "Envoyer maintenant"}
            </button>
          </div>
        </div>
      )}

      {/* Sous une mise à jour ratée, « aucune » ne se redit pas. */}
      {annonces.length === 0 && !ouvre && !isError && (
        <Carte>
          <Vide
            icone={<Icone nom="annonces" />}
            titre="Aucune annonce"
            texte="Rédigez-en une pour prévenir vos clients d'un nouveau livrable, d'une disponibilité ou d'une date."
          />
        </Carte>
      )}

      <ul className="console-liste">
        {annonces.map((a) => (
          <li
            key={a.id}
            className={a.envoyee ? "console-element console-element-fait" : "console-element"}
          >
            <div className="console-element-corps">
              <p className="console-element-titre">
                {a.titre}
                {/* Le brouillon attend un geste : il est en alerte. L'envoyée
                    est faite : en succès. Le mot le dit, la teinte l'appuie. */}
                <span className={a.envoyee ? "pastille pastille-succes" : "pastille pastille-alerte"}>
                  {a.envoyee ? "Envoyée" : "Brouillon"}
                </span>
              </p>
              <p className="ann-carte-message">{a.message}</p>
              <p className="carte-note">
                {a.envoyee
                  ? `Envoyée le ${quand(a.envoyee_le)} · ${a.courriels_envoyes} courriel(s) · lue par ${a.lue_par}`
                  : `Rédigée le ${quand(a.cree_le)}`}
                {a.lien_libelle && a.lien_cible ? ` · bouton « ${a.lien_libelle} »` : ""}
              </p>
            </div>
            <div className="console-gestes">
              {!a.envoyee && (
                <>
                  <button
                    type="button"
                    className="bouton bouton-contour bouton-sm"
                    onClick={() => {
                      setErreur("");
                      setSucces("");
                      setOuvre(false);
                      setRedige(a);
                    }}
                  >
                    Modifier
                  </button>
                  <button
                    type="button"
                    className="bouton bouton-principal bouton-sm"
                    onClick={() => {
                      setErreur("");
                      setSucces("");
                      setConfirme(a);
                    }}
                  >
                    Envoyer
                  </button>
                </>
              )}
              <button
                type="button"
                className="bouton bouton-discret bouton-sm"
                disabled={suppression.isPending}
                onClick={() => {
                  setErreur("");
                  suppression.mutate(a.id);
                }}
              >
                Supprimer
              </button>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
