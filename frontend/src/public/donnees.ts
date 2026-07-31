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
