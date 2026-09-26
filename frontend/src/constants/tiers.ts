/** Ton de pastille d'une formule (`.pastille-<ton>`, `theme/espace.css`).
 *
 * Une formule n'est pas un ÉTAT : le vert du succès et l'orange de l'alerte
 * y disaient autre chose que ce qu'ils voulaient dire (« Structure » en
 * alerte se lisait comme un problème). Le libellé distingue les formules ;
 * la pastille dit seulement « abonné » (info) ou « à l'unité » (neutre). */
type TonFormule = "neutre" | "info";

export const TIER_LABELS: Record<string, string> = {
  solo: "Solo (2 crédits/mois)",
  pro: "Pro (3 crédits/mois)",
  pro_plus: "Pro Plus (5 crédits/mois)",
  structure: "Structure (10 crédits/mois)",
};

export const TIER_LABELS_SHORT: Record<string, string> = {
  solo: "Solo",
  pro: "Pro",
  pro_plus: "Pro Plus",
  structure: "Structure",
};

export function tierTon(tier: string): TonFormule {
  const map: Record<string, TonFormule> = {
    solo: "info", pro: "info", pro_plus: "info", structure: "info",
  };
  return map[tier] ?? "neutre";
}
