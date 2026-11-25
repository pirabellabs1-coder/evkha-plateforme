/** Les icônes de l'administration — un seul jeu, dessiné une fois.
 *
 * La barre latérale portait des caractères typographiques en guise d'icônes
 * (losanges, cercles, carrés) : deux entrées partageaient le même signe, aucun
 * ne disait ce qu'il désignait, et leur dessin dépendait de la police que le
 * poste voulait bien fournir. Ici, chaque icône est un tracé SVG en ligne :
 *
 * - grille de 20 × 20, trait de 1,5, bouts et angles arrondis, aucun aplat ;
 * - `currentColor` : l'icône prend l'encre de ce qui la porte (lien, bouton,
 *   état), sans une seule couleur écrite ici ;
 * - `aria-hidden` et `focusable="false"` : une icône ne nomme rien. Le nom
 *   vient TOUJOURS du texte voisin, ou de l'`aria-label` du bouton qui la
 *   contient quand elle est seule.
 *
 * Aucune bibliothèque : une vingtaine de tracés ne justifient pas une
 * dépendance, et le morceau de l'administration reste léger.
 *
 * Ajouter une icône : une entrée dans `TRACES`, dessinée sur la même grille.
 * `NomIcone` en est déduit — un nom mal écrit ne compile pas.
 */
import type { ReactNode } from "react";

const TRACES = {
  // ── Navigation ────────────────────────────────────────────────────────────
  tableau: (
    <>
      <rect x="3" y="3" width="6" height="7" rx="1.5" />
      <rect x="11" y="3" width="6" height="4" rx="1.5" />
      <rect x="11" y="9" width="6" height="8" rx="1.5" />
      <rect x="3" y="12" width="6" height="5" rx="1.5" />
    </>
  ),
  transactions: (
    <>
      <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
      <path d="M2.5 8.5h15M5.5 12.5h3" />
    </>
  ),
  qualite: (
    <>
      <path d="M10 2.5 16 5v4.6c0 3.6-2.4 6.4-6 7.9-3.6-1.5-6-4.3-6-7.9V5l6-2.5Z" />
      <path d="m7.3 10 1.9 1.9 3.5-3.8" />
    </>
  ),
  livrables: (
    <>
      <path d="M5.5 2.5h6l3.5 3.5v10a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 4 16V4a1.5 1.5 0 0 1 1.5-1.5Z" />
      <path d="M11.5 2.5V6H15M7 10h6M7 13h4" />
    </>
  ),
  boutique: (
    <>
      <path d="M4.5 6.5h11l-.8 9.3a1.5 1.5 0 0 1-1.5 1.4H6.8a1.5 1.5 0 0 1-1.5-1.4l-.8-9.3Z" />
      <path d="M7.5 8.5V5.5a2.5 2.5 0 0 1 5 0v3" />
    </>
  ),
  formations: (
    <>
      <path d="m10 3.5 8 4-8 4-8-4 8-4Z" />
      <path d="M5.5 9.5v3.8c0 1.2 2 2.2 4.5 2.2s4.5-1 4.5-2.2V9.5M18 7.5v4.5" />
    </>
  ),
  organisations: (
    <>
      <path d="M4.5 17.5v-13a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v13M12.5 8.5h2a1 1 0 0 1 1 1v8M2.5 17.5h15" />
      <path d="M7.5 7h2M7.5 10h2M7.5 13h2" />
    </>
  ),
  clients: (
    <>
      <circle cx="7.5" cy="7" r="2.8" />
      <path d="M2.5 16.5c0-2.7 2.2-4.5 5-4.5s5 1.8 5 4.5" />
      <path d="M13 4.5a2.6 2.6 0 0 1 0 5M14.5 12.3c1.8.5 3 2 3 4.2" />
    </>
  ),
  commandes: (
    <>
      <path d="M5 2.5h10v15l-2.5-1.5L10 17.5 7.5 16 5 17.5v-15Z" />
      <path d="M7.5 6.5h5M7.5 9.5h5M7.5 12.5h3" />
    </>
  ),
  demandes: (
    <>
      <path d="M2.5 11.5 5 4.5a1.5 1.5 0 0 1 1.4-1h7.2a1.5 1.5 0 0 1 1.4 1l2.5 7v3.5a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 15v-3.5Z" />
      <path d="M2.5 11.5h4l1 2h5l1-2h4" />
    </>
  ),
  signalements: (
    <>
      <path d="M4.5 17.5v-15" />
      <path d="M4.5 3.5h9.5l-2 3.5 2 3.5H4.5" />
    </>
  ),
  generations: (
    <>
      <path d="m10 2.5 7.5 4-7.5 4-7.5-4 7.5-4Z" />
      <path d="m2.5 10 7.5 4 7.5-4M2.5 13.5l7.5 4 7.5-4" />
    </>
  ),
  incidents: (
    <>
      <path d="M8.7 3.6a1.5 1.5 0 0 1 2.6 0l6.2 10.9a1.5 1.5 0 0 1-1.3 2.2H3.8a1.5 1.5 0 0 1-1.3-2.2L8.7 3.6Z" />
      <path d="M10 8v3.5M10 14v.1" />
    </>
  ),
  annonces: (
    <>
      <path d="M3 8.5v3a1 1 0 0 0 1 1h2l6.5 3.5v-12L6 7.5H4a1 1 0 0 0-1 1Z" />
      <path d="M15 7.5a3.5 3.5 0 0 1 0 5M6.5 12.5l1 4h2" />
    </>
  ),
  prospection: (
    <>
      <circle cx="10" cy="10" r="7.5" />
      <circle cx="10" cy="10" r="3.5" />
      <path d="M10 10h.1" />
    </>
  ),
  audience: (
    <>
      <rect x="2.5" y="4.5" width="15" height="11" rx="1.5" />
      <path d="m3 5.5 7 5.5 7-5.5" />
    </>
  ),

  // ── Coquille ──────────────────────────────────────────────────────────────
  menu: <path d="M3.5 5.5h13M3.5 10h13M3.5 14.5h13" />,
  fermer: <path d="m5 5 10 10M15 5 5 15" />,
  replier: <path d="m10.5 5.5-4.5 4.5 4.5 4.5M15 5.5 10.5 10l4.5 4.5" />,
  deplier: <path d="m9.5 5.5 4.5 4.5-4.5 4.5M5 5.5 9.5 10 5 14.5" />,
  chevron: <path d="m8 5.5 4.5 4.5L8 14.5" />,
  site: (
    <>
      <circle cx="10" cy="10" r="7.5" />
      <path d="M2.5 10h15M10 2.5c2.2 2 3.3 4.5 3.3 7.5s-1.1 5.5-3.3 7.5c-2.2-2-3.3-4.5-3.3-7.5S7.8 4.5 10 2.5Z" />
    </>
  ),
  espace: (
    <>
      <circle cx="10" cy="10" r="7.5" />
      <circle cx="10" cy="8" r="2.5" />
      <path d="M5.3 15.8c.9-1.8 2.6-2.8 4.7-2.8s3.8 1 4.7 2.8" />
    </>
  ),
  deconnexion: (
    <>
      <path d="M8 3.5H5A1.5 1.5 0 0 0 3.5 5v10A1.5 1.5 0 0 0 5 16.5h3" />
      <path d="M12.5 6.5 16 10l-3.5 3.5M16 10H8" />
    </>
  ),

  // ── Gestes et états ───────────────────────────────────────────────────────
  fleche: <path d="M4 10h12M11.5 5.5 16 10l-4.5 4.5" />,
  retour: <path d="M16 10H4M8.5 5.5 4 10l4.5 4.5" />,
  plus: <path d="M10 4v12M4 10h12" />,
  coche: <path d="m4.5 10.5 3.5 3.5 7.5-8" />,
  recherche: (
    <>
      <circle cx="9" cy="9" r="5.5" />
      <path d="m13.2 13.2 3.8 3.8" />
    </>
  ),
  telecharger: <path d="M10 3.5v9M6 9l4 4 4-4M4 16.5h12" />,
  relancer: (
    <>
      <path d="M16.5 10a6.5 6.5 0 1 1-2-4.7" />
      <path d="M16.5 3.5v3.5H13" />
    </>
  ),
  courriel: (
    <>
      <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
      <path d="m3 6 7 5 7-5" />
    </>
  ),
  horloge: (
    <>
      <circle cx="10" cy="10" r="7.5" />
      <path d="M10 5.5V10l3 2" />
    </>
  ),
  vide: (
    <>
      <path d="M3.5 6.5 10 3l6.5 3.5v7L10 17l-6.5-3.5v-7Z" />
      <path d="M3.5 6.5 10 10l6.5-3.5M10 10v7" />
    </>
  ),
} satisfies Record<string, ReactNode>;

export type NomIcone = keyof typeof TRACES;

/** Une icône du jeu. Décorative par construction : elle ne porte jamais de
 *  nom accessible, et ne prend pas le focus (`focusable`, pour les anciens
 *  navigateurs qui arrêtaient la tabulation sur un `<svg>`). */
export function Icone({ nom, taille = 20 }: { nom: NomIcone; taille?: number }) {
  return (
    <svg
      className="console-icone"
      width={taille}
      height={taille}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {TRACES[nom]}
    </svg>
  );
}
