/** Bouton « Continuer avec Google ».
 *
 * Le navigateur obtient le jeton d'identité auprès de Google ; **le serveur le
 * vérifie**. Rien de ce que fait ce module n'est une preuve d'identité : il
 * transporte un jeton, c'est tout.
 *
 * Le script Google n'est chargé que si l'application est configurée, et
 * seulement au premier besoin : une page publique ne doit pas appeler un
 * tiers pour une fonction dont personne ne se sert.
 */

const BASE = import.meta.env.VITE_API_URL ?? "";
const SCRIPT = "https://accounts.google.com/gsi/client";

export type ReglagesPublics = {
  google: { actif: boolean; client_id: string };
};

export type SessionGoogle = {
  jeton: string;
  compte_cree: boolean;
  champs_completes?: string[];
  organisation?: { id: string; raison_sociale: string };
  formule_demandee?: string | null;
  /** Étude à payer, quand le compte vient d'être ouvert depuis `/etudes`.
   *  Absent sur une simple connexion : on ne fait payer personne qui revient. */
  livrable_demande?: string | null;
  abonnement_actif?: boolean;
};

export class RefusGoogle extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.code = code;
  }
}

export async function chargerReglages(): Promise<ReglagesPublics> {
  const reponse = await fetch(`${BASE}/api/public/reglages/`, {
    headers: { Accept: "application/json" },
  });
  if (!reponse.ok) {
    // Un réglage illisible vaut « Google indisponible » : on n'affiche pas un
    // bouton dont on ne sait pas s'il peut marcher.
    return { google: { actif: false, client_id: "" } };
  }
  return (await reponse.json()) as ReglagesPublics;
}

let chargement: Promise<void> | null = null;

/** Charge le script Google une seule fois, quel que soit le nombre d'appels. */
function chargerScript(): Promise<void> {
  if (chargement) return chargement;
  chargement = new Promise<void>((resoudre, rejeter) => {
    if (document.querySelector(`script[src="${SCRIPT}"]`)) {
      resoudre();
      return;
    }
    const balise = document.createElement("script");
    balise.src = SCRIPT;
    balise.async = true;
    balise.onload = () => resoudre();
    balise.onerror = () =>
      rejeter(new Error("Le script Google n'a pas pu être chargé."));
    document.head.appendChild(balise);
  });
  return chargement;
}

type GoogleGlobal = {
  accounts: {
    id: {
      initialize: (o: {
        client_id: string;
        callback: (r: { credential?: string }) => void;
      }) => void;
      prompt: () => void;
      renderButton: (e: HTMLElement, o: Record<string, unknown>) => void;
    };
  };
};

/** Demande un jeton d'identité à Google, via le bouton officiel.
 *
 * Google impose de rendre SON bouton : un bouton maison ne déclenche pas le
 * choix de compte de façon fiable. On le rend donc dans un conteneur fourni
 * par la page, et on habille ce conteneur.
 */
export async function brancherBouton(
  conteneur: HTMLElement,
  clientId: string,
  auJeton: (jeton: string) => void,
): Promise<void> {
  await chargerScript();
  const google = (window as unknown as { google?: GoogleGlobal }).google;
  if (!google) {
    throw new Error("Google n'a pas répondu.");
  }
  google.accounts.id.initialize({
    client_id: clientId,
    callback: (reponse) => {
      if (reponse.credential) auJeton(reponse.credential);
    },
  });
  google.accounts.id.renderButton(conteneur, {
    type: "standard",
    theme: "outline",
    size: "large",
    text: "continue_with",
    shape: "rectangular",
    locale: "fr",
    // La largeur du FORMULAIRE, et non celle du conteneur : au moment du
    // rendu il est encore masqué (`display: none`), sa largeur vaut zéro, et
    // le repli à 340 px donnait un bouton plus étroit que les champs sur
    // ordinateur et plus large que la carte sur un petit téléphone (signalé
    // par le client le 19/11/2026). Google borne ce réglage à 400 px.
    width: largeurDuBouton(conteneur),
  });
}

/** Largeur demandée à Google : celle de la colonne du formulaire, entre les
 *  bornes que Google accepte (200 à 400 px). */
export function largeurDuBouton(conteneur: HTMLElement): number {
  const disponible = conteneur.clientWidth || largeurUtile(conteneur.parentElement);
  if (disponible <= 0) return 320;
  return Math.max(200, Math.min(400, Math.floor(disponible)));
}

/** Largeur où l'on peut réellement poser quelque chose : `clientWidth` moins
 *  les marges intérieures.
 *
 *  `clientWidth` les COMPTE. Sur la carte de connexion (30 px de chaque côté)
 *  le bouton était donc demandé 60 px trop large, et le cadre centré en
 *  rognait la moitié de chaque côté : « Continuer en tant que… » perdait ses
 *  premières lettres et la photo du compte (capture du client, 19/11/2026). */
function largeurUtile(element: HTMLElement | null | undefined): number {
  if (!element) return 0;
  const style = window.getComputedStyle(element);
  const marges = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
  return element.clientWidth - marges;
}

/** Échange le jeton Google contre une session EVKHA.
 *
 * `raison_sociale` n'est utile qu'à la CRÉATION. On l'envoie toujours : le
 * navigateur ne sait pas si le compte existe, et le serveur l'ignore quand il
 * connaît déjà l'adresse.
 */
export async function ouvrirSessionGoogle(
  jetonGoogle: string,
  extras: { raison_sociale?: string; formule?: string; livrable?: string } = {},
): Promise<SessionGoogle> {
  const reponse = await fetch(`${BASE}/api/public/google/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ jeton_google: jetonGoogle, ...extras }),
  });
  const charge: unknown = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    const detail = charge as { erreur?: string; code?: string };
    throw new RefusGoogle(
      detail.erreur ?? `Connexion Google impossible (${reponse.status})`,
      detail.code ?? "",
    );
  }
  return charge as SessionGoogle;
}
