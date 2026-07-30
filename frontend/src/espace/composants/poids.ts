/** Taille de fichier lisible. « 1048576 octets » ne dit rien à personne.
 *
 * Dans son propre fichier : un module qui exporte à la fois un composant et une
 * fonction casse le rafraîchissement à chaud de Vite.
 */
export function poids(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}
