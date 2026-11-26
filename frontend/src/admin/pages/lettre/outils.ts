/** Petites fonctions de l'écran de la lettre, hors des composants. */

/** Une adresse de lien acceptable : web ou courriel. Le serveur refuse le
 *  reste de toute façon ; on le dit ici, au moment de la saisie. */
export function adresseDeLien(saisie: string): string | null {
  const brute = saisie.trim();
  if (!brute) return null;
  if (/^mailto:[^\s@]+@[^\s@]+$/i.test(brute)) return brute;
  if (/^[^\s@:/]+@[^\s@]+\.[^\s@]+$/.test(brute)) return `mailto:${brute}`;
  const avecSchema = /^https?:\/\//i.test(brute) ? brute : `https://${brute}`;
  try {
    const url = new URL(avecSchema);
    return url.hostname.includes(".") ? url.toString() : null;
  } catch {
    return null;
  }
}

/** Le message d'un refus du serveur, ou `repli` s'il n'en a pas donné. */
export function message(cause: unknown, repli: string): string {
  return cause instanceof Error && cause.message ? cause.message : repli;
}
