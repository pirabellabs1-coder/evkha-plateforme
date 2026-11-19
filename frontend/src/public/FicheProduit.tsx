/** La fiche d'une étude de boutique, et son achat.
 *
 * L'aperçu est l'élément qui décide de la vente : un fichier ne se feuillette
 * pas, et sans quelques pages visibles le visiteur engage son argent sur la foi
 * d'un titre. La couverture et les avis jouent le même rôle — ils montrent, là
 * où une description affirme.
 *
 * Il n'y a PAS de fichier d'extrait : le serveur découpe les premières pages du
 * document vendu à la demande. Un extrait à téléverser était un fichier à
 * refaire à chaque mise à jour de l'étude, donc un extrait qui finit par mentir
 * sans que rien ne le signale.
 *
 * L'achat ne demande PAS de créer un compte au préalable. Le compte est ouvert
 * par l'encaissement, et l'acheteur arrive directement sur son téléchargement :
 * pour un fichier remis immédiatement, un formulaire d'inscription avant le
 * paiement est une friction sans contrepartie.
 *
 * Mais quand un espace est DÉJÀ ouvert dans ce navigateur — on arrive ici par
 * « Ouvrir la boutique », depuis Mes achats —, l'achat part par la route de
 * l'espace et suit le compte, pas l'adresse saisie chez le prestataire
 * (`achat.ts`). On ne demande alors pas d'adresse : le serveur ne s'en
 * servirait pas.
 *
 * ## Refonte du 19/11/2026 : une vraie page de contenu
 *
 * La boutique est la porte d'entrée la moins chère de la maison, et chaque
 * fiche est une page que les moteurs indexent. Elle se lit donc comme une page
 * de contenu, dans le langage visuel de l'accueil et de la page des études
 * (socle `Site.css`, cadre `CadreDeBoutique`) : un titre fort, ce qu'on achète,
 * à qui l'étude s'adresse, le sommaire, l'aperçu, le déroulé, les avis — et
 * elle se termine par une passerelle vers l'étude SUR MESURE, sans prix.
 *
 * Le prix et le bouton d'achat restent à portée : la colonne d'achat est
 * collante sur grand écran ; sur téléphone, où elle vient juste sous le titre,
 * une barre fixe en bas d'écran rappelle le prix et ramène à elle dès qu'elle
 * sort de la fenêtre. Cette barre porte un LIEN, pas un second bouton de
 * paiement : l'adresse e-mail se saisit dans le panneau, et un seul bouton
 * ouvre le paiement.
 *
 * La logique n'a pas bougé : chargement, panne (dite, avec « Réessayer »),
 * étude introuvable (seulement quand le serveur répond 404), achat par
 * l'espace ou en visiteur, refus affiché contre le bouton.
 *
 * ## Données structurées
 *
 * Un bloc JSON-LD `Product` + `Offer`, construit sur ce que l'API a rendu et
 * sur rien d'autre (`donneesStructurees`) : un champ absent de la réponse est
 * absent du bloc. Une note inventée, déclarée aux moteurs, serait un faux.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "@tanstack/react-router";

import {
  achatRattacheALEspace,
  messageDuRefusDePaiement,
  payerUnProduit,
} from "./achat";
import {
  CadreDeBoutique,
  CarteProduit,
  Etoiles,
  QuestionsDUneEtude,
} from "./Boutique";
import {
  chargerFiche,
  initiale,
  moisEtAnnee,
  prix,
  RefusBoutique,
  type Avis,
  type ProduitFiche,
  type ProduitResume,
} from "./catalogue";
import { LIENS } from "./contenuSite";
import { Bouton } from "./PiecesSite";
import { useReveler } from "./reveler";
import { lisible, useTitreDePage } from "./site";
// Le socle d'abord, la feuille du lot ensuite.
import "./Site.css";
import "./Boutique.css";

// ── Le texte de la page ─────────────────────────────────────────────────────

const ONGLET = {
  titre: (etude: string) => `${etude} — EVKHA`,
  attente: "Étude en téléchargement — EVKHA",
  description:
    "Une étude de marché déjà rédigée, à télécharger tout de suite : son " +
    "sommaire, un aperçu de ses premières pages et son prix.",
};

const RETOUR = "Toutes les études";

const ETATS = {
  attente: "Chargement…",
  panneTitre: "Un instant",
  panne:
    "Cette page n'a pas pu être chargée. Votre lien est bon : c'est une " +
    "panne passagère de notre côté.",
  reessayer: "Réessayer",
  introuvable: "Cette étude n'est pas disponible",
  boutique: "Revenir à la boutique",
};

const TETE = {
  miseAJour: (mois: string) => `Mise à jour ${mois}`,
  pdfEtWord: "PDF et Word",
  pdf: "PDF",
  note: (note: number) => `${note.toFixed(1).replace(".", ",")} sur 5`,
  avis: (nombre: number) => `${nombre} avis`,
  couverture: (etude: string) => `Couverture — ${etude}`,
};

const BLOCS = {
  achat: "Ce que vous achetez",
  pourQui: {
    titre: "À qui s'adresse cette étude",
    corps:
      "Aux personnes qui préparent un projet dans ce secteur et veulent des " +
      "repères chiffrés avant de s'engager. Elle décrit un marché, avec des " +
      "chiffres récents : elle n'est pas personnalisée.",
    amorce: "Les questions auxquelles elle aide à répondre :",
  },
  sommaire: "Le sommaire",
  apercu: {
    titre: "Feuilleter avant d'acheter",
    corps: (pages: number) =>
      `Les ${pages} premières pages de l'étude sont ouvertes, telles ` +
      "qu'elles figurent dans le document. Aucune inscription n'est demandée.",
    bouton: (pages: number) => `Ouvrir l'aperçu (${pages} pages)`,
  },
  deroule: {
    titre: "Comment ça se passe",
    etapes: [
      {
        titre: "Vous réglez",
        corps: "paiement unique par carte, en ligne sécurisée.",
      },
      {
        titre: "Vous téléchargez",
        corps:
          "le document est disponible dans la seconde qui suit, sur la page de retour.",
      },
      {
        titre: "Vous le retrouvez",
        corps:
          "un espace s'ouvre à votre nom : l'étude y reste, téléchargeable autant de fois que voulu.",
      },
    ],
  },
  avis: {
    titre: "Ce qu'en disent les lectrices",
    lecture: (note: number) => `Note : ${note} sur 5`,
  },
  proches: "Ces études peuvent aussi vous intéresser",
};

const ACHAT = {
  nom: "Acheter cette étude",
  mention: "TTC · paiement unique",
  rattache:
    "Cette étude sera rangée dans votre espace, déjà ouvert dans ce navigateur.",
  email: "Votre adresse e-mail",
  exemple: "vous@exemple.fr",
  acheter: (montant: string) => `Acheter — ${montant}`,
  ouverture: "Ouverture du paiement…",
  refus: "Le paiement n'a pas pu être ouvert. Réessayez dans un instant.",
  feuilleter: (pages: number) => `Feuilleter les ${pages} premières pages`,
  rassurance: (editable: boolean) => [
    "Téléchargement immédiat après paiement",
    editable ? "PDF et version Word" : "PDF",
    "Retrouvable à tout moment dans votre espace",
    "Aucun abonnement, aucun engagement",
  ],
  /** La barre du téléphone : un rappel du prix et un lien vers le panneau. */
  barre: "Acheter cette étude",
  ttc: "TTC",
};

/** La passerelle vers l'étude sur mesure. Aucun prix : ceux des études sur
 *  mesure se lisent sur leur page, qui les tient du serveur. */
const PASSERELLE = {
  surtitre: "Étude sur mesure",
  titre: {
    avant: "Ce secteur vous intéresse",
    fin: "pour votre propre projet et votre propre zone ?",
  },
  corps:
    "Cette étude décrit un marché. Pour une étude bâtie sur votre projet, " +
    "avec votre propre zone de chalandise et vos propres chiffres, " +
    "consultez nos études sur mesure.",
  bouton: "Voir les études sur mesure",
};

// ── Outils ──────────────────────────────────────────────────────────────────

/** « 12 mars 2026 ». Sur un avis, le jour compte : il dit si le témoignage
 *  est récent. C'est l'inverse d'une date de mise à jour, où il n'apporte
 *  rien — d'où deux formats et non un compromis. */
function jourEntier(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

/** Les paragraphes d'une description saisie en texte libre : ceux de la
 *  cliente, séparés par une ligne vide. On ne les recompose pas. */
function paragraphes(description: string): string[] {
  return description.split(/\n\s*\n/).filter((p) => p.trim());
}

/** La description de la page, pour les moteurs : le début du premier
 *  paragraphe de l'étude, coupé entre deux mots. */
function resume(description: string): string {
  const premier = (paragraphes(description)[0] ?? "").replace(/\s+/g, " ").trim();
  if (premier.length <= 160) return premier;
  return `${premier.slice(0, 157).replace(/\s+\S*$/, "")}…`;
}

/** Les données structurées de la fiche (schema.org `Product` et `Offer`).
 *
 *  Tout vient de la réponse de l'API, et un champ qu'elle ne porte pas n'est
 *  pas déclaré : pas de description vide, pas d'offre sans prix lisible ni
 *  devise, pas de note sans avis publié. L'adresse est celle de la page,
 *  bâtie sur le slug que l'API a rendu. Rien d'autre — ni disponibilité, ni
 *  marque, ni note par défaut : ce serait déclarer aux moteurs un fait que
 *  personne n'a établi. */
function donneesStructurees(produit: ProduitFiche): Record<string, unknown> {
  const adresse = `${window.location.origin}/boutique/${encodeURIComponent(produit.slug)}`;
  const avis = Array.isArray(produit.avis) ? produit.avis.length : 0;
  const aUnPrix =
    lisible(produit.prix_cents) &&
    typeof produit.devise === "string" &&
    produit.devise !== "";
  const aUneNote = avis > 0 && typeof produit.note === "number" && produit.note > 0;

  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: produit.titre,
    url: adresse,
    ...(produit.description ? { description: produit.description } : {}),
    ...(produit.theme ? { category: produit.theme } : {}),
    ...(produit.image ? { image: produit.image } : {}),
    ...(aUnPrix
      ? {
          offers: {
            "@type": "Offer",
            price: (produit.prix_cents / 100).toFixed(2),
            priceCurrency: produit.devise,
            url: adresse,
          },
        }
      : {}),
    ...(aUneNote
      ? {
          aggregateRating: {
            "@type": "AggregateRating",
            ratingValue: produit.note,
            reviewCount: avis,
          },
        }
      : {}),
  };
}

function CarteAvis({ avis }: { avis: Avis }) {
  return (
    <li className="bou-avis" data-reveal="">
      <p className="bou-avis-tete">
        <Etoiles note={avis.note} lecture={BLOCS.avis.lecture(avis.note)} />
        <span className="bou-avis-date">{jourEntier(avis.date)}</span>
      </p>
      {avis.texte && <blockquote>{avis.texte}</blockquote>}
      <p className="bou-avis-signature">
        <b>{avis.auteur}</b>
        {avis.qualite && <span>{avis.qualite}</span>}
      </p>
    </li>
  );
}

// ── La page ─────────────────────────────────────────────────────────────────

export function FicheProduit() {
  const { slug } = useParams({ from: "/boutique/$slug" });
  const [produit, setProduit] = useState<ProduitFiche | null>(null);
  const [proches, setProches] = useState<ProduitResume[]>([]);
  const [email, setEmail] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState("");
  const [introuvable, setIntrouvable] = useState(false);
  // Une PANNE n'est pas une étude introuvable. La fiche disait « Cette étude
  // n'est pas disponible » pour toute erreur — un 500, une coupure de dix
  // secondes — et renvoyait à la boutique quelqu'un dont le lien était bon,
  // au moment où il venait acheter (audit du 19/11/2026).
  const [panne, setPanne] = useState(false);
  // Incrémenté par « Réessayer » : il relance le chargement sans recharger
  // la page.
  const [tentative, setTentative] = useState(0);
  // Lu une fois, à l'arrivée : un espace est-il ouvert dans ce navigateur ?
  const [rattache] = useState(achatRattacheALEspace);
  // Le panneau d'achat est-il dans la fenêtre ? La barre du téléphone s'efface
  // alors : elle ne sert qu'à y ramener. Tant que l'observateur n'a rien dit,
  // on le suppose visible — sur téléphone il est juste sous le titre, et la
  // barre ne clignote pas à l'arrivée. Sans observateur, la barre reste.
  const [panneauVisible, setPanneauVisible] = useState(
    () => typeof IntersectionObserver !== "undefined",
  );
  const page = useRef<HTMLDivElement>(null);
  const panneau = useRef<HTMLElement>(null);

  // La fiche arrive après le premier rendu, et change avec le slug : chaque
  // nouvelle fiche rejoue l'observation de ses blocs. L'option : sous
  // mouvement réduit, la révélation reste, en fondu seul (`Site.css`).
  useReveler(page, produit, { memeEnMouvementReduit: true });
  useTitreDePage(
    produit ? ONGLET.titre(produit.titre) : ONGLET.attente,
    (produit?.description && resume(produit.description)) || ONGLET.description,
  );

  useEffect(() => {
    let vivant = true;
    // La remise à zéro passe par la RÉPONSE, pas par le corps de l'effet :
    // remettre l'état à vide de façon synchrone déclenche un rendu en cascade
    // à chaque changement de fiche.
    chargerFiche(slug)
      .then((donnees) => {
        if (!vivant) return;
        setIntrouvable(false);
        setPanne(false);
        setProduit(donnees.produit);
        setProches(donnees.proches);
      })
      .catch((cause: unknown) => {
        if (!vivant) return;
        setProduit(null);
        // « Pas disponible » ne se dit que lorsque le SERVEUR le dit (404).
        const absente = cause instanceof RefusBoutique && cause.statut === 404;
        setIntrouvable(absente);
        setPanne(!absente);
      });
    return () => {
      vivant = false;
    };
  }, [slug, tentative]);

  // Un observateur, pas un écouteur de défilement : il ne parle que lorsque le
  // panneau franchit le bord de la fenêtre. Sans lui (vieux navigateur), la
  // barre reste affichée — elle mène toujours au panneau.
  useEffect(() => {
    const cible = panneau.current;
    if (!cible || typeof IntersectionObserver === "undefined") return undefined;
    const observateur = new IntersectionObserver((entrees) => {
      const derniere = entrees[entrees.length - 1];
      if (derniere) setPanneauVisible(derniere.isIntersecting);
    });
    observateur.observe(cible);
    return () => observateur.disconnect();
  }, [produit]);

  async function acheter() {
    if (!produit) return;
    setEnvoi(true);
    setErreur("");
    try {
      // Par l'espace si une session y est ouverte — l'achat suit alors le
      // compte —, sinon en visiteur. La règle vit dans `achat.ts`.
      const adresse = await payerUnProduit(produit.slug, email.trim());
      // Remplacement et non nouvel onglet : le paiement EST la suite du
      // parcours. Un onglet de plus laisse derrière soi une page morte à
      // laquelle la personne revient, et où elle recliquera.
      window.location.href = adresse;
    } catch (cause) {
      setErreur(messageDuRefusDePaiement(cause, ACHAT.refus));
      setEnvoi(false);
    }
  }

  if (panne) {
    return (
      <CadreDeBoutique racine={page} classe="bou-fiche-page">
        <div className="acc-w bou-etat">
          <h1>{ETATS.panneTitre}</h1>
          <p className="bou-erreur" role="alert">
            {ETATS.panne}
          </p>
          <div className="bou-liens">
            <button
              type="button"
              className="acc-btn acc-btn-noir"
              onClick={() => {
                setPanne(false);
                setTentative((n) => n + 1);
              }}
            >
              {ETATS.reessayer}
              <span className="acc-btn-fleche" aria-hidden="true">
                ↻
              </span>
            </button>
            <Link className="bou-lien" to="/boutique">
              {ETATS.boutique}
            </Link>
          </div>
        </div>
      </CadreDeBoutique>
    );
  }

  if (introuvable) {
    return (
      <CadreDeBoutique racine={page} classe="bou-fiche-page">
        <div className="acc-w bou-etat">
          <h1>{ETATS.introuvable}</h1>
          <div className="bou-liens">
            <Link className="acc-btn acc-btn-noir" to="/boutique">
              {ETATS.boutique}
              <span className="acc-btn-fleche" aria-hidden="true">
                →
              </span>
            </Link>
          </div>
        </div>
      </CadreDeBoutique>
    );
  }

  if (!produit) {
    return (
      <CadreDeBoutique racine={page} classe="bou-fiche-page">
        <div className="acc-w bou-etat">
          <p className="bou-attente" role="status">
            {ETATS.attente}
          </p>
        </div>
      </CadreDeBoutique>
    );
  }

  const maj = moisEtAnnee(produit.mise_a_jour);
  // Sans le nombre de pages : voir `Boutique.tsx`. Le sommaire et l'aperçu
  // disent ce que le document contient, ce qu'un nombre ne dit pas.
  const details = [
    maj ? TETE.miseAJour(maj) : "",
    produit.editable ? TETE.pdfEtWord : TETE.pdf,
  ].filter(Boolean);
  const montant = prix(produit.prix_cents, produit.devise);

  return (
    <CadreDeBoutique racine={page} classe="bou-fiche-page">
      <article className="acc-w bou-fiche" aria-labelledby="bou-fiche-titre">
        {/* ── Le titre ─────────────────────────────────────────────────────
            Un `<div>`, pas un `<header>` : la seule bannière de la page est
            la barre du site. */}
        <div className="bou-fiche-tete">
          <Link className="bou-retour" to="/boutique">
            <span aria-hidden="true">←</span>
            {RETOUR}
          </Link>
          {produit.theme && <p className="acc-tag">{produit.theme}</p>}
          <h1 id="bou-fiche-titre">{produit.titre}</h1>
          <p className="bou-fiche-meta">{details.join(" · ")}</p>
          {produit.avis.length > 0 && (
            <p className="bou-note">
              <Etoiles note={produit.note} />
              <span>
                {TETE.note(produit.note)} ·{" "}
                <a className="bou-lien" href="#avis">
                  {TETE.avis(produit.avis.length)}
                </a>
              </span>
            </p>
          )}
        </div>

        {/* ── Le panneau d'achat ───────────────────────────────────────────
            Juste après le titre dans le document : sur téléphone il vient
            donc avant la lecture ; sur grand écran c'est la colonne de
            droite, collante. */}
        <aside
          className="bou-achat"
          id="bou-achat"
          ref={panneau}
          aria-label={ACHAT.nom}
        >
          <p className="bou-achat-prix">{montant}</p>
          <p className="bou-achat-mention">{ACHAT.mention}</p>

          {/* Avec un espace ouvert, l'achat suit le COMPTE : le serveur
              n'utilise pas d'adresse saisie ici. La demander quand même
              ferait croire qu'on peut l'envoyer ailleurs. */}
          {rattache ? (
            <p className="bou-achat-mention">{ACHAT.rattache}</p>
          ) : (
            <>
              <label htmlFor="bou-email">{ACHAT.email}</label>
              {/* `.champ-saisie` (espace.css) : le champ de la charte, 16 px
                  au moins. */}
              <input
                id="bou-email"
                className="champ-saisie"
                type="email"
                autoComplete="email"
                placeholder={ACHAT.exemple}
                value={email}
                onChange={(evenement) => setEmail(evenement.target.value)}
                aria-describedby={erreur ? "bou-achat-erreur" : undefined}
              />
            </>
          )}

          {/* Le refus s'affiche CONTRE le bouton, avec la phrase que le
              serveur a écrite pour la personne. */}
          {erreur && (
            <p className="bou-erreur" id="bou-achat-erreur" role="alert">
              {erreur}
            </p>
          )}

          {/* Pendant l'ouverture du paiement, une lame de lumière traverse le
              bouton (`.bouton-chargement`, espace.css) : le texte dit
              « Ouverture… », le balayage dit seulement que ça travaille. */}
          <button
            type="button"
            className={
              envoi
                ? "acc-btn acc-btn-noir bou-acheter bouton-chargement"
                : "acc-btn acc-btn-noir bou-acheter"
            }
            onClick={() => void acheter()}
            disabled={envoi}
            aria-describedby={erreur ? "bou-achat-erreur" : undefined}
          >
            {envoi ? ACHAT.ouverture : ACHAT.acheter(montant)}
            <span className="acc-btn-fleche" aria-hidden="true">
              →
            </span>
          </button>

          {produit.apercu && (
            <a
              className="bou-lien bou-achat-apercu"
              href={produit.apercu.adresse}
              target="_blank"
              rel="noreferrer"
            >
              {ACHAT.feuilleter(produit.apercu.pages)}
            </a>
          )}

          <ul className="bou-rassurance">
            {ACHAT.rassurance(produit.editable).map((ligne) => (
              <li key={ligne}>{ligne}</li>
            ))}
          </ul>
        </aside>

        {/* ── La lecture ───────────────────────────────────────────────── */}
        <div className="bou-fiche-corps">
          {/* La couverture EN PREMIER, en grand : c'est ce qu'on regarde
              avant de lire, et c'est la seule chose qui donne une idée du
              document tant qu'on n'a pas ouvert l'aperçu. */}
          <div className="bou-visuel">
            {produit.image ? (
              <img
                className="bou-visuel-image"
                src={produit.image}
                alt={TETE.couverture(produit.titre)}
                width="1200"
                height="800"
              />
            ) : (
              <span className="bou-visuel-vide" aria-hidden="true">
                {initiale(produit.titre)}
              </span>
            )}
          </div>

          {produit.description && (
            <section className="bou-bloc" data-reveal="">
              <h2>{BLOCS.achat}</h2>
              {paragraphes(produit.description).map((paragraphe) => (
                <p key={paragraphe.slice(0, 40)}>{paragraphe}</p>
              ))}
            </section>
          )}

          <section className="bou-bloc" data-reveal="">
            <h2>{BLOCS.pourQui.titre}</h2>
            <p>{BLOCS.pourQui.corps}</p>
            <p className="bou-amorce">{BLOCS.pourQui.amorce}</p>
            <QuestionsDUneEtude />
          </section>

          {produit.sommaire.length > 0 && (
            <section className="bou-bloc" data-reveal="">
              <h2>{BLOCS.sommaire}</h2>
              <ol className="bou-sommaire">
                {produit.sommaire.map((ligne) => (
                  <li key={ligne}>{ligne}</li>
                ))}
              </ol>
            </section>
          )}

          {produit.apercu && (
            <section className="bou-bloc bou-apercu" data-reveal="">
              <h2>{BLOCS.apercu.titre}</h2>
              <p>{BLOCS.apercu.corps(produit.apercu.pages)}</p>
              {/* La flèche « ↗ » dit l'onglet qui s'ouvre ; nichée dans son
                  disque, jamais posée nue à côté du texte. */}
              <a
                className="acc-btn acc-btn-noir bou-bouton-souple"
                href={produit.apercu.adresse}
                target="_blank"
                rel="noreferrer"
              >
                {BLOCS.apercu.bouton(produit.apercu.pages)}
                <span className="acc-btn-fleche" aria-hidden="true">
                  ↗
                </span>
              </a>
            </section>
          )}

          <section className="bou-bloc" data-reveal="">
            <h2>{BLOCS.deroule.titre}</h2>
            {/* Une liste ORDONNÉE : régler, télécharger, retrouver — l'ordre
                porte l'information. */}
            <ol className="bou-etapes">
              {BLOCS.deroule.etapes.map((etape) => (
                <li key={etape.titre}>
                  <span>
                    <b>{etape.titre}</b> — {etape.corps}
                  </span>
                </li>
              ))}
            </ol>
          </section>

          {produit.avis.length > 0 && (
            <section className="bou-bloc" id="avis">
              <h2>{BLOCS.avis.titre}</h2>
              <ul className="bou-avis-liste">
                {produit.avis.map((a) => (
                  <CarteAvis key={`${a.auteur}-${a.date}`} avis={a} />
                ))}
              </ul>
            </section>
          )}
        </div>
      </article>

      {/* ── Les études voisines ──────────────────────────────────────────── */}
      {proches.length > 0 && (
        <section className="acc-section bou-proches">
          <div className="acc-w">
            <h2 data-reveal="">{BLOCS.proches}</h2>
            <ul className="bou-grille">
              {proches.map((p) => (
                <CarteProduit key={p.slug} produit={p} />
              ))}
            </ul>
          </div>
        </section>
      )}

      {/* ── La passerelle vers l'étude sur mesure ────────────────────────── */}
      <section className="acc-fin bou-fin" aria-labelledby="bou-passerelle-titre">
        <div className="acc-w">
          <span className="acc-tag">{PASSERELLE.surtitre}</span>
          <h2 id="bou-passerelle-titre">
            {PASSERELLE.titre.avant}{" "}
            <span className="acc-s">{PASSERELLE.titre.fin}</span>
          </h2>
          <p className="acc-fin-corps">{PASSERELLE.corps}</p>
          <Bouton lien={LIENS.etudes} aspect="noir" className="bou-bouton-souple">
            {PASSERELLE.bouton}
          </Bouton>
        </div>
      </section>

      {/* ── La barre d'achat du téléphone ────────────────────────────────────
          Fixe, en bas d'écran, sous 901 px seulement (la feuille). Un LIEN
          vers le panneau d'achat, pas un second bouton de paiement. Effacée
          (`hidden`) tant que le panneau est dans la fenêtre. */}
      <div className="bou-barre" hidden={panneauVisible}>
        <p className="bou-barre-prix">
          {montant} <span>{ACHAT.ttc}</span>
        </p>
        <a className="acc-btn acc-btn-noir bou-barre-lien" href="#bou-achat">
          {ACHAT.barre}
          <span className="acc-btn-fleche" aria-hidden="true">
            ↑
          </span>
        </a>
      </div>

      {/* Les données structurées, sérialisées par `JSON.stringify` et posées
          en TEXTE : React n'y interprète aucun balisage. */}
      <script type="application/ld+json">
        {JSON.stringify(donneesStructurees(produit))}
      </script>
    </CadreDeBoutique>
  );
}
