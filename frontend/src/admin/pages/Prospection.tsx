/** Espace admin — prospection (le front des phases 1 à 5).
 *
 * Trois onglets : les CAMPAGNES (et leurs prospects, avec les trois agents),
 * la FILE DE VALIDATION (le cœur : rien ne part sans qu'Evangéline relise et
 * valide), et les MÉTRIQUES.
 *
 * Deux garde-fous portés jusqu'à l'écran, parce que le serveur les impose mais
 * que l'interface doit les rendre lisibles : les agents INTERROGENT le modèle
 * (facturé) et l'envoi PART pour de vrai — chacun demande une confirmation
 * explicite, jamais un clic sec.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiProspection as api,
  type Campagne,
  type Message,
  type Prospect,
} from "../apiProspection";
import { Bandeau, Carte, Chiffre, Pastille, Squelette, Vide } from "../../espace/composants/Interface";
import * as f from "../../espace/format";
import "./Prospection.css";

type Onglet = "campagnes" | "valider" | "metriques";

export function ProspectionAdmin() {
  const [onglet, setOnglet] = useState<Onglet>("campagnes");
  const { data: apercu } = useQuery({
    queryKey: ["prospection", "apercu"],
    queryFn: api.apercu,
    staleTime: 30_000,
  });

  const onglets: { cle: Onglet; libelle: string; pastille?: number }[] = [
    { cle: "campagnes", libelle: "Campagnes" },
    { cle: "valider", libelle: "À valider", pastille: apercu?.a_valider },
    { cle: "metriques", libelle: "Métriques" },
  ];

  return (
    <>
      <nav className="prospection-onglets" aria-label="Sections de la prospection">
        {onglets.map((o) => (
          <button
            key={o.cle}
            type="button"
            className={onglet === o.cle ? "prospection-onglet actif" : "prospection-onglet"}
            onClick={() => setOnglet(o.cle)}
          >
            {o.libelle}
            {o.pastille ? <span className="espace-compteur">{o.pastille}</span> : null}
          </button>
        ))}
      </nav>

      {onglet === "campagnes" && <VueCampagnes />}
      {onglet === "valider" && <VueValidation />}
      {onglet === "metriques" && <VueMetriques />}
    </>
  );
}

// ── Bouton d'action payante / sortante, avec confirmation inline ─────────────

function BoutonConfirme({
  libelle,
  avertissement,
  principal = false,
  enCours = false,
  onConfirmer,
}: {
  libelle: string;
  avertissement: string;
  principal?: boolean;
  enCours?: boolean;
  onConfirmer: () => void;
}) {
  const [arme, setArme] = useState(false);
  if (!arme) {
    return (
      <button
        type="button"
        className={`bouton bouton-sm ${principal ? "bouton-principal" : "bouton-contour"}`}
        disabled={enCours}
        onClick={() => setArme(true)}
      >
        {libelle}
      </button>
    );
  }
  return (
    <span className="prospection-confirme">
      <span className="carte-note">{avertissement}</span>
      <button
        type="button"
        className="bouton bouton-principal bouton-sm"
        disabled={enCours}
        onClick={() => {
          onConfirmer();
          setArme(false);
        }}
      >
        Oui
      </button>
      <button
        type="button"
        className="bouton bouton-contour bouton-sm"
        onClick={() => setArme(false)}
      >
        Non
      </button>
    </span>
  );
}

// ── Onglet Campagnes ─────────────────────────────────────────────────────────

function VueCampagnes() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [choisie, setChoisie] = useState<string | null>(null);
  const [nouvelle, setNouvelle] = useState({ nom: "", secteur: "", zone: "", offre_visee: "" });

  const { data: campagnes, isPending } = useQuery({
    queryKey: ["prospection", "campagnes"],
    queryFn: api.campagnes,
  });

  const creer = useMutation({
    mutationFn: () => api.creerCampagne(nouvelle),
    onSuccess: () => {
      setNouvelle({ nom: "", secteur: "", zone: "", offre_visee: "" });
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["prospection"] });
    },
    onError: (c) => setErreur(c instanceof Error ? c.message : "Création impossible."),
  });

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}

      <Carte titre="Nouvelle campagne" note="Un secteur, une zone, l'offre visée.">
        <div className="prospection-formulaire">
          <input
            className="champ-saisie"
            placeholder="Nom de la campagne *"
            aria-label="Nom de la campagne"
            value={nouvelle.nom}
            onChange={(e) => setNouvelle((p) => ({ ...p, nom: e.target.value }))}
          />
          <input
            className="champ-saisie"
            placeholder="Secteur"
            aria-label="Secteur"
            value={nouvelle.secteur}
            onChange={(e) => setNouvelle((p) => ({ ...p, secteur: e.target.value }))}
          />
          <input
            className="champ-saisie"
            placeholder="Zone"
            aria-label="Zone"
            value={nouvelle.zone}
            onChange={(e) => setNouvelle((p) => ({ ...p, zone: e.target.value }))}
          />
          <input
            className="champ-saisie"
            placeholder="Offre visée"
            aria-label="Offre visée"
            value={nouvelle.offre_visee}
            onChange={(e) => setNouvelle((p) => ({ ...p, offre_visee: e.target.value }))}
          />
          <button
            type="button"
            className="bouton bouton-principal bouton-sm"
            disabled={creer.isPending || !nouvelle.nom.trim()}
            onClick={() => creer.mutate()}
          >
            Créer
          </button>
        </div>
      </Carte>

      <Carte titre="Campagnes">
        {isPending ? (
          <Squelette lignes={3} />
        ) : !campagnes || campagnes.length === 0 ? (
          <Vide icone="◇" titre="Aucune campagne" texte="Créez-en une ci-dessus pour commencer." />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Campagne</th>
                  <th scope="col">Secteur / zone</th>
                  <th scope="col">Prospects</th>
                  <th scope="col">Statut</th>
                  <th scope="col"><span className="visuellement-cache">Ouvrir</span></th>
                </tr>
              </thead>
              <tbody>
                {campagnes.map((c: Campagne) => (
                  <tr key={c.id}>
                    <td><strong>{c.nom}</strong></td>
                    <td>{[c.secteur, c.zone].filter(Boolean).join(" · ") || "—"}</td>
                    <td>{c.prospects}</td>
                    <td><Pastille statut={c.statut === "active" ? "active" : "pending"} texte={c.statut} /></td>
                    <td>
                      <button
                        type="button"
                        className="bouton bouton-contour bouton-sm"
                        onClick={() => setChoisie(choisie === c.id ? null : c.id)}
                      >
                        {choisie === c.id ? "Fermer" : "Ouvrir"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>

      {choisie && <PanneauCampagne campagneId={choisie} />}
    </>
  );
}

function PanneauCampagne({ campagneId }: { campagneId: string }) {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const { data, isPending } = useQuery({
    queryKey: ["prospection", "campagne", campagneId],
    queryFn: () => api.campagne(campagneId),
  });

  const rafraichir = () => {
    void cache.invalidateQueries({ queryKey: ["prospection"] });
  };

  const rechercher = useMutation({
    mutationFn: () => api.rechercher(campagneId, 10),
    onSuccess: rafraichir,
    onError: (c) => setErreur(c instanceof Error ? c.message : "Recherche impossible."),
  });
  const qualifier = useMutation({
    mutationFn: (id: string) => api.qualifier(id),
    onSuccess: rafraichir,
    onError: (c) => setErreur(c instanceof Error ? c.message : "Qualification impossible."),
  });
  const rediger = useMutation({
    mutationFn: (id: string) => api.rediger(id),
    onSuccess: rafraichir,
    onError: (c) => setErreur(c instanceof Error ? c.message : "Rédaction impossible."),
  });
  const desinscrire = useMutation({
    mutationFn: (id: string) => api.desinscrire(id),
    onSuccess: rafraichir,
    onError: (c) => setErreur(c instanceof Error ? c.message : "Désinscription impossible."),
  });

  if (isPending || !data) return <Carte titre="Campagne"><Squelette lignes={3} /></Carte>;

  return (
    <Carte
      titre={data.nom}
      note={[data.secteur, data.zone].filter(Boolean).join(" · ") || undefined}
      action={
        <BoutonConfirme
          libelle="Trouver des prospects"
          avertissement="Interroge l'IA et la recherche web (facturé)."
          principal
          enCours={rechercher.isPending}
          onConfirmer={() => rechercher.mutate()}
        />
      }
    >
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {data.prospects_liste.length === 0 ? (
        <Vide
          icone="◇"
          titre="Aucun prospect"
          texte="« Trouver des prospects » lance l'agent de recherche, ou ajoutez-les à la main."
        />
      ) : (
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Prospect</th>
                <th scope="col">Score</th>
                <th scope="col">Statut</th>
                <th scope="col">Agents</th>
              </tr>
            </thead>
            <tbody>
              {data.prospects_liste.map((p: Prospect) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.raison_sociale}</strong>
                    <div className="carte-note">{p.email || "sans e-mail"}</div>
                  </td>
                  <td>
                    {p.score_adequation ?? "—"}
                    {p.raison_score && <div className="carte-note">{p.raison_score}</div>}
                  </td>
                  <td><Pastille statut={p.statut} texte={p.statut} /></td>
                  <td>
                    <div className="prospection-actions">
                      <BoutonConfirme
                        libelle="Qualifier"
                        avertissement="Interroge l'IA (facturé)."
                        enCours={qualifier.isPending}
                        onConfirmer={() => qualifier.mutate(p.id)}
                      />
                      <BoutonConfirme
                        libelle="Rédiger"
                        avertissement="Interroge l'IA (facturé)."
                        enCours={rediger.isPending}
                        onConfirmer={() => rediger.mutate(p.id)}
                      />
                      {p.contactable && (
                        <BoutonConfirme
                          libelle="Désinscrire"
                          avertissement="Retire le consentement (irréversible)."
                          enCours={desinscrire.isPending}
                          onConfirmer={() => desinscrire.mutate(p.id)}
                        />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Carte>
  );
}

// ── Onglet À valider ─────────────────────────────────────────────────────────

function VueValidation() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [par, setPar] = useState("administrateur");

  const brouillons = useQuery({
    queryKey: ["prospection", "messages", "brouillon"],
    queryFn: () => api.messages({ statut: "brouillon" }),
  });
  const valides = useQuery({
    queryKey: ["prospection", "messages", "valide"],
    queryFn: () => api.messages({ statut: "valide" }),
  });

  const rafraichir = () => {
    setErreur("");
    void cache.invalidateQueries({ queryKey: ["prospection"] });
  };
  const surErreur = (c: unknown) =>
    setErreur(c instanceof Error ? c.message : "Action impossible.");

  const valider = useMutation({
    mutationFn: (id: string) => api.valider(id, par),
    onSuccess: rafraichir,
    onError: surErreur,
  });
  const envoyer = useMutation({
    mutationFn: (id: string) => api.envoyerMessage(id),
    onSuccess: rafraichir,
    onError: surErreur,
  });
  const annuler = useMutation({
    mutationFn: (id: string) => api.annuler(id),
    onSuccess: rafraichir,
    onError: surErreur,
  });

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      <Bandeau titre="Rien ne part sans vous">
        Un message est un <strong>brouillon</strong> tant que vous ne l'avez pas validé.
        Vous pouvez le modifier, puis le valider — c'est seulement alors qu'il peut être
        envoyé. L'envoi part <strong>réellement</strong> au destinataire.
      </Bandeau>

      <Carte
        titre="À valider"
        note="Relisez, ajustez, puis validez. La validation est nominative."
        action={
          <input
            className="champ-saisie"
            style={{ maxWidth: 220 }}
            aria-label="Nom du validateur"
            placeholder="Validé par…"
            value={par}
            onChange={(e) => setPar(e.target.value)}
          />
        }
      >
        {brouillons.isPending ? (
          <Squelette lignes={3} />
        ) : !brouillons.data || brouillons.data.length === 0 ? (
          <Vide icone="✓" titre="Aucun brouillon" texte="Les messages rédigés par l'agent apparaîtront ici." />
        ) : (
          brouillons.data.map((m) => (
            <CarteBrouillon
              key={m.id}
              message={m}
              par={par}
              enCours={valider.isPending || annuler.isPending}
              onValider={() => valider.mutate(m.id)}
              onAnnuler={() => annuler.mutate(m.id)}
              onEnregistre={rafraichir}
              onErreur={surErreur}
            />
          ))
        )}
      </Carte>

      <Carte titre="Validés, prêts à envoyer" note="L'envoi part réellement au destinataire.">
        {valides.isPending ? (
          <Squelette lignes={2} />
        ) : !valides.data || valides.data.length === 0 ? (
          <Vide icone="◇" titre="Rien en attente d'envoi" />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Objet</th>
                  <th scope="col">Validé par</th>
                  <th scope="col"><span className="visuellement-cache">Envoyer</span></th>
                </tr>
              </thead>
              <tbody>
                {valides.data.map((m) => (
                  <tr key={m.id}>
                    <td>{m.objet}</td>
                    <td>{m.valide_par || "—"}</td>
                    <td>
                      <div className="prospection-actions">
                        <BoutonConfirme
                          libelle="Envoyer"
                          avertissement="Envoie réellement l'e-mail au destinataire."
                          principal
                          enCours={envoyer.isPending}
                          onConfirmer={() => envoyer.mutate(m.id)}
                        />
                        <BoutonConfirme
                          libelle="Annuler"
                          avertissement="Retire ce message de la file."
                          enCours={annuler.isPending}
                          onConfirmer={() => annuler.mutate(m.id)}
                        />
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

function CarteBrouillon({
  message,
  par,
  enCours,
  onValider,
  onAnnuler,
  onEnregistre,
  onErreur,
}: {
  message: Message;
  par: string;
  enCours: boolean;
  onValider: () => void;
  onAnnuler: () => void;
  onEnregistre: () => void;
  onErreur: (c: unknown) => void;
}) {
  const [objet, setObjet] = useState(message.objet);
  const [corps, setCorps] = useState(message.corps);
  const modifie = objet !== message.objet || corps !== message.corps;

  const enregistrer = useMutation({
    mutationFn: () => api.editerBrouillon(message.id, { objet, corps }),
    onSuccess: onEnregistre,
    onError: onErreur,
  });

  return (
    <div className="prospection-brouillon">
      <input
        className="champ-saisie"
        aria-label="Objet du message"
        value={objet}
        onChange={(e) => setObjet(e.target.value)}
      />
      <textarea
        className="champ-saisie prospection-corps"
        aria-label="Corps du message"
        rows={6}
        value={corps}
        onChange={(e) => setCorps(e.target.value)}
      />
      <div className="prospection-actions">
        <button
          type="button"
          className="bouton bouton-contour bouton-sm"
          disabled={!modifie || enregistrer.isPending}
          onClick={() => enregistrer.mutate()}
        >
          Enregistrer
        </button>
        <button
          type="button"
          className="bouton bouton-principal bouton-sm"
          disabled={enCours || modifie || !par.trim()}
          title={modifie ? "Enregistrez d'abord vos modifications." : undefined}
          onClick={onValider}
        >
          Valider
        </button>
        <BoutonConfirme
          libelle="Annuler"
          avertissement="Retire ce brouillon de la file."
          enCours={enCours}
          onConfirmer={onAnnuler}
        />
      </div>
    </div>
  );
}

// ── Onglet Métriques ─────────────────────────────────────────────────────────

function VueMetriques() {
  const { data, isPending } = useQuery({
    queryKey: ["prospection", "metriques"],
    queryFn: () => api.metriques(),
  });

  if (isPending || !data) return <Carte titre="Métriques"><Squelette lignes={3} /></Carte>;

  return (
    <>
      <Carte titre="Performance" note="Recalculé à partir des événements reçus.">
        <div className="prospection-chiffres">
          <Chiffre libelle="E-mails envoyés" valeur={f.nombre(data.envoyes)} />
          <Chiffre
            libelle="Taux d'ouverture"
            valeur={`${data.taux_ouverture} %`}
            detail={`${data.ouvertures} ouverts · ${data.ouvertures_total} au total`}
            accent
          />
          <Chiffre libelle="Taux de clic" valeur={`${data.taux_clic} %`} detail={`${data.clics} clics`} />
          <Chiffre
            libelle="Taux de réponse"
            valeur={`${data.taux_reponse} %`}
            detail={`${data.reponses} réponses`}
          />
          <Chiffre
            libelle="Taux de conversion"
            valeur={`${data.taux_conversion} %`}
            detail={`${data.conversions} / ${data.prospects_contactes} contactés`}
            accent
          />
          <Chiffre
            libelle="Rebonds / désinscriptions"
            valeur={`${data.rebonds} / ${data.desinscriptions}`}
          />
        </div>
      </Carte>
    </>
  );
}
