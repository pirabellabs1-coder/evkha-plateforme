/** Les quatre pages de l'Académie EVKHA : le catalogue des formations et les
 *  trois pages de formation — reprises de `evkha.fr/formation`,
 *  `/achat-formationsociete`, `/achat-formationmicro` et `/achat-formationpop`,
 *  dans le langage visuel de l'accueil et de la page des études.
 *
 * ## Quatre pages, deux gabarits
 *
 * - `Formations` (`/formations`) : le catalogue.
 * - `FormationSocietes`, `FormationMicro`, `FormationPop` : UNE page de
 *   formation (`PageDeFormation`), paramétrée par une `Fiche`. La fiche ne
 *   porte aucun texte : elle RANGE le contenu de `contenuFormations.ts` dans
 *   les emplacements du gabarit. Un bloc qu'une formation n'a pas (le coaching
 *   pour la P.O.P, la méthode en trois lettres pour les deux autres) vaut
 *   `null`, et sa section n'existe pas.
 *
 * Les quatre partagent `Gabarit` : la barre, le menu, le pied, la pause et la
 * révélation du socle (`EnTeteSite`, `PiedSite`, `PiecesSite`, `site.ts`,
 * `Site.css`), montés comme sur les deux pages de référence.
 *
 * ## D'où vient chaque mot, chaque chiffre
 *
 * Le TEXTE DE VENTE est importé de `contenuFormations.ts` — le relevé du site,
 * puis sa section « ARTICULATION » pour ce que la plateforme ajoute.
 *
 * Les CHIFFRES viennent du serveur : `GET /api/public/formations/`
 * (`donnees.chargerFormations`) rend, pour chaque formation que la gérante a
 * mise en ligne, son prix, sa durée, ses heures de coaching et son programme
 * (modules et leçons). Chaque page y retrouve SA formation par son slug
 * (`formationEnLigne`). Aucun montant, aucune durée n'est écrit ici ni dans le
 * contenu : les phrases de la cliente qui en citent un le portent en marque,
 * que `composerTout` remplit (voir `chiffres.ts`). `les-pages-des-formations`
 * le verrouille.
 *
 * ## Les quatre états d'une formation
 *
 * - ATTENTE (la réponse n'est pas arrivée) : aucun montant, aucun chiffre ;
 *   l'emplacement du prix dit « Tarif en cours de chargement… ».
 * - PANNE (l'appel a échoué, ou la réponse est mal formée) : dite UNE fois
 *   dans la région d'alerte du haut de page, rappelée dans la section du
 *   tarif ; aucun prix.
 * - HORS LIGNE (la formation n'est pas dans la réponse) : la page garde tout
 *   son texte de vente ; le prix dit « Indisponible pour le moment ».
 * - EN LIGNE : le prix, les chiffres dans les phrases, le programme, les
 *   données structurées.
 *
 * Dans les trois premiers, les boutons d'INSCRIPTION sont neutralisés (la
 * pièce du socle, `Bouton inactif`) : on ne propose pas de s'inscrire à une
 * formation dont on ne peut pas afficher le prix.
 *
 * ## L'inscription ouvre le paiement (20/11/2026)
 *
 * Un bouton d'inscription est un vrai `<button>` : il demande au serveur
 * l'adresse de paiement de SA formation (`achat.payerUneFormation` — par
 * l'espace si un compte est ouvert, sinon en visiteur), puis y mène. Pendant
 * l'appel, les TROIS boutons de la page sont occupés : un second clic, sur le
 * même ou sur un autre, n'ouvre pas un second paiement. Un refus se dit dans
 * une alerte posée sous le bouton cliqué, avec la phrase du serveur ; une
 * panne (réseau coupé, réponse illisible) avec une phrase de la page et
 * l'adresse de contact. Le prestataire ramène ensuite l'acheteur sur
 * `/formations/retour` (`RetourFormation.tsx`), ou ici avec
 * `?paiement=abandon` s'il renonce — ce que la page dit dans un bandeau
 * refermable.
 *
 * ## Où mènent les boutons
 *
 * - « Je découvre… » (catalogue) : la page de la formation, sur la plateforme.
 *   Toujours actif : la page se lit même quand la formation n'est pas en
 *   ligne.
 * - Les boutons d'INSCRIPTION : le paiement de la plateforme (voir plus
 *   haut). Un `lien_d_achat` rendu par le serveur n'est PAS suivi. Tout passe
 *   par UN composant, `BoutonDInscription`. Le bloc de commande de l'ancien
 *   tunnel n'est pas rendu.
 * - Présentiel, financement, orientation : un courriel prérempli ou le
 *   rendez-vous en ligne. Aucun formulaire : rien ne le recevrait.
 *
 * ## Le programme
 *
 * Les modules et leurs leçons sont ceux que le serveur rend, dans son ordre.
 * La section affiche leur liste numérotée, et le NOMBRE affiché est celui des
 * modules de cette liste. Sans module : le titre et les phrases
 * d'introduction, sans liste, sans chiffre et sans promesse. La Méthode P.O.P,
 * dont le relevé n'annonce pas de programme, n'a la section que si le serveur
 * lui rend des modules. Le CONTENU d'une leçon n'est jamais ici : le serveur
 * ne le rend pas, et « Aperçu libre » n'est qu'une étiquette.
 *
 * ## Données structurées
 *
 * Une page de formation EN LIGNE pose dans l'en-tête du document un bloc
 * `application/ld+json` de type `Course` (nom, description, fournisseur,
 * offre au prix et à la devise du serveur), retiré en quittant la page. Hors
 * ligne, en attente ou en panne : pas de bloc — un moteur ne doit pas lire
 * une offre que la page ne vend pas.
 *
 * ## Ce qui n'est pas affiché tel que relevé
 *
 * Six retouches, toutes faites dans `contenuFormations.ts` (voir sa section
 * « ARTICULATION ») et non ici : « Attestation Qualiopi » rendue
 * « Attestation de fin de formation » ; les mentions d'outillage interne des
 * cartes de la micro-entreprise retirées ; « plus de 15 ans » d'expérience ;
 * la question de l'assistant IA réservée aux formations qui en annoncent un,
 * et sa parenthèse « (organisation et productivité) » à la seule Méthode
 * P.O.P ; le titre de la section d'avis du catalogue, qui dit que ces avis
 * portent sur les études et l'accompagnement. Les prix passent par
 * `donnees.euros`, comme sur le reste du site.
 * La pastille du nombre de modules de la capture « sociétés », contredite par
 * le tunnel, n'est pas rendue : le nombre affiché est celui du serveur.
 */
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ErreurApi } from "../espace/api";
import {
  MES_FORMATIONS,
  messageDuRefusDePaiement,
  payerUneFormation,
} from "./achat";
import { composerTout } from "./chiffres";
import { CONTACT_EMAIL } from "./contenu";
import { AVIS } from "./contenuAccueil";
import {
  ARTICULATION,
  ATOUTS_DES_FORMATIONS,
  CARTE_MICRO,
  CARTE_POP,
  CARTE_SOCIETES,
  INCLUS_AFFICHE,
  ONGLETS_DES_PAGES,
  ORGANISME_DE_FORMATION,
  PAGE_CATALOGUE,
  PAGE_MICRO,
  PAGE_POP,
  PAGE_SOCIETES,
  POURQUOI_CETTE_FORMATION,
  PRESENTIEL,
  PROMESSE_POP_AFFICHEE,
  QUESTIONS_DES_FORMATIONS,
  REPERES_DES_CARTES,
  ROUTES_FORMATIONS,
  SLUGS_DES_FORMATIONS,
  TITRES_COMMUNS,
  TITRES_DU_CATALOGUE,
  TITRES_MICRO,
  TITRES_POP,
  TITRES_SOCIETES,
  chiffresDeLaFormation,
  dureeDeLecon,
  dureeEnHeures,
  formationEnLigne,
  leconsDuModule,
  modulesDeLaFormation,
  natureDeLecon,
  prixDeLaFormation,
  questionsAffichees,
  sansFleche,
  type Argumentaire,
  type CarteDeFormation,
  type CarteTitreCorps,
  type CleDeFormation,
  type PageDeFormations,
  type TitreEnDeuxTemps,
} from "./contenuFormations";
import { ID_DU_CONTENU, LIENS, MARQUE, TARIFS } from "./contenuSite";
import {
  chargerFormations,
  type FormationPublique,
  type ModulePublic,
} from "./donnees";
import { EnTeteSite } from "./EnTeteSite";
import { Bouton, BoutonPause, type Aspect } from "./PiecesSite";
import { PiedSite } from "./PiedSite";
import { useReveler } from "./reveler";
import {
  lisible,
  tarifDe,
  titreDOnglet,
  useAimants,
  useChargement,
  useMenu,
  usePause,
  useDonneesStructurees,
  useQuestionsStructurees,
  useTitreDePage,
  variables,
  type Chargement,
  type Tarif,
} from "./site";
// Le socle d'abord, la feuille du lot ensuite : à spécificité égale, c'est
// elle qui a le dernier mot.
import "./Site.css";
import "./Formations.css";

// ── Petits outils ───────────────────────────────────────────────────────────

function numero(rang: number): string {
  return String(rang + 1).padStart(2, "0");
}

/** Un courriel à l'adresse de contact, objet prérempli. */
function courriel(objet: string): string {
  return `${LIENS.courriel}?subject=${encodeURIComponent(objet)}`;
}

/** Les mots du ruban, répétés jusqu'à couvrir un grand écran, puis doublés
 *  pour que la boucle ne montre pas de couture. */
function piste(mots: string[]): string[] {
  if (mots.length === 0) return [];
  let base = mots;
  while (base.length < 10) base = [...base, ...mots];
  return [...base, ...base];
}

// ── Ce que le serveur dit d'une formation ───────────────────────────────────

/** Ce qu'une page sait d'UNE formation, à un instant donné.
 *
 *  `tarif` porte les quatre états (voir l'en-tête) : un prix connu, ou la
 *  raison pour laquelle il n'y en a pas. `formation` n'existe que dans le
 *  premier cas : c'est d'elle que viennent les chiffres, le programme,
 *  l'adresse d'inscription et les données structurées. */
type Etat = {
  tarif: Tarif;
  formation: FormationPublique | null;
};

function etatDe(
  chargement: Chargement<FormationPublique[]>,
  cle: CleDeFormation,
): Etat {
  return {
    formation:
      chargement.etat === "recu"
        ? formationEnLigne(chargement.donnees, cle)
        : null,
    tarif: tarifDe(chargement, (formations) => {
      const formation = formationEnLigne(formations, cle);
      return formation ? prixDeLaFormation(formation) : null;
    }),
  };
}

/** Les données structurées d'une formation EN LIGNE (schema.org, `Course`).
 *  Le nom et la description sont ceux que la page affiche et annonce dans son
 *  onglet ; le prix et la devise sont ceux du serveur. Construit par
 *  `JSON.stringify` : aucune chaîne du serveur n'est collée à la main. */
function donneesStructurees(
  fiche: Fiche,
  formation: FormationPublique,
): string {
  const origine = window.location.origin;
  return JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Course",
    name: `${fiche.ouverture.titre.avant} ${fiche.ouverture.titre.fin}`,
    description: fiche.onglet.description,
    provider: { "@type": "Organization", name: MARQUE, url: origine },
    offers: {
      "@type": "Offer",
      category: "Paid",
      price: formation.prix_cents / 100,
      priceCurrency: formation.devise,
      url: `${origine}${ROUTES_FORMATIONS[fiche.cle]}`,
    },
  });
}

// ── Petites pièces ──────────────────────────────────────────────────────────

/** L'emplacement d'un prix : le montant que le serveur rend, ou la phrase du
 *  socle qui dit pourquoi il n'y en a pas (attente, panne, formation hors
 *  ligne). Jamais un montant de repli. */
function Prix({
  tarif,
  className = "for-prix",
  classeSansPrix = "for-prix-absent",
}: {
  tarif: Tarif;
  className?: string;
  classeSansPrix?: string;
}) {
  if (tarif.etat !== "connu") {
    return <p className={classeSansPrix}>{TARIFS[tarif.etat]}</p>;
  }
  return <p className={className}>{tarif.texte}</p>;
}

/** Pastille à coche dorée. Décorative : le texte qui la suit dit déjà tout. */
function Coche() {
  return (
    <span className="for-coche" aria-hidden="true">
      ✓
    </span>
  );
}

function Croix() {
  return (
    <span className="for-croix" aria-hidden="true">
      ✕
    </span>
  );
}

/** Un titre en deux temps : la fin en italique (Fraunces). */
function DeuxTemps({ titre }: { titre: TitreEnDeuxTemps }) {
  return (
    <>
      {titre.avant} <span className="acc-s">{titre.fin}</span>
    </>
  );
}

/** L'introduction d'une section : surtitre, titre en deux temps, puis le
 *  texte s'il y en a. Même habillage que sur l'accueil (`.acc-intro`). */
function Entree({
  surtitre,
  titre,
  children,
}: {
  surtitre?: string;
  titre: TitreEnDeuxTemps;
  children?: ReactNode;
}) {
  return (
    <div
      className={children ? "acc-intro" : "acc-intro for-intro-seule"}
      data-reveal=""
    >
      <div>
        {surtitre && <span className="acc-tag">{surtitre}</span>}
        <h2>
          <DeuxTemps titre={titre} />
        </h2>
      </div>
      {children}
    </div>
  );
}

/** Le bouton du socle, autorisé à passer à la ligne : plusieurs libellés
 *  relevés sont longs (« Je veux être informé(e) des prochaines sessions ! »)
 *  et sortiraient d'un écran de 375 px. */
function BoutonLong({
  lien,
  aspect,
  externe = false,
  inactif = false,
  className = "",
  children,
}: {
  lien: string;
  aspect: Aspect;
  externe?: boolean;
  inactif?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Bouton
      lien={lien}
      aspect={aspect}
      externe={externe}
      inactif={inactif}
      className={`for-bouton ${className}`.trim()}
    >
      {children}
    </Bouton>
  );
}

// ── L'inscription : ouvrir le paiement ──────────────────────────────────────

/** Où se trouve un bouton d'inscription dans la page : le refus se dit sous
 *  le bouton qui a été cliqué, pas sous les trois. */
type Emplacement = "ouverture" | "pratique" | "fin";

/** Ce que le serveur — ou le réseau — a répondu à une demande de paiement. */
type RefusDInscription = {
  ou: Emplacement;
  /** La phrase que le SERVEUR a écrite pour la personne. Vide : il n'a rien
   *  dit de lisible (réseau coupé, réponse d'un relais), et la page dit sa
   *  propre phrase de panne, avec l'adresse de contact. */
  message: string;
  /** Le compte ouvert possède déjà cette formation : on dit où la trouver. */
  dejaAchetee: boolean;
};

/** L'état d'inscription d'UNE page de formation, partagé par ses trois
 *  boutons. */
type Inscription = {
  occupe: boolean;
  refus: RefusDInscription | null;
  payer: (ou: Emplacement) => void;
};

/** Le refus tel qu'on peut le montrer.
 *
 *  Un refus ÉCRIT par le serveur porte une phrase et un code (`formation_
 *  inconnue`, `trop_de_tentatives`, `paiement_indisponible`…). Sans code, la
 *  phrase est un repli du client (« Erreur 502 », « Paiement impossible
 *  (500) ») : elle ne dit rien à la personne, et la page dit la sienne. */
function lireLeRefus(cause: unknown, ou: Emplacement): RefusDInscription {
  const code =
    cause !== null && typeof cause === "object" && "code" in cause
      ? String((cause as { code: unknown }).code ?? "")
      : "";
  return {
    ou,
    message: code === "" ? "" : messageDuRefusDePaiement(cause, ""),
    dejaAchetee:
      cause instanceof ErreurApi && cause.code === "formation_deja_achetee",
  };
}

/** Ouvre le paiement de la formation d'une page.
 *
 *  LE SEUL ENDROIT qui décide où mène une inscription : le slug se lit dans
 *  `SLUGS_DES_FORMATIONS`, la route (espace ou visiteur) se décide dans
 *  `achat.payerUneFormation`, et l'adresse suivie est celle que le serveur
 *  rend. Un `lien_d_achat` de la fiche publique n'est pas lu.
 *
 *  `enVol` est une référence et non l'état : deux clics du même geste
 *  arrivent avant le rendu qui désactive le bouton, et ouvriraient deux
 *  paiements — donc deux paniers, dont un « abandonné » que la gérante
 *  relancerait à tort. */
function useInscription(cle: CleDeFormation): Inscription {
  const [occupe, setOccupe] = useState(false);
  const [refus, setRefus] = useState<RefusDInscription | null>(null);
  const enVol = useRef(false);

  // Revenu du prestataire par « Précédent », le navigateur peut rendre la page
  // telle qu'il l'avait quittée : boutons occupés, pour toujours. On les
  // libère.
  useEffect(() => {
    function auRetour(evenement: PageTransitionEvent) {
      if (!evenement.persisted) return;
      enVol.current = false;
      setOccupe(false);
    }
    window.addEventListener("pageshow", auRetour);
    return () => window.removeEventListener("pageshow", auRetour);
  }, []);

  const payer = useCallback(
    (ou: Emplacement) => {
      if (enVol.current) return;
      enVol.current = true;
      setOccupe(true);
      setRefus(null);
      payerUneFormation(SLUGS_DES_FORMATIONS[cle]).then(
        (adresse) => {
          // Remplacement et non nouvel onglet : le paiement EST la suite du
          // parcours. Les boutons restent occupés jusqu'au départ.
          window.location.href = adresse;
        },
        (cause: unknown) => {
          enVol.current = false;
          setOccupe(false);
          setRefus(lireLeRefus(cause, ou));
        },
      );
    },
    [cle],
  );

  return { occupe, refus, payer };
}

/** Le paiement a-t-il été abandonné ? Le prestataire ramène alors sur
 *  `/formations?paiement=abandon`. Lu une fois, à l'arrivée ; refermer le
 *  bandeau retire le paramètre de l'adresse, pour qu'un rechargement ou un
 *  lien copié ne le redise pas. */
function useAbandon(): { affiche: boolean; fermer: () => void } {
  const [affiche, setAffiche] = useState(
    () =>
      new URLSearchParams(window.location.search).get("paiement") === "abandon",
  );
  const fermer = useCallback(() => {
    setAffiche(false);
    const adresse = new URL(window.location.href);
    adresse.searchParams.delete("paiement");
    window.history.replaceState(
      window.history.state,
      "",
      `${adresse.pathname}${adresse.search}${adresse.hash}`,
    );
  }, []);
  return { affiche, fermer };
}

/** Un bouton d'INSCRIPTION à une formation : il ouvre le paiement.
 *
 *  Les trois boutons de chaque page passent par lui, et par lui seul.
 *
 *  Sans formation en ligne (attente, panne, formation non publiée), il est
 *  neutralisé : la même pièce que sur la page des études, qui ne prend ni le
 *  clic ni le focus et se dit indisponible.
 *
 *  Pendant l'appel : `disabled` (pas de second clic), `aria-busy`, et un
 *  libellé d'attente. Le refus s'affiche sous le bouton, dans une alerte
 *  montée avec son message — comme sur la fiche de boutique. */
function BoutonDInscription({
  cle,
  libelle,
  formation,
  inscription,
  emplacement,
  aspect = "noir",
}: {
  cle: CleDeFormation;
  libelle: string;
  formation: FormationPublique | null;
  inscription: Inscription;
  emplacement: Emplacement;
  aspect?: Aspect;
}) {
  const idDuRefus = useId();

  if (formation === null) {
    return (
      <BoutonLong
        lien=""
        aspect={aspect}
        inactif
        className="for-bouton-achat"
      >
        {libelle}
      </BoutonLong>
    );
  }

  const refus =
    inscription.refus?.ou === emplacement ? inscription.refus : null;
  const classes = [
    `acc-btn acc-btn-${aspect} for-bouton for-bouton-achat`,
    inscription.occupe ? "bouton-chargement" : "",
  ]
    .join(" ")
    .trim();

  return (
    <div className="for-inscription">
      <button
        type="button"
        className={classes}
        data-formation={SLUGS_DES_FORMATIONS[cle]}
        disabled={inscription.occupe}
        aria-busy={inscription.occupe || undefined}
        aria-describedby={refus ? idDuRefus : undefined}
        onClick={() => inscription.payer(emplacement)}
      >
        {inscription.occupe ? ARTICULATION.inscription.attente : libelle}
        <span className="acc-btn-fleche" aria-hidden="true">
          →
        </span>
      </button>
      {refus && (
        <p className="for-refus" id={idDuRefus} role="alert">
          {refus.message === "" ? (
            <>
              {ARTICULATION.inscription.panne}{" "}
              <a href={LIENS.courriel}>{CONTACT_EMAIL}</a>.
            </>
          ) : (
            refus.message
          )}
          {refus.dejaAchetee && (
            <>
              {" "}
              <a href={MES_FORMATIONS}>{ARTICULATION.inscription.dejaAchetee}</a>
            </>
          )}
        </p>
      )}
    </div>
  );
}

/** Une liste cochée. */
function ListeCochee({ points }: { points: string[] }) {
  return (
    <ul className="for-liste">
      {points.map((point) => (
        <li key={point}>
          <Coche />
          <span>{point}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Le gabarit commun aux quatre pages ──────────────────────────────────────

/** La barre, l'ouverture et son bouton de pause, le ruban, les sections, le
 *  pied. La révélation, les boutons aimantés et le titre d'onglet sont
 *  branchés ici, une fois pour les quatre pages. */
function Gabarit({
  onglet,
  ruban,
  ouverture,
  appel,
  children,
}: {
  onglet: { titre: string; description: string };
  /** Décoratif : il ne répète que des mots que la page dit ailleurs. */
  ruban: string[];
  ouverture: ReactNode;
  /** Où en est l'appel au catalogue des formations. */
  appel: Chargement<FormationPublique[]>["etat"];
  children: ReactNode;
}) {
  const menu = useMenu();
  const { fige, basculer: basculerLaPause } = usePause();
  const page = useRef<HTMLDivElement>(null);
  const abandon = useAbandon();

  // La clé : à l'arrivée de la réponse, des blocs se montent (le programme)
  // ou se remontent (une carte dont le titre reçoit son chiffre), et doivent
  // être observés à leur tour — un bloc à révéler naît effacé. L'option : le
  // mouvement réduit garde la révélation, en fondu seul (voir `Site.css`).
  useReveler(page, appel, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(titreDOnglet(onglet.titre), onglet.description);
  // Les questions de la page, déclarées telles qu'elle les affiche.
  useQuestionsStructurees(page);

  return (
    <div className={fige ? "acc for acc-fige" : "acc for"} ref={page}>
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus, sinon certains navigateurs font défiler sans le déplacer. */}
      <main id={ID_DU_CONTENU} tabIndex={-1} inert={menu.ouvert}>
        {/* UNE région d'alerte, toujours dans le DOM : un lecteur d'écran
            annonce ce qui y ARRIVE. Montée avec son message, elle pouvait ne
            pas être lue. Même pièce que sur l'accueil et la page des études. */}
        <div className="acc-alerte" role="alert">
          {appel === "panne" && (
            <p className="acc-w">
              {TARIFS.alerte} {TARIFS.alerteSuite}{" "}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          )}
        </div>

        {/* Le retour d'un paiement abandonné. `status` et non `alert` : rien
            n'a échoué, et rien ne presse. Refermable, et refermé pour de bon
            (le paramètre quitte l'adresse). */}
        {abandon.affiche && (
          <div className="for-abandon" role="status">
            <div className="acc-w">
              <p>{ARTICULATION.inscription.abandon}</p>
              <button
                type="button"
                className="for-abandon-fermer"
                aria-label={ARTICULATION.inscription.fermerLAbandon}
                onClick={abandon.fermer}
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
          </div>
        )}

        <div className="for-ouverture">
          <div className="acc-w acc-pause-rang">
            <BoutonPause
              fige={fige}
              basculer={basculerLaPause}
              className="acc-pause-haut"
            />
          </div>
          {ouverture}
        </div>

        <div className="acc-ruban for-ruban" aria-hidden="true">
          <div className="acc-ruban-piste">
            {piste(ruban).map((mot, k) => (
              <span key={k}>{mot}</span>
            ))}
          </div>
        </div>
        {/* WCAG 2.2.2 : ce qui bouge en boucle peut être arrêté là où il
            bouge. Le second bouton de pause, même état que le premier. */}
        <p className="acc-w for-pause-rang">
          <BoutonPause fige={fige} basculer={basculerLaPause} />
        </p>

        {children}
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}

// ── Les sections que les quatre pages partagent ─────────────────────────────

/** Les trois atouts communs : la méthode, les outils, l'accès. */
function Atouts() {
  const atouts = [
    ATOUTS_DES_FORMATIONS.methode,
    ATOUTS_DES_FORMATIONS.outils,
    ATOUTS_DES_FORMATIONS.acces,
  ];
  return (
    <div className="for-atouts">
      {atouts.map((atout, k) => (
        <article
          key={atout.titre}
          className="for-atout"
          data-reveal=""
          style={variables({ "--i": k })}
        >
          <span className="for-atout-numero" aria-hidden="true">
            {numero(k)}
          </span>
          <h3>{atout.titre}</h3>
          <p>{atout.corps}</p>
        </article>
      ))}
    </div>
  );
}

/** Les formations en présentiel. Le bouton du site ouvrait une inscription par
 *  e-mail ; ici, un courriel prérempli vers l'adresse de contact. */
function Presentiel() {
  return (
    <section className="acc-section acc-section-suite" id="presentiel">
      <div className="acc-w">
        <div className="for-presentiel" data-reveal="">
          <div>
            <span className="acc-tag">{PRESENTIEL.surtitre}</span>
            <h2>
              <DeuxTemps titre={TITRES_COMMUNS.presentiel} />
            </h2>
            <p>{PRESENTIEL.corps}</p>
            <p className="for-presentiel-lieux">{PRESENTIEL.lieux}</p>
          </div>
          <div>
            <ListeCochee points={PRESENTIEL.points} />
            <BoutonLong
              lien={courriel(ARTICULATION.presentiel.objetDuCourriel)}
              aspect="or"
              className="for-presentiel-bouton"
            >
              {PRESENTIEL.bouton.libelle}
            </BoutonLong>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Le financement : la question et la réponse relevées, puis le numéro de
 *  déclaration d'activité de l'organisme, lu dans `ORGANISME_DE_FORMATION`. */
function Financement() {
  const f = ORGANISME_DE_FORMATION;
  return (
    <section className="acc-section acc-section-suite" id="financement">
      <div className="acc-w for-financement">
        <div data-reveal="">
          <span className="acc-tag">{ARTICULATION.financement.surtitre}</span>
          <h2 className="acc-titre-cote">
            <DeuxTemps titre={TITRES_COMMUNS.financement} />
          </h2>
          <p>{f.financement.reponse}</p>
          <BoutonLong
            lien={courriel(ARTICULATION.financement.objetDuCourriel)}
            aspect="noir"
            className="for-financement-bouton"
          >
            {ARTICULATION.financement.bouton}
          </BoutonLong>
        </div>
        <div className="for-nda" data-reveal="" style={variables({ "--i": 1 })}>
          <p className="for-nda-prise">{f.financement.presentiel}</p>
          <p className="for-nda-etiquette">
            {ARTICULATION.financement.etiquetteDuNumero}
          </p>
          <p className="for-nda-numero">{f.nda}</p>
        </div>
      </div>
    </section>
  );
}

/** Les questions fréquentes de la page (`questionsAffichees`). */
function Questions({ page }: { page: PageDeFormations }) {
  return (
    <section className="acc-section acc-section-suite" id="questions">
      <div className="acc-w acc-faq">
        <div data-reveal="">
          <span className="acc-tag">{QUESTIONS_DES_FORMATIONS.surtitre}</span>
          <h2 className="acc-titre-cote">
            <DeuxTemps titre={TITRES_COMMUNS.questions} />
          </h2>
        </div>
        <div data-reveal="">
          {questionsAffichees(page).map((question, k) => (
            <details key={question.q} open={k === 0}>
              <summary>{question.q}</summary>
              <p>{question.r}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

/** Avant l'appel final : les packs pour qui préfère être accompagné, les
 *  études pour qui veut seulement son dossier. Sans prix. */
function Passerelle() {
  const p = ARTICULATION.passerelle;
  return (
    <section className="acc-section acc-section-suite" id="autrement">
      <div className="acc-w">
        <Entree surtitre={p.surtitre} titre={p.titre}>
          <p>{p.corps}</p>
        </Entree>
        <div className="for-portes">
          {p.portes.map((porte, k) => (
            <article
              key={porte.lien}
              className="for-porte"
              data-reveal=""
              style={variables({ "--i": k })}
            >
              <small>{porte.surtitre}</small>
              <h3>{porte.titre}</h3>
              <p>{porte.corps}</p>
              <Bouton lien={porte.lien} aspect="clair" className="for-porte-bouton">
                {porte.bouton}
              </Bouton>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Le catalogue ────────────────────────────────────────────────────────────

/** L'identifiant de la section des trois cartes : le bouton de l'ouverture y
 *  mène. */
const ID_DES_CARTES = "nos-formations";

/** Une formation du catalogue : à gauche ce qu'on achète (nom, prix, bouton
 *  vers sa page), à droite pour qui, combien de temps, sous quel format et ce
 *  qu'on y apprend. */
function CarteDuCatalogue({
  carte: releve,
  rang,
  etat,
}: {
  carte: CarteDeFormation;
  rang: number;
  /** Ce que le serveur dit de CETTE formation : chaque carte a son état. */
  etat: Etat;
}) {
  // Les phrases de la carte et ses repères, avec les chiffres de SA formation
  // — ou sans chiffre, tant qu'elle n'est pas en ligne.
  const chiffres = chiffresDeLaFormation(etat.formation);
  const carte = composerTout(releve, chiffres);
  const reperes = composerTout(REPERES_DES_CARTES[carte.cle], chiffres);
  const titre = `formation-${carte.cle}-titre`;
  return (
    <li>
      <article
        className="for-carte"
        id={`formation-${carte.cle}`}
        aria-labelledby={titre}
        data-reveal=""
      >
        <div className="for-carte-tete">
          <span className="for-carte-numero" aria-hidden="true">
            {numero(rang)}
          </span>
          {carte.sousTitre && (
            <small className="for-carte-surtitre">{carte.sousTitre}</small>
          )}
          <h3 id={titre}>{carte.titre}</h3>
          <Prix tarif={etat.tarif} />
          {carte.mention && <p className="for-carte-mention">{carte.mention}</p>}
          {/* Le bouton mène à la PAGE de la formation, pas à une inscription :
              il reste actif même quand la formation n'est pas en ligne. */}
          <BoutonLong
            lien={ROUTES_FORMATIONS[carte.cle]}
            aspect="noir"
            className="for-carte-bouton"
          >
            {sansFleche(carte.bouton.libelle)}
          </BoutonLong>
        </div>

        <div className="for-carte-corps">
          <p className="for-carte-accroche">{carte.accroche}</p>
          {reperes.length > 0 && (
            <ul className="for-pastilles">
              {reperes.map((repere) => (
                <li key={repere}>{repere}</li>
              ))}
            </ul>
          )}
          {carte.corps.map((paragraphe) => (
            <p key={paragraphe}>{paragraphe}</p>
          ))}
          <p className="for-carte-quoi">{carte.titreDesAcquis}</p>
          <ul className="for-points">
            {carte.acquis.map((acquis) => (
              <li key={acquis}>{acquis}</li>
            ))}
          </ul>
        </div>
      </article>
    </li>
  );
}

export function Formations() {
  const p = PAGE_CATALOGUE;
  const [amorce, ...recit] = p.pourquoi.paragraphes;
  const fin = ARTICULATION.finDuCatalogue;
  const chargement = useChargement(chargerFormations);

  return (
    <Gabarit
      onglet={ONGLETS_DES_PAGES.catalogue}
      appel={chargement.etat}
      ruban={[...p.formations.cartes.map((carte) => carte.titre), ...p.pourQui.profils]}
      ouverture={
        <div className="acc-w for-ouverture-grille">
          <div>
            <span className="acc-tag acc-entre">{p.ouverture.surtitre}</span>
            <h1>
              <span className="acc-ligne-titre">
                <span>{TITRES_DU_CATALOGUE.ouverture.avant}</span>
              </span>{" "}
              <span className="acc-ligne-titre">
                <span className="acc-s">{TITRES_DU_CATALOGUE.ouverture.fin}</span>
              </span>
            </h1>
            <p className="for-promesse acc-entre" style={variables({ "--i": 1 })}>
              {p.ouverture.corps}
            </p>
            <div className="for-achat acc-entre" style={variables({ "--i": 2 })}>
              <Bouton lien={`#${ID_DES_CARTES}`} aspect="noir">
                {ARTICULATION.ouverture.boutonDuCatalogue}
              </Bouton>
            </div>
            <p className="for-preuve acc-entre" style={variables({ "--i": 3 })}>
              {p.ouverture.preuve}
            </p>
          </div>

          {/* Les attributs donnent le ratio, la feuille la taille : rien ne
              saute au chargement. Haut de page : pas de chargement différé. */}
          <div className="for-visuel acc-entre" style={variables({ "--i": 2 })}>
            <img
              className="for-image"
              src={ARTICULATION.image.src}
              alt={ARTICULATION.image.alt}
              width={ARTICULATION.image.largeur}
              height={ARTICULATION.image.hauteur}
              decoding="async"
            />
          </div>
        </div>
      }
    >
      {/* ── Pourquoi se former avec EVKHA ──────────────────────────────── */}
      <section className="acc-section for-section-premiere" id="pourquoi">
        <div className="acc-w">
          <Entree titre={TITRES_DU_CATALOGUE.pourquoi}>
            <p>{amorce}</p>
          </Entree>
          <div className="for-recit" data-reveal="">
            {recit.map((paragraphe) => (
              <p key={paragraphe}>{paragraphe}</p>
            ))}
          </div>
          <p className="acc-tag for-atouts-titre" data-reveal="">
            {p.pourquoi.atouts.titre}
          </p>
          <Atouts />
        </div>
      </section>

      {/* ── Les trois formations ───────────────────────────────────────── */}
      <section className="acc-section acc-section-suite" id={ID_DES_CARTES}>
        <div className="acc-w">
          <Entree titre={TITRES_DU_CATALOGUE.formations} />
          {chargement.etat === "panne" && (
            <p className="acc-panne">{TARIFS.rappel}</p>
          )}
          {/* Les trois cartes, toujours : le texte de vente ne dépend pas du
              serveur. Chacune dit SON état — une formation peut être en ligne
              et sa voisine pas encore. */}
          <ul className="for-cartes" aria-label={ARTICULATION.cartes.nomDeLaListe}>
            {p.formations.cartes.map((carte, k) => (
              <CarteDuCatalogue
                key={carte.cle}
                carte={carte}
                rang={k}
                etat={etatDe(chargement, carte.cle)}
              />
            ))}
          </ul>
        </div>
      </section>

      <Presentiel />

      {/* ── À qui ça s'adresse ─────────────────────────────────────────── */}
      <section className="acc-section acc-section-suite" id="pour-qui">
        <div className="acc-w">
          <Entree
            surtitre={ARTICULATION.pourQui.surtitre}
            titre={TITRES_DU_CATALOGUE.pourQui}
          />
          <ul className="for-publics" data-reveal="">
            {p.pourQui.profils.map((profil, k) => (
              <li key={profil}>
                <span className="for-public-numero" aria-hidden="true">
                  {numero(k)}
                </span>
                {profil}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── Les avis ───────────────────────────────────────────────────────
          Sur le site, neuf avis en image ; leur texte est retranscrit dans
          `contenuAccueil.AVIS`, avec la phrase qui dit d'où ils viennent. */}
      <section className="acc-section acc-section-suite" id="avis">
        <div className="acc-w">
          <Entree surtitre={p.avis.surtitre} titre={TITRES_DU_CATALOGUE.avis}>
            <p>{AVIS.corps}</p>
          </Entree>
          <div className="for-avis">
            {AVIS.liste.map((avis) => (
              <figure key={`${avis.auteur}-${avis.contexte}`} className="for-mot" data-reveal="">
                <p>{avis.texte}</p>
                <figcaption>
                  {avis.auteur}
                  <span className="for-mot-contexte">{avis.contexte}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <Financement />
      <Questions page="catalogue" />
      <Passerelle />

      {/* ── Appel final ────────────────────────────────────────────────── */}
      <section className="acc-fin for-fin" id="contact">
        <div className="acc-w">
          <h2>
            <DeuxTemps titre={fin.titre} />
          </h2>
          <p className="acc-fin-corps">{fin.corps}</p>
          <div className="for-fin-boutons">
            <BoutonLong lien={LIENS.appel} aspect="noir" externe>
              {fin.boutonAppel}
            </BoutonLong>
            <BoutonLong lien={courriel(fin.objetDuCourriel)} aspect="clair">
              {fin.boutonCourriel}
            </BoutonLong>
          </div>
        </div>
      </section>
    </Gabarit>
  );
}

// ── Une page de formation ───────────────────────────────────────────────────

type Liste = { titre?: string; points: string[] };

/** Ce qu'une page de formation affiche, emplacement par emplacement. `null` :
 *  la formation n'a pas ce bloc, la section n'existe pas.
 *
 *  Une fiche ne porte que du TEXTE, dont certaines phrases citent un chiffre
 *  en marque : la page la compose avec ce que le serveur rend
 *  (`composerTout`) avant de l'afficher. */
type Fiche = {
  cle: CleDeFormation;
  onglet: { titre: string; description: string };
  ruban: string[];
  ouverture: {
    etiquette?: string;
    titre: TitreEnDeuxTemps;
    accroche: string;
    paragraphes: string[];
    /** Les statuts couverts, en pastilles dorées (sociétés). */
    sigles: string[];
    pastilles: string[];
    maitrise: { titre: string; points: string[] };
  };
  pourquoi: { argumentaire: Argumentaire; suite: string[] };
  aQui: {
    surtitre: string;
    titre: TitreEnDeuxTemps;
    corps?: string;
    cartes: CarteTitreCorps[];
  } | null;
  objectifs: { surtitre: string; titre: TitreEnDeuxTemps; liste: string[] };
  /** L'habillage de la section du programme. Les modules, leurs leçons et
   *  leur nombre ne sont pas ici : ils viennent du serveur. */
  programme: {
    surtitre: string;
    titre: TitreEnDeuxTemps;
    corps: string[];
    /** `true` : la section s'affiche même sans module (titre et phrases
     *  relevés). `false` : la formation n'annonce pas de programme dans le
     *  relevé, la section n'existe que si le serveur rend des modules. */
    memeSansModule: boolean;
  };
  inclus: { surtitre: string; titre: TitreEnDeuxTemps; cartes: CarteTitreCorps[] };
  /** Le grand chiffre de l'encart — les heures de coaching — n'est pas ici :
   *  il vient du serveur. */
  coaching: {
    surtitre: string;
    titre: TitreEnDeuxTemps;
    paragraphes: string[];
    encart: { surtitre?: string; titre?: string; textes: string[] };
    points: string[];
  } | null;
  methode: {
    surtitre: string;
    titre: TitreEnDeuxTemps;
    corps: string;
    lettres: { lettre: string; verbe: string; corps: string }[];
  } | null;
  formes: {
    surtitre: string;
    titre: TitreEnDeuxTemps;
    corps: string[];
    liste: { sigle: string; nom: string; points: string[] }[];
  } | null;
  /** « En pratique » : le format, le tarif, le bouton d'achat. */
  pratique: {
    titre?: string;
    accroche?: string;
    reperes: string[];
    paragraphes: string[];
    listes: Liste[];
  };
  fin: { titre: string };
  achat: string;
};

const SOCIETES = PAGE_SOCIETES;
const COACHING_SOCIETES = SOCIETES.modalites.coaching;

const FICHE_SOCIETES: Fiche = {
  cle: "societes",
  onglet: ONGLETS_DES_PAGES.societes,
  ruban: [...SOCIETES.ouvertureEnImage.statuts, ...SOCIETES.ouvertureEnImage.pastilles],
  ouverture: {
    etiquette: SOCIETES.ouvertureEnImage.etiquette,
    titre: TITRES_SOCIETES.ouverture,
    accroche: SOCIETES.ouvertureEnImage.accroche,
    paragraphes: [SOCIETES.ouvertureEnImage.corps],
    sigles: SOCIETES.ouvertureEnImage.statuts,
    // Sans la pastille du nombre de modules de la capture, contredite par le
    // tunnel de paiement : le contenu la tient hors de cette liste
    // (`pastilleContredite`).
    pastilles: SOCIETES.ouvertureEnImage.pastilles,
    maitrise: {
      titre: CARTE_SOCIETES.titreDesAcquis,
      points: CARTE_SOCIETES.acquis,
    },
  },
  pourquoi: { argumentaire: SOCIETES.pourQui.argumentaire, suite: [] },
  aQui: { ...SOCIETES.pourQui.aQui, titre: TITRES_SOCIETES.aQui },
  objectifs: { ...SOCIETES.objectifs, titre: TITRES_SOCIETES.objectifs },
  programme: {
    surtitre: SOCIETES.programme.surtitre,
    titre: TITRES_SOCIETES.programme,
    corps: SOCIETES.programme.corps,
    memeSansModule: true,
  },
  inclus: {
    surtitre: SOCIETES.inclus.surtitre,
    titre: TITRES_SOCIETES.inclus,
    cartes: INCLUS_AFFICHE.societes,
  },
  coaching: {
    surtitre: COACHING_SOCIETES.surtitre,
    titre: TITRES_SOCIETES.coaching,
    // Les deux premières lignes relevées forment une seule phrase.
    paragraphes: [
      COACHING_SOCIETES.corps.slice(0, 2).join(" "),
      ...COACHING_SOCIETES.corps.slice(2),
    ],
    encart: {
      surtitre: COACHING_SOCIETES.captureDAchat.surtitre,
      titre: COACHING_SOCIETES.captureDAchat.titre,
      textes: [
        COACHING_SOCIETES.captureDAchat.introduction,
        COACHING_SOCIETES.captureDAchat.corps,
      ],
    },
    points: COACHING_SOCIETES.points,
  },
  methode: null,
  formes: {
    surtitre: SOCIETES.statuts.surtitre,
    titre: TITRES_SOCIETES.statuts,
    // Le premier paragraphe relevé répète la présentation de l'ouverture :
    // il n'est pas redit ici. La phrase retenue est celle du tunnel
    // (« tableau comparatif »), pas celle de la capture (« tableau CMA »).
    corps: SOCIETES.statuts.corps.slice(1),
    liste: SOCIETES.statuts.formes,
  },
  pratique: {
    reperes: SOCIETES.modalites.format,
    paragraphes: CARTE_SOCIETES.mention ? [CARTE_SOCIETES.mention] : [],
    listes: [],
  },
  fin: { titre: CARTE_SOCIETES.accroche },
  achat: SOCIETES.appelFinal.bouton.libelle,
};

const MICRO = PAGE_MICRO;
const COACHING_MICRO = MICRO.modalites.coaching;

const FICHE_MICRO: Fiche = {
  cle: "micro",
  onglet: ONGLETS_DES_PAGES.micro,
  ruban: MICRO.ouvertureEnImage.pastilles,
  ouverture: {
    etiquette: MICRO.ouvertureEnImage.etiquette,
    titre: TITRES_MICRO.ouverture,
    accroche: MICRO.ouvertureEnImage.accroche,
    paragraphes: [MICRO.ouvertureEnImage.corps],
    sigles: [],
    pastilles: MICRO.ouvertureEnImage.pastilles,
    maitrise: { titre: CARTE_MICRO.titreDesAcquis, points: CARTE_MICRO.acquis },
  },
  pourquoi: { argumentaire: MICRO.pourQui.argumentaire, suite: [] },
  aQui: { ...MICRO.pourQui.aQui, titre: TITRES_MICRO.aQui },
  objectifs: { ...MICRO.objectifs, titre: TITRES_MICRO.objectifs },
  programme: {
    surtitre: MICRO.programme.surtitre,
    titre: TITRES_MICRO.programme,
    corps: MICRO.programme.corps,
    memeSansModule: true,
  },
  inclus: {
    surtitre: MICRO.inclus.surtitre,
    titre: TITRES_MICRO.inclus,
    cartes: INCLUS_AFFICHE.micro,
  },
  coaching: {
    surtitre: COACHING_MICRO.surtitre,
    titre: TITRES_MICRO.coaching,
    paragraphes: [COACHING_MICRO.corps.slice(0, 2).join(" ")],
    encart: { textes: COACHING_MICRO.corps.slice(2) },
    points: COACHING_MICRO.points,
  },
  methode: null,
  formes: null,
  pratique: {
    // La carte du catalogue n'a ni ligne de format ni durée : les repères
    // sont les pastilles de l'ouverture.
    reperes: MICRO.ouvertureEnImage.pastilles,
    paragraphes: CARTE_MICRO.mention ? [CARTE_MICRO.mention] : [],
    listes: [],
  },
  fin: { titre: CARTE_MICRO.accroche },
  achat: MICRO.appelFinal.bouton.libelle,
};

const POP = PAGE_POP;

const FICHE_POP: Fiche = {
  cle: "pop",
  onglet: ONGLETS_DES_PAGES.pop,
  ruban: [
    ...POP.ouverture.enBref,
    ...POP.methode.lettres.map((lettre) => lettre.verbe),
  ],
  ouverture: {
    etiquette: CARTE_POP.sousTitre,
    titre: TITRES_POP.ouverture,
    accroche: POP.ouverture.sousTitre,
    paragraphes: [POP.ouverture.constat, POP.ouverture.promesse],
    sigles: [],
    pastilles: POP.ouverture.enBref,
    maitrise: {
      titre: POP.ouverture.titreDesApprentissages,
      points: POP.ouverture.apprentissages,
    },
  },
  pourquoi: {
    argumentaire: POP.pourQui.argumentaire,
    // La promesse porte l'ancienneté retenue pour la refonte.
    suite: [POP.pourQui.public, PROMESSE_POP_AFFICHEE],
  },
  aQui: null,
  objectifs: { ...POP.objectifs, titre: TITRES_POP.objectifs },
  // Le site n'annonce ni programme module par module ni coaching. La section
  // du programme n'existe donc que le jour où le serveur rend des modules ;
  // son surtitre et son titre sont écrits pour ce jour-là.
  programme: {
    surtitre: ARTICULATION.programme.pop.surtitre,
    titre: ARTICULATION.programme.pop.titre,
    corps: [],
    memeSansModule: false,
  },
  inclus: {
    surtitre: POP.inclus.surtitre,
    titre: TITRES_POP.inclus,
    cartes: INCLUS_AFFICHE.pop,
  },
  coaching: null,
  methode: { ...POP.methode, titre: TITRES_POP.methode },
  formes: null,
  pratique: {
    titre: POP.modalites.titre,
    accroche: CARTE_POP.accroche,
    reperes: POP.modalites.format,
    paragraphes: CARTE_POP.corps,
    listes: [
      { points: POP.modalites.contenu },
      { titre: CARTE_POP.titreDesAcquis, points: CARTE_POP.acquis },
    ],
  },
  fin: { titre: CARTE_POP.accroche },
  achat: POP.appelFinal.bouton.libelle,
};

/** Un module du programme : son intitulé, sa description s'il en a une, puis
 *  ses leçons — chacune avec sa nature, sa durée et, si la gérante l'a
 *  marquée ainsi, l'étiquette « aperçu libre ». Tout vient du serveur. */
function Module({ module, rang }: { module: ModulePublic; rang: number }) {
  const description =
    typeof module.description === "string" ? module.description.trim() : "";
  const lecons = leconsDuModule(module);
  return (
    <li>
      {/* Le numéro est décoratif : la liste ordonnée le dit déjà. */}
      <span className="for-module-numero" aria-hidden="true">
        {numero(rang)}
      </span>
      <div className="for-module">
        <h3>{module.titre}</h3>
        {description !== "" && (
          <p className="for-module-description">{description}</p>
        )}
        {lecons.length > 0 && (
          <ol className="for-lecons">
            {lecons.map((lecon, k) => {
              const nature = natureDeLecon(lecon.nature);
              const duree = dureeDeLecon(lecon.duree_minutes);
              return (
                <li key={`${k}-${lecon.titre}`}>
                  <span className="for-lecon-titre">{lecon.titre}</span>{" "}
                  {nature !== null && (
                    <>
                      <span className="for-lecon-repere">{nature}</span>{" "}
                    </>
                  )}
                  {duree !== null && (
                    <>
                      <span className="for-lecon-repere">{duree}</span>{" "}
                    </>
                  )}
                  {/* Une étiquette, pas un lien : le contenu de la leçon
                      n'est pas rendu par le serveur public. */}
                  {lecon.en_apercu_libre === true && (
                    <span className="for-lecon-apercu">
                      {ARTICULATION.programme.apercuLibre}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </li>
  );
}

/** Le programme : le titre, les phrases, puis les modules que le serveur rend
 *  — leur NOMBRE en grand, et leur liste numérotée. Le nombre affiché est
 *  celui des modules de la liste : les deux ne peuvent pas diverger.
 *
 *  Sans module, la section se réduit à son titre et à ses phrases : ni
 *  chiffre, ni liste, ni promesse de contenu à venir. */
function Programme({
  programme,
  modules,
}: {
  programme: Fiche["programme"];
  modules: ModulePublic[];
}) {
  const nombre = modules.length;
  return (
    <section className="acc-section acc-section-suite" id="programme">
      <div className="acc-w">
        <div
          className={
            nombre > 0 ? "for-programme" : "for-programme for-programme-seul"
          }
          data-reveal=""
        >
          {nombre > 0 && (
            <p className="for-programme-nombre">
              <b>{nombre}</b>
              <span>
                {nombre === 1
                  ? ARTICULATION.programme.uniteAuSingulier
                  : ARTICULATION.programme.unite}
              </span>
            </p>
          )}
          <div className="for-programme-corps">
            <span className="acc-tag">{programme.surtitre}</span>
            <h2>
              <DeuxTemps titre={programme.titre} />
            </h2>
            {programme.corps.map((phrase) => (
              <p key={phrase}>{phrase}</p>
            ))}
            {nombre > 0 && (
              <ol className="for-modules">
                {modules.map((module, k) => (
                  <Module key={`${k}-${module.titre}`} module={module} rang={k} />
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function PageDeFormation({ fiche: releve }: { fiche: Fiche }) {
  const chargement = useChargement(chargerFormations);
  const { tarif, formation } = etatDe(chargement, releve.cle);

  // Le texte de la fiche, avec les chiffres que le serveur rend pour CETTE
  // formation. Sans formation en ligne, les passages qui citent un chiffre ne
  // s'affichent pas ; tout le reste du texte de vente, si.
  const fiche = composerTout(releve, chiffresDeLaFormation(formation));
  const { cle, ouverture, pourquoi, aQui, objectifs, programme, inclus } = fiche;
  const { coaching, methode, formes, pratique } = fiche;
  const modules = modulesDeLaFormation(formation);
  const heuresDeCoaching = formation?.heures_de_coaching;
  // UN état d'inscription pour les trois boutons de la page.
  const inscription = useInscription(cle);

  useDonneesStructurees(
    formation ? donneesStructurees(fiche, formation) : null,
  );

  return (
    <Gabarit
      onglet={fiche.onglet}
      appel={chargement.etat}
      ruban={fiche.ruban}
      ouverture={
        <div className="acc-w for-ouverture-grille">
          <div>
            {ouverture.etiquette && (
              <span className="acc-tag acc-entre">{ouverture.etiquette}</span>
            )}
            <h1>
              <span className="acc-ligne-titre">
                <span>{ouverture.titre.avant}</span>
              </span>{" "}
              <span className="acc-ligne-titre">
                <span className="acc-s">{ouverture.titre.fin}</span>
              </span>
            </h1>
            <p className="for-accroche acc-entre" style={variables({ "--i": 1 })}>
              {ouverture.accroche}
            </p>
            {ouverture.paragraphes.map((paragraphe) => (
              <p
                key={paragraphe}
                className="for-promesse acc-entre"
                style={variables({ "--i": 2 })}
              >
                {paragraphe}
              </p>
            ))}
            {ouverture.sigles.length > 0 && (
              <ul
                className="for-pastilles for-sigles acc-entre"
                style={variables({ "--i": 3 })}
              >
                {ouverture.sigles.map((sigle) => (
                  <li key={sigle}>{sigle}</li>
                ))}
              </ul>
            )}
            <ul className="for-pastilles acc-entre" style={variables({ "--i": 3 })}>
              {ouverture.pastilles.map((pastille) => (
                <li key={pastille}>{pastille}</li>
              ))}
            </ul>
            <div className="for-achat acc-entre" style={variables({ "--i": 4 })}>
              <Prix tarif={tarif} />
              <BoutonDInscription
                cle={cle}
                libelle={fiche.achat}
                formation={formation}
                inscription={inscription}
                emplacement="ouverture"
              />
            </div>
          </div>

          <div className="for-maitrise acc-entre" style={variables({ "--i": 3 })}>
            <h2>{ouverture.maitrise.titre}</h2>
            <ListeCochee points={ouverture.maitrise.points} />
          </div>
        </div>
      }
    >
      {/* ── Pourquoi cette formation : difficultés et bénéfices ────────── */}
      <section className="acc-section for-section-premiere" id="pourquoi">
        <div className="acc-w">
          <Entree
            surtitre={POURQUOI_CETTE_FORMATION.surtitre}
            titre={TITRES_COMMUNS.pourquoi}
          >
            {pourquoi.argumentaire.titre && (
              <p className="for-amorce">{pourquoi.argumentaire.titre}</p>
            )}
          </Entree>

          <div className="for-versus">
            <article className="for-versus-colonne for-versus-constat" data-reveal="">
              <h3>{pourquoi.argumentaire.constat.titre}</h3>
              <ul>
                {pourquoi.argumentaire.constat.points.map((point) => (
                  <li key={point}>
                    <Croix />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </article>
            <article
              className="for-versus-colonne for-versus-promesse"
              data-reveal=""
              style={variables({ "--i": 1 })}
            >
              <h3>{pourquoi.argumentaire.promesse.titre}</h3>
              <ul>
                {pourquoi.argumentaire.promesse.points.map((point) => (
                  <li key={point}>
                    <Coche />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          {pourquoi.suite.length > 0 && (
            <div className="for-suite" data-reveal="">
              {pourquoi.suite.map((paragraphe) => (
                <p key={paragraphe}>{paragraphe}</p>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── À qui s'adresse cette formation ────────────────────────────── */}
      {aQui && (
        <section className="acc-section acc-section-suite" id="pour-qui">
          <div className="acc-w">
            <Entree surtitre={aQui.surtitre} titre={aQui.titre}>
              {aQui.corps && <p>{aQui.corps}</p>}
            </Entree>
            <div className="for-profils">
              {aQui.cartes.map((carte, k) => (
                <article
                  key={carte.titre}
                  className="for-profil"
                  data-reveal=""
                  style={variables({ "--i": k })}
                >
                  <span className="for-profil-numero" aria-hidden="true">
                    {numero(k)}
                  </span>
                  <h3>{carte.titre}</h3>
                  <p>{carte.corps}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Objectifs pédagogiques ─────────────────────────────────────────
          Une liste ORDONNÉE : les objectifs sont numérotés sur le site. Ce
          ne sont pas les modules du programme. */}
      <section className="acc-section acc-section-suite" id="objectifs">
        <div className="acc-w">
          <Entree surtitre={objectifs.surtitre} titre={objectifs.titre} />
          <ol className="for-objectifs" data-reveal="">
            {objectifs.liste.map((objectif, k) => (
              <li key={objectif}>
                <span className="for-objectif-numero" aria-hidden="true">
                  {numero(k)}
                </span>
                <span>{objectif}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {(programme.memeSansModule || modules.length > 0) && (
        <Programme programme={programme} modules={modules} />
      )}

      {/* ── Ce qui est inclus ──────────────────────────────────────────── */}
      <section className="acc-section acc-section-suite" id="inclus">
        <div className="acc-w">
          <Entree surtitre={inclus.surtitre} titre={inclus.titre} />
          <div className="for-inclus">
            {/* La clé est le RANG, pas le titre : le titre d'une carte reçoit
                son chiffre à l'arrivée de la réponse, et une clé qui change
                remonterait la carte — donc la révélerait une seconde fois. */}
            {inclus.cartes.map((carte, k) => (
              <article
                key={k}
                className="for-inclus-carte"
                data-reveal=""
                style={variables({ "--i": k % 3 })}
              >
                <span className="for-inclus-signe" aria-hidden="true">
                  ✦
                </span>
                <h3>{carte.titre}</h3>
                <p>{carte.corps}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Le coaching individuel ─────────────────────────────────────── */}
      {coaching && (
        <section className="acc-section for-bande" id="coaching">
          <div className="acc-w for-coaching">
            <div data-reveal="">
              <span className="acc-tag">{coaching.surtitre}</span>
              <h2 className="acc-titre-cote">
                <DeuxTemps titre={coaching.titre} />
              </h2>
              {coaching.paragraphes.map((paragraphe) => (
                <p key={paragraphe}>{paragraphe}</p>
              ))}
            </div>
            <div
              className="for-coaching-encart"
              data-reveal=""
              style={variables({ "--i": 1 })}
            >
              {/* Le grand chiffre : les heures de coaching que le serveur
                  rend. Inconnues, ou nulles : l'encart s'ouvre sur son texte. */}
              {lisible(heuresDeCoaching) && (
                <p className="for-coaching-heures">
                  <b>{dureeEnHeures(heuresDeCoaching)}</b>
                  <span>{ARTICULATION.coaching.unite}</span>
                </p>
              )}
              {coaching.encart.surtitre && (
                <small>{coaching.encart.surtitre}</small>
              )}
              {coaching.encart.titre && <h3>{coaching.encart.titre}</h3>}
              {coaching.encart.textes.map((texte) => (
                <p key={texte}>{texte}</p>
              ))}
              <ListeCochee points={coaching.points} />
            </div>
          </div>
        </section>
      )}

      {/* ── La méthode en trois lettres ────────────────────────────────── */}
      {methode && (
        <section className="acc-section acc-section-suite" id="methode">
          <div className="acc-w">
            <Entree surtitre={methode.surtitre} titre={methode.titre}>
              <p>{methode.corps}</p>
            </Entree>
            <div className="for-lettres">
              {methode.lettres.map((lettre, k) => (
                <article
                  key={lettre.verbe}
                  className="for-lettre"
                  data-reveal=""
                  style={variables({ "--i": k })}
                >
                  <span className="for-lettre-signe" aria-hidden="true">
                    {lettre.lettre}
                  </span>
                  <h3>{lettre.verbe}</h3>
                  <p>{lettre.corps}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Les formes juridiques ──────────────────────────────────────── */}
      {formes && (
        <section
          className={
            coaching ? "acc-section" : "acc-section acc-section-suite"
          }
          id="formes-juridiques"
        >
          <div className="acc-w">
            <Entree surtitre={formes.surtitre} titre={formes.titre}>
              <div className="for-entree-corps">
                {formes.corps.map((paragraphe) => (
                  <p key={paragraphe}>{paragraphe}</p>
                ))}
              </div>
            </Entree>
            <div className="for-formes">
              {formes.liste.map((forme, k) => (
                <article
                  key={forme.sigle}
                  className="for-forme"
                  data-reveal=""
                  style={variables({ "--i": k })}
                >
                  <h3>
                    <span className="for-forme-sigle">{forme.sigle}</span>
                    <span className="for-forme-nom">{forme.nom}</span>
                  </h3>
                  <ul className="for-points">
                    {forme.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── En pratique : format, tarif, achat ─────────────────────────── */}
      <section
        className={
          coaching && !formes ? "acc-section" : "acc-section acc-section-suite"
        }
        id="modalites"
      >
        <div className="acc-w">
          <Entree
            surtitre={ARTICULATION.modalites.surtitre}
            titre={ARTICULATION.modalites.titre}
          />
          {/* Le rappel de la panne, là où le tarif devrait être : l'alerte du
              haut de page l'a annoncée, celui-ci la redit à qui arrive ici. */}
          {chargement.etat === "panne" && (
            <p className="acc-panne">{TARIFS.rappel}</p>
          )}
          <div className="for-pratique" data-reveal="">
            <div className="for-pratique-tete">
              <small>{ARTICULATION.ouverture.etiquetteDuPrix}</small>
              <Prix tarif={tarif} />
              <BoutonDInscription
                cle={cle}
                libelle={fiche.achat}
                formation={formation}
                inscription={inscription}
                emplacement="pratique"
              />
            </div>
            <div className="for-pratique-corps">
              {pratique.titre && <h3>{pratique.titre}</h3>}
              {pratique.accroche && (
                <p className="for-carte-accroche">{pratique.accroche}</p>
              )}
              {pratique.reperes.length > 0 && (
                <ul className="for-pastilles">
                  {pratique.reperes.map((repere) => (
                    <li key={repere}>{repere}</li>
                  ))}
                </ul>
              )}
              {pratique.paragraphes.map((paragraphe) => (
                <p key={paragraphe}>{paragraphe}</p>
              ))}
              {pratique.listes.map((liste) => (
                <div key={liste.points.join("|")} className="for-pratique-liste">
                  {liste.titre && <p className="for-carte-quoi">{liste.titre}</p>}
                  <ul className="for-points">
                    {liste.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Les outils, la méthode, l'accès : communs aux trois ────────── */}
      <section className="acc-section acc-section-suite" id="atouts">
        <div className="acc-w">
          <Entree
            surtitre={ATOUTS_DES_FORMATIONS.titre}
            titre={ARTICULATION.outils.titre}
          />
          <Atouts />
        </div>
      </section>

      <Financement />
      <Presentiel />
      <Questions page={cle} />
      <Passerelle />

      {/* ── Appel final ────────────────────────────────────────────────── */}
      <section className="acc-fin for-fin" id="rejoindre">
        <div className="acc-w">
          <h2>{fiche.fin.titre}</h2>
          <Prix
            tarif={tarif}
            className="acc-fin-corps for-fin-prix"
            classeSansPrix="acc-fin-corps for-fin-sans-prix"
          />
          <BoutonDInscription
            cle={cle}
            libelle={fiche.achat}
            formation={formation}
            inscription={inscription}
            emplacement="fin"
          />
        </div>
      </section>
    </Gabarit>
  );
}

export function FormationSocietes() {
  return <PageDeFormation fiche={FICHE_SOCIETES} />;
}

export function FormationMicro() {
  return <PageDeFormation fiche={FICHE_MICRO} />;
}

export function FormationPop() {
  return <PageDeFormation fiche={FICHE_POP} />;
}
