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
      className="ann-redaction"
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
      <header className="ann-redaction-tete">
        <h3>{annonce ? "Modifier l'annonce" : "Rédiger une annonce"}</h3>
        <button type="button" className="ann-fermer" onClick={onAnnuler} aria-label="Fermer">
          ✕
        </button>
      </header>

      {erreur && (
        <p className="ann-erreur" role="alert">
          {erreur}
        </p>
      )}

      <label className="ann-champ">
        <span>Titre</span>
        <input
          value={titre}
          onChange={(e) => setTitre(e.currentTarget.value)}
          placeholder="Le business plan arrive en octobre"
          maxLength={160}
          autoFocus
        />
        <small>
          C'est aussi l'objet du courriel. {160 - titre.length} caractères restants.
        </small>
      </label>

      <label className="ann-champ">
        <span>Message</span>
        <textarea
          rows={7}
          value={message}
          onChange={(e) => setMessage(e.currentTarget.value)}
          placeholder={
            "Écrivez votre annonce.\n\nLaissez une ligne vide entre deux paragraphes : ils seront séparés à l'affichage comme dans le courriel."
          }
        />
        <small>
          {message.split(/\n\s*\n/).filter((p) => p.trim()).length} paragraphe(s).
        </small>
      </label>

      <div className="ann-duo">
        <label className="ann-champ">
          <span>Texte du bouton</span>
          <input
            value={libelle}
            onChange={(e) => setLibelle(e.currentTarget.value)}
            placeholder="Voir les livrables"
            maxLength={60}
          />
          <small>Laissez vide pour une annonce sans bouton.</small>
        </label>
        <label className="ann-champ">
          <span>Le bouton mène à</span>
          <select value={cible} onChange={(e) => setCible(e.currentTarget.value)}>
            <option value="">Aucune destination</option>
            {destinations.map((d) => (
              <option key={d.cible} value={d.cible}>
                {d.libelle}
              </option>
            ))}
          </select>
          <small>Les pages de l'espace client, et elles seules.</small>
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

      <footer className="ann-redaction-pied">
        <p className="ann-portee">
          Une fois envoyée, elle partira à <b>{destinataires}</b>{" "}
          {destinataires > 1 ? "personnes" : "personne"}.
        </p>
        <div className="ann-boutons">
          <button type="button" className="bouton bouton-discret" onClick={onAnnuler}>
            Annuler
          </button>
          <button type="submit" className="bouton" disabled={enregistrement.isPending}>
            {enregistrement.isPending ? "Enregistrement…" : "Enregistrer le brouillon"}
          </button>
        </div>
      </footer>
    </form>
  );
}

export function Annonces() {
  const cache = useQueryClient();
  const { data, isPending } = useQuery({
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

  if (isPending) return <p>Chargement…</p>;

  const annonces = data?.annonces ?? [];
  const destinations = data?.destinations ?? [];
  const destinataires = data?.destinataires ?? 0;
  const brouillons = annonces.filter((a) => !a.envoyee).length;

  return (
    <section className="ann">
      <header className="ann-entete">
        <dl className="ann-chiffres">
          <div>
            <dt>Annonces</dt>
            <dd>{annonces.length}</dd>
          </div>
          <div>
            <dt>Brouillons</dt>
            <dd>{brouillons}</dd>
          </div>
          <div>
            <dt>Destinataires</dt>
            <dd>{destinataires}</dd>
          </div>
        </dl>
        {!ouvre && !redige && (
          <button
            type="button"
            className="bouton"
            onClick={() => {
              setErreur("");
              setSucces("");
              setOuvre(true);
            }}
          >
            Rédiger une annonce
          </button>
        )}
      </header>

      {erreur && (
        <p className="ann-erreur" role="alert">
          {erreur}
        </p>
      )}
      {succes && (
        <p className="ann-succes" role="status">
          {succes}
        </p>
      )}

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
        <div className="ann-confirmation" role="alertdialog" aria-label="Confirmer l'envoi">
          <p>
            Envoyer <b>« {confirme.titre} »</b> à <b>{destinataires}</b>{" "}
            {destinataires > 1 ? "personnes" : "personne"} ?
          </p>
          <p className="ann-confirmation-note">
            Le courriel part immédiatement et l'annonce s'affichera dans les
            espaces clients. C'est irréversible : une annonce envoyée ne se
            modifie plus.
          </p>
          <div className="ann-boutons">
            <button
              type="button"
              className="bouton bouton-discret"
              onClick={() => setConfirme(null)}
            >
              Annuler
            </button>
            <button
              type="button"
              className="bouton"
              disabled={envoi.isPending}
              onClick={() => envoi.mutate(confirme.id)}
            >
              {envoi.isPending ? "Envoi en cours…" : "Envoyer maintenant"}
            </button>
          </div>
        </div>
      )}

      {annonces.length === 0 && !ouvre && (
        <p className="carte-note">
          Aucune annonce. Rédigez-en une pour prévenir vos clients d'un nouveau
          livrable, d'une disponibilité ou d'une date.
        </p>
      )}

      <ul className="ann-liste">
        {annonces.map((a) => (
          <li key={a.id} className={`ann-carte ${a.envoyee ? "ann-carte-envoyee" : ""}`}>
            <div className="ann-carte-corps">
              <p className="ann-carte-titre">
                {a.titre}
                <span className={`ann-fanion ${a.envoyee ? "ann-fanion-vif" : ""}`}>
                  {a.envoyee ? "envoyée" : "brouillon"}
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
            <div className="ann-carte-boutons">
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
                    className="bouton bouton-sm"
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
    </section>
  );
}
