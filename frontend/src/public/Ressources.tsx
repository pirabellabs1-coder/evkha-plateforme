/** Trois pages reprises du site de la cliente, dans le langage visuel de
 * l'accueil : la boîte à outils (`/boite-a-outils`), le contact (`/contact`)
 * et le partenaire Swapn (`/swapn`). Les deux pages du blog sont dans
 * `Blog.tsx`, qui réutilise le cadre, le titre et la fin d'ici ; les cinq
 * partagent une feuille, `Ressources.css` (classes `res-`).
 *
 * ## D'où vient le texte
 *
 * De `contenuRessources.ts` : le RELEVÉ du site (`BOITE_A_OUTILS`, `CONTACT`,
 * `SWAPN`, `FORMULAIRES`, `COORDONNEES`), au vouvoiement (`auVous`), et ce que
 * la nouvelle forme AJOUTE (`PAGE_BOITE_A_OUTILS`, `PAGE_CONTACT`,
 * `PAGE_SWAPN`). Rien n'est écrit dans ce fichier (règle 5).
 *
 * ## Aucun formulaire
 *
 * Le site en portait quatre sur ces pages (checklist, lexique, contact, mise
 * en relation). La plateforme n'a pas de service pour recevoir un message ni
 * envoyer un document, et un formulaire qui n'envoie rien est interdit. Chaque
 * formulaire est remplacé par le moyen qui marche : un lien `mailto:` vers
 * l'adresse de contact, objet prérempli (`courrielAvecObjet`), et le lien de
 * rendez-vous.
 *
 * Et aucun téléchargement : les deux documents de la boîte à outils se
 * DEMANDENT par courriel. Le texte relevé dit « Téléchargez… » et « à
 * télécharger » ; la boîte à outils l'affiche donc par `dire`, qui passe au
 * vous ET remplace la promesse de téléchargement par ce que la page fait —
 * « à recevoir par e-mail » (`contenuRessources.sansTelechargement`, retouche
 * d'affichage : le relevé n'est pas touché).
 *
 * ## Ces pages sont des portes d'entrée gratuites
 *
 * Chacune se termine par UNE passerelle vers l'étape payante la plus proche
 * (`Passage`), sans prix : aucun montant n'est écrit ici. Le seul qui
 * s'affiche est le « 0 € » de l'offre de SWAPN, lu dans le relevé et présenté
 * comme l'offre du partenaire, pas comme un tarif d'EVKHA.
 *
 * ## Rien ne boucle
 *
 * Ces pages n'ont ni ruban ni mouvement en boucle : elles ne portent donc pas
 * de bouton de pause. Elles ne chargent rien non plus — pas de région
 * d'alerte, qui n'aurait jamais rien à annoncer. L'apparition des blocs au
 * défilement suit la politique du socle : sous mouvement réduit, un fondu
 * seul (`Site.css`).
 */
import { useRef, type ReactNode, type RefObject } from "react";

import { adresseDeLArticle, SLUG_IDEE_BUSINESS_VIABLE } from "./contenuBlog";
import {
  auVous,
  BOITE_A_OUTILS,
  CONTACT,
  COORDONNEES,
  courrielAvecObjet,
  FORMULAIRES,
  PAGE_BOITE_A_OUTILS,
  PAGE_CONTACT,
  PAGE_SWAPN,
  sansTelechargement,
  SWAPN,
  type Passerelle,
  type Ressource,
  type Texte,
} from "./contenuRessources";
import { ID_DU_CONTENU } from "./contenuSite";
import { EnTeteSite } from "./EnTeteSite";
import { Bouton } from "./PiecesSite";
import { PiedSite } from "./PiedSite";
import { useReveler } from "./reveler";
import { titreDOnglet, useAimants, useMenu, useTitreDePage, variables } from "./site";
// Le socle d'abord, la feuille du lot ensuite : à spécificité égale, c'est la
// page qui a le dernier mot.
import "./Site.css";
import "./Ressources.css";

// ── Les pièces que les cinq pages partagent ─────────────────────────────────

/** Le cadre d'une page : la barre, le contenu principal, le pied. `racine`
 *  est la référence que la page passe aussi à ses crochets de révélation et
 *  de boutons aimantés. Le menu ouvert rend inerte ce qui est derrière lui. */
export function CadreDePage({
  racine,
  classe,
  children,
}: {
  racine: RefObject<HTMLDivElement | null>;
  /** La classe propre à la page, à côté de `acc res`. */
  classe: string;
  children: ReactNode;
}) {
  const menu = useMenu();
  return (
    <div className={`acc res ${classe}`} ref={racine}>
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

/** Le titre d'une page, en deux lignes qui montent derrière un masque ; la
 *  seconde en italique (habillage du socle, `.acc-ligne-titre`). */
export function TitreDOuverture({ titre }: { titre: { avant: string; fin: string } }) {
  return (
    <h1>
      <span className="acc-ligne-titre">
        <span>{titre.avant}</span>
      </span>{" "}
      <span className="acc-ligne-titre">
        <span className="acc-s">{titre.fin}</span>
      </span>
    </h1>
  );
}

/** La fin dorée d'une page : UNE passerelle vers l'étape payante la plus
 *  proche. Le pied, doré lui aussi, la prolonge. */
export function Passage({ passerelle }: { passerelle: Passerelle }) {
  return (
    <section className="acc-fin res-fin" aria-labelledby="res-fin-titre">
      <div className="acc-w">
        <h2 id="res-fin-titre">
          {passerelle.titre.avant}{" "}
          <span className="acc-s">{passerelle.titre.fin}</span>
        </h2>
        <p className="acc-fin-corps">{passerelle.corps}</p>
        <Bouton lien={passerelle.bouton.lien} aspect="noir" className="res-bouton-souple">
          {passerelle.bouton.libelle}
        </Bouton>
      </div>
    </section>
  );
}

function numero(rang: number): string {
  return String(rang + 1).padStart(2, "0");
}

/** « Documents pratiques : modèles, guides… » : ce qui précède les deux-points
 *  passe en gras. Le texte n'est pas retouché — mis bout à bout, les deux
 *  morceaux redonnent la phrase relevée. */
function enDeux(point: string): { avant: string; suite: string } {
  const coupe = point.indexOf(" : ");
  return coupe === -1
    ? { avant: "", suite: point }
    : { avant: point.slice(0, coupe), suite: point.slice(coupe) };
}

// ── La boîte à outils ───────────────────────────────────────────────────────

/** Ce que la boîte à outils AFFICHE d'un bloc relevé : au vous, et sans
 *  promesse de téléchargement — la page envoie par courriel. */
function dire(bloc: Texte): string {
  return sansTelechargement(auVous(bloc));
}

/** Une ressource : à gauche ce qu'elle est, à droite ce qu'elle apporte, et
 *  SOUS le texte le moyen de l'obtenir — le texte relevé dit « ci-dessous ».
 *
 *  Un document se demande par courriel : la plateforme ne sait pas l'envoyer,
 *  EVKHA répond avec le fichier. L'article se lit sur le blog. */
function CarteDeRessource({ ressource, rang }: { ressource: Ressource; rang: number }) {
  const a = PAGE_BOITE_A_OUTILS;
  const titre = `res-ressource-${rang + 1}`;
  const nom = dire(ressource.titre);

  return (
    <li>
      <article
        className={`res-ressource res-ressource-${ressource.nature}`}
        aria-labelledby={titre}
        data-reveal=""
      >
        <div className="res-ressource-tete">
          <span className="res-numero" aria-hidden="true">
            {numero(rang)}
          </span>
          <small className="res-etiquette">{a.natures[ressource.nature]}</small>
          {ressource.surtitre && (
            <p className="res-ressource-surtitre">{dire(ressource.surtitre)}</p>
          )}
          <h3 id={titre}>{nom}</h3>
        </div>

        <div className="res-ressource-corps">
          {ressource.paragraphes.map((paragraphe) => (
            <p key={paragraphe.texte}>{dire(paragraphe)}</p>
          ))}

          <div className="res-ressource-action">
            {ressource.formulaire && (
              <>
                <p className="res-ressource-document">
                  {FORMULAIRES[ressource.formulaire].titre.map((ligne) => (
                    <span key={ligne.texte}>{dire(ligne)} </span>
                  ))}
                </p>
                <Bouton
                  lien={courrielAvecObjet(a.objets[ressource.formulaire])}
                  aspect="noir"
                  className="res-bouton-souple"
                >
                  <span>
                    {a.recevoir}
                    {/* Deux boutons au même libellé sur la page : le nom de
                        la ressource les distingue pour un lecteur d'écran. */}
                    <span className="res-invisible"> : {nom}</span>
                  </span>
                </Bouton>
              </>
            )}
            {ressource.nature === "article" && ressource.bouton && (
              <Bouton
                lien={adresseDeLArticle(SLUG_IDEE_BUSINESS_VIABLE)}
                aspect="noir"
                className="res-bouton-souple"
              >
                {ressource.bouton.libelle}
              </Bouton>
            )}
          </div>
        </div>
      </article>
    </li>
  );
}

export function BoiteAOutils() {
  const page = useRef<HTMLDivElement>(null);
  const b = BOITE_A_OUTILS;
  const a = PAGE_BOITE_A_OUTILS;

  useReveler(page, undefined, { memeEnMouvementReduit: true });
  useAimants(page);
  // L'ouverture relevée annonce « des documents à télécharger » : affichée,
  // elle dit ce que la page fait.
  const chapeau = sansTelechargement(b.ouverture.corps);

  useTitreDePage(
    titreDOnglet(b.entete.titreOnglet ? dire(b.entete.titreOnglet) : b.ouverture.titre),
    b.entete.description ? dire(b.entete.description) : chapeau,
  );

  return (
    <CadreDePage racine={page} classe="res-outils">
      {/* ── Ouverture : la promesse, et ce que la page contient ─────────── */}
      <div className="res-ouverture">
        <div className="acc-w res-ouverture-grille">
          <div>
            <span className="acc-tag acc-entre">{a.surtitre}</span>
            <TitreDOuverture titre={a.titre} />
            <p className="res-chapeau acc-entre" style={variables({ "--i": 1 })}>
              {chapeau}
            </p>
          </div>

          <section
            className="res-decouvrir acc-entre"
            aria-labelledby="res-decouvrir-titre"
            style={variables({ "--i": 2 })}
          >
            <h2 id="res-decouvrir-titre">{b.decouvrir.titre}</h2>
            <ul>
              {b.decouvrir.points.map((point, k) => {
                const { avant, suite } = enDeux(point);
                return (
                  <li key={point}>
                    <span className="res-decouvrir-numero" aria-hidden="true">
                      {numero(k)}
                    </span>
                    <span>
                      {avant !== "" && <strong>{avant}</strong>}
                      {suite}
                    </span>
                  </li>
                );
              })}
            </ul>
            <p>{b.decouvrir.suite}</p>
          </section>
        </div>
      </div>

      {/* ── Les trois ressources ────────────────────────────────────────── */}
      <section className="acc-section acc-section-suite" id="ressources">
        <div className="acc-w">
          <div className="acc-intro" data-reveal="">
            <div>
              <span className="acc-tag">{a.surtitreDesRessources}</span>
              <h2>
                {a.titreDesRessources.avant}{" "}
                <span className="acc-s">{a.titreDesRessources.fin}</span>
              </h2>
            </div>
          </div>

          <ol className="res-ressources">
            {b.ressources.map((ressource, k) => (
              <CarteDeRessource key={ressource.titre.texte} ressource={ressource} rang={k} />
            ))}
          </ol>
        </div>
      </section>

      <Passage passerelle={a.passerelle} />
    </CadreDePage>
  );
}

// ── Le contact ──────────────────────────────────────────────────────────────

/** Les réseaux relevés qui ont une adresse. Typés large : la constante est
 *  figée (`as const`), et une comparaison à la chaîne vide n'y aurait pas de
 *  sens pour le compilateur. */
const RESEAUX: readonly { libelle: string; lien: string }[] = COORDONNEES.reseaux;

export function Contact() {
  const page = useRef<HTMLDivElement>(null);
  const a = PAGE_CONTACT;
  const reseaux = RESEAUX.filter((reseau) => reseau.lien !== "");
  // « Un besoin d'informations? » : la première ligne du titre que le site
  // posait au-dessus de son formulaire. La seconde est le délai de réponse,
  // lu dans `COORDONNEES`.
  const [question] = FORMULAIRES.contact.titre;

  useReveler(page, undefined, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(titreDOnglet(a.titreOnglet), a.description);

  return (
    <CadreDePage racine={page} classe="res-contact">
      {/* ── Ouverture : l'accroche et le délai de réponse ───────────────── */}
      <div className="res-ouverture res-ouverture-centree">
        <div className="acc-w">
          <span className="acc-tag acc-entre">{a.surtitre}</span>
          <TitreDOuverture titre={a.titre} />
          <p className="res-chapeau acc-entre" style={variables({ "--i": 1 })}>
            {CONTACT.accroche.corps}
          </p>
          <p className="res-delai acc-entre" style={variables({ "--i": 2 })}>
            {COORDONNEES.delaiDeReponse.dansLaDescription}
          </p>
        </div>
      </div>

      {/* ── Les moyens de joindre EVKHA ─────────────────────────────────── */}
      <section className="acc-section acc-section-suite" id="nous-joindre">
        <div className="acc-w">
          <div className="acc-intro" data-reveal="">
            <div>
              <span className="acc-tag">{a.surtitreDesMoyens}</span>
              {question && <h2>{auVous(question)}</h2>}
            </div>
          </div>

          <div className="res-moyens">
            <article className="res-moyen res-moyen-fort" data-reveal="">
              <small className="res-etiquette">{a.moyens.ecrire.surtitre}</small>
              <h3>{a.moyens.ecrire.titre}</h3>
              <p>{COORDONNEES.delaiDeReponse.surLaPage}</p>
              {/* L'adresse en toutes lettres : qui n'a pas de messagerie
                  réglée sur son appareil peut la recopier. */}
              <p className="res-adresse">{COORDONNEES.courriel}</p>
              <Bouton
                lien={courrielAvecObjet(a.moyens.ecrire.objet)}
                aspect="or"
                className="res-moyen-bouton res-bouton-souple"
              >
                {a.moyens.ecrire.bouton}
              </Bouton>
            </article>

            <article
              className="res-moyen"
              data-reveal=""
              style={variables({ "--i": 1 })}
            >
              <small className="res-etiquette">{a.moyens.rendezVous.surtitre}</small>
              <h3>{a.moyens.rendezVous.titre}</h3>
              <p>{a.moyens.rendezVous.corps}</p>
              <Bouton
                lien={COORDONNEES.rendezVous}
                aspect="noir"
                externe
                className="res-moyen-bouton res-bouton-souple"
              >
                {a.moyens.rendezVous.bouton}
              </Bouton>
            </article>

            {reseaux.length > 0 && (
              <article
                className="res-moyen"
                data-reveal=""
                style={variables({ "--i": 2 })}
              >
                <small className="res-etiquette">{a.moyens.reseaux.surtitre}</small>
                <h3>{a.moyens.reseaux.titre}</h3>
                <p>{a.moyens.reseaux.corps}</p>
                <ul className="res-reseaux">
                  {reseaux.map((reseau) => (
                    <li key={reseau.lien}>
                      <a href={reseau.lien} rel="noopener">
                        {reseau.libelle}
                      </a>
                    </li>
                  ))}
                </ul>
              </article>
            )}
          </div>
        </div>
      </section>

      {/* ── Pour quoi nous écrire : la bonne page, avant le message ─────── */}
      <section className="acc-section acc-section-suite" id="orientation">
        <div className="acc-w res-aide">
          <div data-reveal="">
            <span className="acc-tag">{a.aide.surtitre}</span>
            <h2 className="acc-titre-cote">
              {a.aide.titre.avant} <span className="acc-s">{a.aide.titre.fin}</span>
            </h2>
            <p>{a.aide.corps}</p>
          </div>
          <ul className="res-orientations" data-reveal="">
            {a.aide.orientations.map((orientation) => (
              <li key={orientation.lien}>
                <a href={orientation.lien}>
                  <span className="res-orientation-texte">
                    <strong>{orientation.titre}</strong>{" "}
                    <span>{orientation.corps}</span>
                  </span>
                  <span className="res-fleche" aria-hidden="true">
                    →
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Passage passerelle={a.passerelle} />
    </CadreDePage>
  );
}

// ── Le partenaire Swapn ─────────────────────────────────────────────────────

/** Le libellé d'un champ du formulaire relevé, par son nom. Le formulaire
 *  n'est pas rendu ; deux de ses libellés sont des PHRASES adressées au
 *  visiteur, que la page garde. */
function libelleDuChamp(nom: string): string | null {
  return FORMULAIRES.swapn.champs.find((champ) => champ.nom === nom)?.libelle ?? null;
}

export function Swapn() {
  const page = useRef<HTMLDivElement>(null);
  const a = PAGE_SWAPN;
  const offre = SWAPN.texteLuDansLeVisuel;
  const lienDeMiseEnRelation = courrielAvecObjet(a.relation.objet);
  const demande = libelleDuChamp("demande");
  const promesse = libelleDuChamp("message");

  useReveler(page, undefined, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(
    titreDOnglet(
      SWAPN.entete.propose?.titreOnglet ?? SWAPN.entete.titreOnglet?.texte ?? a.surtitre,
    ),
    SWAPN.entete.propose?.description ?? SWAPN.entete.description?.texte ?? "",
  );

  return (
    <CadreDePage racine={page} classe="res-swapn">
      {/* ── Ouverture : le titre, le logo, la mise en relation ──────────── */}
      <div className="res-ouverture">
        <div className="acc-w res-swapn-grille">
          <div>
            <span className="acc-tag acc-entre">{a.surtitre}</span>
            <TitreDOuverture titre={a.titre} />
            <div className="res-appels acc-entre" style={variables({ "--i": 1 })}>
              <Bouton lien={lienDeMiseEnRelation} aspect="noir" className="res-bouton-souple">
                {a.relation.bouton}
              </Bouton>
            </div>
          </div>

          {/* La plaque fixe la place du logo : ses attributs donnent le
              ratio, la feuille la taille — rien ne saute au chargement. */}
          <div className="res-logo-plaque acc-entre" style={variables({ "--i": 2 })}>
            <div className="res-logo-carte">
              <img
                className="res-logo"
                src={a.logo.src}
                alt={a.logo.alt}
                width={a.logo.largeur}
                height={a.logo.hauteur}
                decoding="async"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── L'offre DU PARTENAIRE, attribuée ────────────────────────────── */}
      <section className="acc-section acc-section-suite" id="offre">
        <div className="acc-w">
          <div className="acc-intro" data-reveal="">
            <div>
              <span className="acc-tag">{a.offre.surtitre}</span>
              <h2>
                {a.offre.titre.avant} <span className="acc-s">{a.offre.titre.fin}</span>
              </h2>
            </div>
            <p>{a.offre.continuite}</p>
          </div>

          {/* Une figure et sa légende : les mots sont ceux de SWAPN, lus sur
              son visuel ; la légende dit à qui ils engagent. */}
          <figure className="res-offre" data-reveal="">
            <div className="res-offre-corps">
              <p className="res-offre-selon">{a.offre.attribution}</p>
              <p className="res-offre-accroche">{offre.accroche}</p>
              <p className="res-offre-mention">{offre.mention}</p>
              <ul className="res-offre-ligne">
                {offre.offre.map((mot) => (
                  <li key={mot}>{mot}</li>
                ))}
              </ul>
            </div>
            <ul className="res-arguments">
              {offre.arguments.map((argument) => (
                <li key={argument.titre}>
                  <h3>{argument.titre}</h3>
                  <p>{argument.corps}</p>
                </li>
              ))}
            </ul>
            <figcaption>{a.offre.source}</figcaption>
          </figure>
        </div>
      </section>

      {/* ── La mise en relation : un courriel à EVKHA ───────────────────── */}
      <section className="acc-section acc-section-suite" id="mise-en-relation">
        <div className="acc-w">
          <div className="res-relation" data-reveal="">
            <div>
              <span className="acc-tag">{a.relation.surtitre}</span>
              <h2 className="acc-titre-cote">
                {a.relation.titre.avant}{" "}
                <span className="acc-s">{a.relation.titre.fin}</span>
              </h2>
              <p>{a.relation.corps}</p>
            </div>
            <div className="res-relation-action">
              {demande && <p className="res-capitales">{demande}</p>}
              <Bouton lien={lienDeMiseEnRelation} aspect="or" className="res-bouton-souple">
                {a.relation.bouton}
              </Bouton>
              {promesse && <p className="res-capitales res-capitales-douces">{promesse}</p>}
            </div>
          </div>
        </div>
      </section>

      <Passage passerelle={a.passerelle} />
    </CadreDePage>
  );
}
