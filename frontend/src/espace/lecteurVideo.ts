/** Comment montrer la vidéo d'une leçon, d'après l'adresse que la gérante a
 *  saisie.
 *
 * L'adresse est un texte libre de l'administration : elle peut désigner
 * n'importe quel site. On ne l'intègre donc dans la page (`<iframe>`) que
 * pour les hébergeurs d'une LISTE FERMÉE, dont on sait construire soi-même
 * l'adresse d'intégration — on ne pose jamais dans un cadre l'adresse reçue.
 *
 * - YouTube, Vimeo : le lecteur de l'hébergeur, à une adresse reconstruite
 *   ici à partir du seul identifiant de la vidéo.
 * - Un fichier vidéo direct (`.mp4`, `.webm`) : le lecteur du navigateur.
 * - Toute autre adresse `https://` : un lien à ouvrir dans un nouvel onglet.
 * - Le reste (vide, illisible, `http://`, `javascript:`…) : rien. La page dit
 *   que la vidéo n'est pas disponible, et ne rend aucun lien.
 *
 * L'hôte est comparé EXACTEMENT : `youtube.com.exemple.fr` ou
 * `https://youtube.com@exemple.fr/` ne sont pas YouTube. Aucune expression
 * régulière à regard arrière (Safari avant 16.4 ne charge pas le fichier).
 *
 * Pas de composant dans ce fichier : des fonctions pures, que le test éprouve
 * adresse par adresse.
 */
import { hoteConnuDeLApi } from "./api";

export type LecteurVideo =
  | { genre: "integre"; hebergeur: "YouTube" | "Vimeo"; adresse: string }
  | { genre: "fichier"; adresse: string }
  | { genre: "lien"; adresse: string }
  | { genre: "aucun" };

/** L'identifiant d'une vidéo YouTube : onze signes, lettres, chiffres, tiret
 *  et tiret bas. Tout le reste est refusé — c'est lui, et lui seul, qui entre
 *  dans l'adresse d'intégration. */
const ID_YOUTUBE = /^[A-Za-z0-9_-]{11}$/;

const HOTES_YOUTUBE = ["www.youtube.com", "youtube.com", "m.youtube.com"];
const HOTE_YOUTUBE_COURT = "youtu.be";
const HOTE_YOUTUBE_SANS_TEMOIN = "www.youtube-nocookie.com";

/** Les chemins de YouTube qui portent l'identifiant en second segment. */
const CHEMINS_YOUTUBE = ["embed", "shorts", "live"];

const ID_VIMEO = /^\d{1,12}$/;
/** La clé d'une vidéo Vimeo non répertoriée (`vimeo.com/<id>/<clé>`). */
const CLE_VIMEO = /^[0-9a-f]{6,32}$/i;

const HOTES_VIMEO = ["vimeo.com", "www.vimeo.com"];
const HOTE_VIMEO_LECTEUR = "player.vimeo.com";

const FICHIER_VIDEO = /\.(?:mp4|webm)$/i;

function segments(adresse: URL): string[] {
  return adresse.pathname.split("/").filter((segment) => segment !== "");
}

function identifiantYouTube(adresse: URL): string | null {
  const morceaux = segments(adresse);
  let candidat: string | null = null;
  if (adresse.hostname === HOTE_YOUTUBE_COURT) {
    candidat = morceaux.length === 1 ? morceaux[0] : null;
  } else if (HOTES_YOUTUBE.includes(adresse.hostname)) {
    if (morceaux.length === 1 && morceaux[0] === "watch") {
      candidat = adresse.searchParams.get("v");
    } else if (morceaux.length === 2 && CHEMINS_YOUTUBE.includes(morceaux[0])) {
      candidat = morceaux[1];
    }
  } else if (adresse.hostname === HOTE_YOUTUBE_SANS_TEMOIN) {
    candidat = morceaux.length === 2 && morceaux[0] === "embed" ? morceaux[1] : null;
  }
  return candidat !== null && ID_YOUTUBE.test(candidat) ? candidat : null;
}

function videoVimeo(adresse: URL): { id: string; cle: string | null } | null {
  const morceaux = segments(adresse);
  let id: string | null = null;
  let cle: string | null = null;
  if (HOTES_VIMEO.includes(adresse.hostname)) {
    if (morceaux.length === 1 || morceaux.length === 2) {
      id = morceaux[0];
      cle = morceaux[1] ?? null;
    }
  } else if (adresse.hostname === HOTE_VIMEO_LECTEUR) {
    if (morceaux.length === 2 && morceaux[0] === "video") {
      id = morceaux[1];
      cle = adresse.searchParams.get("h");
    }
  }
  if (id === null || !ID_VIMEO.test(id)) return null;
  // Une clé mal formée ne s'ignore pas : sans elle, le lecteur afficherait
  // « vidéo introuvable ». L'adresse est alors rendue en simple lien.
  if (cle !== null && !CLE_VIMEO.test(cle)) return null;
  return { id, cle };
}

/** Ce que la page montre pour cette adresse. */
export function lecteurDe(brut: unknown): LecteurVideo {
  if (typeof brut !== "string" || brut.trim() === "") return { genre: "aucun" };
  let adresse: URL;
  try {
    adresse = new URL(brut.trim());
  } catch {
    return { genre: "aucun" };
  }
  // `https://` seulement : ni `http://` (contenu mixte, et lisible en chemin),
  // ni aucun autre schéma.
  if (adresse.protocol !== "https:") return { genre: "aucun" };

  // Un hébergeur connu se reconnaît à son hôte nu : ni port, ni identifiants.
  const hoteNu =
    adresse.port === "" && adresse.username === "" && adresse.password === "";

  if (hoteNu) {
    const youtube = identifiantYouTube(adresse);
    if (youtube !== null) {
      return {
        genre: "integre",
        hebergeur: "YouTube",
        // Le domaine « sans témoin » de YouTube : aucun cookie n'est posé
        // tant que la lecture n'a pas commencé.
        adresse: `https://${HOTE_YOUTUBE_SANS_TEMOIN}/embed/${youtube}`,
      };
    }
    const vimeo = videoVimeo(adresse);
    if (vimeo !== null) {
      const cle = vimeo.cle === null ? "" : `?h=${vimeo.cle}`;
      return {
        genre: "integre",
        hebergeur: "Vimeo",
        adresse: `https://${HOTE_VIMEO_LECTEUR}/video/${vimeo.id}${cle}`,
      };
    }
  }

  if (FICHIER_VIDEO.test(adresse.pathname)) {
    return { genre: "fichier", adresse: adresse.href };
  }
  return { genre: "lien", adresse: adresse.href };
}

/** Les hôtes du poste de développement : les seuls où `http://` est admis. */
const HOTES_DE_DEVELOPPEMENT = ["localhost", "127.0.0.1"];

/** Le lien signé d'un document peut-il être suivi ?
 *
 *  Le serveur le rend en adresse absolue (`signatures.lien_absolu`). Il n'est
 *  suivi que si :
 *
 *  - il est en `https://` — ou en `http://` sur `localhost` / `127.0.0.1`,
 *    le poste de développement, où l'API n'est pas servie en `https`. Nulle
 *    part ailleurs : un document acheté ne voyage pas en clair ;
 *  - il ne porte pas d'identifiants (`https://serveur@ailleurs/`) ;
 *  - son hôte est EXACTEMENT celui de l'API, quand ce client le connaît
 *    (`hoteConnuDeLApi`, lu à la base du client d'API — aucun domaine n'est
 *    recopié ici). Le port n'est pas comparé : en développement, la page
 *    passe par le relais de Vite et le fichier vient droit du serveur.
 *
 *  `hoteDeLApi` vaut `null` quand le client joint l'API par un relais, sans
 *  connaître son hôte : l'hôte du lien n'est alors PAS vérifié — le comparer
 *  à celui de la page refuserait tous les documents (voir `hoteConnuDeLApi`).
 *
 *  Le second paramètre n'existe que pour l'épreuve : l'écran ne le passe pas. */
export function lienDeDocument(
  brut: unknown,
  hoteDeLApi: string | null = hoteConnuDeLApi(),
): string | null {
  if (typeof brut !== "string" || brut === "") return null;
  let adresse: URL;
  try {
    adresse = new URL(brut);
  } catch {
    return null;
  }
  const enClairSurLePoste =
    adresse.protocol === "http:" && HOTES_DE_DEVELOPPEMENT.includes(adresse.hostname);
  if (adresse.protocol !== "https:" && !enClairSurLePoste) return null;
  if (adresse.username !== "" || adresse.password !== "") return null;
  if (hoteDeLApi !== null && adresse.hostname !== hoteDeLApi) return null;
  // Rendu TEL QUE REÇU : le lien est signé, on ne le réécrit pas.
  return brut;
}
