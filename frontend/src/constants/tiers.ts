/** Ton de pastille d'une formule (`.pastille-<ton>`, `theme/espace.css`).
 *  Les anciennes couleurs Radix, ton pour ton : gray → neutre, blue →
 *  information, green → succès, amber → alerte. */
type TonFormule = "neutre" | "info" | "succes" | "alerte";

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
    solo: "neutre", pro: "info", pro_plus: "succes", structure: "alerte",
  };
  return map[tier] ?? "neutre";
}
