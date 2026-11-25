/** Page publique des études vendues à l'unité — reprise de
 *  `evkha.fr/etudedemarche`, dans le langage visuel de la page d'accueil.
 *
 * C'est la page de vente principale : le bouton « Commander une étude » de
 * l'accueil y mène. Elle s'adresse au porteur de projet qui achète une étude,
 * et renvoie, avant son appel final, vers les deux autres portes — la boutique
 * d'études prêtes et les abonnements des professionnels.
 *
 * ## Refonte du 19/11/2026 : la forme change, pas ce que la page dit
 *
 * Tous les blocs d'avant sont là, avec leur texte de `contenu.ts` : ouverture,
 * preuves chiffrées, méthode en quatre étapes, « quatre études au choix », les
 * cartes, les interrogations du porteur, le comparatif, les questions, l'appel
 * final. Ce que la nouvelle forme ajoute — l'italique d'un titre, la barre
 * d'ancres, la ligne « ensuite dans le parcours », la passerelle — est dans
 * `contenuEtudes.ts`. La barre, le menu, le pied, les boutons et la feuille de
 * base sont ceux de l'accueil, lus dans le socle commun (`EnTeteSite`,
 * `PiedSite`, `PiecesSite`, `site.ts`, `Site.css`) et non recopiés (règle 5).
 *
 * ## Deux principes de construction, inchangés
 *
 * 1. **Les prix viennent du serveur.** Ils sont lus dans
 *    `/api/public/livrables/`, qui les tient de la table `Offer` — y compris
 *    la fourchette de l'ouverture, calculée sur le catalogue et non écrite.
 *    « 149 € » posé dans ce fichier ferait une seconde source, qui
 *    contredirait le paiement au premier changement de tarif (règle 5). Le
 *    texte éditorial, lui, vit dans `contenu.ts` — y compris le nombre de
 *    chapitres ANNONCÉ, qui n'est pas celui du plan de production et n'a pas à
 *    l'être : voir `ArgumentaireEtude`.
 *
 * 2. **Aucun tarif n'est affiché tant qu'il n'est pas chargé**, et une panne
 *    ne se lit pas comme un vide. Un prix de repli en attendant l'API
 *    afficherait un prix faux à qui a une connexion lente. L'emplacement de la
 *    fourchette dit s'il attend, s'il a échoué ou si le catalogue est vide ;
 *    une seule région d'alerte, en haut de page et toujours dans le DOM,
 *    annonce la panne (règle 1). Une réponse 200 mal formée est une panne :
 *    `chargerLivrables` lève alors une erreur.
 *
 * ## L'ordre des cartes est celui du parcours, pas celui du serveur
 *
 * Voir `ordonnees` : marché, concurrence, business plan, stratégie. Les
 * cartes sont numérotées dans cet ordre, et chacune est suivie d'une ligne qui
 * nomme le document suivant — sans remise ni lot, qui n'existent pas.
 *
 * ## Où mènent les boutons
 *
 * Vers la création de compte, pas vers la connexion : le visiteur qui clique
 * n'a par définition pas encore de compte, et lui présenter un écran de
 * connexion est le meilleur moyen de le perdre. L'étude choisie voyage dans
 * l'adresse (`/inscription?livrable=etude-marche`, voir `lienCommande`).
 * C'est l'inscription qui enchaîne ensuite sur le paiement.
 *
 * ## Le mouvement réduit RÉDUIT, il ne supprime pas
 *
 * Même politique que l'accueil (décision du client du 19/11/2026) : sous
 * `prefers-reduced-motion`, les blocs apparaissent encore au défilement, en
 * fondu et sans translation — d'où l'option passée à `useReveler` —, les
 * survols restent doux, le ruban défile au ralenti. Les soulèvements et les
 * boutons aimantés sont coupés. Deux boutons de pause arrêtent le ruban
 * (WCAG 2.2.2).
 */
import { useEffect, useRef, type ReactNode } from "react";

import { CONTACT_EMAIL, ETUDES, ETUDES_PAGE } from "./contenu";
import {
  CARTES,
  COMPARATIF,
  DESCRIPTION_DE_LA_PAGE,
  ID_DES_CARTES,
  IMAGE_D_OUVERTURE,
  LIBELLES_COURTS,
  MENTION_DU_PRIX,
  OUVERTURE_ETUDES,
  PARCOURS_DES_ETUDES,
  PASSERELLE,
  RUBAN_DES_ETUDES,
  SUITE_DU_PARCOURS,
  TITRE_DE_LA_PAGE,
  TITRES,
} from "./contenuEtudes";
import { ID_DU_CONTENU, TARIFS } from "./contenuSite";
import {
  chargerLivrables,
  euros,
  ancreDeLEtude,
  lienCommande,
  type LivrablePublic,
} from "./donnees";
import { EnTeteSite } from "./EnTeteSite";
import { Bouton, BoutonPause } from "./PiecesSite";
import { PiedSite } from "./PiedSite";
import { useReveler } from "./reveler";
import {
  bornes,
  lisible,
  tarifDe,
  useAimants,
  useChargement,
  useMenu,
  usePause,
  useDonneesStructurees,
  useQuestionsStructurees,
  useTitreDePage,
  variables,
  type Tarif,
} from "./site";
import { servicesDesEtudes } from "./referencement";
// Le socle d'abord, la feuille de la page ensuite : à spécificité égale, c'est
// la page qui a le dernier mot.
import "./Site.css";
import "./NosEtudes.css";

/** L'ordre de la page de vente, et non celui du serveur.
 *
 * L'API trie par prix croissant — un ordre juste pour un catalogue, faux pour
 * une page de vente : il mettait l'étude de concurrence en tête, quand
 * `evkha.fr` ouvre sur l'étude de marché. La première carte n'est pas la moins
 * chère, c'est le produit d'appel, et les suivantes sont les étapes du projet.
 *
 * L'ordre est celui de `ETUDES`, qui reprend la page de la cliente. Une offre
 * sans argumentaire passe à la fin plutôt que de disparaître : une étude
 * invisible parce qu'un texte manque serait un défaut bien pire qu'un ordre
 * imparfait. Une entrée sans slug ni libellé, elle, n'est pas une offre : on
 * ne saurait ni la nommer ni la commander.
 */
function ordonnees(etudes: LivrablePublic[]): LivrablePublic[] {
  const place = (slug: string) => {
    const index = PARCOURS_DES_ETUDES.indexOf(slug);
    return index === -1 ? PARCOURS_DES_ETUDES.length : index;
  };
  return etudes
    .filter(
      (e) =>
        typeof e?.slug === "string" &&
        e.slug !== "" &&
        typeof e.libelle === "string" &&
        e.libelle !== "",
    )
    .sort((a, b) => place(a.slug) - place(b.slug));
}

/** « de 89 € à 195 € », calculé sur le catalogue chargé.
 *
 * L'ouverture annonce une fourchette de prix. L'écrire dans le contenu en
 * ferait le seul endroit de la page où un tarif ne vient pas du serveur — et
 * le premier à mentir le jour d'un changement. Même calcul et mêmes mots que
 * la carte « Livrable sur mesure » de l'accueil : les deux pages annoncent la
 * même chose. Une offre à zéro n'entre pas dans le calcul (`site.bornes`).
 */
function fourchette(etudes: LivrablePublic[]): string | null {
  const b = bornes(etudes.map((e) => e.prix_cents));
  if (!b) return null;
  return b.bas === b.haut
    ? euros(b.bas)
    : `de ${euros(b.bas)} à ${euros(b.haut)}`;
}

/** L'identifiant d'une carte : écrit une fois, dans `donnees.ts`, que
 *  l'accueil lit aussi pour y renvoyer. */
const ancreDe = ancreDeLEtude;

function numero(rang: number): string {
  return String(rang + 1).padStart(2, "0");
}

/** Pastille à coche dorée. La coche est décorative : elle double une
 *  information déjà portée par le texte, et un lecteur d'écran qui
 *  l'annoncerait dirait « coche » avant chaque ligne sans rien apporter. */
function Coche() {
  return (
    <span className="etu-coche" aria-hidden="true">
      ✓
    </span>
  );
}

/** L'introduction d'une section : surtitre, titre en deux temps (le second
 *  en italique), puis le texte. Même habillage que sur l'accueil
 *  (`.acc-intro`, `Site.css`). */
function Entree({
  surtitre,
  titre,
  children,
}: {
  surtitre: string;
  titre: { avant: string; fin: string };
  children: ReactNode;
}) {
  return (
    <div className="acc-intro" data-reveal="">
      <div>
        <span className="acc-tag">{surtitre}</span>
        <h2>
          {titre.avant} <span className="acc-s">{titre.fin}</span>
        </h2>
      </div>
      {children}
    </div>
  );
}

/** Une étude : à gauche ce qu'on achète (numéro, nom, prix, bouton), à droite
 *  ce qu'on reçoit. Le bouton de commande est dans la première colonne, donc
 *  en haut de la carte sur un téléphone : on n'a pas à la lire jusqu'au bout
 *  pour le trouver.
 *
 *  `suivante` : le document suivant du parcours, s'il est au catalogue. */
function Carte({
  etude,
  rang,
  suivante,
  provisoire = false,
}: {
  etude: Pick<LivrablePublic, "slug" | "libelle"> & { prix_cents?: number };
  rang: number;
  suivante: Pick<LivrablePublic, "slug" | "libelle"> | null;
  /** Le catalogue n'a pas encore répondu : la carte porte son argumentaire,
   *  la phrase d'attente à la place du prix, et un bouton neutralisé. */
  provisoire?: boolean;
}) {
  const texte = ETUDES[etude.slug];
  const suite = SUITE_DU_PARCOURS[etude.slug];
  // Une offre créée à zéro (brouillon, erreur de saisie) n'a pas de prix :
  // la carte le dit et son bouton est neutralisé, comme sur l'accueil.
  const vendable = !provisoire && lisible(etude.prix_cents);
  const titre = `${ancreDe(etude.slug)}-titre`;

  return (
    <li>
      <article
        className="etu-carte"
        id={ancreDe(etude.slug)}
        aria-labelledby={titre}
        data-reveal=""
        data-provisoire={provisoire ? "" : undefined}
      >
        <div className="etu-carte-tete">
          <span className="etu-carte-numero" aria-hidden="true">
            {numero(rang)}
          </span>
          {texte && <small className="etu-carte-surtitre">{texte.surtitre}</small>}
          <h3 id={titre}>{etude.libelle}</h3>
          {vendable ? (
            <p className="etu-prix">
              {euros(etude.prix_cents ?? 0)}
              <span className="etu-prix-mention"> {MENTION_DU_PRIX}</span>
            </p>
          ) : (
            <p className="etu-prix-absent">{provisoire ? TARIFS.attente : TARIFS.absent}</p>
          )}
          <Bouton
            lien={lienCommande(etude.slug)}
            aspect="noir"
            inactif={!vendable}
            className="etu-carte-bouton"
          >
            {texte?.bouton ?? CARTES.commanderSobre(etude.libelle)}
          </Bouton>
        </div>

        <div className="etu-carte-corps">
          <p className="etu-quoi">{CARTES.quoi}</p>
          {/* Le chapeau porte le nombre de chapitres ANNONCÉ (`contenu.ts`) ;
              une offre sans argumentaire garde une carte sobre. */}
          <p className="etu-chapeau">
            {texte ? (
              <>
                <b>{texte.chapitres}</b> {texte.chapeau}
              </>
            ) : (
              CARTES.chapeauSobre
            )}
          </p>
          {texte && texte.details.length > 0 && (
            <ul className="etu-points">
              {texte.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          )}
          {texte && <p className="etu-carte-pied">{texte.pied}</p>}
        </div>
      </article>

      {suite && suivante && (
        <p className="etu-suite" data-reveal="">
          <span className="etu-suite-etiquette">{CARTES.etiquetteDuParcours}</span>
          <a href={`#${ancreDe(suivante.slug)}`}>
            <strong>{suivante.libelle}</strong>, {suite.benefice}
            <span aria-hidden="true"> ↓</span>
          </a>
        </p>
      )}
    </li>
  );
}

/** La fourchette de l'ouverture, ou la phrase qui dit pourquoi elle manque. */
function Fourchette({ tarif, libelle }: { tarif: Tarif; libelle: string }) {
  if (tarif.etat !== "connu") {
    return (
      <>
        <span className="etu-preuve-absent">{TARIFS[tarif.etat]}</span>
        <span className="etu-preuve-libelle">{libelle}</span>
      </>
    );
  }
  return (
    <>
      <b>{tarif.texte}</b>
      <span className="etu-preuve-libelle">
        {libelle} · {MENTION_DU_PRIX}
      </span>
    </>
  );
}

/** Calculé une fois : rien n'y dépend d'un rendu. */
const SERVICES_DES_ETUDES = servicesDesEtudes(DESCRIPTION_DE_LA_PAGE);

export function NosEtudes() {
  const livrables = useChargement(chargerLivrables);
  const menu = useMenu();
  const { fige, basculer: basculerLaPause } = usePause();
  const page = useRef<HTMLDivElement>(null);

  // La clé : les cartes d'étude arrivent après le premier rendu, et doivent
  // être observées à leur tour. L'option : sur cette page comme sur l'accueil,
  // le mouvement réduit garde la révélation (en fondu seul, voir `Site.css`)
  // au lieu de tout afficher d'emblée.
  useReveler(page, livrables.etat, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(TITRE_DE_LA_PAGE, DESCRIPTION_DE_LA_PAGE);
  useDonneesStructurees(SERVICES_DES_ETUDES);
  // Les questions de la page, déclarées telles qu'elle les affiche.
  useQuestionsStructurees(page);

  // Arrivé d'une autre page sur `/etudes#carte-<slug>` (le parcours de
  // l'accueil, le menu) : la carte n'existe qu'une fois le catalogue reçu, et
  // le navigateur a déjà renoncé à l'ancre. On y défile alors, UNE fois.
  const ancreSuivie = useRef(false);
  useEffect(() => {
    if (livrables.etat !== "recu" || ancreSuivie.current) return;
    ancreSuivie.current = true;
    const ancre = decodeURIComponent(window.location.hash.slice(1));
    if (!ancre.startsWith(ancreDeLEtude(""))) return;
    const carte = document.getElementById(ancre);
    if (!carte) return;
    const reduit = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    carte.scrollIntoView({ block: "start", behavior: reduit ? "auto" : "smooth" });
  }, [livrables.etat]);

  const p = ETUDES_PAGE;
  const etudes = livrables.etat === "recu" ? ordonnees(livrables.donnees) : [];
  const enPanne = livrables.etat === "panne";
  // Sur les études AFFICHÉES : la fourchette ne compte pas une entrée que la
  // page ne montre pas.
  const tarif = tarifDe(livrables, (liste) => fourchette(ordonnees(liste)));
  // Le bouton de l'appel final commande la première étude du parcours qui se
  // vend. Sans catalogue chargé, il renvoie vers les cartes plutôt que vers
  // un lien mort.
  const premiere = etudes.find((e) => lisible(e.prix_cents)) ?? null;
  const vendue = (slug: string) =>
    etudes.find((e) => e.slug === slug && lisible(e.prix_cents)) ?? null;

  return (
    <div className={fige ? "acc etu acc-fige" : "acc etu"} ref={page}>
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus, sinon certains navigateurs font défiler sans le déplacer. */}
      <main id={ID_DU_CONTENU} tabIndex={-1} inert={menu.ouvert}>
        {/* UNE région d'alerte, toujours dans le DOM : un lecteur d'écran
            annonce ce qui y ARRIVE. Montée avec son message, elle pouvait ne
            pas être lue. */}
        <div className="acc-alerte" role="alert">
          {enPanne && (
            <p className="acc-w">
              {CARTES.panne} {CARTES.panneSuite}{" "}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          )}
        </div>

        {/* ── Ouverture ────────────────────────────────────────────────── */}
        <div className="etu-ouverture">
          <div className="acc-w acc-pause-rang">
            <BoutonPause
              fige={fige}
              basculer={basculerLaPause}
              className="acc-pause-haut"
            />
          </div>
          <div className="acc-w etu-ouverture-grille">
            <div className="etu-ouverture-texte">
              <span className="acc-tag acc-entre">{p.hero.accroche}</span>
              <h1>
                <span className="acc-ligne-titre">
                  <span>{TITRES.ouverture.avant}</span>
                </span>{" "}
                <span className="acc-ligne-titre">
                  <span className="acc-s">{TITRES.ouverture.fin}</span>
                </span>
              </h1>
              <p className="etu-promesse acc-entre" style={variables({ "--i": 1 })}>
                {p.hero.corps}
              </p>
              <ul className="etu-coches acc-entre" style={variables({ "--i": 2 })}>
                {p.hero.questions.map((question) => (
                  <li key={question}>
                    <Coche />
                    <span>{question}</span>
                  </li>
                ))}
              </ul>
              <div className="etu-appels acc-entre" style={variables({ "--i": 3 })}>
                <Bouton lien={OUVERTURE_ETUDES.bouton.lien} aspect="noir">
                  {OUVERTURE_ETUDES.bouton.libelle}
                </Bouton>
              </div>
            </div>

            {/* Le cadre fixe la place de l'image : ses attributs donnent le
                ratio, la feuille la taille — rien ne saute au chargement. */}
            <div className="etu-cadre acc-entre" style={variables({ "--i": 2 })}>
              <div className="etu-cadre-bord">
                <img
                  className="etu-image"
                  src={p.hero.image}
                  alt={p.hero.alt}
                  width={IMAGE_D_OUVERTURE.largeur}
                  height={IMAGE_D_OUVERTURE.hauteur}
                  decoding="async"
                />
              </div>
            </div>

            {/* Les preuves chiffrées. `valeur: null` = la fourchette de prix,
                calculée sur le catalogue : c'est la case sombre, la plus
                visible des trois. */}
            <ul
              className="etu-preuves acc-entre"
              aria-label={OUVERTURE_ETUDES.nomDesPreuves}
              style={variables({ "--i": 4 })}
            >
              {p.preuves.map((preuve) =>
                preuve.valeur === null ? (
                  <li key={preuve.libelle} className="etu-preuve-prix">
                    <Fourchette tarif={tarif} libelle={preuve.libelle} />
                  </li>
                ) : (
                  <li key={preuve.libelle}>
                    <b>{preuve.valeur}</b>
                    <span className="etu-preuve-libelle">{preuve.libelle}</span>
                  </li>
                ),
              )}
            </ul>
          </div>
        </div>

        {/* ── Comment ça marche ────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="comment-ca-marche">
          <div className="acc-w">
            <Entree surtitre={p.methode.surtitre} titre={TITRES.methode}>
              <div className="etu-entree-corps">
                <p className="etu-sous">{p.methode.sous}</p>
                {p.methode.corps.map((paragraphe) => (
                  <p key={paragraphe}>{paragraphe}</p>
                ))}
              </div>
            </Entree>

            {/* Une liste ORDONNÉE : la numérotation encode une vraie
                séquence — choisir, payer, décrire, recevoir. */}
            <ol className="etu-etapes" data-reveal="">
              {p.etapes.map((etape, k) => (
                <li key={etape.titre}>
                  <span className="etu-etape-numero" aria-hidden="true">
                    {numero(k)}
                  </span>
                  <h3>{etape.titre}</h3>
                  <p>{etape.corps}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── Quatre études au choix : les cartes ──────────────────────── */}
        <section className="acc-section acc-section-suite" id={ID_DES_CARTES}>
          <div className="acc-w">
            <Entree surtitre={p.choix.surtitre} titre={TITRES.choix}>
              <p>{p.choix.corps}</p>
            </Entree>

            {enPanne && <p className="acc-panne">{CARTES.rappel}</p>}

            {/* Tant que le catalogue n'a pas répondu, les quatre études
                s'affichent DÉJÀ, par leur argumentaire (`contenu.ETUDES`) :
                seuls le prix et le bouton attendent. La page montrait
                « Chargement du catalogue… » et quatre formes vides — et
                c'est cet état que le pré-rendu écrit pour les robots, qui
                n'interrogent jamais le serveur : ils ne lisaient aucune des
                quatre études de la page qui les vend. */}
            {livrables.etat === "attente" && (
              <>
                <p className="etu-attente" role="status">
                  {CARTES.attente}
                </p>
                <ol className="etu-cartes">
                  {PARCOURS_DES_ETUDES.map((slug, k) => (
                    <Carte
                      key={slug}
                      etude={{ slug, libelle: ETUDES[slug].nom }}
                      rang={k}
                      suivante={null}
                      provisoire
                    />
                  ))}
                </ol>
              </>
            )}

            {livrables.etat === "recu" && etudes.length === 0 && (
              <p className="etu-vide">
                {CARTES.vide} {CARTES.panneSuite}{" "}
                <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
              </p>
            )}

            {etudes.length > 0 && (
              <>
                {/* La barre d'ancres : des liens, rien d'autre. Elle reste
                    collée sous la barre du site tant qu'on lit les cartes,
                    et son nom accessible est le titre de la section. */}
                <nav className="etu-ancres" aria-label={p.cartes.titre}>
                  <span className="etu-ancres-titre" aria-hidden="true">
                    {p.cartes.titre}
                  </span>
                  <ul>
                    {etudes.map((etude, k) => (
                      <li key={etude.slug}>
                        <a href={`#${ancreDe(etude.slug)}`}>
                          <span className="etu-ancres-numero" aria-hidden="true">
                            {numero(k)}
                          </span>
                          {LIBELLES_COURTS[etude.slug] ?? etude.libelle}
                        </a>
                      </li>
                    ))}
                  </ul>
                </nav>

                <ol className="etu-cartes">
                  {etudes.map((etude, k) => (
                    <Carte
                      key={etude.slug}
                      etude={etude}
                      rang={k}
                      suivante={
                        SUITE_DU_PARCOURS[etude.slug]
                          ? vendue(SUITE_DU_PARCOURS[etude.slug].vers)
                          : null
                      }
                    />
                  ))}
                </ol>
              </>
            )}
          </div>
        </section>

        {/* ── Ruban ────────────────────────────────────────────────────── */}
        <div className="acc-ruban etu-ruban" aria-hidden="true">
          <div className="acc-ruban-piste">
            {[...RUBAN_DES_ETUDES, ...RUBAN_DES_ETUDES].map((mot, k) => (
              <span key={k}>{mot}</span>
            ))}
          </div>
        </div>
        {/* WCAG 2.2.2 : ce qui bouge en boucle peut être arrêté là où il
            bouge. Le second bouton de pause, même état que le premier. */}
        <p className="acc-w etu-pause-rang">
          <BoutonPause fige={fige} basculer={basculerLaPause} />
        </p>

        {/* ── Les questions du porteur ─────────────────────────────────── */}
        <section className="acc-section etu-section-interrogations">
          <div className="acc-w etu-interrogations">
            <div data-reveal="">
              <h2 className="acc-titre-cote">
                {TITRES.interrogations.avant}{" "}
                <span className="acc-s">{TITRES.interrogations.fin}</span>
              </h2>
              <p className="etu-interrogations-pied">{p.interrogations.pied}</p>
            </div>
            <ul className="etu-questions" data-reveal="">
              {p.interrogations.liste.map((question) => (
                <li key={question}>
                  <Coche />
                  <span>{question}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Ce n'est pas une étude générique ─────────────────────────── */}
        <section className="acc-section etu-comparatif">
          <div className="acc-w">
            <Entree surtitre={p.comparatif.surtitre} titre={TITRES.comparatif}>
              <p>{p.comparatif.corps}</p>
            </Entree>

            <div className="etu-versus">
              <article className="etu-versus-colonne etu-versus-evite" data-reveal="">
                <small>{COMPARATIF.evite}</small>
                <h3>{p.comparatif.generique.titre}</h3>
                <ul>
                  {p.comparatif.generique.points.map((point) => (
                    <li key={point}>
                      <span className="etu-croix" aria-hidden="true">
                        ✕
                      </span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </article>

              <article
                className="etu-versus-colonne etu-versus-recu"
                data-reveal=""
                style={variables({ "--i": 1 })}
              >
                <small>{COMPARATIF.recu}</small>
                <h3>{p.comparatif.evkha.titre}</h3>
                <ul>
                  {p.comparatif.evkha.points.map((point) => (
                    <li key={point}>
                      <Coche />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </article>
            </div>

            <p className="etu-relecture" data-reveal="">
              {p.comparatif.pied}
            </p>
          </div>
        </section>

        {/* ── Vos questions ────────────────────────────────────────────── */}
        <section className="acc-section" id="questions">
          <div className="acc-w acc-faq">
            <div data-reveal="">
              <span className="acc-tag">{p.faq.surtitre}</span>
              <h2 className="acc-titre-cote">
                {TITRES.faq.avant} <span className="acc-s">{TITRES.faq.fin}</span>
              </h2>
            </div>
            <div data-reveal="">
              {p.faq.questions.map((question, k) => (
                <details key={question.q} open={k === 0}>
                  <summary>{question.q}</summary>
                  <p>{question.r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ── Passerelle : la boutique et les abonnements ──────────────── */}
        <section className="acc-section acc-section-suite" id="autrement">
          <div className="acc-w">
            <Entree surtitre={PASSERELLE.surtitre} titre={PASSERELLE.titre}>
              <p>{PASSERELLE.corps}</p>
            </Entree>
            <div className="etu-portes">
              {PASSERELLE.portes.map((porte, k) => (
                <article
                  key={porte.lien}
                  className="etu-porte"
                  data-reveal=""
                  style={variables({ "--i": k })}
                >
                  <small>{porte.surtitre}</small>
                  <h3>{porte.titre}</h3>
                  <p>{porte.corps}</p>
                  <Bouton lien={porte.lien} aspect="clair" className="etu-porte-bouton">
                    {porte.bouton}
                  </Bouton>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── Appel final ──────────────────────────────────────────────── */}
        <section className="acc-fin etu-fin" id="commander">
          <div className="acc-w">
            <h2>
              {TITRES.appel.avant}{" "}
              <span className="acc-s">{TITRES.appel.fin}</span>
            </h2>
            <p className="acc-fin-corps">{p.appel.sous}</p>
            <Bouton
              lien={premiere ? lienCommande(premiere.slug) : `#${ID_DES_CARTES}`}
              aspect="noir"
            >
              {p.appel.bouton}
            </Bouton>
          </div>
        </section>
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}
