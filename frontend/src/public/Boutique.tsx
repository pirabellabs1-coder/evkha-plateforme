/** La boutique publique : le catalogue des études déjà rédigées.
 *
 * Une étude de boutique est écrite depuis des mois et remise telle quelle. Le
 * paiement ne déclenche aucune production — d'où une boutique distincte de la
 * page des études sur mesure.
 *
 * ## Ce que cette page doit faire, et que la première ne faisait pas
 *
 * Elle posait un titre, un paragraphe et une grille. C'est une LISTE, pas une
 * boutique : rien n'y disait ce qu'on achète exactement, ce qui se passe après
 * le paiement, ni pourquoi ces études-là. Un visiteur qui découvre la maison
 * devait tout déduire de neuf vignettes.
 *
 * Elle répond désormais, dans l'ordre où les questions viennent : ce que c'est
 * (ouverture), ce qu'une étude tranche (questions), ce qui est compris
 * (promesses), ce qu'il y a (catalogue), ce qu'en disent nos clients (avis),
 * et le reste des questions (repères). Chaque bloc existe parce qu'une
 * question existe — aucun n'est là pour remplir.
 *
 * ## Deux principes, communs aux pages publiques
 *
 * 1. **Les prix viennent du serveur.** Ils sont lus dans
 *    `/api/public/boutique/`, qui les tient de la base. Un montant écrit ici
 *    ferait une seconde source, qui contredirait le paiement au premier
 *    changement de tarif.
 * 2. **Aucun prix n'est affiché tant qu'il n'est pas chargé.** Un prix de
 *    repli afficherait un montant faux à qui a une connexion lente.
 *
 * ## Refonte du 19/11/2026 : la forme change, pas ce que la page dit ni fait
 *
 * La page passe au langage visuel de l'accueil et de la page des études :
 * papier crème, or, encre, Fraunces pour les prix et les mots d'accent, cartes
 * à double bord, boutons-pilules. La barre, le menu et le pied sont ceux du
 * socle (`EnTeteSite`, `PiedSite`, `Site.css`), montés par `CadreDeBoutique`
 * que la fiche et le retour de paiement réutilisent ; l'ancien menu
 * (`MenuSite`) renvoyait vers l'ancien site. Tous les blocs d'avant sont là,
 * avec leur texte ; le chargement, la panne (dite, jamais lue comme un
 * catalogue vide), le catalogue vide et le filtre par thème n'ont pas changé
 * de logique.
 *
 * Trois choses bougent dans la forme, pour l'accessibilité :
 *
 * - une carte n'est plus UN lien qui englobe tout son contenu (son nom
 *   accessible récitait le thème, le prix, la date et la note) : le lien est
 *   son titre, étendu à toute la carte par la feuille ; le bouton « Voir
 *   l'étude » est décoratif ;
 * - la panne du catalogue arrive dans une région d'alerte TOUJOURS présente
 *   dans le document : un lecteur d'écran annonce ce qui y arrive, alors
 *   qu'une alerte montée avec son message pouvait ne pas être lue ;
 * - une note en étoiles porte sa lecture en toutes lettres (`Etoiles`).
 *
 * Le texte de la page reste dans ce fichier, comme avant, dans des constantes
 * nommées : le lot de la refonte ne comporte pas de fichier de contenu.
 */
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { Link } from "@tanstack/react-router";

import {
  chargerCatalogue,
  etoiles,
  initiale,
  moisEtAnnee,
  prix,
  type AvisALaUne,
  type ProduitResume,
} from "./catalogue";
import { CONTACT_EMAIL } from "./contenu";
import { ID_DU_CONTENU, LIENS } from "./contenuSite";
import { EnTeteSite } from "./EnTeteSite";
import { Bouton } from "./PiecesSite";
import { PiedSite } from "./PiedSite";
import { useReveler } from "./reveler";
import { useAimants, useMenu, useTitreDePage, variables } from "./site";
// Le socle d'abord, la feuille du lot ensuite : à spécificité égale, c'est la
// page qui a le dernier mot.
import "./Site.css";
import "./Boutique.css";

// ── Ce que les trois pages de la boutique partagent ─────────────────────────

/** Le cadre d'une page de la boutique : la racine `.acc`, l'en-tête du socle,
 *  le contenu principal (cible du lien d'évitement), le pied du socle.
 *
 *  Le catalogue, la fiche et le retour de paiement le montent tous les trois :
 *  une seule écriture de ce montage (règle 5). L'état du menu plein écran vit
 *  ici — c'est le cadre qui rend inerte ce qui est derrière le menu ouvert.
 *
 *  `racine` : la page y accroche sa révélation au défilement (`useReveler`),
 *  qu'elle appelle elle-même — le fichier qui pose un bloc à révéler est celui
 *  qui appelle le crochet. */
export function CadreDeBoutique({
  racine,
  classe,
  children,
}: {
  racine: RefObject<HTMLDivElement | null>;
  classe: string;
  children: ReactNode;
}) {
  const menu = useMenu();
  useAimants(racine);

  return (
    <div className={`acc bou ${classe}`} ref={racine}>
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus, sinon certains navigateurs font défiler sans le déplacer. */}
      <main id={ID_DU_CONTENU} tabIndex={-1} inert={menu.ouvert}>
        {children}
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}

/** Une note en étoiles. Les étoiles sont un dessin : un lecteur d'écran les
 *  épellerait une à une. `lecture` dit la note en toutes lettres à qui ne les
 *  voit pas ; sans elle, le texte voisin la porte déjà. */
export function Etoiles({ note, lecture }: { note: number; lecture?: string }) {
  return (
    <span className="bou-etoiles">
      <span aria-hidden="true">{etoiles(note)}</span>
      {lecture && <span className="bou-lu">{lecture}</span>}
    </span>
  );
}

/** « 4,5 » : la note à une décimale, à la française. */
function noteEnChiffres(note: number): string {
  return note.toFixed(1).replace(".", ",");
}

/** Pastille à coche dorée. Décorative : elle double ce que le texte dit. */
function Coche() {
  return (
    <span className="bou-coche" aria-hidden="true">
      ✓
    </span>
  );
}

// ── Le texte de la page ─────────────────────────────────────────────────────

const TITRE_DE_LA_PAGE = "Études en téléchargement immédiat — EVKHA";

const DESCRIPTION_DE_LA_PAGE =
  "Des études de marché déjà rédigées, secteur par secteur, à télécharger " +
  "tout de suite : vous réglez une fois, l'étude est à vous.";

/** Ce que la carte et le catalogue écrivent autour des données du serveur. */
const CARTE = {
  miseAJour: (mois: string) => `Mise à jour ${mois}`,
  avis: (note: number, nombre: number) => `${noteEnChiffres(note)} · ${nombre} avis`,
  voir: "Voir l'étude",
};

const OUVERTURE = {
  surtitre: "Téléchargement immédiat",
  titre: { avant: "Le marché de votre secteur,", fin: "déjà étudié et chiffré" },
  chapeau:
    "De nouvelles études ajoutées chaque mois, mises à jour tous les six " +
    "mois. Vous réglez une fois, vous téléchargez, l'étude est à vous.",
  bouton: "Voir le catalogue",
  aPartirDe: "à partir de",
  ttc: "TTC",
};

/** Ce que contient chaque étude, listé dans l'ouverture. Dit ce qu'on ACHÈTE —
 *  pas une promesse commerciale, les cinq lignes d'un sommaire résumé. Le
 *  « 22 chapitres » est le nombre ANNONCÉ (cf. `ETUDES` dans `contenu.ts`),
 *  pas le nombre d'entrées du plan de production. */
const HERO_INCLUS = [
  "La taille du marché et son évolution",
  "Le profil et le budget de vos clients",
  "Les prix pratiqués et les charges du secteur",
  "Les risques à anticiper et la rentabilité réelle",
  "Etc. — 22 chapitres par étude",
] as const;

/** Les questions qu'une étude tranche. Écrites comme le porteur se les pose —
 *  la même intention que la section « interrogations » de la page des études
 *  sur mesure, resserrée sur six lignes. */
const QUESTIONS = {
  nom: "Ce qu'une étude vous répond",
  titre: { avant: "Une étude qui répond enfin", fin: "à vos questions" },
  liste: [
    "Ce marché est-il rentable ?",
    "Est-il saturé, ou y a-t-il encore de la place ?",
    "Comment orienter ma création d'entreprise ?",
    "Combien de clients potentiels dans ma zone ?",
    "Quels prix pratiquer pour rester compétitif ?",
    "Quels risques dois-je anticiper avant de me lancer ?",
  ],
};

/** Les quatre promesses tenues par la mécanique elle-même.
 *
 *  Chacune décrit ce que le code fait vraiment : l'accès est ouvert par
 *  l'encaissement, le fichier est remis dans la seconde, il reste accessible
 *  tant que l'achat existe, et rien n'est prélevé ensuite. Écrire ici une
 *  promesse que le système ne tient pas serait un mensonge de vitrine. */
const PROMESSES = {
  nom: "Ce qui est compris",
  liste: [
    {
      signe: "↓",
      titre: "Disponible tout de suite",
      texte: "Téléchargement en quelques minutes après paiement.",
    },
    {
      signe: "€",
      titre: "Paiement unique",
      texte: "Aucun abonnement, aucun prélèvement ensuite.",
    },
    {
      signe: "▤",
      titre: "PDF + Word",
      texte:
        "Le PDF prêt à imprimer, et la version Word quand elle existe, pour l'adapter vous-même.",
    },
    {
      signe: "◈",
      titre: "Toujours accessible",
      texte:
        "Un espace personnel à votre nom : l'étude y reste, téléchargeable à volonté.",
    },
  ],
};

const CATALOGUE = {
  surtitre: "Les études disponibles",
  titre: { avant: "Le", fin: "catalogue" },
  compte: (etudes: number, secteurs: number) =>
    `${etudes} étude${etudes > 1 ? "s" : ""} disponible${etudes > 1 ? "s" : ""}` +
    `${secteurs > 1 ? `, ${secteurs} secteurs` : ""}.`,
  panne: "La boutique est momentanément indisponible.",
  panneSuite: "Écrivez-nous à",
  attente: "Chargement du catalogue…",
  vide:
    "Aucune étude n'est disponible pour le moment. Revenez bientôt : le " +
    "catalogue s'élargit chaque mois.",
  filtres: "Filtrer par thème",
  toutes: "Toutes",
};

const AVIS = {
  surtitre: "Avis",
  titre: { avant: "Ce qu'en disent", fin: "nos clients" },
  lecture: (note: number) => `Note : ${note} sur 5`,
};

/** Les questions qu'on se pose avant de payer une étude.
 *
 *  Elles sont écrites à partir de ce qui est vrai du système — la première dit
 *  la différence avec une étude sur mesure, qui est LA confusion possible
 *  entre les deux pages publiques. */
type Repere = {
  question: string;
  reponse: string;
  /** Facultatif : seule la première question renvoie ailleurs. */
  lien?: { vers: "/etudes"; libelle: string };
};

const REPERES: { surtitre: string; titre: { avant: string; fin: string }; liste: Repere[] } = {
  surtitre: "Avant d'acheter",
  titre: { avant: "Bon", fin: "à savoir" },
  liste: [
    {
      question: "Ces études sont-elles faites sur mon projet ?",
      reponse:
        "Les études ne sont pas personnalisées. En revanche, elles sont " +
        "construites secteur par secteur, avec des chiffres récents : des " +
        "études écrites et mises à jour sur un marché précis. Pour une étude " +
        "bâtie sur votre projet, avec votre propre zone de chalandise et vos " +
        "propres chiffres, consultez nos études sur mesure.",
      lien: { vers: "/etudes", libelle: "Voir les études sur mesure" },
    },
    {
      question: "Que reçois-je exactement ?",
      reponse:
        "Le document complet en PDF, et sa version Word lorsqu'elle existe. " +
        "Le sommaire de chaque étude est affiché sur sa fiche, et un extrait " +
        "est consultable avant l'achat quand il est disponible.",
    },
    {
      // La réponse dit OUI — il y a bien un espace client — sans mentir sur
      // l'ordre des étapes : le parcours d'achat n'ouvre AUCUN formulaire de
      // compte avant le paiement (cf. `FicheProduit`, un champ e-mail puis
      // Stripe). Écrire « créez votre compte, puis commandez » décrirait un
      // écran qui n'existe pas, et la première acheteuse le verrait.
      question: "Dois-je créer un compte avant de payer ?",
      reponse:
        "Oui, un espace client est ouvert à votre nom : c'est là que vos " +
        "études restent, téléchargeables à volonté. Vous n'avez aucun " +
        "formulaire à remplir avant : vous indiquez votre adresse e-mail, vous " +
        "passez votre commande, et votre espace s'ouvre aussitôt avec l'étude " +
        "dedans. Vous y choisissez votre mot de passe depuis le courriel reçu.",
    },
    {
      question: "Les études sont-elles à jour ?",
      reponse:
        "Les études sont mises à jour tous les six mois. La date de la " +
        "dernière mise à jour est affichée sur chaque fiche.",
    },
    {
      question: "Et si j'ai fait une erreur dans ma commande ?",
      reponse:
        `Écrivez-nous à ${CONTACT_EMAIL}. Sachez qu'un document téléchargé ne ` +
        "peut pas être repris, mais nous pouvons trouver une solution.",
    },
  ],
};

const APPEL = {
  titre: { avant: "Une question", fin: "avant d'acheter ?" },
  corps: "N'hésitez pas à nous contacter. Nous répondons dans les 48 heures.",
};

// ── Les pièces du catalogue, que la fiche réutilise ─────────────────────────

/** Une carte du catalogue : un élément de liste, à poser dans `.bou-grille`.
 *
 *  Le lien de la carte est son TITRE, étendu à toute la carte par la feuille —
 *  une cible de la taille de la carte se vise mieux qu'un lien de deux mots, et
 *  son nom accessible reste le titre de l'étude. Le bouton « Voir l'étude »
 *  est décoratif. La carte s'allume à l'entrée dans la fenêtre
 *  (`data-reveal`). */
export function CarteProduit({ produit }: { produit: ProduitResume }) {
  // Le nombre de pages n'est PAS affiché. Il se lit comme une mesure de la
  // valeur — et il la mesure mal : trente-cinq pages utiles valent mieux que
  // soixante délayées, et l'acheteuse qui compare deux nombres compare
  // exactement ce qui ne compte pas. Ce qui la renseigne, c'est le sommaire et
  // l'extrait, tous deux sur la fiche.
  const maj = moisEtAnnee(produit.mise_a_jour);

  return (
    <li>
      <article className="bou-carte" data-reveal="">
        <div className="bou-couverture">
          {produit.image ? (
            <img
              className="bou-couverture-image"
              src={produit.image}
              alt=""
              width="1200"
              height="800"
              loading="lazy"
            />
          ) : (
            // Pas de cadre vide : une couverture absente affiche l'initiale de
            // l'étude, qui se lit comme un choix et non comme une image qui
            // n'aurait pas chargé.
            <span className="bou-couverture-vide" aria-hidden="true">
              {initiale(produit.titre)}
            </span>
          )}
        </div>
        <div className="bou-carte-corps">
          {produit.theme && <span className="acc-tag">{produit.theme}</span>}
          <h3>
            <Link
              className="bou-carte-lien"
              to="/boutique/$slug"
              params={{ slug: produit.slug }}
            >
              {produit.titre}
            </Link>
          </h3>
          {maj && <p className="bou-carte-meta">{CARTE.miseAJour(maj)}</p>}
          {produit.nombre_d_avis > 0 && (
            <p className="bou-note">
              <Etoiles note={produit.note} />
              <span>{CARTE.avis(produit.note, produit.nombre_d_avis)}</span>
            </p>
          )}
          <div className="bou-carte-pied">
            <p className="bou-carte-prix">
              {prix(produit.prix_cents, produit.devise)}
            </p>
            <span
              className="acc-btn acc-btn-noir bou-carte-voir"
              aria-hidden="true"
            >
              {CARTE.voir}
              <span className="acc-btn-fleche">→</span>
            </span>
          </div>
        </div>
      </article>
    </li>
  );
}

/** Les questions qu'une étude de boutique tranche, en liste cochée. Le
 *  catalogue les pose sous son ouverture ; la fiche les reprend pour dire à
 *  qui l'étude s'adresse — une seule liste pour les deux (règle 5). */
export function QuestionsDUneEtude() {
  return (
    <ul className="bou-questions">
      {QUESTIONS.liste.map((question) => (
        <li key={question}>
          <Coche />
          <span>{question}</span>
        </li>
      ))}
    </ul>
  );
}

function AvisALaUneCarte({ avis, rang }: { avis: AvisALaUne; rang: number }) {
  return (
    <li>
      <figure
        className="bou-temoignage"
        data-reveal=""
        style={variables({ "--i": rang % 3 })}
      >
        <Etoiles note={avis.note} lecture={AVIS.lecture(avis.note)} />
        <blockquote>{avis.texte}</blockquote>
        <figcaption>
          <b>{avis.auteur}</b>
          {avis.qualite && <span>{avis.qualite}</span>}
          <Link to="/boutique/$slug" params={{ slug: avis.slug }}>
            {avis.etude}
          </Link>
        </figcaption>
      </figure>
    </li>
  );
}

// ── La page ─────────────────────────────────────────────────────────────────

export function Boutique() {
  const [produits, setProduits] = useState<ProduitResume[] | null>(null);
  const [themes, setThemes] = useState<string[]>([]);
  const [avis, setAvis] = useState<AvisALaUne[]>([]);
  const [theme, setTheme] = useState("");
  const [erreur, setErreur] = useState("");
  const page = useRef<HTMLDivElement>(null);

  // Le catalogue et les avis arrivent après le premier rendu, et le filtre
  // remonte des cartes : chaque changement rejoue l'observation des blocs non
  // révélés. L'option : sous mouvement réduit, la révélation reste, en fondu
  // seul (`Site.css`).
  useReveler(page, `${produits?.length ?? -1}:${avis.length}:${theme}`, {
    memeEnMouvementReduit: true,
  });
  useTitreDePage(TITRE_DE_LA_PAGE, DESCRIPTION_DE_LA_PAGE);

  useEffect(() => {
    let vivant = true;
    chargerCatalogue()
      .then((donnees) => {
        if (!vivant) return;
        setProduits(donnees.produits);
        setThemes(donnees.themes);
        setAvis(donnees.avis ?? []);
      })
      .catch(() => {
        if (vivant) setErreur(CATALOGUE.panne);
      });
    return () => {
      vivant = false;
    };
  }, []);

  // Le filtre s'applique à l'affichage, pas au serveur : le catalogue tient en
  // quelques dizaines d'entrées, et un aller-retour par clic rendrait le
  // filtre poussif pour aucun gain.
  const visibles = useMemo(
    () => (produits ?? []).filter((p) => !theme || p.theme === theme),
    [produits, theme],
  );

  // Le prix le plus bas, dit tel quel. « À partir de » suppose un plancher, et
  // l'écrire en dur mentirait le jour où la cliente change un tarif.
  const plancher = useMemo(
    () =>
      produits && produits.length > 0
        ? Math.min(...produits.map((p) => p.prix_cents))
        : null,
    [produits],
  );

  return (
    <CadreDeBoutique racine={page} classe="bou-catalogue-page">
      {/* ── Ouverture ──────────────────────────────────────────────────── */}
      <div className="bou-ouverture">
        <div className="acc-w bou-ouverture-grille">
          <div>
            <span className="acc-tag acc-entre">{OUVERTURE.surtitre}</span>
            <h1>
              <span className="acc-ligne-titre">
                <span>{OUVERTURE.titre.avant}</span>
              </span>{" "}
              <span className="acc-ligne-titre">
                <span className="acc-s">{OUVERTURE.titre.fin}</span>
              </span>
            </h1>
            <p className="bou-chapeau acc-entre" style={variables({ "--i": 1 })}>
              {OUVERTURE.chapeau}
            </p>
            <ul className="bou-inclus acc-entre" style={variables({ "--i": 2 })}>
              {HERO_INCLUS.map((item) => (
                <li key={item}>
                  <Coche />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <div className="bou-appels acc-entre" style={variables({ "--i": 3 })}>
              <Bouton lien="#catalogue" aspect="noir">
                {OUVERTURE.bouton}
              </Bouton>
              {/* Rien tant que le catalogue n'a pas répondu : pas de prix de
                  repli. */}
              {plancher !== null && (
                <p className="bou-plancher">
                  {OUVERTURE.aPartirDe} <b>{prix(plancher)}</b> {OUVERTURE.ttc}
                </p>
              )}
            </div>
          </div>

          {/* Trois couvertures en éventail : la vitrine d'une boutique montre
              ce qu'elle vend avant de l'expliquer. Purement décoratif — la
              grille plus bas porte l'information. Sa place est réservée par la
              feuille : rien ne saute quand le catalogue arrive. */}
          <div
            className="bou-eventail acc-entre"
            aria-hidden="true"
            style={variables({ "--i": 2 })}
          >
            {(produits ?? []).slice(0, 3).map((p, index) => (
              <div key={p.slug} className={`bou-eventail-carte bou-eventail-${index}`}>
                {p.image ? (
                  <img
                    className="bou-eventail-image"
                    src={p.image}
                    alt=""
                    width="1200"
                    height="800"
                  />
                ) : (
                  <span>{initiale(p.titre)}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Ce qu'une étude vous répond ────────────────────────────────── */}
      <section className="acc-section acc-section-suite" aria-label={QUESTIONS.nom}>
        <div className="acc-w bou-reponses">
          <h2 data-reveal="">
            {QUESTIONS.titre.avant}{" "}
            <span className="acc-s">{QUESTIONS.titre.fin}</span>
          </h2>
          <div data-reveal="">
            <QuestionsDUneEtude />
          </div>
        </div>
      </section>

      {/* ── Ce qui est compris ─────────────────────────────────────────── */}
      <section className="acc-section acc-section-suite" aria-label={PROMESSES.nom}>
        <div className="acc-w">
          <ul className="bou-promesses" data-reveal="">
            {PROMESSES.liste.map((promesse) => (
              <li key={promesse.titre}>
                <span className="bou-promesse-signe" aria-hidden="true">
                  {promesse.signe}
                </span>
                <p className="bou-promesse-titre">{promesse.titre}</p>
                <p>{promesse.texte}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── Le catalogue ───────────────────────────────────────────────── */}
      <section className="acc-section acc-section-suite" id="catalogue">
        <div className="acc-w">
          <div className="bou-section-tete" data-reveal="">
            <div>
              <span className="acc-tag">{CATALOGUE.surtitre}</span>
              <h2>
                {CATALOGUE.titre.avant}{" "}
                <span className="acc-s">{CATALOGUE.titre.fin}</span>
              </h2>
            </div>
            {produits !== null && produits.length > 0 && (
              <p className="bou-section-note">
                {CATALOGUE.compte(produits.length, themes.length)}
              </p>
            )}
          </div>

          {/* UNE région d'alerte, toujours dans le document : un lecteur
              d'écran annonce ce qui y ARRIVE. Une panne se dit ici — jamais
              par un catalogue vide. `!== ""` : la région vide n'a AUCUN nœud,
              pas même un texte vide — la feuille la replie par `:empty`. */}
          <div className="bou-alerte" role="alert">
            {erreur !== "" && (
              <p>
                {erreur} {CATALOGUE.panneSuite}{" "}
                <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
              </p>
            )}
          </div>

          {produits === null && !erreur && (
            <p className="bou-attente" role="status">
              {CATALOGUE.attente}
            </p>
          )}

          {produits !== null && produits.length === 0 && (
            <p className="bou-vide">{CATALOGUE.vide}</p>
          )}

          {themes.length > 1 && (
            <div className="bou-filtres" role="group" aria-label={CATALOGUE.filtres}>
              <button
                type="button"
                className="bou-filtre"
                aria-pressed={theme === ""}
                onClick={() => setTheme("")}
              >
                {CATALOGUE.toutes}
              </button>
              {themes.map((t) => (
                <button
                  key={t}
                  type="button"
                  className="bou-filtre"
                  aria-pressed={theme === t}
                  onClick={() => setTheme(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {visibles.length > 0 && (
            <ul className="bou-grille">
              {visibles.map((p) => (
                <CarteProduit key={p.slug} produit={p} />
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* ── Ce qu'en disent nos clients ────────────────────────────────── */}
      {avis.length > 0 && (
        <section className="acc-section acc-section-suite">
          <div className="acc-w">
            <div className="bou-section-tete" data-reveal="">
              <div>
                <span className="acc-tag">{AVIS.surtitre}</span>
                <h2>
                  {AVIS.titre.avant}{" "}
                  <span className="acc-s">{AVIS.titre.fin}</span>
                </h2>
              </div>
            </div>
            <ul className="bou-temoignages">
              {avis.map((a, k) => (
                <AvisALaUneCarte
                  key={`${a.slug}-${a.auteur}-${a.date}`}
                  avis={a}
                  rang={k}
                />
              ))}
            </ul>
          </div>
        </section>
      )}

      {/* ── Bon à savoir ───────────────────────────────────────────────── */}
      <section className="acc-section acc-section-suite">
        <div className="acc-w acc-faq">
          <div data-reveal="">
            <span className="acc-tag">{REPERES.surtitre}</span>
            <h2 className="acc-titre-cote">
              {REPERES.titre.avant}{" "}
              <span className="acc-s">{REPERES.titre.fin}</span>
            </h2>
          </div>
          <div data-reveal="">
            {REPERES.liste.map((repere) => (
              <details key={repere.question}>
                <summary>{repere.question}</summary>
                <p>
                  {repere.reponse}
                  {repere.lien && (
                    <>
                      {" "}
                      <Link className="bou-lien" to={repere.lien.vers}>
                        {repere.lien.libelle}
                      </Link>
                      .
                    </>
                  )}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ── Une question avant d'acheter ? ─────────────────────────────── */}
      <section className="acc-fin bou-fin">
        <div className="acc-w">
          <h2>
            {APPEL.titre.avant} <span className="acc-s">{APPEL.titre.fin}</span>
          </h2>
          <p className="acc-fin-corps">{APPEL.corps}</p>
          <Bouton lien={LIENS.courriel} aspect="noir" className="bou-bouton-souple">
            {CONTACT_EMAIL}
          </Bouton>
        </div>
      </section>
    </CadreDeBoutique>
  );
}
