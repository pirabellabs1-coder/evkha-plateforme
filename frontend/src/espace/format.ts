/** Formatage en français. Une seule source, sinon les écrans divergent.
 *
 * `Intl` fait le travail : réimplémenter l'espace insécable des milliers ou le
 * nom des mois produirait des variantes d'un écran à l'autre.
 */

const LOCALE = "fr-FR";

export const nombre = (valeur: number): string =>
  new Intl.NumberFormat(LOCALE).format(valeur);

/** Un signe explicite : dans un journal de mouvements, « 3 » et « −3 » ne
 *  doivent jamais pouvoir être confondus. */
export const quantiteSignee = (valeur: number): string =>
  new Intl.NumberFormat(LOCALE, { signDisplay: "exceptZero" }).format(valeur);

/** Coût d'API, en euros, à la précision du centime de centime.
 *
 * Les coûts de génération (quelques centimes par chapitre) se lisent à quatre
 * décimales ; la console les écrivait `toFixed(4) + " €"` : point décimal à
 * l'anglaise, et une espace SÉCABLE qui laissait « € » seul à la ligne dans la
 * colonne Coût (vu le 26/09/2026). `Intl` pose la virgule et l'espace
 * insécable. Reçoit la chaîne décimale de l'API (`"1.4724"`). */
export const coutApi = (eur: string | number): string =>
  new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(typeof eur === "number" ? eur : parseFloat(eur));

export const montant = (cents: number, devise = "EUR"): string =>
  new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: devise,
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);

export const date = (iso: string | null): string =>
  iso
    ? new Intl.DateTimeFormat(LOCALE, { dateStyle: "long" }).format(new Date(iso))
    : "—";

/** « un an », « 30 jours »… La durée vient du serveur ; l'écran ne la recopie pas. */
export const dureeDeConservation = (jours: number): string => {
  if (jours >= 360 && jours <= 366) return "un an";
  if (jours % 30 === 0 && jours >= 60) return `${jours / 30} mois`;
  return `${jours} jours`;
};

export const dateHeure = (iso: string | null): string =>
  iso
    ? new Intl.DateTimeFormat(LOCALE, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(iso))
    : "—";

/** Accord du pluriel. « 1 crédits » se remarque tout de suite. */
export const credits = (nombreDeCredits: number): string =>
  `${nombre(nombreDeCredits)} crédit${Math.abs(nombreDeCredits) > 1 ? "s" : ""}`;

const LIBELLE_LIVRABLE: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de la concurrence",
  business_plan: "Business plan",
  business_strategy: "Stratégie d'entreprise",
};

export const typeLivrable = (code: string): string =>
  LIBELLE_LIVRABLE[code] ?? code;

const LIBELLE_MOUVEMENT: Record<string, string> = {
  dotation: "Dotation d'abonnement",
  achat: "Achat de crédits",
  geste: "Geste commercial",
  debit: "Génération",
  remboursement: "Remboursement",
  expiration: "Expiration",
};

export const typeMouvement = (code: string): string =>
  LIBELLE_MOUVEMENT[code] ?? code;

const LIBELLE_ROLE: Record<string, string> = {
  proprietaire: "Propriétaire",
  membre: "Membre",
  lecture: "Lecture seule",
};

export const role = (code: string): string => LIBELLE_ROLE[code] ?? code;

const LIBELLE_DEMANDE: Record<string, string> = {
  changement_formule: "Changement de formule",
  credits_additionnels: "Achat de crédits",
  resiliation: "Résiliation",
};

export const typeDemande = (code: string): string =>
  LIBELLE_DEMANDE[code] ?? code;

const LIBELLE_REPORT: Record<string, string> = {
  aucun: "Aucun report",
  integral: "Report intégral",
  plafonne: "Report plafonné",
};

export const reportCredits = (code: string): string =>
  LIBELLE_REPORT[code] ?? code;
