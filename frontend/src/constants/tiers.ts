type RadixColor = "gray" | "blue" | "green" | "amber";

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

export function tierColor(tier: string): RadixColor {
  const map: Record<string, RadixColor> = {
    solo: "gray", pro: "blue", pro_plus: "green", structure: "amber",
  };
  return map[tier] ?? "gray";
}
