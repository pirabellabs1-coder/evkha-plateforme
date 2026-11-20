/** Le blog : la liste (`/blog`) et la page d'un article (`/blog/$slug`).
 *
 * Le site de la cliente n'avait pas de blog, seulement un article rangé sous
 * sa boîte à outils. La plateforme lui donne une liste, des thèmes et une
 * vraie mise en page de lecture. La SOURCE des articles est `contenuBlog.ts` :
 * un article s'y ajoute par une entrée de liste, et ces deux pages n'ont rien
 * à apprendre de lui — filtres, carte, sommaire, temps de lecture et données
 * structurées se construisent sur la liste (règle 5).
 *
 * ## La liste
 *
 * - Les filtres sont des boutons à bascule (`aria-pressed`), « Tous » par
 *   défaut. Un thème SANS article reste affiché, désactivé : la liste fermée
 *   des thèmes dit de quoi parle le blog, sans promettre d'article.
 * - Le filtre choisi s'écrit dans l'adresse (`?theme=…`), sans recharger la
 *   page ni empiler une entrée d'historique : l'adresse copiée rouvre la liste
 *   sur le même thème, et « Précédent » quitte le blog au lieu de défaire les
 *   filtres un à un. La région d'état annonce le nombre ET le thème.
 * - Le premier article de la liste filtrée est mis en avant, en grand. Avec
 *   un seul article, la page n'a donc ni grille clairsemée ni case vide.
 * - Une carte = UN lien, porté par son titre et étendu à toute la carte : le
 *   faux bouton « Lire l'article » est décoratif, masqué aux lecteurs
 *   d'écran, qui entendraient sinon le même libellé à chaque carte.
 *
 * ## L'article
 *
 * Une colonne de lecture étroite (voir la feuille), un sommaire des parties
 * avec ancres, les encadrés « Demandez-vous » et « Exemple » distingués par
 * leur amorce autant que par leur habillage, et les données structurées
 * `Article` en JSON-LD. Aucune date n'y figure tant que `publieLe` vaut
 * `null` : une date supposée serait un fait inventé, déclaré aux moteurs.
 *
 * ## La photo, les citations, les liens sortants (portraits, 20/11/2026)
 *
 * Un article PEUT porter une photo (`image`) : elle ouvre sa page, coiffe sa
 * carte dans la liste, et se déclare dans les données structurées. Sans
 * photo, rien ne change — ni cadre vide, ni image de remplacement.
 * Une citation est un `<blockquote>`, son auteur une légende ; un lien qui
 * sort du site s'ouvre dans un nouvel onglet, et le dit.
 *
 * Le corps de l'article n'attend pas le défilement pour apparaître : un texte
 * qu'on vient lire s'affiche. Seul l'encadré de fin est révélé.
 *
 * Un slug inconnu rend une page « article introuvable », avec retour au blog
 * — jamais une page vide (règle 1). Elle demande aux moteurs de ne pas
 * l'indexer, le temps de son affichage.
 *
 * ## Les passerelles
 *
 * Le blog est une porte d'entrée gratuite : chaque page se termine par UNE
 * passerelle vers l'étape payante la plus proche de son sujet (`Passage`),
 * sans prix. Aucun montant n'est écrit ici.
 */
import { useRef, useState, type CSSProperties } from "react";
import { useParams } from "@tanstack/react-router";

import {
  adresseDeLArticle,
  adresseDuTheme,
  ARTICLES,
  articleDuSlug,
  AUTEUR_DU_BLOG,
  BLOG,
  estUnTheme,
  libelleDuTheme,
  PAGE_ARTICLE,
  PARAMETRE_DU_THEME,
  ROUTE_DU_BLOG,
  THEMES,
  type Article,
  type ImageDArticle,
  type SlugDeTheme,
} from "./contenuBlog";
import type { ElementDArticle } from "./contenuRessources";
import { CHEMINS } from "./contenuSite";
import { Bouton } from "./PiecesSite";
import { CadreDePage, Passage, TitreDOuverture } from "./Ressources";
import { useReveler } from "./reveler";
import {
  titreDOnglet,
  useAimants,
  useSansIndexation,
  useTitreDePage,
  variables,
} from "./site";
// Le socle d'abord, la feuille du lot ensuite.
import "./Site.css";
import "./Ressources.css";

// ── La liste ────────────────────────────────────────────────────────────────

function aDesArticles(theme: SlugDeTheme): boolean {
  return ARTICLES.some((article) => article.theme === theme);
}

/** Le thème demandé par l'adresse (`/blog?theme=…`), s'il existe et s'il a au
 *  moins un article. Tout le reste — paramètre absent, inconnu, thème vide —
 *  rend `null` : « Tous ». */
function themeDeLAdresse(): SlugDeTheme | null {
  const demande = new URLSearchParams(window.location.search).get(PARAMETRE_DU_THEME);
  return estUnTheme(demande) && aDesArticles(demande) ? demande : null;
}

/** Écrit le thème choisi dans l'adresse, SANS recharger la page et sans
 *  empiler d'entrée d'historique (`replaceState`). « Tous » retire le
 *  paramètre : l'adresse nue reste celle de la liste entière. Le reste de
 *  l'adresse — autres paramètres, ancre — et l'état de l'historique, dont le
 *  routeur se sert, sont gardés tels quels. */
function ecrireLeThemeDansLAdresse(theme: SlugDeTheme | null): void {
  const adresse = new URL(window.location.href);
  if (theme === null) adresse.searchParams.delete(PARAMETRE_DU_THEME);
  else adresse.searchParams.set(PARAMETRE_DU_THEME, theme);
  window.history.replaceState(
    window.history.state,
    "",
    `${adresse.pathname}${adresse.search}${adresse.hash}`,
  );
}

/** Le point de la photo gardé en vue quand son cadre la rogne. Sans cadrage
 *  écrit, aucun style : la feuille centre. */
function cadrageDe(image: ImageDArticle): CSSProperties | undefined {
  return image.cadrage === undefined ? undefined : { objectPosition: image.cadrage };
}

/** Une carte d'article. `aLaUne` : la première de la liste, en grand. */
function CarteDArticle({ article, aLaUne }: { article: Article; aLaUne: boolean }) {
  const { image } = article;
  return (
    <li className={aLaUne ? "res-article-rang res-article-rang-une" : "res-article-rang"}>
      <article className={image ? "res-article res-article-illustre" : "res-article"} data-reveal="">
        {/* La photo coiffe la carte. Le cadre donne la forme, les attributs
            le ratio du fichier : rien ne saute au chargement. Sous la ligne
            de flottaison : chargée à l'approche. */}
        {image && (
          <div className="res-article-image">
            <img
              className="res-article-photo"
              src={image.src}
              alt={image.alt}
              width={image.largeur}
              height={image.hauteur}
              loading="lazy"
              decoding="async"
              style={cadrageDe(image)}
            />
          </div>
        )}
        <div className="res-article-tete">
          <span className="acc-tag">{libelleDuTheme(article.theme)}</span>
          <h3>
            <a href={adresseDeLArticle(article.slug)}>{article.titre}</a>
          </h3>
          <p className="res-article-sous-titre">{article.sousTitre}</p>
        </div>
        <div className="res-article-corps">
          {aLaUne && <small className="res-etiquette">{BLOG.aLaUne}</small>}
          <p>{article.accroche}</p>
          <p className="res-article-meta">{BLOG.lecture(article.tempsDeLecture)}</p>
          {/* Décoratif : le lien de la carte est son titre, étendu à toute la
              carte par la feuille. */}
          <span className="acc-btn acc-btn-noir res-article-lire" aria-hidden="true">
            {BLOG.lire}
            <span className="acc-btn-fleche">→</span>
          </span>
        </div>
      </article>
    </li>
  );
}

export function Blog() {
  const page = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<SlugDeTheme | null>(themeDeLAdresse);

  // La clé : changer de filtre monte de nouvelles cartes, à observer à leur
  // tour.
  useReveler(page, theme, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(titreDOnglet(BLOG.titreOnglet), BLOG.description);

  /** Un filtre choisi : l'état de la page, et l'adresse qui le dit. */
  function choisir(prochain: SlugDeTheme | null) {
    setTheme(prochain);
    ecrireLeThemeDansLAdresse(prochain);
  }

  const visibles =
    theme === null ? ARTICLES : ARTICLES.filter((article) => article.theme === theme);

  return (
    <CadreDePage racine={page} classe="res-blog">
      {/* ── Ouverture ───────────────────────────────────────────────────── */}
      <div className="res-ouverture res-ouverture-courte">
        <div className="acc-w">
          <span className="acc-tag acc-entre">{BLOG.surtitre}</span>
          <TitreDOuverture titre={BLOG.titre} />
          <p className="res-chapeau acc-entre" style={variables({ "--i": 1 })}>
            {BLOG.presentation}
          </p>
        </div>
      </div>

      {/* ── Les articles, filtrés par thème ─────────────────────────────── */}
      <section className="acc-section acc-section-suite" aria-labelledby="res-articles-titre">
        <div className="acc-w">
          <div className="res-articles-tete">
            <h2 id="res-articles-titre">{BLOG.titreDesArticles}</h2>
            <div className="res-filtres" role="group" aria-label={BLOG.filtres.nom}>
              <button
                className="res-filtre"
                type="button"
                aria-pressed={theme === null}
                onClick={() => choisir(null)}
              >
                {BLOG.filtres.tous}
              </button>
              {THEMES.map((entree) => (
                <button
                  key={entree.slug}
                  className="res-filtre"
                  type="button"
                  aria-pressed={theme === entree.slug}
                  // Un thème sans article : montré, mais hors d'atteinte.
                  disabled={!aDesArticles(entree.slug)}
                  // Une bascule : un second clic revient à « Tous ».
                  onClick={() => choisir(theme === entree.slug ? null : entree.slug)}
                >
                  {entree.libelle}
                </button>
              ))}
            </div>
          </div>

          {/* Annoncé à chaque changement de filtre : le nombre, et le thème
              quand un filtre est posé. */}
          <p className="res-compte" role="status">
            {BLOG.compte(visibles.length, theme === null ? null : libelleDuTheme(theme))}
          </p>

          {visibles.length === 0 ? (
            <p className="res-vide">{BLOG.aucun}</p>
          ) : (
            <ul className="res-articles">
              {visibles.map((article, k) => (
                <CarteDArticle key={article.slug} article={article} aLaUne={k === 0} />
              ))}
            </ul>
          )}
        </div>
      </section>

      <Passage passerelle={BLOG.passerelle} />
    </CadreDePage>
  );
}

// ── L'article ───────────────────────────────────────────────────────────────

/** Une date `AAAA-MM-JJ` en toutes lettres. Lue en temps universel : une date
 *  de publication n'a pas d'heure, et ne doit pas reculer d'un jour selon le
 *  fuseau du lecteur. */
function dateEnLettres(jour: string): string {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeZone: "UTC" }).format(
    new Date(`${jour}T00:00:00Z`),
  );
}

/** Un élément du corps. L'encadré « Demandez-vous » et l'encadré « Exemple »
 *  gardent leur amorce relevée : c'est elle, pas la couleur, qui dit lequel
 *  est lequel. */
function ElementDuCorps({ element }: { element: ElementDArticle }) {
  switch (element.genre) {
    case "paragraphe":
      return <p>{element.texte}</p>;
    case "liste":
      return (
        <>
          {element.introduction && (
            <p className="res-liste-amorce">{element.introduction}</p>
          )}
          <ul className="res-liste">
            {element.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </>
      );
    case "question":
      return (
        <div className="res-encadre res-encadre-question">
          <p className="res-encadre-amorce">{element.amorce}</p>
          <p>{element.texte}</p>
        </div>
      );
    case "exemple":
      return (
        <div className="res-encadre res-encadre-exemple">
          <p className="res-encadre-amorce">{element.amorce}</p>
          <p>{element.texte}</p>
        </div>
      );
    case "citation":
      // Les guillemets sont du TEXTE, pas un décor de la feuille : ils
      // suivent la citation quand on la copie.
      return (
        <figure className="res-citation">
          <blockquote>
            <p>
              {PAGE_ARTICLE.guillemets.ouvrant}
              {element.texte}
              {PAGE_ARTICLE.guillemets.fermant}
            </p>
          </blockquote>
          {element.auteur && <figcaption>{element.auteur}</figcaption>}
        </figure>
      );
    case "lien":
      // Un site tiers : nouvel onglet, sans lui donner la main sur celui-ci
      // (`noopener`). Le libellé dit où il mène, la mention qu'il sort.
      return (
        <p className="res-lien-sortant">
          <a href={element.lien} target="_blank" rel="noopener">
            {element.libelle} <span className="res-lien-mention">{PAGE_ARTICLE.nouvelOnglet}</span>
          </a>
        </p>
      );
  }
}

/** Les éléments d'une partie, dans l'ordre de lecture. L'ordre ne change
 *  jamais : le rang sert de clé. */
function Elements({ elements }: { elements: ElementDArticle[] }) {
  return (
    <>
      {elements.map((element, k) => (
        <ElementDuCorps key={k} element={element} />
      ))}
    </>
  );
}

/** Les données structurées de l'article (schema.org `Article`). Tout vient de
 *  l'article ; `datePublished` n'est déclarée que si la date est connue.
 *  L'auteur est un NOM COMPLET, dans l'écriture du reste du site — pas la
 *  signature affichée, qui n'est qu'un prénom (`contenuBlog.AUTEUR_DU_BLOG`). */
function donneesStructurees(article: Article): Record<string, unknown> {
  const adresse = `${window.location.origin}${adresseDeLArticle(article.slug)}`;
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: article.titre,
    alternativeHeadline: article.sousTitre,
    description: article.entete.description,
    articleSection: libelleDuTheme(article.theme),
    inLanguage: "fr",
    wordCount: article.nombreDeMots,
    timeRequired: `PT${article.tempsDeLecture}M`,
    author: { "@type": "Person", name: article.auteur ?? AUTEUR_DU_BLOG },
    publisher: { "@type": "Organization", name: PAGE_ARTICLE.editeur },
    mainEntityOfPage: adresse,
    url: adresse,
    // La photo, à son adresse complète et à ses dimensions — seulement si
    // l'article en a une.
    ...(article.image
      ? {
          image: {
            "@type": "ImageObject",
            url: `${window.location.origin}${article.image.src}`,
            width: article.image.largeur,
            height: article.image.hauteur,
          },
        }
      : {}),
    ...(article.publieLe === null ? {} : { datePublished: article.publieLe }),
  };
}

const ANCRE_DE_LA_CONCLUSION = "conclusion";

function PageDArticle({ article }: { article: Article }) {
  const page = useRef<HTMLDivElement>(null);

  useReveler(page, article.slug, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(
    titreDOnglet(article.entete.titreOnglet),
    article.entete.description,
    true,
    article.image,
  );

  const theme = libelleDuTheme(article.theme);
  // Les parties du sommaire : chaque section, puis la conclusion. Les ancres
  // sont numérotées — un intertitre peut changer sans casser un lien partagé.
  const sections = article.sections.map((section, k) => ({
    section,
    ancre: `partie-${k + 1}`,
  }));
  const sommaire = [
    ...sections.map(({ section, ancre }) => ({ ancre, intertitre: section.intertitre })),
    { ancre: ANCRE_DE_LA_CONCLUSION, intertitre: article.conclusion.intertitre },
  ];

  return (
    <CadreDePage racine={page} classe="res-lecture">
      <article aria-labelledby="res-article-titre">
        {/* ── En-tête de l'article ──────────────────────────────────────── */}
        {/* Un `<div>`, pas un `<header>` : la page n'a qu'UN en-tête de page,
            celui du site. Un second `<header>` se lit comme un second repère
            « bannière » dans les outils qui ne regardent pas son parent. */}
        <div className="res-ouverture res-ouverture-courte">
          {/* Avec une photo, l'en-tête se met sur deux colonnes : le titre à
              gauche, la photo à droite. Posée SOUS le titre, une photo
              verticale laissait vide toute la moitié droite de l'écran
              (retour du client, 20/11/2026). */}
          <div
            className={
              article.image
                ? "acc-w res-lecture-largeur res-ouverture-illustree"
                : "acc-w res-lecture-largeur"
            }
          >
            <div className="res-ouverture-texte">
            <nav className="res-fil acc-entre" aria-label={PAGE_ARTICLE.filDAriane}>
              <ol>
                <li>
                  <a href={ROUTE_DU_BLOG}>{PAGE_ARTICLE.blog}</a>
                </li>
                <li>
                  <a href={adresseDuTheme(article.theme)}>{theme}</a>
                </li>
                <li aria-current="page">{article.titre}</li>
              </ol>
            </nav>
            <h1 id="res-article-titre" className="acc-entre" style={variables({ "--i": 1 })}>
              {article.titre}
            </h1>
            <p className="res-sous-titre acc-entre" style={variables({ "--i": 2 })}>
              {article.sousTitre}
            </p>
            <ul className="res-meta acc-entre" style={variables({ "--i": 3 })}>
              <li>{theme}</li>
              <li>{BLOG.lecture(article.tempsDeLecture)}</li>
              {article.publieLe !== null && (
                <li>
                  {PAGE_ARTICLE.publieLe}{" "}
                  <time dateTime={article.publieLe}>{dateEnLettres(article.publieLe)}</time>
                </li>
              )}
            </ul>
            </div>
            {/* La photo de l'article. Haut de page : pas de chargement
                différé. Une photo verticale garde un cadre vertical, plus
                étroit, plutôt que d'être rognée en bandeau. */}
            {article.image && (
              <div
                className={
                  article.image.hauteur > article.image.largeur
                    ? "res-photo res-photo-verticale"
                    : "res-photo"
                }
              >
                <img
                  className="res-photo-image"
                  src={article.image.src}
                  alt={article.image.alt}
                  width={article.image.largeur}
                  height={article.image.hauteur}
                  loading="eager"
                  decoding="async"
                  style={cadrageDe(article.image)}
                />
              </div>
            )}
          </div>
        </div>

        <div className="acc-w res-lecture-largeur res-lecture-grille">
          {/* ── Sommaire ─────────────────────────────────────────────────── */}
          <nav className="res-sommaire" aria-labelledby="res-sommaire-titre">
            <h2 id="res-sommaire-titre">{PAGE_ARTICLE.sommaire}</h2>
            <ol>
              {sommaire.map((partie) => (
                <li key={partie.ancre}>
                  <a href={`#${partie.ancre}`}>{partie.intertitre}</a>
                </li>
              ))}
            </ol>
          </nav>

          {/* ── Le texte ─────────────────────────────────────────────────── */}
          <div className="res-prose">
            <section className="res-chapo">
              <h2>{article.chapo.intertitre}</h2>
              {article.chapo.paragraphes.map((paragraphe, k) => (
                <p key={paragraphe} className={k === 0 ? "res-chapo-premier" : undefined}>
                  {paragraphe}
                </p>
              ))}
            </section>

            {sections.map(({ section, ancre }) => (
              <section key={ancre}>
                <h2 id={ancre}>{section.intertitre}</h2>
                <Elements elements={section.elements} />
                {(section.sousSections ?? []).map((sous) => (
                  <div key={sous.intertitre} className="res-sous-partie">
                    <h3>{sous.intertitre}</h3>
                    <Elements elements={sous.elements} />
                  </div>
                ))}
              </section>
            ))}

            <section>
              <h2 id={ANCRE_DE_LA_CONCLUSION}>{article.conclusion.intertitre}</h2>
              <Elements elements={article.conclusion.elements} />
              <p className="res-salut">{article.conclusion.salut}</p>
              <p className="res-signature">{article.conclusion.signature}</p>
            </section>

            {/* ── L'appel de fin d'article : un document à demander ──────── */}
            <aside className="res-bonus" aria-labelledby="res-bonus-titre" data-reveal="">
              <h2 id="res-bonus-titre">{article.appel.titre}</h2>
              <p className="res-bonus-document">{article.appel.document}</p>
              <p>{article.appel.corps}</p>
              <Bouton
                lien={article.appel.bouton.lien}
                aspect="clair"
                className="res-bouton-souple"
              >
                {article.appel.bouton.libelle}
              </Bouton>
            </aside>
          </div>
        </div>
      </article>

      <Passage passerelle={article.passerelle} />

      {/* Les données structurées, sérialisées par `JSON.stringify` et posées
          en TEXTE : React n'y interprète aucun balisage. */}
      <script type="application/ld+json">{JSON.stringify(donneesStructurees(article))}</script>
    </CadreDePage>
  );
}

function ArticleIntrouvable() {
  const page = useRef<HTMLDivElement>(null);
  const i = PAGE_ARTICLE.introuvable;

  useAimants(page);
  useTitreDePage(titreDOnglet(i.titreOnglet), i.description, false);
  // L'application répond 200 à toute adresse : sans cette balise, un moteur
  // indexerait « article introuvable » à l'adresse fautive.
  useSansIndexation();

  return (
    <CadreDePage racine={page} classe="res-introuvable">
      <div className="res-ouverture res-ouverture-centree">
        <div className="acc-w">
          <span className="acc-tag acc-entre">{i.surtitre}</span>
          <TitreDOuverture titre={i.titre} />
          <p className="res-chapeau acc-entre" style={variables({ "--i": 1 })}>
            {i.corps}
          </p>
          <div className="res-appels acc-entre" style={variables({ "--i": 2 })}>
            <Bouton lien={ROUTE_DU_BLOG} aspect="noir">
              {i.bouton}
            </Bouton>
          </div>
        </div>
      </div>

      <Passage passerelle={BLOG.passerelle} />
    </CadreDePage>
  );
}

/** `/blog/$slug`. Le slug est lu dans l'adresse, comme la fiche d'un produit
 *  de la boutique lit le sien. La clé remonte la page quand on passe d'un
 *  article à un autre : son sommaire et ses blocs révélés repartent de zéro. */
export function ArticleDeBlog() {
  const { slug } = useParams({ from: CHEMINS.article });
  const article = articleDuSlug(slug);
  return article ? <PageDArticle key={article.slug} article={article} /> : <ArticleIntrouvable />;
}
