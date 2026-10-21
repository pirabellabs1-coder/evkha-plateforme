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

async function lire<T>(reponse: Response): Promise<T> {
  if (reponse.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Non autorisé");
  }
  if (!reponse.ok) {
    const charge = (await reponse.json().catch(() => ({}))) as { erreur?: string };
    throw new Error(charge.erreur ?? `Erreur ${reponse.status}`);
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
  contactable: boolean;
  desinscrit_le: string | null;
  notes: string;
  cree_le: string;
  messages?: Message[];
}

export interface Message {
  id: string;
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
  error_message: string;
  envoyable: boolean;
  cree_le: string;
}

export interface Apercu {
  campagnes_actives: number;
  prospects: number;
  prospects_par_statut: Record<string, number>;
  a_valider: number;
  valides_en_attente: number;
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
  rebonds: number;
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

export interface Automatisation {
  active: boolean;
  prospects_par_jour: number;
  campagne_id: string | null;
  jours: number[];
  derniere_execution: string | null;
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
  desinscrire: (id: string) => envoyer<Prospect>("POST", `/prospects/${id}/desinscrire/`, {}),
  changerStatut: (id: string, statut: StatutProspect) =>
    envoyer<Prospect>("POST", `/prospects/${id}/statut/`, { statut }),

  messages: (params?: { statut?: string; prospect?: string; campagne?: string }) =>
    get<Message[]>("/messages/", params),
  editerBrouillon: (id: string, corps: { objet?: string; corps?: string }) =>
    envoyer<Message>("PUT", `/messages/${id}/`, corps),
  valider: (id: string, par: string) =>
    envoyer<Message>("POST", `/messages/${id}/valider/`, { par }),
  envoyerMessage: (id: string) => envoyer<Message>("POST", `/messages/${id}/envoyer/`, {}),
  annuler: (id: string) => envoyer<Message>("POST", `/messages/${id}/annuler/`, {}),

  // Les agents : chaque passage interroge le modèle (facturé). `confirmer` est
  // exigé par le serveur — jamais d'appel payant par accident.
  rechercher: (campagneId: string, limite = 10, criteres = "") =>
    envoyer<{ crees: number; prospects: Prospect[] }>(
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
  reglerAutomatisation: (r: Partial<Automatisation>) =>
    envoyer<Automatisation>("PUT", "/automatisation/", r),
  qualifier: (prospectId: string) =>
    envoyer<Prospect>("POST", `/prospects/${prospectId}/qualifier/`, { confirmer: true }),
  rediger: (prospectId: string, nbRelances = 4) =>
    envoyer<{ crees: number; messages: Message[] }>(
      "POST", `/prospects/${prospectId}/rediger/`, { confirmer: true, nb_relances: nbRelances },
    ),
};
