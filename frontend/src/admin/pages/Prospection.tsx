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
import { Fragment, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiProspection as api,
  ErreurApi,
  type BilanAutomatisation,
  type Campagne,
  type EtatAutomatisation,
  type Message,
  type MessageAssistant,
  type Prospect,
  type ResultatRecherche,
  type StatutProspect,
} from "../apiProspection";
import { Bandeau, Carte, Chiffre, Pastille, Squelette, Vide } from "../../espace/composants/Interface";
import * as f from "../../espace/format";
import "./Prospection.css";

type Onglet =
  | "campagnes" | "prospects" | "assistant" | "valider" | "metriques" | "automatisation";

export function ProspectionAdmin() {
  const [onglet, setOnglet] = useState<Onglet>("campagnes");
  const { data: apercu } = useQuery({
    queryKey: ["prospection", "apercu"],
    queryFn: api.apercu,
    staleTime: 30_000,
  });

  const onglets: { cle: Onglet; libelle: string; pastille?: number }[] = [
    { cle: "campagnes", libelle: "Campagnes" },
    { cle: "prospects", libelle: "Prospects", pastille: apercu?.prospects },
    { cle: "assistant", libelle: "Assistant" },
    // Un envoi en échec attend une décision dans cet onglet : il se compte
    // avec ce qui est à valider, sinon rien ne le signale depuis les autres.
    {
      cle: "valider",
      libelle: "À valider",
      pastille: apercu ? apercu.a_valider + apercu.en_echec : undefined,
    },
    { cle: "metriques", libelle: "Métriques" },
    { cle: "automatisation", libelle: "Automatisation" },
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
            {o.pastille ? <span className="prospection-compteur">{o.pastille}</span> : null}
          </button>
        ))}
      </nav>

      {onglet === "campagnes" && <VueCampagnes />}
      {onglet === "prospects" && <VueProspects />}
      {onglet === "assistant" && <VueAssistant />}
      {onglet === "valider" && <VueValidation />}
      {onglet === "metriques" && <VueMetriques />}
      {onglet === "automatisation" && <VueAutomatisation />}
    </>
  );
}

// ── Onglet Automatisation : la prospection quotidienne, réglée par la cliente ─

const JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

/** Les réglages qu'on édite localement. `active` n'en fait PAS partie : la
 *  bascule enregistre aussitôt, l'écran n'affiche que l'état du serveur. */
interface ReglageLocal {
  prospects_par_jour: number;
  campagne_id: string | null;
  jours: number[];
}

const LIBELLE_ETAT_AUTO: Record<Exclude<EtatAutomatisation, "">, string> = {
  en_cours: "en cours",
  reussie: "réussie",
  partielle: "terminée avec des échecs",
  echouee: "en échec",
  interrompue: "interrompue — le traitement a été coupé avant la fin",
};

function tonEtatAuto(etat: EtatAutomatisation): "alerte" | "echec" | "succes" {
  if (etat === "reussie") return "succes";
  if (etat === "echouee" || etat === "interrompue") return "echec";
  return "alerte";
}

/** Le bilan d'une tentative, en une phrase lisible. */
function direLeBilan(b: BilanAutomatisation): string {
  const morceaux = [
    `${b.crees ?? 0} prospect(s) créé(s) sur ${b.proposees ?? 0} proposé(s)`,
    `${b.qualifies ?? 0} qualifié(s)`,
    `${b.rediges ?? 0} séquence(s) rédigée(s)`,
  ];
  if (b.deja_connues) morceaux.push(`${b.deja_connues} déjà connu(s)`);
  if (b.non_contactables) {
    morceaux.push(`${b.non_contactables} sans adresse utilisable (non rédigé)`);
  }
  if (b.echecs) morceaux.push(`${b.echecs} en échec`);
  return `${morceaux.join(" · ")}.`;
}

function VueAutomatisation() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [brouillon, setBrouillon] = useState<ReglageLocal | null>(null);

  const reglage = useQuery({
    queryKey: ["prospection", "automatisation"],
    queryFn: api.automatisation,
  });
  const { data: campagnes } = useQuery({
    queryKey: ["prospection", "campagnes"],
    queryFn: api.campagnes,
  });

  // On édite une copie locale, initialisée depuis le serveur.
  const serveur = reglage.data;
  const r: ReglageLocal | null = brouillon ?? (serveur
    ? {
        prospects_par_jour: serveur.prospects_par_jour,
        campagne_id: serveur.campagne_id,
        jours: serveur.jours,
      }
    : null);

  // Un seul chemin d'enregistrement, pour le bouton « Enregistrer » comme pour
  // la bascule : `active` est toujours DIT par l'appelant, jamais lu dans la
  // copie locale.
  const enregistrer = useMutation({
    mutationFn: (active: boolean) => api.reglerAutomatisation({ ...(r ?? {}), active }),
    onSuccess: (maj) => {
      setErreur("");
      setBrouillon(null);
      cache.setQueryData(["prospection", "automatisation"], maj);
      void cache.invalidateQueries({ queryKey: ["prospection", "automatisation"] });
    },
    onError: (c) => setErreur(c instanceof Error ? c.message : "Enregistrement impossible."),
  });

  if (reglage.isPending) return <Carte titre="Automatisation"><Squelette lignes={3} /></Carte>;
  if (!serveur || !r) {
    return (
      <Bandeau ton="echec">
        Les réglages de l'automatisation n'ont pas pu être chargés. Rechargez la page.
      </Bandeau>
    );
  }

  const maj = (p: Partial<ReglageLocal>) => setBrouillon({ ...r, ...p });
  // Le plafond vient du serveur, qui est seul à l'appliquer : l'écran écrivait
  // « max 50 » en dur pendant que la recherche en créait au plus 25.
  const maximum = serveur.prospects_par_jour_max;
  // Estimation avec Opus (le modèle de qualité des agents) : ~0,04 €/prospect.
  const coutJour = (r.prospects_par_jour * 0.04).toFixed(2);
  const etat = serveur.dernier_etat;

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      <Bandeau titre="Comment ça marche">
        Quand c'est <strong>activé</strong>, chaque jour l'assistant cherche vos prospects,
        les qualifie et <strong>prépare les e-mails en brouillon</strong> — vous n'avez plus
        qu'à les relire et valider dans « À valider ». <strong>Rien ne part sans vous.</strong>
        Désactivé, rien ne tourne (et rien n'est facturé).
      </Bandeau>

      <Carte
        titre="Prospection automatique quotidienne"
        action={
          // La bascule ENREGISTRE (audit du 19/11/2026). Elle ne changeait que
          // la copie locale : l'écran affichait « Activée ✓ » alors que rien
          // n'était activé tant qu'on n'avait pas cliqué « Enregistrer ». Le
          // libellé dit désormais l'état du SERVEUR, rien d'autre.
          <button
            type="button"
            className={
              serveur.active ? "bouton bouton-principal bouton-sm" : "bouton bouton-contour bouton-sm"
            }
            aria-pressed={serveur.active}
            disabled={enregistrer.isPending}
            title={
              serveur.active
                ? "Cliquer pour désactiver (enregistré aussitôt)"
                : "Cliquer pour activer (enregistré aussitôt)"
            }
            onClick={() => enregistrer.mutate(!serveur.active)}
          >
            {serveur.active ? "Activée ✓" : "Désactivée"}
          </button>
        }
      >
        <div className="prospection-reglage">
          <p className="carte-note">
            {serveur.active
              ? "L'automatisation tourne. Cliquez sur « Activée ✓ » pour l'arrêter : c'est enregistré aussitôt."
              : "L'automatisation est à l'arrêt. Cliquez sur « Désactivée » pour la lancer : c'est enregistré aussitôt, avec les réglages ci-dessous."}
          </p>
          <label className="prospection-etiquette">Campagne à prospecter</label>
          <select
            className="champ-saisie"
            aria-label="Campagne à prospecter"
            value={r.campagne_id ?? ""}
            onChange={(e) => maj({ campagne_id: e.target.value || null })}
          >
            <option value="">— choisir une campagne —</option>
            {(campagnes ?? []).map((c: Campagne) => (
              <option key={c.id} value={c.id}>{c.nom}</option>
            ))}
          </select>

          <label className="prospection-etiquette">Prospects par jour (max {maximum})</label>
          <input
            type="number"
            min={1}
            max={maximum}
            className="champ-saisie"
            style={{ maxWidth: 160 }}
            aria-label={`Prospects par jour, ${maximum} au plus`}
            value={r.prospects_par_jour}
            onChange={(e) =>
              maj({
                prospects_par_jour: Math.max(1, Math.min(Number(e.target.value) || 1, maximum)),
              })
            }
          />
          <p className="carte-note">≈ {coutJour}{"\u00a0"}€ d'IA par jour (préparation ; l'envoi reste quasi gratuit).</p>

          <label className="prospection-etiquette">Jours</label>
          <div className="prospection-jours">
            {JOURS.map((lib, i) => (
              <button
                key={i}
                type="button"
                className={r.jours.includes(i) ? "prospection-jour actif" : "prospection-jour"}
                onClick={() =>
                  maj({
                    jours: r.jours.includes(i)
                      ? r.jours.filter((j) => j !== i)
                      : [...r.jours, i].sort((a, b) => a - b),
                  })
                }
              >
                {lib}
              </button>
            ))}
          </div>

          <div className="prospection-actions" style={{ marginTop: "var(--e-3)" }}>
            <button
              type="button"
              className="bouton bouton-principal bouton-sm"
              disabled={enregistrer.isPending || brouillon === null}
              onClick={() => enregistrer.mutate(serveur.active)}
            >
              Enregistrer les réglages
            </button>
            {brouillon !== null && (
              <span className="carte-note">Modifications non enregistrées.</span>
            )}
          </div>
        </div>
      </Carte>

      {/* Ce qu'a donné la dernière tentative (audit du 19/11/2026) : une panne
          quotidienne ne se voyait nulle part, l'écran disait « Activée ✓ ». */}
      <Carte
        titre="Dernière exécution"
        note="La tâche tourne au plus une fois par jour, les jours cochés."
      >
        {serveur.derniere_tentative && etat ? (
          <Bandeau
            ton={tonEtatAuto(etat)}
            titre={`${f.dateHeure(serveur.derniere_tentative)} — ${LIBELLE_ETAT_AUTO[etat]}`}
          >
            <div>{direLeBilan(serveur.dernier_bilan)}</div>
            {serveur.derniere_erreur && (
              <div className="prospection-motif-echec">
                Dernière erreur : {serveur.derniere_erreur}
              </div>
            )}
            {(etat === "echouee" || etat === "interrompue") && (
              <div>
                Elle ne sera pas rejouée aujourd'hui. Vous pouvez lancer une recherche à la
                main depuis la campagne.
              </div>
            )}
          </Bandeau>
        ) : serveur.derniere_execution ? (
          <p className="carte-note">
            Dernière exécution : {f.dateHeure(serveur.derniere_execution)}
          </p>
        ) : (
          <p className="carte-note">Aucune exécution pour l'instant.</p>
        )}
      </Carte>
    </>
  );
}

// ── Onglet Prospects : le pipeline (identifier, filtrer, agir) ────────────────

const ETAPES: { code: StatutProspect | ""; libelle: string }[] = [
  { code: "", libelle: "Tous" },
  { code: "nouveau", libelle: "Nouveaux" },
  { code: "qualifie", libelle: "Qualifiés" },
  { code: "contacte", libelle: "Contactés" },
  { code: "en_relance", libelle: "En relance" },
  { code: "a_repondu", libelle: "Ont répondu" },
  { code: "converti", libelle: "Convertis" },
  { code: "exclu", libelle: "Exclus" },
  { code: "desinscrit", libelle: "Désinscrits" },
];

function VueProspects() {
  const [statut, setStatut] = useState<StatutProspect | "">("");
  const [campagneId, setCampagneId] = useState("");
  const [recherche, setRecherche] = useState("");
  const [ouvert, setOuvert] = useState<string | null>(null);

  const { data: apercu } = useQuery({
    queryKey: ["prospection", "apercu"],
    queryFn: api.apercu,
    staleTime: 15_000,
  });
  const { data: campagnes } = useQuery({
    queryKey: ["prospection", "campagnes"],
    queryFn: api.campagnes,
  });
  const prospects = useQuery({
    queryKey: ["prospection", "prospects", statut, campagneId],
    queryFn: () =>
      api.prospects({
        ...(statut ? { statut } : {}),
        ...(campagneId ? { campagne: campagneId } : {}),
      }),
  });

  const parStatut = apercu?.prospects_par_statut ?? {};
  const liste = (prospects.data ?? []).filter((p) =>
    p.raison_sociale.toLowerCase().includes(recherche.trim().toLowerCase()),
  );

  return (
    <>
      <nav className="prospection-etapes" aria-label="Étapes du pipeline">
        {ETAPES.map((e) => (
          <button
            key={e.code || "tous"}
            type="button"
            className={statut === e.code ? "prospection-etape actif" : "prospection-etape"}
            onClick={() => setStatut(e.code)}
          >
            {e.libelle}
            {e.code && parStatut[e.code] ? (
              <span className="prospection-compteur">{parStatut[e.code]}</span>
            ) : null}
          </button>
        ))}
      </nav>

      <Carte
        titre="Prospects"
        note="Cliquez sur un prospect pour voir sa fiche, ses e-mails envoyés et ses relances."
        action={
          <select
            className="champ-saisie"
            style={{ maxWidth: 220 }}
            aria-label="Filtrer par campagne"
            value={campagneId}
            onChange={(e) => setCampagneId(e.target.value)}
          >
            <option value="">Toutes les campagnes</option>
            {(campagnes ?? []).map((c: Campagne) => (
              <option key={c.id} value={c.id}>{c.nom}</option>
            ))}
          </select>
        }
      >
        <input
          className="champ-saisie"
          style={{ marginBottom: "var(--e-3)" }}
          placeholder="Rechercher par nom…"
          aria-label="Rechercher un prospect"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
        />
        {prospects.isPending ? (
          <Squelette lignes={4} />
        ) : liste.length === 0 ? (
          <Vide icone="◇" titre="Aucun prospect" texte="Ajustez les filtres, ou trouvez-en via une campagne." />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Prospect</th>
                  <th scope="col">Étape</th>
                  <th scope="col">Score</th>
                  <th scope="col"><span className="visuellement-cache">Ouvrir</span></th>
                </tr>
              </thead>
              <tbody>
                {liste.map((p) => (
                  <Fragment key={p.id}>
                    <tr>
                      <td>
                        <strong>{p.raison_sociale}</strong>
                        <div className="carte-note">{p.email || "sans e-mail"}</div>
                      </td>
                      <td><Pastille statut={p.statut} texte={libelleStatut(p.statut)} /></td>
                      <td>{p.score_adequation ?? "—"}</td>
                      <td>
                        <button
                          type="button"
                          className="bouton bouton-contour bouton-sm"
                          onClick={() => setOuvert(ouvert === p.id ? null : p.id)}
                        >
                          {ouvert === p.id ? "Fermer" : "Voir"}
                        </button>
                      </td>
                    </tr>
                    {ouvert === p.id && (
                      <tr>
                        <td colSpan={4}>
                          <FicheProspect prospectId={p.id} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>
    </>
  );
}

function libelleStatut(s: StatutProspect): string {
  return ETAPES.find((e) => e.code === s)?.libelle.replace(/s$/, "") ?? s;
}

function FicheProspect({ prospectId }: { prospectId: string }) {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [correction, setCorrection] = useState(false);
  const { data: p, isPending } = useQuery({
    queryKey: ["prospection", "prospect", prospectId],
    queryFn: () => api.prospect(prospectId),
  });

  const rafraichir = () => {
    setErreur("");
    void cache.invalidateQueries({ queryKey: ["prospection"] });
  };
  const surErreur = (c: unknown) =>
    setErreur(c instanceof Error ? c.message : "Action impossible.");

  const qualifier = useMutation({
    mutationFn: () => api.qualifier(prospectId), onSuccess: rafraichir, onError: surErreur,
  });
  const rediger = useMutation({
    mutationFn: () => api.rediger(prospectId), onSuccess: rafraichir, onError: surErreur,
  });
  const statut = useMutation({
    mutationFn: (s: StatutProspect) => api.changerStatut(prospectId, s),
    onSuccess: rafraichir, onError: surErreur,
  });
  const desinscrire = useMutation({
    mutationFn: () => api.desinscrire(prospectId), onSuccess: rafraichir, onError: surErreur,
  });

  if (isPending || !p) return <Squelette lignes={3} />;

  const envoyes = (p.messages ?? []).filter((m) => m.statut === "envoye");
  const enCours = (p.messages ?? []).filter((m) => m.statut !== "envoye" && m.statut !== "annule");

  return (
    <div className="prospection-fiche">
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}

      {/* Pourquoi on ne peut pas lui écrire — dit, au lieu de laisser un
          bouton « Rédiger » payer une séquence qui ne partira pas. */}
      {!p.contactable && p.motif_non_contact && (
        <Bandeau titre="Ce prospect ne peut pas recevoir de message">
          {p.motif_non_contact.charAt(0).toUpperCase() + p.motif_non_contact.slice(1)}.
        </Bandeau>
      )}

      <div className="prospection-fiche-infos">
        <Info libelle="E-mail" valeur={p.email} />
        <Info libelle="Secteur" valeur={p.secteur} />
        <Info libelle="Zone" valeur={p.zone} />
        <Info libelle="Contact" valeur={[p.nom_contact, p.fonction].filter(Boolean).join(" · ")} />
        <Info libelle="Site" valeur={p.site_web} />
        <Info libelle="Source" valeur={p.source} />
        <Info libelle="Score" valeur={p.score_adequation != null ? String(p.score_adequation) : "—"} />
      </div>
      {p.raison_score && (
        <p className="carte-note" style={{ marginTop: "var(--e-2)" }}>{p.raison_score}</p>
      )}
      {p.notes && (
        <p className="carte-note" style={{ marginTop: "var(--e-2)" }}>Notes : {p.notes}</p>
      )}

      {correction && (
        <FormulaireFiche
          prospect={p}
          onEnregistre={() => {
            setCorrection(false);
            rafraichir();
          }}
          onFermer={() => setCorrection(false)}
        />
      )}

      <div className="prospection-actions" style={{ marginTop: "var(--e-3)" }}>
        {!correction && (
          <button type="button" className="bouton bouton-contour bouton-sm"
            onClick={() => setCorrection(true)}>
            Corriger la fiche
          </button>
        )}
        <BoutonConfirme libelle="Qualifier" avertissement="Interroge l'IA (facturé)."
          enCours={qualifier.isPending} onConfirmer={() => qualifier.mutate()} />
        {p.contactable && (
          <BoutonConfirme libelle="Rédiger les e-mails" avertissement="Interroge l'IA (facturé)."
            enCours={rediger.isPending} onConfirmer={() => rediger.mutate()} />
        )}
        <button type="button" className="bouton bouton-contour bouton-sm"
          disabled={statut.isPending} onClick={() => statut.mutate("a_repondu")}>
          A répondu
        </button>
        <button type="button" className="bouton bouton-contour bouton-sm"
          disabled={statut.isPending} onClick={() => statut.mutate("converti")}>
          Converti
        </button>
        <BoutonConfirme libelle="Exclure" avertissement="Sort ce prospect de la prospection."
          enCours={statut.isPending} onConfirmer={() => statut.mutate("exclu")} />
        {/* Désinscrire reste offert tant que la fiche ne l'est pas — et surtout
            à qui n'est plus « contactable » : un prospect qui répond « STOP »
            est classé « a répondu », et c'est précisément lui qu'il faut
            pouvoir inscrire au registre des oppositions (relecture du
            19/11/2026). */}
        {p.statut !== "desinscrit" && (
          <BoutonConfirme libelle="Désinscrire" avertissement="Retire le consentement (irréversible)."
            enCours={desinscrire.isPending} onConfirmer={() => desinscrire.mutate()} />
        )}
      </div>

      <div className="prospection-fiche-mails">
        <h3 className="carte-titre" style={{ fontSize: "1rem" }}>
          E-mails envoyés ({envoyes.length})
        </h3>
        {envoyes.length === 0 ? (
          <p className="carte-note">Aucun e-mail encore envoyé.</p>
        ) : (
          envoyes.map((m) => <LigneMail key={m.id} message={m} />)
        )}
        <h3 className="carte-titre" style={{ fontSize: "1rem", marginTop: "var(--e-3)" }}>
          En cours — brouillons et relances ({enCours.length})
        </h3>
        {enCours.length === 0 ? (
          <p className="carte-note">Rien en préparation. « Rédiger les e-mails » prépare la séquence.</p>
        ) : (
          enCours.map((m) => <LigneMail key={m.id} message={m} />)
        )}
      </div>
    </div>
  );
}

/** Corriger une fiche : l'adresse, le contact, le site, les notes.
 *
 * Audit du 19/11/2026 : rien ne permettait de modifier un prospect. Une fiche
 * née sans adresse, ou avec une adresse qui rebondit, restait telle quelle.
 * Le serveur valide l'adresse et la refuse si elle n'en a pas la forme.
 */
function FormulaireFiche({
  prospect,
  onEnregistre,
  onFermer,
}: {
  prospect: Prospect;
  onEnregistre: () => void;
  onFermer: () => void;
}) {
  const [erreur, setErreur] = useState("");
  const [champs, setChamps] = useState({
    email: prospect.email,
    nom_contact: prospect.nom_contact,
    fonction: prospect.fonction,
    site_web: prospect.site_web,
    notes: prospect.notes,
  });
  const enregistrer = useMutation({
    mutationFn: () => api.modifierProspect(prospect.id, champs),
    onSuccess: onEnregistre,
    onError: (c) => setErreur(c instanceof Error ? c.message : "Enregistrement impossible."),
  });

  return (
    <div className="prospection-correction">
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      <label className="prospection-etiquette" htmlFor={`fiche-email-${prospect.id}`}>
        Adresse e-mail
      </label>
      <input
        id={`fiche-email-${prospect.id}`}
        type="email"
        className="champ-saisie"
        placeholder="contact@organisation.fr"
        autoComplete="off"
        value={champs.email}
        onChange={(e) => setChamps((c) => ({ ...c, email: e.target.value }))}
      />
      <div className="prospection-formulaire">
        <input
          className="champ-saisie"
          placeholder="Nom du contact"
          aria-label="Nom du contact"
          value={champs.nom_contact}
          onChange={(e) => setChamps((c) => ({ ...c, nom_contact: e.target.value }))}
        />
        <input
          className="champ-saisie"
          placeholder="Fonction"
          aria-label="Fonction du contact"
          value={champs.fonction}
          onChange={(e) => setChamps((c) => ({ ...c, fonction: e.target.value }))}
        />
        <input
          className="champ-saisie"
          placeholder="Site web"
          aria-label="Site web"
          value={champs.site_web}
          onChange={(e) => setChamps((c) => ({ ...c, site_web: e.target.value }))}
        />
      </div>
      <label className="prospection-etiquette" htmlFor={`fiche-notes-${prospect.id}`}>
        Notes
      </label>
      <textarea
        id={`fiche-notes-${prospect.id}`}
        className="champ-saisie prospection-corps"
        rows={3}
        value={champs.notes}
        onChange={(e) => setChamps((c) => ({ ...c, notes: e.target.value }))}
      />
      <div className="prospection-actions">
        <button
          type="button"
          className="bouton bouton-principal bouton-sm"
          disabled={enregistrer.isPending}
          onClick={() => enregistrer.mutate()}
        >
          Enregistrer la fiche
        </button>
        <button type="button" className="bouton bouton-contour bouton-sm" onClick={onFermer}>
          Fermer sans enregistrer
        </button>
      </div>
    </div>
  );
}

function Info({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <div className="prospection-info">
      <span className="prospection-info-libelle">{libelle}</span>
      <span>{valeur || "—"}</span>
    </div>
  );
}

function LigneMail({ message }: { message: Message }) {
  const quand = message.envoye_le || message.cree_le;
  return (
    <div className="prospection-ligne-mail">
      <div style={{ minWidth: 0 }}>
        <div className="prospection-ligne-mail-objet">{message.objet}</div>
        <div className="carte-note">{f.dateHeure(quand)}</div>
      </div>
      <Pastille statut={message.statut} texte={message.statut} />
    </div>
  );
}

// ── Onglet Assistant ─────────────────────────────────────────────────────────

function VueAssistant() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [campagneId, setCampagneId] = useState("");
  const [saisie, setSaisie] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [fil, setFil] = useState<MessageAssistant[]>([]);
  const [proposition, setProposition] = useState<{ criteres: string; limite: number } | null>(null);
  // Le dernier texte resté sans réponse (panne du modèle) : « Réessayer » le renvoie.
  const [aReessayer, setAReessayer] = useState<string | null>(null);

  const { data: campagnes } = useQuery({
    queryKey: ["prospection", "campagnes"],
    queryFn: api.campagnes,
  });
  const discussions = useQuery({
    queryKey: ["prospection", "conversations"],
    queryFn: () => api.conversations(),
  });

  function nouvelle() {
    setConversationId(null);
    setFil([]);
    setProposition(null);
    setErreur("");
    setAReessayer(null);
  }

  const rouvrir = useMutation({
    mutationFn: (id: string) => api.conversation(id),
    onSuccess: (c) => {
      setErreur("");
      setProposition(null);
      setAReessayer(null);
      setConversationId(c.id);
      setFil(c.messages);
    },
    onError: (c) => setErreur(c instanceof Error ? c.message : "Discussion introuvable."),
  });

  const envoyer = useMutation({
    mutationFn: (texte: string) =>
      api.assistant(texte, conversationId || undefined, campagneId || undefined),
    onSuccess: (rep) => {
      setErreur("");
      setAReessayer(null);
      setConversationId(rep.conversation_id);
      setFil(rep.messages); // la vérité vient du serveur (gardée en mémoire)
      setProposition(rep.proposition_recherche);
      void cache.invalidateQueries({ queryKey: ["prospection", "conversations"] });
    },
    // Une panne du modèle ne perd plus rien (audit du 19/11/2026). Le serveur
    // a enregistré le tour saisi AVANT d'appeler le modèle, et son 502 porte la
    // discussion : on y reste, le texte y est, et « Réessayer » le renvoie sans
    // le doubler. Si le serveur n'a rien reçu (coupure), le texte revient dans
    // la zone de saisie.
    onError: (c, texte) => {
      setErreur(c instanceof Error ? c.message : "L'assistant n'a pas répondu.");
      const charge = c instanceof ErreurApi ? c.charge : null;
      if (charge && typeof charge.conversation_id === "string") {
        setConversationId(charge.conversation_id);
        if (Array.isArray(charge.messages)) setFil(charge.messages as MessageAssistant[]);
        setAReessayer(texte);
        void cache.invalidateQueries({ queryKey: ["prospection", "conversations"] });
      } else {
        setFil((precedent) => precedent.slice(0, -1)); // retire l'écho immédiat
        setSaisie(texte);
      }
    },
  });

  const lancer = useMutation({
    mutationFn: () =>
      api.rechercher(campagneId, proposition?.limite ?? 10, proposition?.criteres ?? ""),
    onSuccess: (r) => {
      // Le même compte rendu que sur la campagne : le zéro se dit, avec sa cause.
      setFil((precedent) => [
        ...precedent,
        { role: "assistant", content: `J'ai lancé la recherche. ${direLaRecherche(r).texte}` },
      ]);
      setProposition(null);
      void cache.invalidateQueries({ queryKey: ["prospection"] });
    },
    onError: (c) => setErreur(c instanceof Error ? c.message : "Recherche impossible."),
  });

  function soumettre() {
    const texte = saisie.trim();
    if (!texte || envoyer.isPending) return;
    setFil((precedent) => [...precedent, { role: "user", content: texte }]); // écho immédiat
    setSaisie("");
    setAReessayer(null);
    envoyer.mutate(texte);
  }

  return (
    <>
      {erreur && (
        <Bandeau ton="echec">
          {erreur}
          {aReessayer && (
            <div className="prospection-actions" style={{ marginTop: "var(--e-2)" }}>
              <span className="carte-note">Votre message est gardé dans la discussion.</span>
              <button
                type="button"
                className="bouton bouton-contour bouton-sm"
                disabled={envoyer.isPending}
                onClick={() => envoyer.mutate(aReessayer)}
              >
                Réessayer
              </button>
            </div>
          )}
        </Bandeau>
      )}

      <Carte
        titre="Vos discussions"
        note="Elles sont gardées en mémoire : rouvrez-en une pour la continuer."
        action={
          <button type="button" className="bouton bouton-principal bouton-sm" onClick={nouvelle}>
            + Nouvelle discussion
          </button>
        }
      >
        {!discussions.data || discussions.data.length === 0 ? (
          <p className="carte-note">Aucune discussion pour l'instant.</p>
        ) : (
          <div className="prospection-discussions">
            {discussions.data.map((d) => (
              <button
                key={d.id}
                type="button"
                className={
                  d.id === conversationId
                    ? "prospection-discussion actif"
                    : "prospection-discussion"
                }
                onClick={() => rouvrir.mutate(d.id)}
              >
                <span className="prospection-discussion-titre">{d.titre || "Sans titre"}</span>
                <span className="carte-note">{d.nb_messages} message(s) · {f.dateHeure(d.maj_le)}</span>
              </button>
            ))}
          </div>
        )}
      </Carte>

      <Carte
        titre="Assistant de prospection"
        note="Discutez pour affiner votre cible ; il proposera une recherche à lancer."
        action={
          <select
            className="champ-saisie"
            style={{ maxWidth: 240 }}
            aria-label="Campagne de rattachement"
            value={campagneId}
            onChange={(e) => setCampagneId(e.target.value)}
          >
            <option value="">Sans campagne</option>
            {(campagnes ?? []).map((c: Campagne) => (
              <option key={c.id} value={c.id}>{c.nom}</option>
            ))}
          </select>
        }
      >
        <div className="prospection-fil">
          {fil.length === 0 && (
            <Vide
              icone="◎"
              titre="Dites-lui qui vous cherchez"
              texte="Par exemple : « Des cabinets RH à Lyon qui recrutent en ce moment »."
            />
          )}
          {fil.map((m, i) => (
            <div
              key={i}
              className={m.role === "user" ? "prospection-bulle vous" : "prospection-bulle assistant"}
            >
              {m.content}
            </div>
          ))}
          {envoyer.isPending && <div className="prospection-bulle assistant">…</div>}
        </div>

        {proposition && (
          <Bandeau ton="succes" titre="Recherche proposée">
            <div>{proposition.criteres}</div>
            <div className="prospection-actions" style={{ marginTop: "var(--e-2)" }}>
              <BoutonConfirme
                libelle={campagneId ? "Lancer cette recherche" : "Choisissez d'abord une campagne"}
                avertissement="Interroge l'IA et la recherche web (facturé)."
                principal
                enCours={lancer.isPending || !campagneId}
                onConfirmer={() => campagneId && lancer.mutate()}
              />
            </div>
          </Bandeau>
        )}

        <div className="prospection-saisie">
          <textarea
            className="champ-saisie prospection-corps"
            rows={2}
            aria-label="Votre message à l'assistant"
            placeholder="Écrivez à l'assistant…"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                soumettre();
              }
            }}
          />
          <button
            type="button"
            className="bouton bouton-principal bouton-sm"
            disabled={envoyer.isPending || !saisie.trim()}
            onClick={soumettre}
          >
            Envoyer
          </button>
        </div>
      </Carte>
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

      {/* `key` : changer de campagne repart d'un panneau neuf — sinon le résultat
          de la recherche d'une campagne s'afficherait sous la suivante. */}
      {choisie && <PanneauCampagne key={choisie} campagneId={choisie} />}
    </>
  );
}

/** Ce qu'une recherche a donné, dit en clair — y compris quand c'est zéro.
 *
 * Audit du 19/11/2026 : l'écran n'affichait RIEN après une recherche. Zéro
 * prospect se confondait avec « le bouton n'a pas marché », alors que c'est
 * souvent voulu (une cible hors des cibles d'EVKHA ne ramène personne). Le
 * serveur distingue trois zéros ; on les dit séparément.
 */
function direLaRecherche(r: ResultatRecherche): { ton: "succes" | "alerte"; texte: string } {
  if (r.crees > 0) {
    const morceaux = [`${r.crees} prospect(s) créé(s)`];
    if (r.deja_connues) morceaux.push(`${r.deja_connues} déjà connu(s), écarté(s)`);
    if (r.sans_adresse) {
      morceaux.push(`${r.sans_adresse} sans adresse : complétez la fiche avant de rédiger`);
    }
    return { ton: "succes", texte: `${morceaux.join(" · ")}.` };
  }
  if (r.proposees > 0) {
    return {
      ton: "alerte",
      texte: `Aucun nouveau prospect : les ${r.proposees} organisation(s) trouvée(s) sont déjà dans la campagne.`,
    };
  }
  return {
    ton: "alerte",
    texte:
      "Aucune organisation correspondant aux cibles d'EVKHA n'a été trouvée pour cette campagne. " +
      "Affinez le secteur ou la zone, ou ajoutez un prospect à la main.",
  };
}

/** Ajouter un prospect à la main, dans une campagne.
 *
 * L'écran disait « ou ajoutez-les à la main » sans offrir de quoi le faire :
 * `creerProspect` n'était appelé nulle part (audit du 19/11/2026).
 */
function FormulaireAjout({ campagneId, onAjoute }: { campagneId: string; onAjoute: () => void }) {
  const vide = { raison_sociale: "", email: "", nom_contact: "", fonction: "", site_web: "" };
  const [erreur, setErreur] = useState("");
  const [fiche, setFiche] = useState(vide);
  const ajouter = useMutation({
    mutationFn: () => api.creerProspect({ ...fiche, campagne_id: campagneId, source: "manuel" }),
    onSuccess: () => {
      setErreur("");
      setFiche(vide);
      onAjoute();
    },
    onError: (c) => setErreur(c instanceof Error ? c.message : "Ajout impossible."),
  });

  return (
    <div className="prospection-ajout">
      <h3 className="carte-titre" style={{ fontSize: "1rem" }}>Ajouter un prospect à la main</h3>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      <div className="prospection-formulaire">
        <input
          className="champ-saisie"
          placeholder="Raison sociale *"
          aria-label="Raison sociale"
          value={fiche.raison_sociale}
          onChange={(e) => setFiche((p) => ({ ...p, raison_sociale: e.target.value }))}
        />
        <input
          type="email"
          className="champ-saisie"
          placeholder="Adresse e-mail"
          aria-label="Adresse e-mail"
          autoComplete="off"
          value={fiche.email}
          onChange={(e) => setFiche((p) => ({ ...p, email: e.target.value }))}
        />
        <input
          className="champ-saisie"
          placeholder="Nom du contact"
          aria-label="Nom du contact"
          value={fiche.nom_contact}
          onChange={(e) => setFiche((p) => ({ ...p, nom_contact: e.target.value }))}
        />
        <input
          className="champ-saisie"
          placeholder="Fonction"
          aria-label="Fonction du contact"
          value={fiche.fonction}
          onChange={(e) => setFiche((p) => ({ ...p, fonction: e.target.value }))}
        />
        <input
          className="champ-saisie"
          placeholder="Site web"
          aria-label="Site web"
          value={fiche.site_web}
          onChange={(e) => setFiche((p) => ({ ...p, site_web: e.target.value }))}
        />
        <button
          type="button"
          className="bouton bouton-principal bouton-sm"
          disabled={ajouter.isPending || !fiche.raison_sociale.trim()}
          onClick={() => ajouter.mutate()}
        >
          Ajouter
        </button>
      </div>
    </div>
  );
}

function PanneauCampagne({ campagneId }: { campagneId: string }) {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [bilan, setBilan] = useState<{ ton: "succes" | "alerte"; texte: string } | null>(null);
  const { data, isPending } = useQuery({
    queryKey: ["prospection", "campagne", campagneId],
    queryFn: () => api.campagne(campagneId),
  });

  const rafraichir = () => {
    void cache.invalidateQueries({ queryKey: ["prospection"] });
  };

  const rechercher = useMutation({
    mutationFn: () => api.rechercher(campagneId, 10),
    onSuccess: (r) => {
      setErreur("");
      setBilan(direLaRecherche(r));
      rafraichir();
    },
    onError: (c) => {
      setBilan(null);
      setErreur(c instanceof Error ? c.message : "Recherche impossible.");
    },
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
      {bilan && <Bandeau ton={bilan.ton} titre="Résultat de la recherche">{bilan.texte}</Bandeau>}
      {data.prospects_liste.length === 0 ? (
        <Vide
          icone="◇"
          titre="Aucun prospect"
          texte="« Trouver des prospects » lance l'agent de recherche ; vous pouvez aussi en ajouter à la main, ci-dessous."
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
                      {/* On ne rédige (appel payant) que pour une fiche à qui
                          l'on peut écrire ; sinon on dit pourquoi. */}
                      {p.contactable ? (
                        <BoutonConfirme
                          libelle="Rédiger"
                          avertissement="Interroge l'IA (facturé)."
                          enCours={rediger.isPending}
                          onConfirmer={() => rediger.mutate(p.id)}
                        />
                      ) : (
                        <span className="carte-note">
                          Pas de rédaction : {p.motif_non_contact ?? "prospect non contactable"}.
                        </span>
                      )}
                      {p.statut !== "desinscrit" && (
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
      <FormulaireAjout campagneId={campagneId} onAjoute={rafraichir} />
    </Carte>
  );
}

// ── Onglet À valider ─────────────────────────────────────────────────────────

/** Les étapes présentes dans la file, dans l'ordre de la séquence. */
function etapesPresentes(messages: Message[]): number[] {
  return [...new Set(messages.map((m) => m.etape))].sort((a, b) => a - b);
}

function libelleEtape(etape: number): string {
  return etape === 0 ? "Premiers mails" : `Relance ${etape}`;
}

function VueValidation() {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [bilan, setBilan] = useState("");
  const [par, setPar] = useState("administrateur");
  // `null` = toutes les étapes. On ouvre sur les premiers mails : c'est par eux
  // que la séquence commence, les relances ne viennent qu'à leur tour.
  const [etape, setEtape] = useState<number | null>(0);

  // Seulement ce qui est À SON TOUR : une relance n'apparaît qu'une fois
  // l'étape d'avant envoyée et son délai écoulé (le serveur en décide).
  const brouillons = useQuery({
    queryKey: ["prospection", "messages", "brouillon", "prets"],
    queryFn: () => api.messages({ statut: "brouillon", pret: "1" }),
  });
  const valides = useQuery({
    queryKey: ["prospection", "messages", "valide"],
    queryFn: () => api.messages({ statut: "valide" }),
  });
  // Les envois que le fournisseur a refusés (audit du 19/11/2026). L'écran ne
  // chargeait que les brouillons prêts et les validés : un message en échec
  // disparaissait, sans motif ni bouton, et ses relances attendaient sans fin.
  const echecs = useQuery({
    queryKey: ["prospection", "messages", "echoue"],
    queryFn: () => api.messages({ statut: "echoue" }),
  });
  const { data: apercu } = useQuery({
    queryKey: ["prospection", "apercu"],
    queryFn: api.apercu,
  });

  const rafraichir = () => {
    setErreur("");
    setBilan("");
    void cache.invalidateQueries({ queryKey: ["prospection"] });
  };
  const surErreur = (c: unknown) =>
    setErreur(c instanceof Error ? c.message : "Action impossible.");
  const dire = (fait: string, refus: string[]) => {
    // Résumé, pas une liste de cent lignes : les « pas encore à son tour » se
    // comptent, les autres refus se nomment.
    const attente = refus.filter((r) => r.endsWith("pas encore à son tour")).length;
    const autres = refus.filter((r) => !r.endsWith("pas encore à son tour"));
    const morceaux = [fait];
    if (attente) morceaux.push(`${attente} pas encore à leur tour.`);
    if (autres.length) morceaux.push(`Non traités : ${autres.join(" · ")}`);
    rafraichir();
    setBilan(morceaux.join(" "));
  };

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
  const remettre = useMutation({
    mutationFn: (id: string) => api.remettreEnBrouillon(id),
    onSuccess: rafraichir,
    onError: surErreur,
  });
  const validerTout = useMutation({
    mutationFn: (ids: string[]) => api.validerLot(par, ids),
    onSuccess: (r) => dire(`${r.valides} message(s) validé(s).`, r.refus),
    onError: surErreur,
  });
  const envoyerTout = useMutation({
    mutationFn: (ids: string[]) => api.envoyerLot(ids),
    onSuccess: (r) => dire(`${r.envoyes} message(s) envoyé(s).`, r.refus),
    onError: surErreur,
  });

  const tousBrouillons = brouillons.data ?? [];
  const tousValides = valides.data ?? [];
  // TOUS les échecs, quelle que soit l'étape affichée : un échec ne se cache
  // pas derrière un filtre.
  const enEchec = echecs.data ?? [];
  const filtre = (m: Message) => etape === null || m.etape === etape;
  const aValider = tousBrouillons.filter(filtre);
  const aEnvoyer = tousValides.filter(filtre);
  const envoyables = aEnvoyer.filter((m) => m.pret);
  const presentes = etapesPresentes([...tousBrouillons, ...tousValides]);
  const etapes = presentes.includes(0) ? presentes : [0, ...presentes];
  const portee = etape === null ? "toutes étapes" : libelleEtape(etape).toLowerCase();

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {bilan && <Bandeau ton="succes">{bilan}</Bandeau>}
      <Bandeau titre="Rien ne part sans vous">
        Les <strong>premiers mails</strong> se valident d'abord. Chaque relance n'apparaît
        ici qu'une fois le message précédent <strong>envoyé</strong> et son délai écoulé
        {apercu?.relances_en_attente
          ? ` — ${apercu.relances_en_attente} relance(s) déjà rédigée(s) attendent leur tour`
          : ""}
        . L'envoi part <strong>réellement</strong> au destinataire.
      </Bandeau>

      <nav className="prospection-onglets" aria-label="Étape de la séquence">
        <button
          type="button"
          className={etape === null ? "prospection-onglet actif" : "prospection-onglet"}
          aria-pressed={etape === null}
          onClick={() => setEtape(null)}
        >
          Toutes
        </button>
        {etapes.map((e) => {
          const nombre = tousBrouillons.filter((m) => m.etape === e).length;
          return (
            <button
              key={e}
              type="button"
              className={etape === e ? "prospection-onglet actif" : "prospection-onglet"}
              aria-pressed={etape === e}
              onClick={() => setEtape(e)}
            >
              {libelleEtape(e)}
              {nombre ? (
                <span className="prospection-compteur">
                  {nombre}
                  <span className="visuellement-cache"> à valider</span>
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      {echecs.isError && (
        <Bandeau ton="echec">Les envois en échec n'ont pas pu être chargés. Rechargez la page.</Bandeau>
      )}
      {enEchec.length > 0 && (
        <Carte
          ton="echec"
          titre={`En échec (${enEchec.length})`}
          note="Le fournisseur d'e-mails a refusé ces envois. Tant qu'un message reste ici, ses relances attendent."
        >
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Étape</th>
                  <th scope="col">Prospect</th>
                  <th scope="col">Objet</th>
                  <th scope="col">Motif du refus</th>
                  <th scope="col"><span className="visuellement-cache">Décider</span></th>
                </tr>
              </thead>
              <tbody>
                {enEchec.map((m) => (
                  <tr key={m.id}>
                    <td>{m.etape_libelle}</td>
                    <td>{m.prospect_nom}</td>
                    <td>{m.objet}</td>
                    <td className="prospection-motif-echec">
                      {m.error_message || "Motif non communiqué par le fournisseur."}
                    </td>
                    <td>
                      <div className="prospection-actions">
                        <button
                          type="button"
                          className="bouton bouton-principal bouton-sm"
                          disabled={valider.isPending || !par.trim()}
                          title="Revalide le message tel quel : il repasse dans « Validés, prêts à envoyer »."
                          onClick={() => valider.mutate(m.id)}
                        >
                          Revalider
                        </button>
                        <button
                          type="button"
                          className="bouton bouton-contour bouton-sm"
                          disabled={remettre.isPending}
                          title="Le message redevient un brouillon, à retoucher puis valider."
                          onClick={() => remettre.mutate(m.id)}
                        >
                          Remettre en brouillon
                        </button>
                        <BoutonConfirme
                          libelle="Annuler"
                          avertissement="Retire ce message : ses relances ne partiront pas."
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
        </Carte>
      )}

      <Carte
        titre={`À valider — ${portee}`}
        note="Relisez, ajustez, puis validez. La validation est nominative."
        action={
          <div className="prospection-actions">
            <input
              className="champ-saisie"
              style={{ maxWidth: 220 }}
              aria-label="Nom du validateur"
              placeholder="Validé par…"
              value={par}
              onChange={(e) => setPar(e.target.value)}
            />
            {aValider.length > 0 && (
              <BoutonConfirme
                libelle={`Tout valider (${aValider.length})`}
                avertissement={`Valide les ${aValider.length} message(s) affichés. Rien ne part encore.`}
                principal
                enCours={validerTout.isPending || !par.trim()}
                onConfirmer={() => validerTout.mutate(aValider.map((m) => m.id))}
              />
            )}
          </div>
        }
      >
        {brouillons.isPending ? (
          <Squelette lignes={3} />
        ) : brouillons.isError ? (
          <Bandeau ton="echec">La file n'a pas pu être chargée. Rechargez la page.</Bandeau>
        ) : aValider.length === 0 ? (
          <Vide
            icone="✓"
            titre="Rien à valider à cette étape"
            texte="Une relance apparaît ici une fois le message précédent envoyé."
          />
        ) : (
          aValider.map((m) => (
            <CarteBrouillon
              key={m.id}
              message={m}
              par={par}
              enCours={valider.isPending || annuler.isPending || validerTout.isPending}
              onValider={() => valider.mutate(m.id)}
              onAnnuler={() => annuler.mutate(m.id)}
              onEnregistre={rafraichir}
              onErreur={surErreur}
            />
          ))
        )}
      </Carte>

      <Carte
        titre={`Validés, prêts à envoyer — ${portee}`}
        note="L'envoi part réellement au destinataire."
        action={
          envoyables.length > 0 ? (
            <BoutonConfirme
              libelle={`Tout envoyer (${envoyables.length})`}
              avertissement={`Envoie RÉELLEMENT ${envoyables.length} e-mail(s) aux destinataires.`}
              principal
              enCours={envoyerTout.isPending}
              onConfirmer={() => envoyerTout.mutate(envoyables.map((m) => m.id))}
            />
          ) : null
        }
      >
        {valides.isPending ? (
          <Squelette lignes={2} />
        ) : valides.isError ? (
          <Bandeau ton="echec">Les messages validés n'ont pas pu être chargés.</Bandeau>
        ) : aEnvoyer.length === 0 ? (
          <Vide icone="◇" titre="Rien en attente d'envoi" />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Étape</th>
                  <th scope="col">Prospect</th>
                  <th scope="col">Objet</th>
                  <th scope="col">Validé par</th>
                  <th scope="col"><span className="visuellement-cache">Envoyer</span></th>
                </tr>
              </thead>
              <tbody>
                {aEnvoyer.map((m) => (
                  <tr key={m.id}>
                    <td>{m.etape_libelle}</td>
                    <td>{m.prospect_nom}</td>
                    <td>{m.objet}</td>
                    <td>{m.valide_par || "—"}</td>
                    <td>
                      <div className="prospection-actions">
                        {m.pret ? (
                          <BoutonConfirme
                            libelle="Envoyer"
                            avertissement="Envoie réellement l'e-mail au destinataire."
                            principal
                            enCours={envoyer.isPending || envoyerTout.isPending}
                            onConfirmer={() => envoyer.mutate(m.id)}
                          />
                        ) : (
                          <span className="carte-note">
                            {m.disponible_le
                              ? `À partir du ${new Date(m.disponible_le).toLocaleString("fr-FR", {
                                  dateStyle: "short",
                                  timeStyle: "short",
                                })}`
                              : "Après l'étape précédente"}
                          </span>
                        )}
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

/** Le document affiché dans le cadre d'aperçu d'un brouillon.
 *
 * Le corps est écrit par un modèle à partir de pages web qu'il a lues : c'est
 * une entrée EXTERNE, pas « notre propre brouillon ». Il était injecté tel quel
 * dans la page de l'espace admin (audit du 19/11/2026) — un `<img onerror>` ou
 * un `<script>` glissé dans une page lue par l'agent s'exécutait avec la
 * session de l'administratrice.
 *
 * Il vit désormais dans un cadre `sandbox` sans aucune permission : pas de
 * script, pas de formulaire, pas d'accès à l'origine de la page. La politique
 * de contenu, placée AVANT le corps, coupe en plus tout chargement extérieur
 * (une image distante trahirait l'ouverture de l'aperçu), et `<base
 * target="_blank">` neutralise les liens — les fenêtres sont interdites au
 * cadre.
 */
function documentApercu(corps: string): string {
  return [
    '<!doctype html><html lang="fr"><head><meta charset="utf-8">',
    `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`,
    '<base target="_blank">',
    "<style>body{margin:0;padding:16px 18px;font:15px/1.6 -apple-system,BlinkMacSystemFont,",
    "'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#2a2a2a;background:#fff}",
    "p{margin:0 0 .75em}p:last-child{margin-bottom:0}</style>",
    `</head><body>${corps}</body></html>`,
  ].join("");
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
  const [edition, setEdition] = useState(false);
  const modifie = objet !== message.objet || corps !== message.corps;

  const enregistrer = useMutation({
    mutationFn: () => api.editerBrouillon(message.id, { objet, corps }),
    onSuccess: () => {
      setEdition(false);
      onEnregistre();
    },
    onError: onErreur,
  });

  return (
    <div className="prospection-brouillon">
      {edition ? (
        <>
          <label className="prospection-etiquette">Objet</label>
          <input
            className="champ-saisie"
            aria-label="Objet du message"
            value={objet}
            onChange={(e) => setObjet(e.target.value)}
          />
          <label className="prospection-etiquette">
            Corps (mise en forme HTML — l'aperçu montre le rendu)
          </label>
          <textarea
            className="champ-saisie prospection-corps"
            aria-label="Corps du message"
            rows={8}
            value={corps}
            onChange={(e) => setCorps(e.target.value)}
          />
        </>
      ) : (
        <div className="prospection-apercu-mail">
          <div className="carte-note">
            {message.etape_libelle} · {message.prospect_nom}
            {message.prospect_contact ? ` (${message.prospect_contact})` : ""}
          </div>
          <div className="prospection-apercu-objet">{message.objet}</div>
          {/* Aperçu du rendu, dans un cadre isolé : voir `documentApercu`. */}
          <iframe
            className="prospection-apercu-cadre"
            title={`Aperçu du message « ${message.objet} »`}
            sandbox=""
            referrerPolicy="no-referrer"
            srcDoc={documentApercu(message.corps)}
          />
        </div>
      )}
      <div className="prospection-actions">
        {edition ? (
          <>
            <button
              type="button"
              className="bouton bouton-principal bouton-sm"
              disabled={!modifie || enregistrer.isPending}
              onClick={() => enregistrer.mutate()}
            >
              Enregistrer
            </button>
            <button
              type="button"
              className="bouton bouton-contour bouton-sm"
              onClick={() => {
                setObjet(message.objet);
                setCorps(message.corps);
                setEdition(false);
              }}
            >
              Retour à l'aperçu
            </button>
          </>
        ) : (
          <button
            type="button"
            className="bouton bouton-contour bouton-sm"
            onClick={() => setEdition(true)}
          >
            Modifier
          </button>
        )}
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
            detail={`${data.plaintes} plainte(s) · ${data.retards} remise(s) retardée(s), non comptées en rebond`}
          />
        </div>
      </Carte>
    </>
  );
}
