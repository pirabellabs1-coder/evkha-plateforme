/** Les trois pages des packs d'accompagnement — reprise de `evkha.fr/packs`,
 *  `/paiement-packcrea` et `/paiement-packcreapremium`, dans le langage visuel
 *  de l'accueil et de la page des études.
 *
 *  - `Packs` (`/packs`) : les deux packs côte à côte, leur comparatif, le
 *    rappel de qui les réalise, l'appel final ;
 *  - `PackEssentiel` (`/packs/essentiel`) et `PackPremium` (`/packs/premium`) :
 *    deux pages JUMELLES. Un seul composant, `PageDePack`, reçoit le contenu
 *    de l'une ou de l'autre ; un bloc que l'une des deux n'a pas (le support
 *    détaillé, l'aperçu des documents, le comparatif…) ne s'affiche pas.
 *
 * ## D'où vient le texte
 *
 * De `contenuPacks.ts`, relevé sur le site de la cliente et non réécrit. Ce
 * que la plateforme y ajoute — surtitres, intitulés de boutons, passerelle —
 * est dans le même fichier, sous son propre bandeau. Rien n'est écrit ici.
 *
 * ## Les prix
 *
 * Ces offres ne sont dans aucune API : leurs montants se lisent dans UNE
 * constante, `contenuPacks.TARIFS_PACKS`, et nulle part ailleurs (règle 5).
 * Aucun montant n'est écrit dans ce fichier ; le test
 * `les-pages-des-packs` le verrouille.
 *
 * ## La formation P.O.P offerte : sa valeur et sa durée viennent du serveur
 *
 * Le Premium offre la Méthode P.O.P, et les trois pages en citent la
 * « valeur » ou la durée. Ces deux chiffres sont ceux de la formation telle
 * qu'elle est vendue : les pages lisent la MÊME réponse que les pages des
 * formations (`donnees.chargerFormations`) et composent leur texte avec
 * (`chiffresDesPacks`, `composerTout`). Tant que la réponse n'est pas arrivée,
 * si l'appel échoue ou si la formation n'est pas en ligne, la mention
 * disparaît de la phrase — sans parenthèse vide — et la page reste entière.
 * Pas de région d'alerte ici : aucun prix de pack ne dépend de cet appel.
 *
 * ## Où mènent les boutons
 *
 * Les boutons d'achat sortent vers les pages de paiement du site
 * (`LIENS_PACKS`) : la plateforme n'encaisse pas encore ces offres. Le
 * formulaire de commande de Systeme.io (`formulaireDeCommande`) n'est donc PAS
 * rendu — un formulaire qui n'envoie rien serait un piège.
 *
 * ## Une page n'affiche pas un nombre qu'elle contredit
 *
 * Trois accords, faits à l'affichage par les fonctions de `contenuPacks.ts`
 * (le texte relevé n'est pas touché) : l'ancienneté s'écrit « plus de 16
 * ans » (cliente, 24/11/2026) ; le nombre d'étapes annoncé est celui des étapes affichées ; le
 * nombre de livrables du Premium, que la page compte de trois façons, n'est
 * pas affiché.
 *
 * ## Mouvement
 *
 * Comme sur les pages de référence : révélation au défilement gardée en fondu
 * sous mouvement réduit (`useReveler`, option passée), ruban que deux boutons
 * de pause arrêtent (WCAG 2.2.2), boutons aimantés coupés par leur crochet.
 */
import { useRef, type ReactNode } from "react";

import { composerTout, type Chiffres } from "./chiffres";
import {
  ARTICULATION_PACK_ESSENTIEL,
  ARTICULATION_PACK_PREMIUM,
  COMMUN_PACKS,
  COMPARATIF_PACKS,
  ENSEMBLE_PACKS,
  PAGE_PACKS,
  PAGE_PACK_ESSENTIEL,
  PAGE_PACK_PREMIUM,
  PASSERELLE_PACKS,
  PORTRAIT_DES_PACKS,
  PRIX_DES_PACKS,
  ROUTES_PACKS,
  TITRES_PACKS,
  TITRES_PACK_ESSENTIEL,
  TITRES_PACK_PREMIUM,
  UNITES_A_ACCORDER,
  chiffresDesPacks,
  compteRendu,
  pointDeListe,
  sansCompte,
  sansFleche,
  type ApercuDeDocument,
  type ArticulationDePack,
  type BoutonDePack,
  type CarteDeLaPageDEnsemble,
  type CarteDePack,
  type DeuxTemps,
  type LigneDeComparatif,
  type LivrableDePack,
  type QuestionDePack,
} from "./contenuPacks";
import { ID_DU_CONTENU, LIENS } from "./contenuSite";
import { chargerFormations, type FormationPublique } from "./donnees";
import { EnTeteSite } from "./EnTeteSite";
import { Bouton, BoutonPause } from "./PiecesSite";
import { PiedSite } from "./PiedSite";
import { useReveler } from "./reveler";
import {
  ancienneteSure,
  titreDOnglet,
  useAimants,
  useChargement,
  useMenu,
  usePause,
  useQuestionsStructurees,
  useTitreDePage,
  variables,
  type Chargement,
} from "./site";
// Le socle d'abord, la feuille du lot ensuite : à spécificité égale, c'est la
// page qui a le dernier mot.
import "./Site.css";
import "./Packs.css";

// ── Ce qu'une page de pack peut porter ──────────────────────────────────────

/** Le comparatif Essentiel / Premium, tel que `contenuPacks.ts` le tient. */
type Comparatif = {
  titre: string;
  corps: string;
  colonnes: { essentiel: string; premium: string };
  lignes: LigneDeComparatif[];
};

/** Le contenu d'une page de pack. Les blocs obligatoires sont ceux que les
 *  deux pages ont ; les autres sont propres à l'une des deux. L'ordre des
 *  clés est celui du rendu — celui des deux pages d'origine, fusionné. */
type ContenuDePack = {
  ouverture: { titre: string; corps: string; points: string[] };
  pourQui: { titre: string; corps: string; profils: CarteDePack[] };
  seulOuAccompagne?: {
    titre: string;
    seul: { titre: string; points: string[] };
    avecLePack: { titre: string; points: string[] };
  };
  cePlusDuPremium?: {
    titre: string;
    corps: string;
    cartes: { chiffre: string | null; titre: string; corps: string }[];
  };
  contenuDuPack: { titre: string; corps: string; livrables: LivrableDePack[] };
  formationOfferte?: { titre: string; corps: string; carte: LivrableDePack };
  processus: { titre: string; corps: string; etapes: CarteDePack[] };
  support?: { titre: string; corps: string; points: string[] };
  aQuoiSertLePack?: { titre: string; benefices: CarteDePack[] };
  apercuDesDocuments?: {
    titre: string;
    corps: string;
    documents: ApercuDeDocument[];
  };
  comparatif?: Comparatif;
  experte: { titre: string; corps: string };
  faq: { titre: string; questions: QuestionDePack[] };
  versLePremium?: { titre: string; corps: string; bouton: BoutonDePack };
  appelFinal: { titre: string; corps: string; mention: string };
};

/** Les titres coupés en deux temps : un par bloc affiché. */
type TitresDePack = Partial<Record<keyof ContenuDePack, DeuxTemps>> &
  Record<
    | "ouverture"
    | "pourQui"
    | "contenuDuPack"
    | "processus"
    | "experte"
    | "faq"
    | "appelFinal",
    DeuxTemps
  >;

type Pause = { fige: boolean; basculer: () => void };

/** Ce qui accorde un texte avant de l'afficher (voir l'en-tête). */
type Dire = (texte: string) => string;

function numero(rang: number): string {
  return String(rang + 1).padStart(2, "0");
}

// ── La formation P.O.P offerte : ce que le serveur en dit ───────────────────

/** Où en est l'appel au catalogue des formations. */
type Appel = Chargement<FormationPublique[]>["etat"];

/** Les chiffres de la Méthode P.O.P que les pages des packs citent (sa valeur,
 *  sa durée), lus dans la réponse du serveur — et l'état de l'appel, pour que
 *  la coquille observe les blocs qui changent à son arrivée.
 *
 *  Tant que la réponse n'est pas là, en cas de panne, ou si la formation n'est
 *  pas en ligne : aucun chiffre. Les phrases s'affichent alors sans leur
 *  mention (voir `chiffresDesPacks`). */
function useFormationOfferte(): { chiffres: Chiffres; appel: Appel } {
  const formations = useChargement(chargerFormations);
  return {
    chiffres: chiffresDesPacks(
      formations.etat === "recu" ? formations.donnees : null,
    ),
    appel: formations.etat,
  };
}

// ── Petites pièces ──────────────────────────────────────────────────────────

/** La pastille d'une ligne de liste. Décorative : elle double ce que le texte
 *  dit déjà, un lecteur d'écran n'a pas à l'annoncer. */
function Puce({ ton }: { ton: "oui" | "non" | "bonus" }) {
  const signe = { oui: "✓", non: "✕", bonus: "★" }[ton];
  return (
    <span className={`pak-puce pak-puce-${ton}`} aria-hidden="true">
      {signe}
    </span>
  );
}

/** Une liste à pastilles. Une ligne « BONUS » porte l'étoile et se détache. */
function Points({
  points,
  dire,
  ton = "oui",
  className = "",
  nom,
}: {
  points: string[];
  dire: Dire;
  ton?: "oui" | "non";
  className?: string;
  nom?: string;
}) {
  return (
    <ul className={`pak-points ${className}`.trim()} aria-label={nom}>
      {points.map((point) => {
        const { texte, vedette } = pointDeListe(point);
        return (
          <li key={point} className={vedette ? "pak-point-vedette" : undefined}>
            <Puce ton={vedette ? "bonus" : ton} />
            <span>{dire(texte)}</span>
          </li>
        );
      })}
    </ul>
  );
}

/** Un titre en deux temps : la fin en italique (Fraunces). */
function EnDeuxTemps({ titre, dire }: { titre: DeuxTemps; dire: Dire }) {
  return (
    <>
      {dire(titre.avant)} <span className="acc-s">{dire(titre.fin)}</span>
    </>
  );
}

/** L'introduction d'une section : surtitre, titre, puis le texte. Même
 *  habillage que sur l'accueil (`.acc-intro`, `Site.css`). */
function Entree({
  surtitre,
  titre,
  dire,
  children,
}: {
  surtitre: string;
  titre: DeuxTemps;
  dire: Dire;
  children?: ReactNode;
}) {
  return (
    <div className="acc-intro" data-reveal="">
      <div>
        <span className="acc-tag">{surtitre}</span>
        <h2>
          <EnDeuxTemps titre={titre} dire={dire} />
        </h2>
      </div>
      {children}
    </div>
  );
}

/** Le bandeau défilant et son bouton de pause. Décoratif : il ne répète que
 *  ce que la page écrit ailleurs en toutes lettres. */
function Ruban({ mots, pause }: { mots: string[]; pause: Pause }) {
  return (
    <>
      <div className="acc-ruban pak-ruban" aria-hidden="true">
        <div className="acc-ruban-piste">
          {[...mots, ...mots].map((mot, k) => (
            <span key={k}>{mot}</span>
          ))}
        </div>
      </div>
      {/* WCAG 2.2.2 : ce qui bouge en boucle peut être arrêté là où il bouge. */}
      <p className="acc-w pak-pause-rang">
        <BoutonPause fige={pause.fige} basculer={pause.basculer} />
      </p>
    </>
  );
}

// ── Le comparatif, en vrai tableau ──────────────────────────────────────────

/** Une case du comparatif. Le signe du site reste affiché ; sa lecture
 *  (« Inclus », « Non inclus », « Bonus ») est dite aux lecteurs d'écran, pour
 *  qui un tiret ou une étoile ne veulent rien dire. */
function Case({ valeur }: { valeur: string }) {
  const connu = COMPARATIF_PACKS.signes.find((s) => valeur.startsWith(s.signe));
  if (!connu) return <>{valeur}</>;
  const reste = valeur.slice(connu.signe.length).trim();
  return (
    <>
      <span className={`pak-signe pak-signe-${connu.ton}`} aria-hidden="true">
        {connu.signe}
      </span>
      <span className="pak-lu">
        {connu.lecture}
        {reste === "" ? "" : ", "}
      </span>
      {reste}
    </>
  );
}

/** Le comparatif Essentiel / Premium. Un `<table>` : ce sont des données à
 *  deux entrées, et un lecteur d'écran doit pouvoir annoncer « Business plan,
 *  Premium : 40 pages ». Sa boîte défile à l'horizontale si l'écran est trop
 *  étroit ; elle est alors nommée et focalisable, pour que le clavier puisse
 *  la faire défiler. `children` : ce qui suit le tableau. */
function SectionComparatif({
  comparatif,
  dire,
  children,
}: {
  comparatif: Comparatif;
  dire: Dire;
  children?: ReactNode;
}) {
  const legende = "pak-comparatif-legende";
  return (
    <section
      className="acc-section pak-bande"
      id={ENSEMBLE_PACKS.idDuComparatif}
    >
      <div className="acc-w">
        <Entree
          surtitre={COMPARATIF_PACKS.surtitre}
          titre={TITRES_PACKS.comparatif}
          dire={dire}
        >
          <p>{dire(comparatif.corps)}</p>
        </Entree>

        <div
          className="pak-tableau"
          role="region"
          aria-labelledby={legende}
          tabIndex={0}
          data-reveal=""
        >
          <table>
            <caption id={legende}>{COMPARATIF_PACKS.legende}</caption>
            <thead>
              <tr>
                <th scope="col">{COMPARATIF_PACKS.colonneDesCriteres}</th>
                <th scope="col">{comparatif.colonnes.essentiel}</th>
                <th scope="col">{comparatif.colonnes.premium}</th>
              </tr>
            </thead>
            <tbody>
              {comparatif.lignes.map((ligne) => (
                <tr key={ligne.critere}>
                  <th scope="row">{ligne.critere}</th>
                  <td>
                    <Case valeur={ligne.essentiel} />
                  </td>
                  <td>
                    <Case valeur={ligne.premium} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {children}
      </div>
    </section>
  );
}

// ── L'experte ───────────────────────────────────────────────────────────────

function SectionExperte({
  titre,
  corps,
  dire,
}: {
  titre: DeuxTemps;
  corps: string;
  dire: Dire;
}) {
  return (
    <section className="acc-section" id="experte">
      <div className="acc-w pak-experte">
        <div className="pak-cadre" data-reveal="">
          <div className="pak-cadre-bord">
            <img
              className="pak-portrait"
              src={PORTRAIT_DES_PACKS.adresse}
              alt={PORTRAIT_DES_PACKS.alt}
              width={PORTRAIT_DES_PACKS.largeur}
              height={PORTRAIT_DES_PACKS.hauteur}
              loading="lazy"
              decoding="async"
            />
          </div>
        </div>
        <div className="pak-experte-texte" data-reveal="">
          <span className="acc-tag">{COMMUN_PACKS.surtitreExperte}</span>
          <h2 className="acc-titre-cote">
            <EnDeuxTemps titre={titre} dire={dire} />
          </h2>
          <p className="pak-experte-corps">{dire(corps)}</p>
        </div>
      </div>
    </section>
  );
}

// ── Les autres portes : l'autre pack, les études à l'unité ──────────────────

type Porte = {
  surtitre: string;
  titre: DeuxTemps;
  corps: string;
  bouton: string;
  lien: string;
};

/** La passerelle vers les études à l'unité, sans prix. */
const PORTE_DES_ETUDES: Porte = {
  surtitre: PASSERELLE_PACKS.surtitre,
  titre: PASSERELLE_PACKS.titre,
  corps: PASSERELLE_PACKS.corps,
  bouton: PASSERELLE_PACKS.bouton,
  lien: LIENS.etudes,
};

function SectionPortes({ portes, dire }: { portes: Porte[]; dire: Dire }) {
  return (
    <section className="acc-section acc-section-suite" id="autrement">
      <div className="acc-w pak-portes">
        {portes.map((porte, k) => (
          <article
            key={porte.lien}
            className="pak-porte"
            data-reveal=""
            style={variables({ "--i": k })}
          >
            <span className="acc-tag">{porte.surtitre}</span>
            <h2>
              <EnDeuxTemps titre={porte.titre} dire={dire} />
            </h2>
            <p>{dire(porte.corps)}</p>
            <Bouton lien={porte.lien} aspect="clair" className="pak-btn">
              {porte.bouton}
            </Bouton>
          </article>
        ))}
      </div>
    </section>
  );
}

// ── La coquille : ce que les trois pages montent de la même façon ───────────

/** La barre, le contenu principal, le pied, et les crochets du socle. Le
 *  contenu reçoit l'état de la pause, pour ses boutons. */
function Coquille({
  titre,
  description,
  appel,
  children,
}: {
  titre: string;
  description: string;
  /** Où en est l'appel au catalogue des formations (voir
   *  `useFormationOfferte`). */
  appel: Appel;
  children: (pause: Pause) => ReactNode;
}) {
  const menu = useMenu();
  const pause = usePause();
  const page = useRef<HTMLDivElement>(null);

  // La clé : à l'arrivée de la réponse, quelques phrases reçoivent leur
  // chiffre, et un bloc dont la clé de liste est son texte se remonte — il
  // doit être observé à son tour, un bloc à révéler naissant effacé.
  // L'option : le mouvement réduit garde la révélation, en fondu seul (voir
  // `Site.css`).
  useReveler(page, appel, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(titreDOnglet(titre), description);
  // Les questions de la page, déclarées telles qu'elle les affiche.
  useQuestionsStructurees(page);

  return (
    // `data-formations` : où en est l'appel. Sur ces pages, une formation hors
    // ligne ou une panne ne change RIEN de visible — c'est voulu — et rien
    // d'autre ne permettrait de savoir, en test comme en diagnostic, que la
    // réponse a bien été lue.
    <div
      className={pause.fige ? "acc pak acc-fige" : "acc pak"}
      data-formations={appel}
      ref={page}
    >
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus, sinon certains navigateurs font défiler sans le déplacer. */}
      <main id={ID_DU_CONTENU} tabIndex={-1} inert={menu.ouvert}>
        {children(pause)}
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}

// ── /packs : la page d'ensemble ─────────────────────────────────────────────

/** Une carte de pack : en tête ce qu'on achète (nom, prix, accroche), puis ce
 *  qu'il contient et ce à quoi il sert, puis sa durée et ses deux boutons. */
function CarteDEnsemble({
  carte,
  prix,
  route,
  vedette,
  rang,
  dire,
}: {
  carte: CarteDeLaPageDEnsemble;
  prix: string;
  route: string;
  vedette: boolean;
  rang: number;
  dire: Dire;
}) {
  // « Tarif : » en petit, le montant en grand. Si la phrase relevée ne se
  // termine plus par le prix de la constante, elle s'affiche telle quelle.
  const libelle = carte.tarif.endsWith(prix)
    ? carte.tarif.slice(0, -prix.length)
    : null;
  const titre = `pak-carte-${rang}`;

  return (
    <article
      className={vedette ? "pak-carte pak-carte-vedette" : "pak-carte"}
      aria-labelledby={titre}
      data-reveal=""
      style={variables({ "--i": rang })}
    >
      <div className="pak-carte-tete">
        <h2 id={titre}>{carte.nom}</h2>
        {libelle === null ? (
          <p className="pak-prix">{carte.tarif}</p>
        ) : (
          <p className="pak-prix">
            <span className="pak-prix-libelle">{libelle}</span>
            <b>{prix}</b>
          </p>
        )}
        <p className="pak-carte-accroche">{dire(carte.accroche)}</p>
      </div>

      <div className="pak-carte-corps">
        <h3>{carte.contenuTitre}</h3>
        <Points points={carte.contenu} dire={dire} />
        <h3>{carte.sertATitre}</h3>
        <ul className="pak-etoiles">
          {carte.sertA.map((usage) => (
            <li key={usage}>{dire(usage)}</li>
          ))}
        </ul>
      </div>

      <div className="pak-carte-pied">
        <p className="pak-duree">{carte.duree}</p>
        <div className="pak-appels">
          <Bouton lien={carte.bouton.lien} aspect="noir" externe className="pak-btn">
            {carte.bouton.libelle}
          </Bouton>
          <Bouton lien={route} aspect="clair" className="pak-btn">
            {ENSEMBLE_PACKS.detail}
            <span className="pak-lu"> — {carte.nom}</span>
          </Bouton>
        </div>
      </div>
    </article>
  );
}

export function Packs() {
  // Le texte relevé, avec la valeur de la formation P.O.P offerte si le
  // serveur la rend ; sans elle, les phrases s'affichent sans cette mention.
  const { chiffres, appel } = useFormationOfferte();
  const p = composerTout(PAGE_PACKS, chiffres);
  const comparatif = composerTout(PAGE_PACK_PREMIUM.comparatif, chiffres);
  const dire: Dire = ancienneteSure;

  return (
    <Coquille
      titre={p.titreDeLOnglet}
      description={p.metaDescription}
      appel={appel}
    >
      {(pause) => (
        <>
          {/* ── Ouverture ──────────────────────────────────────────────── */}
          <div className="pak-ouverture pak-ouverture-ensemble">
            <div className="acc-w acc-pause-rang">
              <BoutonPause
                fige={pause.fige}
                basculer={pause.basculer}
                className="acc-pause-haut"
              />
            </div>
            <div className="acc-w pak-ouverture-grille">
              <div>
                <span className="acc-tag acc-entre">{ENSEMBLE_PACKS.surtitre}</span>
                <h1>
                  <span className="acc-ligne-titre">
                    <span>{TITRES_PACKS.ouverture.avant}</span>
                  </span>{" "}
                  <span className="acc-ligne-titre">
                    <span className="acc-s">{TITRES_PACKS.ouverture.fin}</span>
                  </span>
                </h1>
                {p.ouverture.corps.map((paragraphe, k) => (
                  <p
                    key={paragraphe}
                    className="pak-promesse acc-entre"
                    style={variables({ "--i": k + 1 })}
                  >
                    {dire(paragraphe)}
                  </p>
                ))}
              </div>
              <div>
                <div className="pak-appels acc-entre" style={variables({ "--i": 3 })}>
                  <Bouton
                    lien={`#${ENSEMBLE_PACKS.idDesPacks}`}
                    aspect="noir"
                    className="pak-btn"
                  >
                    {COMMUN_PACKS.voirLesDeuxPacks}
                  </Bouton>
                  <Bouton
                    lien={`#${ENSEMBLE_PACKS.idDuComparatif}`}
                    aspect="clair"
                    className="pak-btn"
                  >
                    {ENSEMBLE_PACKS.comparer}
                  </Bouton>
                </div>
              </div>
            </div>
          </div>

          {/* ── Les deux packs, côte à côte ────────────────────────────── */}
          <section
            className="acc-section acc-section-suite"
            id={ENSEMBLE_PACKS.idDesPacks}
            aria-label={ENSEMBLE_PACKS.nomDesPacks}
          >
            <div className="acc-w pak-duo">
              <CarteDEnsemble
                carte={p.packEssentiel}
                prix={PRIX_DES_PACKS.essentiel}
                route={ROUTES_PACKS.essentiel}
                vedette={false}
                rang={0}
                dire={dire}
              />
              <CarteDEnsemble
                carte={p.packPremium}
                prix={PRIX_DES_PACKS.premium}
                route={ROUTES_PACKS.premium}
                vedette
                rang={1}
                dire={dire}
              />
            </div>
          </section>

          <Ruban mots={ENSEMBLE_PACKS.ruban} pause={pause} />

          {/* ── Comparatif ─────────────────────────────────────────────── */}
          <SectionComparatif comparatif={comparatif} dire={dire} />

          {/* ── Une experte, pas un junior ─────────────────────────────── */}
          <SectionExperte
            titre={TITRES_PACKS.experte}
            corps={PAGE_PACK_ESSENTIEL.experte.corps}
            dire={dire}
          />

          {/* ── Passerelle : les études à l'unité ──────────────────────── */}
          <SectionPortes portes={[PORTE_DES_ETUDES]} dire={dire} />

          {/* ── Appel final ────────────────────────────────────────────── */}
          <section className="acc-fin pak-fin" id="commander">
            <div className="acc-w">
              <h2>
                <EnDeuxTemps titre={ENSEMBLE_PACKS.fin.titre} dire={dire} />
              </h2>
              <p className="acc-fin-corps">{ENSEMBLE_PACKS.fin.corps}</p>
              <div className="pak-appels pak-appels-centre">
                <Bouton lien={LIENS.appel} aspect="noir" externe className="pak-btn">
                  {COMMUN_PACKS.appelGratuit}
                </Bouton>
                <Bouton
                  lien={p.packEssentiel.bouton.lien}
                  aspect="clair"
                  externe
                  className="pak-btn"
                >
                  {p.packEssentiel.bouton.libelle}
                </Bouton>
                <Bouton
                  lien={p.packPremium.bouton.lien}
                  aspect="clair"
                  externe
                  className="pak-btn"
                >
                  {p.packPremium.bouton.libelle}
                </Bouton>
              </div>
            </div>
          </section>
        </>
      )}
    </Coquille>
  );
}

// ── /packs/essentiel et /packs/premium : les pages jumelles ─────────────────

function PageDePack({
  contenu,
  titres,
  articulation,
  versLAutre,
}: {
  contenu: ContenuDePack;
  titres: TitresDePack;
  articulation: ArticulationDePack;
  /** Le renvoi vers l'autre pack : sa page, et l'intitulé du lien posé sous
   *  le comparatif quand la page en a un. */
  versLAutre: { route: string; libelle: string };
}) {
  // Le texte relevé, avec la valeur et la durée de la formation P.O.P offerte
  // si le serveur les rend ; sans elles, les phrases s'en passent.
  const { chiffres, appel } = useFormationOfferte();
  const c = composerTout(contenu, chiffres);
  const s = articulation.surtitres;
  const etapes = c.processus.etapes;

  // Les accords (voir l'en-tête). `dire` vaut pour toute la page ;
  // `direLesEtapes` n'accorde le nombre d'étapes que là où il est annoncé.
  const dire: Dire = (texte) =>
    ancienneteSure(
      articulation.compteDeLivrablesFiable
        ? texte
        : sansCompte(texte, UNITES_A_ACCORDER.livrables),
    );
  const direLesEtapes: Dire = (texte) =>
    compteRendu(dire(texte), UNITES_A_ACCORDER.etapes, etapes.length);

  const portes: Porte[] = [];
  if (c.versLePremium && titres.versLePremium) {
    portes.push({
      surtitre: s.autrePack,
      titre: titres.versLePremium,
      corps: c.versLePremium.corps,
      bouton: sansFleche(c.versLePremium.bouton.libelle),
      // Sur le site, ce bouton pointe vers « # » : il mène ici à la page de
      // l'autre pack.
      lien: versLAutre.route,
    });
  }
  portes.push(PORTE_DES_ETUDES);

  return (
    <Coquille
      titre={articulation.titreDeLOnglet}
      description={c.ouverture.corps}
      appel={appel}
    >
      {(pause) => (
        <>
          {/* ── Ouverture : le texte, et l'encart du prix ──────────────── */}
          <div className="pak-ouverture">
            <div className="acc-w acc-pause-rang">
              <BoutonPause
                fige={pause.fige}
                basculer={pause.basculer}
                className="acc-pause-haut"
              />
            </div>
            <div className="acc-w pak-ouverture-grille">
              <div>
                <span className="acc-tag acc-entre">{articulation.surtitre}</span>
                <h1>
                  <span className="acc-ligne-titre">
                    <span>{titres.ouverture.avant}</span>
                  </span>{" "}
                  <span className="acc-ligne-titre">
                    <span className="acc-s">{titres.ouverture.fin}</span>
                  </span>
                </h1>
                <p className="pak-promesse acc-entre" style={variables({ "--i": 1 })}>
                  {dire(c.ouverture.corps)}
                </p>
                <div className="pak-appels acc-entre" style={variables({ "--i": 3 })}>
                  <Bouton
                    lien={articulation.commande.lien}
                    aspect="noir"
                    externe
                    className="pak-btn"
                  >
                    {articulation.commande.libelle}
                  </Bouton>
                  <Bouton lien={LIENS.appel} aspect="clair" externe className="pak-btn">
                    {COMMUN_PACKS.appelGratuit}
                  </Bouton>
                </div>
                <p className="pak-retour acc-entre" style={variables({ "--i": 4 })}>
                  <a href={ROUTES_PACKS.ensemble}>{COMMUN_PACKS.voirLesDeuxPacks}</a>
                </p>
              </div>

              <div className="pak-encart acc-entre" style={variables({ "--i": 2 })}>
                <div className="pak-encart-tete">
                  <p className="pak-prix">
                    <span className="pak-prix-libelle">
                      {COMMUN_PACKS.libelleDuPrix}
                    </span>{" "}
                    <b>{articulation.prix}</b>
                  </p>
                  <p className="pak-duree">{articulation.duree}</p>
                </div>
                <Points
                  points={c.ouverture.points}
                  dire={dire}
                  className="pak-encart-points"
                  nom={COMMUN_PACKS.nomDesPoints}
                />
              </div>
            </div>
          </div>

          <Ruban
            mots={c.ouverture.points.map((point) => pointDeListe(point).texte)}
            pause={pause}
          />

          {/* ── Pour qui ───────────────────────────────────────────────── */}
          <section className="acc-section pak-section-apres-ruban" id="pour-qui">
            <div className="acc-w">
              <Entree surtitre={s.pourQui} titre={titres.pourQui} dire={dire}>
                <p>{dire(c.pourQui.corps)}</p>
              </Entree>
              <ul className="pak-profils">
                {c.pourQui.profils.map((profil, k) => (
                  <li key={profil.titre} data-reveal="" style={variables({ "--i": k })}>
                    <span className="pak-ornement" aria-hidden="true">
                      ✦
                    </span>
                    <h3>{profil.titre}</h3>
                    <p>{dire(profil.corps)}</p>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          {/* ── Seul, ou avec le pack (Essentiel) ──────────────────────── */}
          {c.seulOuAccompagne && titres.seulOuAccompagne && (
            <section className="acc-section pak-bande" id="seul-ou-accompagne">
              <div className="acc-w">
                <Entree
                  surtitre={s.seulOuAccompagne}
                  titre={titres.seulOuAccompagne}
                  dire={dire}
                />
                <div className="pak-versus">
                  <article className="pak-versus-colonne pak-versus-evite" data-reveal="">
                    <small>{s.eviter}</small>
                    <h3>{c.seulOuAccompagne.seul.titre}</h3>
                    <Points
                      points={c.seulOuAccompagne.seul.points}
                      dire={dire}
                      ton="non"
                    />
                  </article>
                  <article
                    className="pak-versus-colonne pak-versus-recu"
                    data-reveal=""
                    style={variables({ "--i": 1 })}
                  >
                    <small>{s.obtenir}</small>
                    <h3>{c.seulOuAccompagne.avecLePack.titre}</h3>
                    <Points points={c.seulOuAccompagne.avecLePack.points} dire={dire} />
                  </article>
                </div>
              </div>
            </section>
          )}

          {/* ── Ce que le Premium ajoute (Premium) ─────────────────────── */}
          {c.cePlusDuPremium && titres.cePlusDuPremium && (
            <section className="acc-section pak-bande" id="en-plus">
              <div className="acc-w">
                <Entree
                  surtitre={s.cePlusDuPremium}
                  titre={titres.cePlusDuPremium}
                  dire={dire}
                >
                  <p>{dire(c.cePlusDuPremium.corps)}</p>
                </Entree>
                <ul className="pak-plus">
                  {c.cePlusDuPremium.cartes.map((carte, k) => (
                    <li key={carte.titre} data-reveal="" style={variables({ "--i": k })}>
                      {/* Le chiffre de la carte n'a pas été relevé (`null`) :
                          la carte s'affiche alors avec un simple ornement,
                          sans rien inventer à sa place. */}
                      {carte.chiffre === null ? (
                        <span className="pak-ornement" aria-hidden="true">
                          ✦
                        </span>
                      ) : (
                        <span className="pak-plus-chiffre">{carte.chiffre}</span>
                      )}
                      <h3>{carte.titre}</h3>
                      <p>{dire(carte.corps)}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          {/* ── Contenu du pack ────────────────────────────────────────── */}
          <section className="acc-section" id="contenu">
            <div className="acc-w">
              <Entree
                surtitre={s.contenuDuPack}
                titre={titres.contenuDuPack}
                dire={dire}
              >
                <p>{dire(c.contenuDuPack.corps)}</p>
              </Entree>
              <ul className="pak-livrables">
                {/* La clé est le RANG, pas le titre : celui de la formation
                    offerte reçoit sa valeur à l'arrivée de la réponse, et une
                    clé qui change remonterait la carte — donc la révélerait
                    une seconde fois. */}
                {c.contenuDuPack.livrables.map((livrable, k) => (
                  <li key={k} data-reveal="">
                    <h3>{dire(livrable.titre)}</h3>
                    <p>{dire(livrable.corps)}</p>
                    <ul className="pak-etoiles">
                      {livrable.points.map((point) => (
                        <li key={point}>{dire(point)}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          {/* ── La formation offerte (Premium) ─────────────────────────── */}
          {c.formationOfferte && titres.formationOfferte && (
            <section className="acc-section acc-section-suite" id="formation-offerte">
              <div className="acc-w">
                <div className="pak-formation" data-reveal="">
                  <div>
                    <span className="acc-tag">{s.formationOfferte}</span>
                    <h2 className="acc-titre-cote">
                      <EnDeuxTemps titre={titres.formationOfferte} dire={dire} />
                    </h2>
                    <p>{dire(c.formationOfferte.corps)}</p>
                  </div>
                  <div className="pak-formation-carte">
                    <h3>{c.formationOfferte.carte.titre}</h3>
                    <p>{dire(c.formationOfferte.carte.corps)}</p>
                    <Points points={c.formationOfferte.carte.points} dire={dire} />
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ── Le processus, étape par étape ──────────────────────────── */}
          <section className="acc-section acc-section-suite" id="processus">
            <div className="acc-w">
              <Entree
                surtitre={s.processus}
                titre={titres.processus}
                dire={direLesEtapes}
              >
                <p>{direLesEtapes(c.processus.corps)}</p>
              </Entree>
              {/* Une liste ORDONNÉE : la numérotation encode une vraie
                  séquence, de la commande au suivi. */}
              <ol className="pak-etapes" data-reveal="">
                {etapes.map((etape, k) => (
                  <li key={etape.titre}>
                    <span className="pak-etape-numero" aria-hidden="true">
                      {numero(k)}
                    </span>
                    <div>
                      <h3>{etape.titre}</h3>
                      <p>{dire(etape.corps)}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>

          {/* ── Le support après la livraison (Essentiel) ──────────────── */}
          {c.support && titres.support && (
            <section className="acc-section acc-section-suite" id="support">
              <div className="acc-w pak-support">
                <div data-reveal="">
                  <span className="acc-tag">{s.support}</span>
                  <h2 className="acc-titre-cote">
                    <EnDeuxTemps titre={titres.support} dire={dire} />
                  </h2>
                  <p>{dire(c.support.corps)}</p>
                </div>
                <div className="pak-support-points" data-reveal="">
                  <Points points={c.support.points} dire={dire} />
                </div>
              </div>
            </section>
          )}

          {/* ── À quoi sert le pack (Essentiel) ────────────────────────── */}
          {c.aQuoiSertLePack && titres.aQuoiSertLePack && (
            <section className="acc-section acc-section-suite" id="a-quoi-sert-le-pack">
              <div className="acc-w">
                <Entree
                  surtitre={s.aQuoiSertLePack}
                  titre={titres.aQuoiSertLePack}
                  dire={dire}
                />
                <ul className="pak-benefices">
                  {c.aQuoiSertLePack.benefices.map((benefice, k) => (
                    <li key={benefice.titre} data-reveal="" style={variables({ "--i": k })}>
                      <span className="pak-benefice-numero" aria-hidden="true">
                        {numero(k)}
                      </span>
                      <h3>{benefice.titre}</h3>
                      <p>{dire(benefice.corps)}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          {/* ── L'aperçu des documents (Essentiel) ─────────────────────── */}
          {c.apercuDesDocuments && titres.apercuDesDocuments && (
            <section className="acc-section pak-bande" id="apercu">
              <div className="acc-w">
                <Entree
                  surtitre={s.apercuDesDocuments}
                  titre={titres.apercuDesDocuments}
                  dire={dire}
                >
                  <p>{dire(c.apercuDesDocuments.corps)}</p>
                </Entree>
                <ul className="pak-documents">
                  {c.apercuDesDocuments.documents.map((apercu, k) => (
                    <li key={apercu.etiquette} data-reveal="" style={variables({ "--i": k })}>
                      {/* La vignette est dessinée, comme sur le site : une
                          page de garde, son titre et son volume. */}
                      <div className="pak-vignette">
                        <div className="pak-vignette-page">
                          <strong>{apercu.vignette.titre}</strong>
                          <span className="pak-vignette-volume">
                            {apercu.vignette.volume}
                          </span>
                        </div>
                      </div>
                      <small>{apercu.etiquette}</small>
                      <h3>{apercu.titre}</h3>
                      <p>{dire(apercu.corps)}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          {/* ── Le comparatif (Premium) ────────────────────────────────── */}
          {c.comparatif && (
            <SectionComparatif comparatif={c.comparatif} dire={dire}>
              <p className="pak-apres-tableau" data-reveal="">
                <Bouton lien={versLAutre.route} aspect="clair" className="pak-btn">
                  {versLAutre.libelle}
                </Bouton>
              </p>
            </SectionComparatif>
          )}

          {/* ── L'experte ──────────────────────────────────────────────── */}
          <SectionExperte titre={titres.experte} corps={c.experte.corps} dire={dire} />

          {/* ── Les questions ──────────────────────────────────────────── */}
          <section className="acc-section acc-section-suite" id="questions">
            <div className="acc-w acc-faq">
              <div data-reveal="">
                <span className="acc-tag">{COMMUN_PACKS.surtitreFaq}</span>
                <h2 className="acc-titre-cote">
                  <EnDeuxTemps titre={titres.faq} dire={dire} />
                </h2>
              </div>
              <div data-reveal="">
                {c.faq.questions.map((question, k) => (
                  <details key={question.question} open={k === 0}>
                    <summary>{question.question}</summary>
                    <p>{dire(question.reponse)}</p>
                  </details>
                ))}
              </div>
            </div>
          </section>

          {/* ── L'autre pack, et les études à l'unité ──────────────────── */}
          <SectionPortes portes={portes} dire={dire} />

          {/* ── Appel final ────────────────────────────────────────────── */}
          <section className="acc-fin pak-fin" id="commander">
            <div className="acc-w">
              <h2>
                <EnDeuxTemps titre={titres.appelFinal} dire={dire} />
              </h2>
              <p className="acc-fin-corps">{dire(c.appelFinal.corps)}</p>
              <div className="pak-appels pak-appels-centre">
                <Bouton
                  lien={articulation.commande.lien}
                  aspect="noir"
                  externe
                  className="pak-btn"
                >
                  {articulation.commande.libelle}
                </Bouton>
                <Bouton lien={LIENS.appel} aspect="clair" externe className="pak-btn">
                  {COMMUN_PACKS.appelGratuit}
                </Bouton>
              </div>
              <p className="pak-fin-mention">{c.appelFinal.mention}</p>
            </div>
          </section>
        </>
      )}
    </Coquille>
  );
}

export function PackEssentiel() {
  return (
    <PageDePack
      contenu={PAGE_PACK_ESSENTIEL}
      titres={TITRES_PACK_ESSENTIEL}
      articulation={ARTICULATION_PACK_ESSENTIEL}
      versLAutre={{
        route: ROUTES_PACKS.premium,
        libelle: COMPARATIF_PACKS.versLePremium,
      }}
    />
  );
}

export function PackPremium() {
  return (
    <PageDePack
      contenu={PAGE_PACK_PREMIUM}
      titres={TITRES_PACK_PREMIUM}
      articulation={ARTICULATION_PACK_PREMIUM}
      versLAutre={{
        route: ROUTES_PACKS.essentiel,
        libelle: COMPARATIF_PACKS.versLEssentiel,
      }}
    />
  );
}
