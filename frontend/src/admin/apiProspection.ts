/** Client d'API de la prospection (`/api/dashboard/prospection/`).
 *
 * Module séparé du gros `admin/api.ts` : les deux parlent au même dashboard,
 * avec le même jeton partagé, mais la prospection a ses propres types et son
 * verbe PUT (séquence, édition d'un brouillon). Isolé pour ne pas faire grossir
 * encore un fichier déjà dense.
 */
import { clearToken, getToken } from "../auth";

const BASE = import.meta.env.VITE_API_URL ?? "";
const RACINE = "/api/dashboard/prospection";

function entetes(json = true): HeadersInit {
  return {
    Accept: "application/json",
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
  };
}

/** Un refus du serveur, AVEC sa charge.
 *
 * Une `Error` nue ne gardait que le message. Or l'assistant, quand le modèle
 * tombe, rend dans son 502 l'identifiant de la discussion et le tour déjà
 * enregistré : sans la charge, l'écran perdait la discussion et le texte saisi
 * (audit du 19/11/2026). Reste une `Error` : tout `c instanceof Error` existant
 * continue de lire `message`.
 */
export class ErreurApi extends Error {
  readonly statut: number;
  readonly charge: Record<string, unknown>;

  constructor(message: string, statut: number, charge: Record<string, unknown>) {
    super(message);
    this.name = "ErreurApi";
    this.statut = statut;
    this.charge = charge;
  }
}

async function lire<T>(reponse: Response): Promise<T> {
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Non autorisé");
  }
  if (!reponse.ok) {
    const brut: unknown = await reponse.json().catch(() => ({}));
    const charge: Record<string, unknown> =
      typeof brut === "object" && brut !== null ? (brut as Record<string, unknown>) : {};
    const message =
      typeof charge.erreur === "string" ? charge.erreur : `Erreur ${reponse.status}`;
    throw new ErreurApi(message, reponse.status, charge);
  }
  return (await reponse.json()) as T;
}

function get<T>(chemin: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${RACINE}${chemin}`, window.location.origin);
  if (params) Object.entries(params).forEach(([c, v]) => v && url.searchParams.set(c, v));
  return fetch(url.toString(), { headers: entetes(false) }).then((r) => lire<T>(r));
}

function envoyer<T>(methode: string, chemin: string, corps?: unknown): Promise<T> {
  return fetch(`${BASE}${RACINE}${chemin}`, {
    method: methode,
    headers: entetes(),
    body: corps === undefined ? undefined : JSON.stringify(corps),
  }).then((r) => lire<T>(r));
}

// ── Types ────────────────────────────────────────────────────────────────────

export type StatutProspect =
  | "nouveau" | "qualifie" | "contacte" | "en_relance"
  | "a_repondu" | "converti" | "exclu" | "desinscrit";

export type StatutMessage =
  | "brouillon" | "valide" | "programme" | "envoye" | "echoue" | "annule";

export interface Campagne {
  id: string;
  nom: string;
  secteur: string;
  zone: string;
  offre_visee: string;
  statut: string;
  notes: string;
  cree_par: string;
  cree_le: string;
  prospects: number;
}

export interface EtapeSequence {
  id: string;
  ordre: number;
  delai_jours: number;
  est_une_relance: boolean;
  objet_gabarit: string;
  corps_gabarit: string;
}

export interface Prospect {
  id: string;
  campagne_id: string | null;
  raison_sociale: string;
  secteur: string;
  zone: string;
  email: string;
  nom_contact: string;
  fonction: string;
  site_web: string;
  source: string;
  statut: StatutProspect;
  score_adequation: number | null;
  raison_score: string;
  /** Peut-on lui écrire ? Jugé par le serveur (`services.motif_de_non_contact`). */
  contactable: boolean;
  /** Pourquoi on ne peut pas lui écrire, en clair — `null` s'il est contactable. */
  motif_non_contact: string | null;
  /** L'ADRESSE est interdite, toutes fiches confondues : opposition ou rebond. */
  adresse_interdite: "desinscription" | "plainte" | "rebond_definitif" | null;
  desinscrit_le: string | null;
  notes: string;
  cree_le: string;
  messages?: Message[];
}

export interface Message {
  id: string;
  /** 0 = premier message, 1, 2… = relances. */
  etape: number;
  etape_libelle: string;
  /** Peut partir maintenant : premier message, ou étape d'avant envoyée et délai écoulé. */
  pret: boolean;
  /** L'étape d'avant n'a plus de message vivant : il ne partira jamais seul. */
  rompue: boolean;
  disponible_le: string | null;
  prospect_nom: string;
  prospect_contact: string;
  prospect_id: string;
  campagne_id: string | null;
  sequence_id: string | null;
  objet: string;
  corps: string;
  statut: StatutMessage;
  valide_par: string;
  valide_le: string | null;
  programme_pour: string | null;
  envoye_le: string | null;
  provider_message_id: string;
  /** Le motif du refus du fournisseur, pour un message `echoue`. */
  error_message: string;
  /** L'adresse où le message est réellement parti ("" tant qu'il n'est pas envoyé). */
  destinataire: string;
  envoyable: boolean;
  cree_le: string;
}

export interface Apercu {
  campagnes_actives: number;
  prospects: number;
  prospects_par_statut: Record<string, number>;
  a_valider: number;
  /** Relances rédigées d'avance qui attendent l'envoi de l'étape d'avant. */
  relances_en_attente: number;
  valides_en_attente: number;
  /** Envois refusés par le fournisseur, qui attendent une décision. */
  en_echec: number;
  envoyes: number;
}

export interface Metriques {
  envoyes: number;
  ouvertures: number;
  ouvertures_total: number;
  taux_ouverture: number;
  clics: number;
  taux_clic: number;
  reponses: number;
  taux_reponse: number;
  /** Rebonds DÉFINITIFS et non-remis ; les simples retards sont comptés à part. */
  rebonds: number;
  retards: number;
  plaintes: number;
  desinscriptions: number;
  prospects_contactes: number;
  conversions: number;
  taux_conversion: number;
}

export interface CampagneDetail extends Campagne {
  sequence: EtapeSequence[];
  prospects_liste: Prospect[];
}

export interface MessageAssistant {
  role: "user" | "assistant";
  content: string;
}

export interface PropositionRecherche {
  criteres: string;
  limite: number;
}

export interface ReponseAssistant {
  conversation_id: string;
  reponse: string;
  proposition_recherche: PropositionRecherche | null;
  messages: MessageAssistant[];
}

export interface ResumeConversation {
  id: string;
  titre: string;
  campagne_id: string | null;
  cree_par: string;
  maj_le: string;
  nb_messages: number;
}

export interface ConversationDetail extends ResumeConversation {
  messages: MessageAssistant[];
}

/** Ce qu'une recherche a rendu : le zéro se DIT, et il a trois causes. */
export interface ResultatRecherche {
  crees: number;
  /** Organisations proposées par le modèle, avant dédoublonnage. */
  proposees: number;
  /** Écartées : déjà dans la campagne (nom, site ou adresse). */
  deja_connues: number;
  /** Créées sans adresse : à compléter avant toute rédaction. */
  sans_adresse: number;
  prospects: Prospect[];
}

/** Les champs d'une fiche qu'un humain corrige. */
export interface CorrectionProspect {
  raison_sociale?: string;
  secteur?: string;
  zone?: string;
  email?: string;
  nom_contact?: string;
  fonction?: string;
  site_web?: string;
  notes?: string;
}

export type EtatAutomatisation =
  | "" | "en_cours" | "reussie" | "partielle" | "echouee" | "interrompue";

export interface BilanAutomatisation {
  proposees?: number;
  crees?: number;
  deja_connues?: number;
  qualifies?: number;
  rediges?: number;
  non_contactables?: number;
  echecs?: number;
}

export interface Automatisation {
  active: boolean;
  prospects_par_jour: number;
  /** Le plafond réellement appliqué par le serveur — l'écran n'en recopie aucun. */
  prospects_par_jour_max: number;
  campagne_id: string | null;
  jours: number[];
  derniere_execution: string | null;
  /** La dernière TENTATIVE (réussie ou non), son état, son bilan, son erreur. */
  derniere_tentative: string | null;
  dernier_etat: EtatAutomatisation;
  dernier_bilan: BilanAutomatisation;
  derniere_erreur: string;
}

/** Ce que l'écran ENVOIE pour régler l'automatisation. */
export interface ReglageAutomatisation {
  active?: boolean;
  prospects_par_jour?: number;
  campagne_id?: string | null;
  jours?: number[];
}

// ── Méthodes ──────────────────────────────────────────────────────────────────

export const apiProspection = {
  apercu: () => get<Apercu>("/apercu/"),
  metriques: (campagne?: string) =>
    get<Metriques>("/metriques/", campagne ? { campagne } : undefined),

  campagnes: () => get<Campagne[]>("/campagnes/"),
  creerCampagne: (c: Partial<Campagne>) => envoyer<Campagne>("POST", "/campagnes/", c),
  campagne: (id: string) => get<CampagneDetail>(`/campagnes/${id}/`),
  definirSequence: (id: string, etapes: Partial<EtapeSequence>[]) =>
    envoyer<EtapeSequence[]>("PUT", `/campagnes/${id}/sequence/`, { etapes }),

  prospects: (params?: { campagne?: string; statut?: string }) =>
    get<Prospect[]>("/prospects/", params),
  creerProspect: (p: Partial<Prospect> & { campagne_id?: string }) =>
    envoyer<Prospect>("POST", "/prospects/", p),
  prospect: (id: string) => get<Prospect>(`/prospects/${id}/`),
  // Corrige une fiche : seuls les champs envoyés sont touchés ; l'adresse est
  // validée par le serveur (400 si elle n'a pas la forme d'une adresse).
  modifierProspect: (id: string, champs: CorrectionProspect) =>
    envoyer<Prospect>("PUT", `/prospects/${id}/`, champs),
  desinscrire: (id: string) => envoyer<Prospect>("POST", `/prospects/${id}/desinscrire/`, {}),
  changerStatut: (id: string, statut: StatutProspect) =>
    envoyer<Prospect>("POST", `/prospects/${id}/statut/`, { statut }),

  messages: (params?: {
    statut?: string;
    prospect?: string;
    campagne?: string;
    etape?: string;
    pret?: string;
  }) => get<Message[]>("/messages/", params),
  // Un lot porte EXACTEMENT les messages affichés : le serveur ne valide ni
  // n'envoie ce que l'écran n'a pas montré.
  validerLot: (par: string, ids: string[]) =>
    envoyer<{ valides: number; refus: string[] }>("POST", "/messages/valider-lot/", { par, ids }),
  envoyerLot: (ids: string[]) =>
    envoyer<{ envoyes: number; refus: string[] }>("POST", "/messages/envoyer-lot/", {
      confirmer: true,
      ids,
    }),
  editerBrouillon: (id: string, corps: { objet?: string; corps?: string }) =>
    envoyer<Message>("PUT", `/messages/${id}/`, corps),
  valider: (id: string, par: string) =>
    envoyer<Message>("POST", `/messages/${id}/valider/`, { par }),
  envoyerMessage: (id: string) => envoyer<Message>("POST", `/messages/${id}/envoyer/`, {}),
  annuler: (id: string) => envoyer<Message>("POST", `/messages/${id}/annuler/`, {}),
  // Sortie de l'impasse d'un envoi en échec : le message redevient un
  // brouillon (validation retirée) pour être retouché puis revalidé.
  remettreEnBrouillon: (id: string) =>
    envoyer<Message>("POST", `/messages/${id}/brouillon/`, {}),

  // Les agents : chaque passage interroge le modèle (facturé). `confirmer` est
  // exigé par le serveur — jamais d'appel payant par accident.
  rechercher: (campagneId: string, limite = 10, criteres = "") =>
    envoyer<ResultatRecherche>(
      "POST", `/campagnes/${campagneId}/rechercher/`, { confirmer: true, limite, criteres },
    ),
  // L'assistant conversationnel : la discussion est GARDÉE EN MÉMOIRE côté
  // serveur. On envoie un seul message + l'id de la discussion (absent = nouvelle).
  assistant: (message: string, conversationId?: string, campagneId?: string) =>
    envoyer<ReponseAssistant>("POST", "/assistant/", {
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
      ...(campagneId ? { campagne_id: campagneId } : {}),
    }),
  conversations: (campagneId?: string) =>
    get<ResumeConversation[]>("/conversations/", campagneId ? { campagne: campagneId } : undefined),
  conversation: (id: string) => get<ConversationDetail>(`/conversations/${id}/`),

  automatisation: () => get<Automatisation>("/automatisation/"),
  reglerAutomatisation: (r: ReglageAutomatisation) =>
    envoyer<Automatisation>("PUT", "/automatisation/", r),
  qualifier: (prospectId: string) =>
    envoyer<Prospect>("POST", `/prospects/${prospectId}/qualifier/`, { confirmer: true }),
  rediger: (prospectId: string, nbRelances = 4) =>
    envoyer<{ crees: number; messages: Message[] }>(
      "POST", `/prospects/${prospectId}/rediger/`, { confirmer: true, nb_relances: nbRelances },
    ),
};
