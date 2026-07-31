/** Accès au catalogue commercial, sans jeton.
 *
 * C'est le seul appel de l'application qui ne porte pas d'authentification :
 * la page partenaires s'adresse à qui n'a pas encore de compte. Il vit donc
 * dans son propre module, à l'écart de `espace/api.ts` où chaque requête
 * attache un jeton nominatif.
 */

export type FormulePublique = {
  code: string;
  libelle: string;
  credits_par_echeance: number;
  prix_mensuel_cents: number;
  prix_credit_supplementaire_cents: number;
  /** Calculé par le serveur : prix mensuel ÷ crédits. Jamais recalculé ici —
   *  deux formules de calcul finiraient par diverger (règle 5). */
  cout_par_livrable_cents: number;
  devise: string;
  avantages: string[];
  mise_en_avant: boolean;
};

const BASE = import.meta.env.VITE_API_URL ?? "";

export async function chargerFormules(): Promise<FormulePublique[]> {
  const reponse = await fetch(`${BASE}/api/public/formules/`, {
    headers: { Accept: "application/json" },
  });
  if (!reponse.ok) {
    throw new Error(`Catalogue indisponible (${reponse.status})`);
  }
  const charge = (await reponse.json()) as { formules: FormulePublique[] };
  return charge.formules ?? [];
}

/** Montant en euros, sans centimes quand il n'y en a pas.
 *
 * « 129 € » et non « 129,00 € » pour un prix rond, mais « 64,50 € » garde ses
 * décimales : c'est ainsi que la page est écrite aujourd'hui, et un tarif
 * affiché autrement qu'attendu se lit comme une erreur.
 */
export function euros(cents: number): string {
  const montant = cents / 100;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: Number.isInteger(montant) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(montant);
}

export type Inscription = {
  raison_sociale: string;
  email: string;
  mot_de_passe: string;
  prenom?: string;
  nom?: string;
  formule?: string;
};

export type CompteOuvert = {
  jeton: string;
  organisation: { id: string; raison_sociale: string };
  formule_demandee: string | null;
  /** Toujours `false` aujourd'hui : rien n'est encaissé, donc rien n'est
   *  activé. Le champ existe pour que l'interface n'ait pas à le deviner —
   *  et pour qu'elle n'ait rien à changer le jour où Stripe le fait passer à
   *  `true`. */
  abonnement_actif: boolean;
  demande_id: string | null;
};

/** Refus du serveur, avec son code.
 *
 * Le `code` désigne le champ fautif sans comparer une phrase : un message
 * reformulé casserait silencieusement une interface qui se fie au texte.
 */
export class RefusInscription extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.code = code;
  }
}

export async function inscrire(saisie: Inscription): Promise<CompteOuvert> {
  const reponse = await fetch(`${BASE}/api/public/inscription/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(saisie),
  });
  const charge: unknown = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    const detail = charge as { erreur?: string; code?: string };
    throw new RefusInscription(
      detail.erreur ?? `Inscription impossible (${reponse.status})`,
      detail.code ?? "",
    );
  }
  return charge as CompteOuvert;
}
