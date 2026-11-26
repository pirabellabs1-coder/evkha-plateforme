/** La newsletter d'EVKHA (demandes de la gérante du 26/11/2026).
 *
 * Quatre onglets :
 * - LETTRES : rédiger (éditeur enrichi, images), relire (aperçu, essai),
 *   puis envoyer tout de suite ou programmer. Une lettre envoyée se lit, elle
 *   ne se modifie plus ;
 * - MODÈLES : des points de départ réutilisables ;
 * - AUTOMATISATIONS : des suites de messages qui partent d'elles-mêmes après
 *   une inscription ou un téléchargement, chacune à son délai ;
 * - ABONNÉS : en ajouter (une adresse, une liste collée, un export), et
 *   l'accès à l'écran « Audience », qui les liste, les exporte et les
 *   désinscrit.
 *
 * Les envois partent du serveur, à la minute (`lettre/envoi.py`) : fermer cet
 * écran n'arrête rien, et chaque message porte son lien de désinscription.
 */
import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import {
  adminApi,
  type AutomatisationAdmin,
  type ContenuDeLettre,
  type Declencheur,
  type EtapeDAutomatisation,
  type LettreAdmin as Lettre,
  type ModeleDeLettre,
  type StatutDeLettre,
} from "../api";
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
import { message } from "./lettre/outils";
import { ChampsDuContenu, Relecture, Vignette } from "./lettre/Redaction";
import "./Lettre.css";

type Onglet = "lettres" | "modeles" | "automatisations" | "abonnes";

const VIDE: ContenuDeLettre = { objet: "", apercu: "", corps_html: "" };

const STATUTS: Record<StatutDeLettre, { libelle: string; ton: string }> = {
  brouillon: { libelle: "Brouillon", ton: "neutre" },
  programmee: { libelle: "Programmée", ton: "info" },
  en_cours: { libelle: "Envoi en cours", ton: "info" },
  envoyee: { libelle: "Envoyée", ton: "succes" },
  annulee: { libelle: "Annulée", ton: "alerte" },
};

const CLE = ["admin", "lettre"] as const;

function StatutDeLaLettre({ statut }: { statut: StatutDeLettre }) {
  const s = STATUTS[statut];
  return <span className={`pastille pastille-${s.ton}`}>{s.libelle}</span>;
}

/** `datetime-local` lit et écrit l'heure LOCALE, sans fuseau. */
function versHeureLocale(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const decalage = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - decalage).toISOString().slice(0, 16);
}

function Retour({ retour }: { retour: { ton: "succes" | "echec"; texte: string } | null }) {
  if (!retour) return null;
  return <Bandeau ton={retour.ton}>{retour.texte}</Bandeau>;
}

// ── Lettres ─────────────────────────────────────────────────────────────────

function FicheDeLettre({
  lettreId,
  depart,
  inscrits,
  fermer,
}: {
  lettreId: string | null;
  depart: ContenuDeLettre;
  inscrits: number;
  fermer: () => void;
}) {
  const cache = useQueryClient();
  const [id, setId] = useState(lettreId);
  const [contenu, setContenu] = useState<ContenuDeLettre | null>(lettreId ? null : depart);
  const [quand, setQuand] = useState("");
  const [retour, setRetour] = useState<{ ton: "succes" | "echec"; texte: string } | null>(null);

  const lecture = useQuery({
    queryKey: [...CLE, "lettre", id],
    queryFn: () => adminApi.lettre(id as string),
    enabled: id !== null,
    refetchInterval: (requete) =>
      requete.state.data?.statut === "en_cours" || requete.state.data?.statut === "programmee"
        ? 5000
        : false,
  });
  const lettre: Lettre | undefined = lecture.data;
  if (lettre && contenu === null) {
    setContenu({ objet: lettre.objet, apercu: lettre.apercu, corps_html: lettre.corps_html });
  }
  const statut: StatutDeLettre = lettre?.statut ?? "brouillon";
  const modifiable = statut === "brouillon";

  function rafraichir(maj?: Lettre) {
    if (maj) cache.setQueryData([...CLE, "lettre", maj.id], maj);
    void cache.invalidateQueries({ queryKey: [...CLE, "lettres"] });
    void cache.invalidateQueries({ queryKey: [...CLE, "resume"] });
  }

  async function enregistrer(): Promise<Lettre> {
    if (!contenu) throw new Error("Rien à enregistrer.");
    const maj = id
      ? await adminApi.modifierUneLettre(id, contenu)
      : await adminApi.creerUneLettre(contenu);
    // Le texte saisi reste celui de l'éditeur : réinjecter la version
    // nettoyée par le serveur (mêmes balises, écrites autrement) ferait
    // sauter le curseur et vider l'historique d'annulation.
    setId(maj.id);
    rafraichir(maj);
    return maj;
  }

  const sauvegarde = useMutation({
    mutationFn: enregistrer,
    onSuccess: () => setRetour({ ton: "succes", texte: "Brouillon enregistré." }),
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "L'enregistrement a échoué.") }),
  });

  const programmation = useMutation({
    mutationFn: async (moment: string | null) => {
      const enregistree = await enregistrer();
      return adminApi.programmerUneLettre(enregistree.id, moment);
    },
    onSuccess: (maj) => {
      rafraichir(maj);
      setRetour({
        ton: "succes",
        texte:
          maj.programmee_pour && new Date(maj.programmee_pour).getTime() > Date.now() + 90_000
            ? `Newsletter programmée pour le ${f.dateHeure(maj.programmee_pour)}, à ${f.nombre(maj.destinataires_prevus ?? inscrits)} inscrits.`
            : `C'est parti : la newsletter part dans la minute à ${f.nombre(maj.destinataires_prevus ?? inscrits)} inscrits.`,
      });
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "La newsletter n'a pas été programmée.") }),
  });

  const annulation = useMutation({
    mutationFn: () => adminApi.annulerUneLettre(id as string),
    onSuccess: (maj) => {
      rafraichir(maj);
      setRetour({
        ton: "succes",
        texte:
          maj.statut === "brouillon"
            ? "La newsletter est déprogrammée : elle redevient un brouillon."
            : "L'envoi est arrêté : les messages pas encore partis ne partiront pas.",
      });
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "L'annulation a échoué.") }),
  });

  const suppression = useMutation({
    mutationFn: () => adminApi.supprimerUneLettre(id as string),
    onSuccess: () => {
      rafraichir();
      fermer();
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "La suppression a échoué.") }),
  });

  const enModele = useMutation({
    mutationFn: (nom: string) => adminApi.creerUnModele({ nom, ...(contenu ?? VIDE) }),
    onSuccess: (m) => {
      void cache.invalidateQueries({ queryKey: [...CLE, "modeles"] });
      setRetour({ ton: "succes", texte: `Modèle « ${m.nom} » enregistré.` });
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "Le modèle n'a pas été créé.") }),
  });

  if (lecture.isError) {
    return <ErreurDeChargement quoi="la newsletter" erreur={lecture.error} perimees={false} />;
  }
  if (!contenu) return <Squelette lignes={6} />;

  const occupe =
    sauvegarde.isPending || programmation.isPending || annulation.isPending || suppression.isPending;
  const prete = contenu.objet.trim() !== "" && contenu.corps_html.trim() !== "";

  function envoyerMaintenant() {
    if (
      window.confirm(
        `Envoyer « ${contenu?.objet} » maintenant à ${f.nombre(inscrits)} inscrit${inscrits > 1 ? "s" : ""} ? Une newsletter envoyée ne se rattrape pas.`,
      )
    ) {
      programmation.mutate(null);
    }
  }

  function programmer() {
    const moment = new Date(quand);
    if (Number.isNaN(moment.getTime())) {
      setRetour({ ton: "echec", texte: "Choisissez une date et une heure d'envoi." });
      return;
    }
    if (window.confirm(`Programmer l'envoi pour le ${f.dateHeure(moment.toISOString())} ?`)) {
      programmation.mutate(moment.toISOString());
    }
  }

  return (
    <Carte
      titre={id ? contenu.objet || "Newsletter sans objet" : "Nouvelle newsletter"}
      note={
        lettre?.statut === "programmee"
          ? `Programmée pour le ${f.dateHeure(lettre.programmee_pour)}.`
          : lettre?.statut === "envoyee"
            ? `Envoyée le ${f.dateHeure(lettre.terminee_le)} : ${f.nombre(lettre.envois.envoye)} reçue${lettre.envois.envoye > 1 ? "s" : ""}, ${f.nombre(lettre.envois.echec)} échec${lettre.envois.echec > 1 ? "s" : ""}.`
            : lettre?.statut === "en_cours"
              ? `Envoi en cours : ${f.nombre(lettre.envois.envoye)} parties, ${f.nombre(lettre.envois.a_envoyer)} en attente.`
              : "Rédigez, relisez avec l'aperçu ou un essai, puis envoyez ou programmez."
      }
      action={
        <div className="lt-actions">
          {lettre && <StatutDeLaLettre statut={lettre.statut} />}
          <button type="button" className="bouton bouton-contour bouton-sm" onClick={fermer}>
            Retour à la liste
          </button>
        </div>
      }
    >
      <Retour retour={retour} />
      <ChampsDuContenu contenu={contenu} changer={setContenu} lectureSeule={!modifiable} />
      <Relecture contenu={contenu} />

      <div className="lt-pied">
        {modifiable && (
          <>
            <button
              type="button"
              className="bouton bouton-contour"
              onClick={() => sauvegarde.mutate()}
              disabled={occupe || !contenu.objet.trim()}
            >
              Enregistrer le brouillon
            </button>
            <div className="lt-envoi">
              <label className="champ">
                <span className="champ-libelle">Programmer pour</span>
                <input
                  className="champ-saisie"
                  type="datetime-local"
                  value={quand}
                  min={versHeureLocale(new Date().toISOString())}
                  onChange={(e) => setQuand(e.target.value)}
                />
              </label>
              <button
                type="button"
                className="bouton bouton-contour"
                onClick={programmer}
                disabled={occupe || !prete || !quand || inscrits === 0}
              >
                Programmer
              </button>
              <button
                type="button"
                className="bouton bouton-principal"
                onClick={envoyerMaintenant}
                disabled={occupe || !prete || inscrits === 0}
              >
                Envoyer maintenant
              </button>
            </div>
            {inscrits === 0 && (
              <p className="lt-note">
                Personne n'a encore confirmé son inscription : l'envoi s'ouvrira au premier abonné.
              </p>
            )}
          </>
        )}
        {(statut === "programmee" || statut === "en_cours") && (
          <button
            type="button"
            className="bouton bouton-echec"
            disabled={occupe}
            onClick={() => {
              const texte =
                statut === "programmee"
                  ? "Déprogrammer cette newsletter ? Elle redeviendra un brouillon."
                  : "Arrêter l'envoi ? Les messages déjà partis le restent.";
              if (window.confirm(texte)) annulation.mutate();
            }}
          >
            {statut === "programmee" ? "Déprogrammer" : "Arrêter l'envoi"}
          </button>
        )}
        <button
          type="button"
          className="bouton bouton-contour"
          disabled={enModele.isPending || !contenu.corps_html.trim()}
          onClick={() => {
            const nom = window.prompt("Nom du modèle :", contenu.objet);
            if (nom && nom.trim()) enModele.mutate(nom.trim());
          }}
        >
          Enregistrer comme modèle
        </button>
        {id && (statut === "brouillon" || statut === "annulee") && (
          <button
            type="button"
            className="bouton bouton-echec"
            disabled={occupe}
            onClick={() => {
              if (window.confirm("Supprimer définitivement cette newsletter ?")) suppression.mutate();
            }}
          >
            Supprimer
          </button>
        )}
      </div>
    </Carte>
  );
}

function OngletLettres({
  depart,
  consommerDepart,
}: {
  depart: ContenuDeLettre | null;
  consommerDepart: () => void;
}) {
  const [ouverte, setOuverte] = useState<{ id: string | null; depart: ContenuDeLettre } | null>(
    depart ? { id: null, depart } : null,
  );
  const lecture = useQuery({ queryKey: [...CLE, "lettres"], queryFn: adminApi.lettres });
  const modeles = useQuery({ queryKey: [...CLE, "modeles"], queryFn: adminApi.modelesDeLettre });

  if (ouverte) {
    return (
      <FicheDeLettre
        lettreId={ouverte.id}
        depart={ouverte.depart}
        inscrits={lecture.data?.inscrits ?? 0}
        fermer={() => {
          setOuverte(null);
          consommerDepart();
        }}
      />
    );
  }

  const lettres = lecture.data?.lettres ?? [];
  return (
    <Carte
      titre="Les newsletters"
      note="Les plus récentes d'abord."
      action={
        <div className="lt-actions">
          {(modeles.data?.modeles.length ?? 0) > 0 && (
            <select
              className="champ-saisie lt-choix-modele"
              aria-label="Partir d'un modèle"
              value=""
              onChange={(e) => {
                const m = modeles.data?.modeles.find((x) => x.id === e.target.value);
                if (m) setOuverte({ id: null, depart: { objet: m.objet, apercu: m.apercu, corps_html: m.corps_html } });
              }}
            >
              <option value="">Partir d'un modèle…</option>
              {modeles.data?.modeles.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nom}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            className="bouton bouton-principal bouton-sm"
            onClick={() => setOuverte({ id: null, depart: VIDE })}
          >
            <Icone nom="plus" taille={16} />
            Nouvelle newsletter
          </button>
        </div>
      }
    >
      {lecture.isError && (
        <ErreurDeChargement quoi="les newsletters" erreur={lecture.error} perimees={lecture.isRefetchError} />
      )}
      {lecture.isPending ? (
        <Squelette lignes={3} />
      ) : lettres.length === 0 ? (
        <Vide
          icone={<Icone nom="lettre" />}
          titre="Aucune newsletter pour l'instant"
          texte="Écrivez la première : elle partira à toutes les personnes qui ont confirmé leur inscription."
        />
      ) : (
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Objet</th>
                <th scope="col">État</th>
                <th scope="col">Date</th>
                <th scope="col">Reçues</th>
                <th scope="col">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {lettres.map((l) => (
                <tr key={l.id}>
                  <td>{l.objet}</td>
                  <td>
                    <StatutDeLaLettre statut={l.statut} />
                  </td>
                  <td>
                    {l.statut === "programmee"
                      ? f.dateHeure(l.programmee_pour)
                      : l.terminee_le
                        ? f.dateHeure(l.terminee_le)
                        : f.dateHeure(l.modifiee_le)}
                  </td>
                  <td>
                    {f.nombre(l.envois.envoye)}
                    {l.envois.echec > 0 && ` (${f.nombre(l.envois.echec)} échec${l.envois.echec > 1 ? "s" : ""})`}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="bouton bouton-contour bouton-sm"
                      onClick={() => setOuverte({ id: l.id, depart: VIDE })}
                    >
                      {l.statut === "brouillon" ? "Modifier" : "Ouvrir"}
                    </button>
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

// ── Modèles ─────────────────────────────────────────────────────────────────

function FicheDeModele({
  modele,
  fermer,
  ecrireAvec,
}: {
  modele: ModeleDeLettre | null;
  fermer: () => void;
  ecrireAvec: (contenu: ContenuDeLettre) => void;
}) {
  const cache = useQueryClient();
  const [nom, setNom] = useState(modele?.nom ?? "");
  const [contenu, setContenu] = useState<ContenuDeLettre>(
    modele ? { objet: modele.objet, apercu: modele.apercu, corps_html: modele.corps_html } : VIDE,
  );
  const [retour, setRetour] = useState<{ ton: "succes" | "echec"; texte: string } | null>(null);
  const [id, setId] = useState(modele?.id ?? null);

  const sauvegarde = useMutation({
    mutationFn: () =>
      id ? adminApi.modifierUnModele(id, { nom, ...contenu }) : adminApi.creerUnModele({ nom, ...contenu }),
    onSuccess: (m) => {
      setId(m.id);
      void cache.invalidateQueries({ queryKey: [...CLE, "modeles"] });
      setRetour({ ton: "succes", texte: "Modèle enregistré." });
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "L'enregistrement a échoué.") }),
  });
  const suppression = useMutation({
    mutationFn: () => adminApi.supprimerUnModele(id as string),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: [...CLE, "modeles"] });
      fermer();
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "La suppression a échoué.") }),
  });

  return (
    <Carte
      titre={id ? nom || "Modèle" : "Nouveau modèle"}
      action={
        <button type="button" className="bouton bouton-contour bouton-sm" onClick={fermer}>
          Retour aux modèles
        </button>
      }
    >
      <Retour retour={retour} />
      <label className="champ">
        <span className="champ-libelle">Nom du modèle</span>
        <input
          className="champ-saisie"
          value={nom}
          maxLength={120}
          required
          onChange={(e) => setNom(e.target.value)}
        />
      </label>
      <ChampsDuContenu contenu={contenu} changer={setContenu} objetObligatoire={false} />
      <div className="lt-pied">
        <button
          type="button"
          className="bouton bouton-principal"
          disabled={sauvegarde.isPending || !nom.trim()}
          onClick={() => sauvegarde.mutate()}
        >
          Enregistrer le modèle
        </button>
        <button type="button" className="bouton bouton-contour" onClick={() => ecrireAvec(contenu)}>
          Écrire une newsletter avec ce modèle
        </button>
        {id && (
          <button
            type="button"
            className="bouton bouton-echec"
            disabled={suppression.isPending}
            onClick={() => {
              if (window.confirm("Supprimer ce modèle ? Les newsletters déjà écrites avec lui ne changent pas.")) {
                suppression.mutate();
              }
            }}
          >
            Supprimer
          </button>
        )}
      </div>
    </Carte>
  );
}

function OngletModeles({ ecrireAvec }: { ecrireAvec: (contenu: ContenuDeLettre) => void }) {
  const [ouvert, setOuvert] = useState<ModeleDeLettre | "nouveau" | null>(null);
  const lecture = useQuery({ queryKey: [...CLE, "modeles"], queryFn: adminApi.modelesDeLettre });

  if (ouvert) {
    return (
      <FicheDeModele
        modele={ouvert === "nouveau" ? null : ouvert}
        fermer={() => setOuvert(null)}
        ecrireAvec={ecrireAvec}
      />
    );
  }
  const modeles = lecture.data?.modeles ?? [];
  return (
    <Carte
      titre="Les modèles"
      note="Une mise en page et un texte de départ, à reprendre pour chaque nouvelle newsletter."
      action={
        <button
          type="button"
          className="bouton bouton-principal bouton-sm"
          onClick={() => setOuvert("nouveau")}
        >
          <Icone nom="plus" taille={16} />
          Nouveau modèle
        </button>
      }
    >
      {lecture.isError && (
        <ErreurDeChargement quoi="les modèles" erreur={lecture.error} perimees={lecture.isRefetchError} />
      )}
      {lecture.isPending ? (
        <Squelette lignes={3} />
      ) : modeles.length === 0 ? (
        <Vide
          icone={<Icone nom="lettre" />}
          titre="Aucun modèle"
          texte="Créez un modèle, ou enregistrez une newsletter réussie comme modèle depuis sa fiche."
        />
      ) : (
        <ul className="lt-liste lt-liste-modeles">
          {modeles.map((m) => (
            <li key={m.id} className="lt-ligne lt-ligne-modele">
              <Vignette contenu={m} nom={m.nom} />
              <div className="lt-ligne-texte">
                <strong>{m.nom}</strong>
                <span className="lt-detail">Modifié le {f.date(m.modifie_le)}</span>
              </div>
              <div className="lt-actions">
                <button type="button" className="bouton bouton-contour bouton-sm" onClick={() => setOuvert(m)}>
                  Modifier
                </button>
                <button
                  type="button"
                  className="bouton bouton-principal bouton-sm"
                  onClick={() => ecrireAvec({ objet: m.objet, apercu: m.apercu, corps_html: m.corps_html })}
                >
                  Écrire une newsletter
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Carte>
  );
}

// ── Automatisations ─────────────────────────────────────────────────────────

const ETAPE_VIDE: EtapeDAutomatisation = { delai_jours: 0, ...VIDE };

/** Un message tel que l'écran le tient : avec une clé à lui, stable même
 *  avant son premier enregistrement. Retirer le premier de deux messages
 *  neufs ne doit pas donner à l'autre l'aperçu et l'essai du disparu. */
type EtapeALEcran = EtapeDAutomatisation & { cle: string };

let compteurDeCles = 0;
function avecCle(etape: EtapeDAutomatisation): EtapeALEcran {
  compteurDeCles += 1;
  return { ...etape, cle: etape.id ?? `nouvelle-${compteurDeCles}` };
}

function sansCle(etape: EtapeALEcran): EtapeDAutomatisation {
  const copie: Partial<EtapeALEcran> = { ...etape };
  delete copie.cle;
  return copie as EtapeDAutomatisation;
}

function FicheDAutomatisation({
  automatisation,
  declencheurs,
  fermer,
}: {
  automatisation: AutomatisationAdmin | null;
  declencheurs: { valeur: Declencheur; libelle: string }[];
  fermer: () => void;
}) {
  const cache = useQueryClient();
  const [id, setId] = useState(automatisation?.id ?? null);
  const [nom, setNom] = useState(automatisation?.nom ?? "");
  const [declencheur, setDeclencheur] = useState<Declencheur>(automatisation?.declencheur ?? "inscription");
  const [active, setActive] = useState(automatisation?.active ?? false);
  const [etapes, setEtapes] = useState<EtapeALEcran[]>(() =>
    (automatisation?.etapes.length ? automatisation.etapes : [{ ...ETAPE_VIDE }]).map(avecCle),
  );
  const [activeDepuis, setActiveDepuis] = useState(automatisation?.active_depuis ?? null);
  const [retour, setRetour] = useState<{ ton: "succes" | "echec"; texte: string } | null>(null);

  const sauvegarde = useMutation({
    mutationFn: () => {
      const corps = { nom, declencheur, active, etapes: etapes.map(sansCle) };
      return id ? adminApi.modifierUneAutomatisation(id, corps) : adminApi.creerUneAutomatisation(corps);
    },
    onSuccess: (a) => {
      setId(a.id);
      setEtapes(a.etapes.map(avecCle));
      setActiveDepuis(a.active_depuis);
      void cache.invalidateQueries({ queryKey: [...CLE, "automatisations"] });
      setRetour({
        ton: "succes",
        texte: a.active
          ? "Automatisation enregistrée et active : elle écrira aux personnes à partir de maintenant."
          : "Automatisation enregistrée, en pause : rien ne part tant qu'elle n'est pas activée.",
      });
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "L'enregistrement a échoué.") }),
  });
  const suppression = useMutation({
    mutationFn: () => adminApi.supprimerUneAutomatisation(id as string),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: [...CLE, "automatisations"] });
      fermer();
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "La suppression a échoué.") }),
  });

  function changerEtape(rang: number, maj: Partial<EtapeDAutomatisation>) {
    setEtapes((liste) => liste.map((e, i) => (i === rang ? { ...e, ...maj } : e)));
  }
  function deplacer(rang: number, sens: -1 | 1) {
    setEtapes((liste) => {
      const copie = [...liste];
      const [etape] = copie.splice(rang, 1);
      copie.splice(rang + sens, 0, etape);
      return copie;
    });
  }

  return (
    <Carte
      titre={id ? nom || "Automatisation" : "Nouvelle automatisation"}
      note={
        activeDepuis && active
          ? `Active depuis le ${f.dateHeure(activeDepuis)}. Seules les personnes arrivées depuis reçoivent ces messages.`
          : "En pause : aucun message ne part. À la réactivation, seules les personnes arrivées ensuite recevront la suite."
      }
      action={
        <button type="button" className="bouton bouton-contour bouton-sm" onClick={fermer}>
          Retour aux automatisations
        </button>
      }
    >
      <Retour retour={retour} />
      <div className="lt-grille">
        <label className="champ">
          <span className="champ-libelle">Nom</span>
          <input
            className="champ-saisie"
            value={nom}
            maxLength={120}
            required
            onChange={(e) => setNom(e.target.value)}
          />
        </label>
        <label className="champ">
          <span className="champ-libelle">Déclencheur</span>
          <select
            className="champ-saisie"
            value={declencheur}
            onChange={(e) => setDeclencheur(e.target.value as Declencheur)}
          >
            {declencheurs.map((d) => (
              <option key={d.valeur} value={d.valeur}>
                {d.libelle}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="lt-bascule">
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
        <span>Active : les messages partent d'eux-mêmes</span>
      </label>
      <p className="lt-note">
        Seules les personnes inscrites à la newsletter reçoivent ces messages, même pour un
        téléchargement. Le délai compte depuis l'événement déclencheur.
      </p>

      <ol className="lt-etapes">
        {etapes.map((etape, rang) => (
          <li key={etape.cle} className="lt-etape">
            <div className="lt-etape-tete">
              <h3>Message {rang + 1}</h3>
              <label className="champ lt-delai">
                <span className="champ-libelle">Envoyé après (jours)</span>
                <input
                  className="champ-saisie"
                  type="number"
                  min={0}
                  max={365}
                  value={etape.delai_jours}
                  onChange={(e) => changerEtape(rang, { delai_jours: Math.max(0, Math.min(365, Number(e.target.value) || 0)) })}
                />
              </label>
              <div className="lt-actions">
                <button
                  type="button"
                  className="bouton bouton-contour bouton-sm"
                  disabled={rang === 0}
                  onClick={() => deplacer(rang, -1)}
                  aria-label={`Monter le message ${rang + 1}`}
                >
                  Monter
                </button>
                <button
                  type="button"
                  className="bouton bouton-contour bouton-sm"
                  disabled={rang === etapes.length - 1}
                  onClick={() => deplacer(rang, 1)}
                  aria-label={`Descendre le message ${rang + 1}`}
                >
                  Descendre
                </button>
                <button
                  type="button"
                  className="bouton bouton-echec bouton-sm"
                  disabled={etapes.length === 1}
                  onClick={() => {
                    if (window.confirm(`Retirer le message ${rang + 1} ?`)) {
                      setEtapes((liste) => liste.filter((_, i) => i !== rang));
                    }
                  }}
                >
                  Retirer
                </button>
              </div>
            </div>
            {etape.envoyes !== undefined && etape.envoyes > 0 && (
              <p className="lt-detail">Déjà reçu par {f.nombre(etape.envoyes)} personne{etape.envoyes > 1 ? "s" : ""}.</p>
            )}
            <ChampsDuContenu
              contenu={etape}
              changer={(c) => changerEtape(rang, c)}
              apercuEnDirect={false}
            />
            <Relecture contenu={etape} />
          </li>
        ))}
      </ol>
      <div className="lt-pied">
        <button
          type="button"
          className="bouton bouton-contour"
          disabled={etapes.length >= 20}
          onClick={() =>
            setEtapes((liste) => [
              ...liste,
              avecCle({ ...ETAPE_VIDE, delai_jours: (liste.at(-1)?.delai_jours ?? 0) + 3 }),
            ])
          }
        >
          Ajouter un message
        </button>
        <button
          type="button"
          className="bouton bouton-principal"
          disabled={sauvegarde.isPending || !nom.trim()}
          onClick={() => {
            if (
              active &&
              !automatisation?.active &&
              !window.confirm("Activer cette automatisation ? Les messages partiront d'eux-mêmes aux nouvelles personnes.")
            ) {
              return;
            }
            sauvegarde.mutate();
          }}
        >
          Enregistrer
        </button>
        {id && (
          <button
            type="button"
            className="bouton bouton-echec"
            disabled={suppression.isPending}
            onClick={() => {
              if (window.confirm("Supprimer cette automatisation ? Les messages en attente ne partiront pas.")) {
                suppression.mutate();
              }
            }}
          >
            Supprimer
          </button>
        )}
      </div>
    </Carte>
  );
}

function OngletAutomatisations({
  declencheurs,
}: {
  declencheurs: { valeur: Declencheur; libelle: string }[];
}) {
  const [ouverte, setOuverte] = useState<AutomatisationAdmin | "nouvelle" | null>(null);
  const lecture = useQuery({ queryKey: [...CLE, "automatisations"], queryFn: adminApi.automatisations });
  const libelle = (v: Declencheur) => declencheurs.find((d) => d.valeur === v)?.libelle ?? v;

  if (ouverte) {
    return (
      <FicheDAutomatisation
        automatisation={ouverte === "nouvelle" ? null : ouverte}
        declencheurs={declencheurs}
        fermer={() => setOuverte(null)}
      />
    );
  }
  const liste = lecture.data?.automatisations ?? [];
  return (
    <Carte
      titre="Les automatisations"
      note="Une bienvenue après l'inscription, une suite après un téléchargement : des messages qui partent seuls."
      action={
        <button
          type="button"
          className="bouton bouton-principal bouton-sm"
          onClick={() => setOuverte("nouvelle")}
        >
          <Icone nom="plus" taille={16} />
          Nouvelle automatisation
        </button>
      }
    >
      {lecture.isError && (
        <ErreurDeChargement quoi="les automatisations" erreur={lecture.error} perimees={lecture.isRefetchError} />
      )}
      {lecture.isPending ? (
        <Squelette lignes={3} />
      ) : liste.length === 0 ? (
        <Vide
          icone={<Icone nom="lettre" />}
          titre="Aucune automatisation"
          texte="Par exemple : un message de bienvenue le jour de l'inscription, puis un conseil trois jours plus tard."
        />
      ) : (
        <ul className="lt-liste">
          {liste.map((a) => (
            <li key={a.id} className="lt-ligne">
              <div>
                <strong>{a.nom}</strong>
                <span className="lt-detail">
                  {libelle(a.declencheur)} · {a.etapes.length} message{a.etapes.length > 1 ? "s" : ""}
                </span>
              </div>
              <div className="lt-actions">
                <span className={`pastille pastille-${a.active ? "succes" : "neutre"}`}>
                  {a.active ? "Active" : "En pause"}
                </span>
                <button type="button" className="bouton bouton-contour bouton-sm" onClick={() => setOuverte(a)}>
                  Modifier
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Carte>
  );
}

// ── Abonnés ─────────────────────────────────────────────────────────────────

/** Un export de plusieurs dizaines de milliers de lignes fige le champ. */
const TAILLE_MAX_FICHIER = 5 * 1024 * 1024;

function AjoutDAbonnes() {
  const id = useId();
  const cache = useQueryClient();
  const [texte, setTexte] = useState("");
  const [provenance, setProvenance] = useState("");
  const [accord, setAccord] = useState(false);
  const [retour, setRetour] = useState<{ ton: "succes" | "echec"; texte: string } | null>(null);
  const [lecture, setLecture] = useState("");

  const ajout = useMutation({
    mutationFn: () => adminApi.ajouterDesAbonnes(texte, provenance, accord),
    onSuccess: (r) => {
      void cache.invalidateQueries({ queryKey: [...CLE] });
      void cache.invalidateQueries({ queryKey: ["admin", "audience"] });
      const morceaux = [
        `${f.nombre(r.ajoutees)} adresse${r.ajoutees > 1 ? "s" : ""} ajoutée${r.ajoutees > 1 ? "s" : ""}`,
      ];
      if (r.deja_inscrites) morceaux.push(`${f.nombre(r.deja_inscrites)} déjà abonnée${r.deja_inscrites > 1 ? "s" : ""}`);
      if (r.desinscrites_non_reinscrites) {
        morceaux.push(
          `${f.nombre(r.desinscrites_non_reinscrites)} désinscrite${r.desinscrites_non_reinscrites > 1 ? "s" : ""} laissée${r.desinscrites_non_reinscrites > 1 ? "s" : ""} hors de la liste (elles seules peuvent revenir)`,
        );
      }
      if (r.lignes_ecartees) {
        morceaux.push(
          `${f.nombre(r.lignes_ecartees)} ligne${r.lignes_ecartees > 1 ? "s" : ""} marquée${r.lignes_ecartees > 1 ? "s" : ""} « désinscrit » ou « rebond » écartée${r.lignes_ecartees > 1 ? "s" : ""}`,
        );
      }
      if (r.invalides_total) {
        const reste = r.invalides_total - r.invalides.length;
        morceaux.push(
          `illisibles : ${r.invalides.join(", ")}${reste > 0 ? ` et ${f.nombre(reste)} autre${reste > 1 ? "s" : ""}` : ""}`,
        );
      }
      setRetour({ ton: "succes", texte: `${morceaux.join(" ; ")}. ${f.nombre(r.inscrits)} abonnés en tout.` });
      setTexte("");
      // Chaque lot s'atteste à nouveau : la case ne reste pas cochée.
      setAccord(false);
    },
    onError: (c) => setRetour({ ton: "echec", texte: message(c, "L'ajout n'a pas abouti.") }),
  });

  async function lireLeFichier(fichier: File | undefined) {
    if (!fichier) return;
    if (fichier.size > TAILLE_MAX_FICHIER) {
      setRetour({ ton: "echec", texte: "Fichier trop lourd : 5 Mo au plus. Coupez la liste en deux." });
      return;
    }
    try {
      const contenu = await fichier.text();
      setLecture(fichier.name);
      setTexte((avant) => (avant.trim() ? `${avant}\n${contenu}` : contenu));
    } catch {
      setRetour({ ton: "echec", texte: `Le fichier « ${fichier.name} » n'a pas pu être lu.` });
    }
  }

  // Le même découpage que le serveur (`audience/adresses.py`) : on compte les
  // morceaux qui portent un @, sans chercher d'adresse au milieu d'un mot.
  const nombre = texte.split(/[\s,;<>"'()[\]|]+/).filter((m) => m.includes("@")).length;

  return (
    <Carte
      titre="Ajouter des abonnés"
      note="Une adresse, une liste collée, ou le fichier exporté d'un autre outil (Systeme.io, tableur en CSV) : seules les adresses e-mail sont lues."
    >
      <Retour retour={retour} />
      <form
        className="lt-ajout"
        onSubmit={(e) => {
          e.preventDefault();
          setRetour(null);
          ajout.mutate();
        }}
      >
        <div className="champ">
          <label className="champ-libelle" htmlFor={`${id}-adresses`}>
            Adresses e-mail
          </label>
          <textarea
            id={`${id}-adresses`}
            aria-describedby={`${id}-compte`}
            className="champ-saisie lt-adresses"
            rows={6}
            value={texte}
            placeholder={"marie@exemple.fr\npaul@exemple.fr"}
            onChange={(e) => setTexte(e.target.value)}
          />
          <span className="champ-aide" id={`${id}-compte`} aria-live="polite">
            {nombre > 0 ? `${f.nombre(nombre)} adresse${nombre > 1 ? "s" : ""} repérée${nombre > 1 ? "s" : ""}.` : "Une par ligne, ou séparées par des virgules."}
          </span>
        </div>
        <label className="champ">
          <span className="champ-libelle">Ou un fichier (CSV, texte)</span>
          <input
            className="champ-saisie"
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            onChange={(e) => {
              void lireLeFichier(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          {lecture && <span className="champ-aide">« {lecture} » ajouté au champ ci-dessus.</span>}
        </label>
        <div className="champ">
          <label className="champ-libelle" htmlFor={`${id}-provenance`}>
            D'où vient cette liste ?
          </label>
          <input
            id={`${id}-provenance`}
            className="champ-saisie"
            value={provenance}
            maxLength={200}
            required
            placeholder="Export Systeme.io du 26/11/2026"
            aria-describedby={`${id}-provenance-aide`}
            onChange={(e) => setProvenance(e.target.value)}
          />
          <span className="champ-aide" id={`${id}-provenance-aide`}>
            Gardé avec chaque adresse : c'est la trace de leur accord.
          </span>
        </div>
        <label className="lt-bascule">
          <input type="checkbox" checked={accord} onChange={(e) => setAccord(e.target.checked)} />
          <span>Ces personnes ont accepté de recevoir la newsletter d'EVKHA.</span>
        </label>
        <p className="lt-note">
          Elles sont abonnées tout de suite, sans courriel de confirmation, et ne reçoivent pas
          les messages de bienvenue automatiques. N'importez que les contacts actifs : une
          personne désinscrite ou effacée n'est jamais réabonnée, et les lignes marquées «
          désinscrit » ou « rebond » sont écartées.
        </p>
        <div className="lt-pied">
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={ajout.isPending || !accord || nombre === 0 || !provenance.trim()}
          >
            {ajout.isPending ? "Ajout…" : "Ajouter à la newsletter"}
          </button>
        </div>
      </form>
    </Carte>
  );
}

// ── L'écran ─────────────────────────────────────────────────────────────────

const ONGLETS: { cle: Onglet; libelle: string }[] = [
  { cle: "lettres", libelle: "Newsletters" },
  { cle: "modeles", libelle: "Modèles" },
  { cle: "automatisations", libelle: "Automatisations" },
  { cle: "abonnes", libelle: "Abonnés" },
];

export function LettreAdmin() {
  const [onglet, setOnglet] = useState<Onglet>("lettres");
  const [depart, setDepart] = useState<ContenuDeLettre | null>(null);
  const resume = useQuery({ queryKey: [...CLE, "resume"], queryFn: adminApi.resumeDeLaLettre });
  const r = resume.data;

  return (
    <>
      {resume.isError && (
        <ErreurDeChargement quoi="la newsletter" erreur={resume.error} perimees={resume.isRefetchError} />
      )}
      {r && (
        <div className="grille-chiffres">
          <Chiffre
            libelle="Abonnés"
            valeur={f.nombre(r.inscrits)}
            detail="Ont confirmé leur adresse"
            accent
          />
          <Chiffre
            libelle="En attente de confirmation"
            valeur={f.nombre(r.en_attente_de_confirmation)}
            detail="N'ont pas encore cliqué le lien reçu"
          />
          <Chiffre libelle="Désinscrits" valeur={f.nombre(r.desinscrits)} detail="Ne reçoivent plus rien" />
        </div>
      )}

      <nav className="console-onglets" aria-label="Sections de la newsletter">
        {ONGLETS.map((o) => (
          <button
            key={o.cle}
            type="button"
            className={`console-onglet${onglet === o.cle ? " actif" : ""}`}
            aria-pressed={onglet === o.cle}
            onClick={() => setOnglet(o.cle)}
          >
            {o.libelle}
          </button>
        ))}
      </nav>

      {onglet === "lettres" && (
        <OngletLettres key={depart ? "depart" : "liste"} depart={depart} consommerDepart={() => setDepart(null)} />
      )}
      {onglet === "modeles" && (
        <OngletModeles
          ecrireAvec={(contenu) => {
            setDepart(contenu);
            setOnglet("lettres");
          }}
        />
      )}
      {onglet === "automatisations" && <OngletAutomatisations declencheurs={r?.declencheurs ?? []} />}
      {onglet === "abonnes" && <AjoutDAbonnes />}
      {onglet === "abonnes" && (
        <Carte
          titre="La liste des abonnés"
          note="Les inscriptions venues du site sont confirmées par courriel ; celles que vous ajoutez sont abonnées aussitôt."
        >
          {resume.isPending ? (
            <Squelette lignes={2} />
          ) : (
            <div className="lt-abonnes">
              <p>
                Les personnes s'inscrivent aussi d'elles-mêmes, depuis le blog ou en cochant la
                case des ressources gratuites (accueil, boîte à outils), puis confirment leur
                adresse. Chaque message porte un lien pour se désinscrire en un clic, et les
                messageries affichent aussi leur propre bouton « Se désinscrire ».
              </p>
              <p>
                La liste complète, la recherche, l'export pour un tableur, la désinscription ou
                l'effacement d'une personne qui le demande se font dans l'écran Audience.
              </p>
              <Link to="/admin/audience" className="bouton bouton-principal">
                Ouvrir l'écran Audience
              </Link>
            </div>
          )}
        </Carte>
      )}
    </>
  );
}
