/** Accès à la boutique publique.
 *
 * Les prix viennent tous du serveur, qui les tient de la base. Écrire un
 * montant dans le React en ferait une seconde source, qui contredirait le
 * paiement au premier changement de tarif.
 */
import { BASE } from "./donnees";

export type ProduitResume = {
  slug: string;
  titre: string;
  theme: string;
  prix_cents: number;
  devise: string;
  pages: number;
  /** Date ISO, ou chaîne vide si la cliente ne l'a pas renseignée. */
  mise_a_jour: string;
  /** Adresse de l'image de couverture, ou chaîne vide. */
  image: string;
  /** Moyenne des avis publiés, à une décimale. `0` s'il n'y en a aucun. */
  note: number;
  nombre_d_avis: number;
};

export type Avis = {
  auteur: string;
  /** Métier ou ville — « Restauratrice, Lyon ». Peut être vide. */
  qualite: string;
  note: number;
  texte: string;
  /** Date ISO du jour où l'avis a été saisi. */
  date: string;
};

export type ProduitFiche = ProduitResume & {
  description: string;
  /** Une entrée par ligne, découpée côté serveur. */
  sommaire: string[];
  /** Les pages consultables avant achat, ou chaîne vide. */
  extrait: string;
  editable: boolean;
  /** Les avis publiés, du plus récent au plus ancien. */
  avis: Avis[];
};

export class RefusBoutique extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.code = code;
  }
}

async function lire<T>(chemin: string, init?: RequestInit): Promise<T> {
  const reponse = await fetch(`${BASE}/api/public/boutique/${chemin}`, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...init,
  });
  const charge = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    throw new RefusBoutique(
      charge.erreur ?? "La boutique est momentanément indisponible.",
      charge.code ?? "indisponible",
    );
  }
  return charge as T;
}

export type AvisALaUne = Avis & {
  /** Le titre de l'étude dont parle l'avis. Un témoignage sans son objet ne
   *  veut rien dire sur une page qui en présente plusieurs. */
  etude: string;
  slug: string;
};

export const chargerCatalogue = () =>
  lire<{ produits: ProduitResume[]; themes: string[]; avis: AvisALaUne[] }>("");

export const chargerFiche = (slug: string) =>
  lire<{ produit: ProduitFiche; proches: ProduitResume[] }>(
    `${encodeURIComponent(slug)}/`,
  );

/** Ouvre le paiement et rend l'adresse où envoyer l'acheteur.
 *
 * On n'envoie qu'un slug : le tarif appliqué est celui du catalogue.
 * Transmettre un montant depuis le navigateur reviendrait à laisser choisir
 * combien payer.
 */
export const ouvrirLePaiement = (produit: string, email = "") =>
  lire<{ adresse: string }>("acheter/", {
    method: "POST",
    body: JSON.stringify({ produit, email }),
  }).then((r) => r.adresse);

/** Constitue l'achat au retour du paiement, et ouvre la session. */
export const confirmerLAchat = (session: string) =>
  lire<{
    jeton: string;
    titre: string;
    slug: string;
    telechargement: string;
    editable: string;
  }>("retour/", { method: "POST", body: JSON.stringify({ session }) });

/** « 89 € », sans décimales quand il n'y en a pas — comme sur le site. */
export function prix(cents: number, devise = "EUR"): string {
  const entier = cents % 100 === 0;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: devise,
    minimumFractionDigits: entier ? 0 : 2,
    maximumFractionDigits: entier ? 0 : 2,
  }).format(cents / 100);
}

/** « ★★★★☆ » — la note arrondie, sur cinq.
 *
 * Les étoiles vides comptent autant que les pleines : sans elles, trois et
 * cinq étoiles ne se distinguent qu'à la longueur du trait, ce qui ne se voit
 * pas dans une grille où chaque carte a la sienne.
 */
export function etoiles(note: number): string {
  const pleines = Math.min(5, Math.max(0, Math.round(note)));
  return "★".repeat(pleines) + "☆".repeat(5 - pleines);
}

/** L'initiale du titre, pour les études sans couverture.
 *
 * L'article est retiré : « Le marché des foodtrucks » donnerait sinon un « L »
 * pour toutes les études du catalogue.
 */
export function initiale(titre: string): string {
  const mot = titre.replace(/^(le|la|les|l'|un|une|du|de|des)\s+/i, "").trim();
  return (mot[0] ?? "?").toUpperCase();
}

/** « janvier 2026 ». Le jour n'apporte rien sur une date de mise à jour. */
export function moisEtAnnee(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("fr-FR", {
    month: "long",
    year: "numeric",
  }).format(date);
}
