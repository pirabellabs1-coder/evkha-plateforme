/** Les quatre pages légales publiques : mentions légales, charte RGPD,
 * CGV / CGU, politique de confidentialité.
 *
 * UN gabarit, `PageLegale`, et quatre composants qui lui passent chacun son
 * texte. Le texte vient de `contenuLegal.ts`, repris mot pour mot du site de
 * la cliente : ce fichier ne l'écrit pas, ne le résume pas, ne le corrige pas.
 * La liste interne des passages à faire relire, dans le même fichier de
 * contenu, n'est PAS importée ici : elle n'est pas pour le visiteur.
 *
 * ## Ce que le gabarit ajoute au texte, et rien d'autre
 *
 * - Quatre courts textes d'articulation (`ARTICULATION`, `NOMS_DES_TEXTES`) :
 *   le mot du sommaire, « Mise à jour le », « Retour en haut », et le nom des
 *   quatre textes dans la barre qui les relie. Aucune phrase juridique.
 * - Des ancres. Chaque titre de section en reçoit une, dérivée de son titre
 *   (`ancres`) : stable d'un rendu à l'autre, et UNIQUE dans la page — deux
 *   articles peuvent porter le même numéro (CGV puis CGU), le second reçoit
 *   alors un suffixe. Une ancre ne peut pas non plus prendre un identifiant
 *   du socle (`RESERVES`).
 * - Des liens. Une adresse écrite dans le texte devient cliquable SANS que le
 *   texte change : le paragraphe est découpé au rendu (`avecLiens`), et le
 *   lien porte exactement les caractères écrits. Voir `ADRESSE` pour ce qui
 *   compte comme une adresse.
 *
 * ## Une page de lecture
 *
 * Tout est visible d'emblée : aucun bloc n'attend le défilement pour
 * apparaître, rien ne tourne en boucle — donc ni bouton de pause, ni région
 * d'alerte (la page ne charge rien). La date est écrite en casse normale ; le
 * relevé la donne tantôt en capitales, tantôt précédée de « LE ».
 *
 * Le sommaire ne liste que les sections de niveau 2. Sur grand écran, c'est
 * une colonne collante à gauche ; en dessous, un `<details>` replié en haut de
 * page. La bascule suit la même largeur que la barre du socle (`GRAND_ECRAN`,
 * et la même valeur dans `PagesLegales.css`).
 */
import { useRef, type ReactNode } from "react";

import { CONTACT_EMAIL } from "./contenu";
import {
  PAGES_LEGALES,
  type BlocLegal,
  type CheminLegal,
  type PageLegale as TexteLegal,
  type SectionLegale,
} from "./contenuLegal";
import { ID_DU_CONTENU } from "./contenuSite";
import { EnTeteSite } from "./EnTeteSite";
import { PiedSite } from "./PiedSite";
import { useAimants, useMedia, useMenu, useTitreDePage } from "./site";
// Le socle d'abord, la feuille de la page ensuite : à spécificité égale, c'est
// la page qui a le dernier mot.
import "./Site.css";
import "./PagesLegales.css";

// ── Les textes d'articulation ───────────────────────────────────────────────

const ARTICULATION = {
  sommaire: "Sommaire",
  miseAJour: "Mise à jour le",
  retour: "Retour en haut",
  /** Le nom accessible de la barre qui relie les quatre textes. */
  nomDeLaBarre: "Textes légaux",
};

/** Le nom court de chaque texte, dans la barre de liens. Indexé par le type
 *  des chemins : un cinquième texte sans nom ne compilerait pas. */
const NOMS_DES_TEXTES: Record<CheminLegal, string> = {
  "/mentions-legales": "Mentions légales",
  "/rgpd": "RGPD",
  "/cgv": "CGV / CGU",
  "/politique-de-confidentialite": "Politique de confidentialité",
};

/** La largeur à partir de laquelle le sommaire passe en colonne. La même que
 *  celle où le socle montre les liens de la barre ; `PagesLegales.css` écrit
 *  la même valeur. */
const GRAND_ECRAN = "(min-width: 1001px)";

// ── La date ─────────────────────────────────────────────────────────────────

/** « LE 28 AVRIL 2026 » → « 28 avril 2026 ». La casse et l'article du relevé
 *  sont ramenés à une écriture courante ; le jour, le mois et l'année ne sont
 *  pas touchés. */
function dateLisible(brute: string): string {
  return brute
    .trim()
    .toLocaleLowerCase("fr")
    .replace(/^le\s+/, "");
}

// ── Les ancres ──────────────────────────────────────────────────────────────

/** Les identifiants que le socle pose déjà sur la page : une ancre de section
 *  ne doit pas pouvoir prendre l'un d'eux. */
const RESERVES = [ID_DU_CONTENU, "acc-menu"];

/** Le titre, réduit à des lettres sans accent, des chiffres et des tirets.
 *  Un titre qui n'en contient aucun reçoit « section ». */
function racineDAncre(titre: string): string {
  const racine = titre
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return racine || "section";
}

/** Une ancre par section, dans l'ordre des sections, sans doublon : une ancre
 *  déjà prise reçoit le premier suffixe libre (`-2`, `-3`…). Le résultat ne
 *  dépend que des titres et de leur ordre. */
function ancres(sections: SectionLegale[]): string[] {
  const prises = new Set<string>(RESERVES);
  return sections.map((section) => {
    const racine = racineDAncre(section.titre);
    let ancre = racine;
    for (let rang = 2; prises.has(ancre); rang += 1) {
      ancre = `${racine}-${rang}`;
    }
    prises.add(ancre);
    return ancre;
  });
}

// ── Les adresses écrites dans le texte ──────────────────────────────────────

/** Le domaine du site, lu dans l'adresse de contact : il n'est pas écrit une
 *  seconde fois ici. */
const DOMAINE = CONTACT_EMAIL.slice(CONTACT_EMAIL.indexOf("@") + 1).toLowerCase();

const HOTE = "[a-z0-9-]+(?:\\.[a-z0-9-]+)+";
const CHEMIN = "(?:/[^\\s]*[a-z0-9/])?";

/** Ce qui compte comme une adresse, dans un paragraphe :
 *
 *  1. une adresse e-mail (premier groupe) ;
 *  2. une adresse de site ÉCRITE COMME TELLE — elle commence par `http://`,
 *     `https://` ou `www.` — ou le domaine du site écrit nu (« sur le site
 *     evkha.fr »).
 *
 *  Un nom de marque qui se termine comme un domaine (« Systeme.io », cité
 *  parmi les prestataires) n'est PAS une adresse : le texte nomme une société,
 *  il n'invite pas à s'y rendre. La ponctuation qui suit une adresse (point
 *  final, parenthèse, virgule) reste hors du lien. */
const ADRESSE = new RegExp(
  `([a-z0-9._%+-]+@${HOTE})` +
    `|(?<![a-z0-9@._-])(?:(?:https?://${HOTE}|www\\.${HOTE})${CHEMIN}` +
    `|${DOMAINE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?!\\.?[a-z0-9-]))`,
  "gi",
);

/** Où mène une adresse de site telle qu'elle est écrite. Le domaine du site,
 *  nu ou non, mène à son adresse canonique. */
function adresseDuSite(ecrite: string): string {
  if (/^https?:\/\//i.test(ecrite)) return ecrite;
  if (ecrite.toLowerCase() === DOMAINE) return `https://www.${DOMAINE}`;
  const coupe = ecrite.indexOf("/");
  const hote = coupe === -1 ? ecrite : ecrite.slice(0, coupe);
  const chemin = coupe === -1 ? "" : ecrite.slice(coupe);
  return `https://${hote.toLowerCase()}${chemin}`;
}

/** Le texte, découpé autour de ses adresses. Mis bout à bout, les morceaux
 *  redonnent le texte caractère pour caractère : un lien porte ce qui est
 *  écrit, rien de plus. */
function avecLiens(texte: string): ReactNode[] {
  const morceaux: ReactNode[] = [];
  let fin = 0;
  for (const trouvee of texte.matchAll(ADRESSE)) {
    const ecrite = trouvee[0];
    const debut = trouvee.index ?? 0;
    if (debut > fin) morceaux.push(texte.slice(fin, debut));
    morceaux.push(
      <a
        key={debut}
        href={trouvee[1] ? `mailto:${ecrite}` : adresseDuSite(ecrite)}
      >
        {ecrite}
      </a>,
    );
    fin = debut + ecrite.length;
  }
  if (fin < texte.length) morceaux.push(texte.slice(fin));
  return morceaux;
}

// ── Les pièces de la page ───────────────────────────────────────────────────

/** Un bloc du texte : un paragraphe ou une liste. Les clés sont des rangs —
 *  le texte est figé, et deux paragraphes peuvent être identiques. */
function Bloc({ bloc }: { bloc: BlocLegal }) {
  if (bloc.type === "liste") {
    return (
      <ul>
        {bloc.elements.map((element, k) => (
          <li key={k}>{avecLiens(element)}</li>
        ))}
      </ul>
    );
  }
  return <p>{avecLiens(bloc.texte)}</p>;
}

type EntreeDeSommaire = { ancre: string; titre: string };

/** Le sommaire des sections de niveau 2. Le même contenu sous deux formes :
 *  une colonne toujours ouverte sur grand écran, un `<details>` replié en
 *  dessous. Sans `matchMedia`, la forme repliée — celle du téléphone. */
function Sommaire({ entrees }: { entrees: EntreeDeSommaire[] }) {
  const enColonne = useMedia(GRAND_ECRAN);
  const liste = (
    <ol>
      {entrees.map((entree) => (
        <li key={entree.ancre}>
          <a href={`#${entree.ancre}`}>{entree.titre}</a>
        </li>
      ))}
    </ol>
  );

  return (
    <nav className="leg-sommaire" aria-label={ARTICULATION.sommaire}>
      {enColonne ? (
        <>
          {/* Le nom de la région le dit déjà à un lecteur d'écran. */}
          <p className="leg-sommaire-titre" aria-hidden="true">
            {ARTICULATION.sommaire}
          </p>
          {liste}
        </>
      ) : (
        <details>
          <summary>{ARTICULATION.sommaire}</summary>
          {liste}
        </details>
      )}
    </nav>
  );
}

// ── Le gabarit ──────────────────────────────────────────────────────────────

export function PageLegale({ page }: { page: TexteLegal }) {
  const menu = useMenu();
  const racine = useRef<HTMLDivElement>(null);

  // Le bouton de la barre du site se comporte ici comme sur les autres pages.
  useAimants(racine);
  useTitreDePage(page.titreOnglet, page.metaDescription);

  const identifiants = ancres(page.sections);
  const sommaire: EntreeDeSommaire[] = page.sections.flatMap((section, k) =>
    section.niveau === 2
      ? [{ ancre: identifiants[k], titre: section.titre }]
      : [],
  );

  return (
    <div className="acc leg" ref={racine}>
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement — et de « Retour en
          haut » — doit pouvoir recevoir le focus. */}
      <main id={ID_DU_CONTENU} tabIndex={-1} inert={menu.ouvert}>
        <div className="acc-w">
          <header className="leg-tete">
            <h1>{page.titre}</h1>
            {page.dateDeMiseAJour !== null && (
              <p className="leg-date">
                {ARTICULATION.miseAJour} {dateLisible(page.dateDeMiseAJour)}
              </p>
            )}
            <nav className="leg-textes" aria-label={ARTICULATION.nomDeLaBarre}>
              <ul>
                {PAGES_LEGALES.map((texte) => (
                  <li key={texte.chemin}>
                    <a
                      href={texte.chemin}
                      aria-current={
                        texte.chemin === page.chemin ? "page" : undefined
                      }
                    >
                      {NOMS_DES_TEXTES[texte.chemin]}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </header>

          <div className="leg-corps">
            {sommaire.length > 0 && <Sommaire entrees={sommaire} />}

            <div className="leg-colonne">
              {/* Le texte, et lui seul : rien d'autre n'entre dans cet
                  élément, pour qu'on puisse le comparer au contenu. */}
              <article className="leg-texte">
                {page.introduction.length > 0 && (
                  <div className="leg-intro">
                    {page.introduction.map((bloc, k) => (
                      <Bloc key={k} bloc={bloc} />
                    ))}
                  </div>
                )}
                {page.sections.map((section, k) => {
                  const Titre = section.niveau === 2 ? "h2" : "h3";
                  return (
                    <div
                      key={identifiants[k]}
                      className={`leg-section leg-section-${section.niveau}`}
                    >
                      <Titre id={identifiants[k]}>{section.titre}</Titre>
                      {section.blocs.map((bloc, rang) => (
                        <Bloc key={rang} bloc={bloc} />
                      ))}
                    </div>
                  );
                })}
              </article>

              <p className="leg-retour">
                <a href={`#${ID_DU_CONTENU}`}>{ARTICULATION.retour}</a>
              </p>
            </div>
          </div>
        </div>
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}

// ── Les quatre pages ────────────────────────────────────────────────────────

/** Le texte d'une page, par son chemin. Un texte absent est une erreur dite,
 *  pas une page blanche. */
function texteDe(chemin: CheminLegal): TexteLegal {
  const page = PAGES_LEGALES.find((texte) => texte.chemin === chemin);
  if (!page) throw new Error(`Texte légal introuvable : ${chemin}`);
  return page;
}

/** `/mentions-legales` */
export function MentionsLegales() {
  return <PageLegale page={texteDe("/mentions-legales")} />;
}

/** `/rgpd` */
export function Rgpd() {
  return <PageLegale page={texteDe("/rgpd")} />;
}

/** `/cgv` */
export function Cgv() {
  return <PageLegale page={texteDe("/cgv")} />;
}

/** `/politique-de-confidentialite` */
export function PolitiqueDeConfidentialite() {
  return <PageLegale page={texteDe("/politique-de-confidentialite")} />;
}
