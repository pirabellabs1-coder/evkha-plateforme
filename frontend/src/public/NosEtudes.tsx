/** Page publique des études vendues à l'unité — reprise de
 *  `evkha.fr/etudedemarche`.
 *
 * Jumelle de `Partenaires` : même menu, même charte, même partage des rôles.
 * L'une s'adresse aux professionnels qui s'abonnent, l'autre aux porteurs de
 * projet qui achètent une étude. Elles se répondent — chacune renvoie vers
 * l'autre, parce qu'un visiteur arrive rarement sur la bonne du premier coup.
 *
 * ## Deux principes de construction, repris à l'identique
 *
 * 1. **Les prix viennent du serveur.** Ils sont lus dans
 *    `/api/public/livrables/`, qui les tient de la table `Offer` — y compris
 *    la fourchette du bandeau noir, calculée sur le catalogue et non écrite.
 *    « 149 € » posé dans ce fichier ferait une seconde source, qui
 *    contredirait le paiement au premier changement de tarif (règle 5). Le
 *    texte éditorial, lui, vit dans `contenu.ts` — y compris le nombre de
 *    chapitres ANNONCÉ, qui n'est pas celui du plan de production et n'a pas à
 *    l'être : voir `ArgumentaireEtude`.
 *
 * 2. **Aucun tarif n'est affiché tant qu'il n'est pas chargé.** Un prix de
 *    repli en attendant l'API afficherait un prix faux à qui a une connexion
 *    lente. Sur une page de vente, c'est inacceptable.
 *
 * ## Où mènent les boutons
 *
 * Vers la création de compte, pas vers la connexion : le visiteur qui clique
 * n'a par définition pas encore de compte, et lui présenter un écran de
 * connexion est le meilleur moyen de le perdre. L'étude choisie voyage dans
 * l'adresse (`/inscription?livrable=etude-marche`), exactement comme la
 * formule sur la page partenaires. C'est l'inscription qui enchaîne ensuite
 * sur le paiement.
 */
import { useEffect, useState } from "react";

import { CONTACT_EMAIL, ETUDES, ETUDES_PAGE } from "./contenu";
import { chargerLivrables, euros, type LivrablePublic } from "./donnees";
import { MenuSite } from "./MenuSite";
import "./Partenaires.css";
import "./NosEtudes.css";

/** Destination du bouton « Commander ».
 *
 * Le slug voyage dans l'adresse. La page d'inscription le lit, rappelle ce
 * qu'on achète avec son prix, puis ouvre le paiement une fois le compte créé.
 */
function lienCommande(slug: string): string {
  return `/inscription?livrable=${encodeURIComponent(slug)}`;
}

/** L'ordre de la page de vente, et non celui du serveur.
 *
 * L'API trie par prix croissant — un ordre juste pour un catalogue, faux pour
 * une page de vente : il mettait l'étude de concurrence à 89 € en tête, quand
 * `evkha.fr` ouvre sur l'étude de marché. La première carte n'est pas la moins
 * chère, c'est le produit d'appel.
 *
 * L'ordre est celui de `ETUDES`, qui reprend la page de la cliente. Une offre
 * sans argumentaire passe à la fin plutôt que de disparaître : une étude
 * invisible parce qu'un texte manque serait un défaut bien pire qu'un ordre
 * imparfait.
 */
function ordonnees(etudes: LivrablePublic[]): LivrablePublic[] {
  const rang = Object.keys(ETUDES);
  const place = (slug: string) => {
    const index = rang.indexOf(slug);
    return index === -1 ? rang.length : index;
  };
  return [...etudes].sort((a, b) => place(a.slug) - place(b.slug));
}

/** « 89–195 € », calculé sur le catalogue chargé.
 *
 * Le bandeau noir annonce une fourchette de prix. L'écrire dans le contenu en
 * ferait le seul endroit de la page où un tarif ne vient pas du serveur — et
 * le premier à mentir le jour d'un changement.
 */
function fourchette(etudes: LivrablePublic[]): string {
  const prix = etudes.map((e) => e.prix_cents);
  const bas = Math.min(...prix);
  const haut = Math.max(...prix);
  return bas === haut ? euros(bas) : `${euros(bas)} – ${euros(haut)}`;
}

/** Puce à coche dorée, comme sur la page partenaires. La coche est décorative :
 *  elle double une information déjà portée par le texte, et un lecteur d'écran
 *  qui l'annoncerait dirait « coche » avant chaque ligne sans rien apporter. */
function Puce({ children }: { children: React.ReactNode }) {
  return (
    <li>
      <span className="pp-coche" aria-hidden="true">
        ✓
      </span>
      <span>{children}</span>
    </li>
  );
}

function Carte({ etude }: { etude: LivrablePublic }) {
  const texte = ETUDES[etude.slug];

  return (
    <article className="ne-carte">
      {texte && <div className="ne-surtitre">{texte.surtitre}</div>}

      <h3>{etude.libelle}</h3>
      <div className="ne-prix">
        {euros(etude.prix_cents)} <span>TTC · paiement unique</span>
      </div>

      <div className="ne-quoi">Ce que vous obtenez :</div>
      <ul className="ne-points">
        <Puce>
          <b>
            {texte
              ? `${texte.chapitres} ${texte.chapeau}`
              : "Un document complet, en Word et en PDF"}
          </b>
        </Puce>
        {(texte?.details ?? []).map((detail) => (
          <li key={detail} className="ne-detail">
            <span className="pp-coche" aria-hidden="true">
              ✓
            </span>
            <span>{detail}</span>
          </li>
        ))}
      </ul>

      {texte && <p className="ne-pied">{texte.pied}</p>}

      {/* Poussé en bas de carte par `margin-top: auto` : quatre cartes de
          hauteurs différentes alignent quand même leurs boutons, et l'œil les
          balaie d'un seul mouvement. */}
      <a className="ne-bouton" href={lienCommande(etude.slug)}>
        {texte?.bouton ?? `Commander ${etude.libelle.toLowerCase()}`}
      </a>
    </article>
  );
}

export function NosEtudes() {
  const [etudes, setEtudes] = useState<LivrablePublic[] | null>(null);
  const [erreur, setErreur] = useState("");

  // Le gabarit HTML annonce « EVKHA — Espace client » : juste pour les deux
  // espaces connectés, faux pour une page publique que l'on partage par lien
  // et que les moteurs indexent.
  useEffect(() => {
    const precedent = document.title;
    document.title = "Nos études et livrables — EVKHA";
    return () => {
      document.title = precedent;
    };
  }, []);

  useEffect(() => {
    let vivant = true;
    chargerLivrables()
      .then((liste) => {
        if (vivant) setEtudes(liste);
      })
      .catch(() => {
        if (vivant) setErreur("Le catalogue est momentanément indisponible.");
      });
    return () => {
      vivant = false;
    };
  }, []);

  const p = ETUDES_PAGE;
  // Le premier bouton du catalogue, pour l'appel final. Sans catalogue chargé,
  // on renvoie vers les cartes plutôt que vers un lien mort.
  const premiere = etudes && etudes.length ? ordonnees(etudes)[0] : null;

  return (
    <div className="pp ne">
      <MenuSite />

      {/* ── Ouverture ──────────────────────────────────────────────────── */}
      <header className="pp-large ne-hero">
        <div>
          <h1>{p.hero.titre}</h1>
          <p className="ne-hero-accroche">{p.hero.accroche}</p>
          <p className="ne-hero-corps">{p.hero.corps}</p>
          <ul className="ne-hero-questions">
            {p.hero.questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
        <img className="ne-hero-image" src={p.hero.image} alt={p.hero.alt} />
      </header>

      {/* ── Bandeau de preuves ─────────────────────────────────────────── */}
      <div className="pp-large">
        <div className="ne-preuves">
          {p.preuves.map((preuve) => (
            <div key={preuve.libelle}>
              <div className="ne-preuve-valeur">
                {/* `valeur: null` = la fourchette, calculée sur le catalogue.
                    Une insécable pendant le chargement plutôt qu'un tiret :
                    la ligne ne bouge pas quand le chiffre arrive. */}
                {preuve.valeur ?? (etudes?.length ? fourchette(etudes) : " ")}
              </div>
              <div className="ne-preuve-libelle">{preuve.libelle}</div>
            </div>
          ))}
        </div>
      </div>

      <main>
        {/* ── Comment ça marche ────────────────────────────────────────── */}
        <section className="pp-large ne-section ne-methode">
          <p className="ne-eyebrow">
            {p.methode.surtitre} <span>{p.methode.titre}</span>
          </p>
          <p className="ne-sous">{p.methode.sous}</p>
          {p.methode.corps.map((paragraphe) => (
            <p className="ne-centre" key={paragraphe}>
              {paragraphe}
            </p>
          ))}

          <ol className="ne-etapes">
            {p.etapes.map((etape, index) => (
              <li key={etape.titre}>
                <span className="ne-etape-numero" aria-hidden="true">
                  {index + 1}
                </span>
                <h3>{etape.titre}</h3>
                <p>{etape.corps}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ── Quatre études au choix ───────────────────────────────────── */}
        <section className="ne-choix">
          <div className="pp-large">
            <p className="ne-eyebrow">{p.choix.surtitre}</p>
            <h2>{p.choix.titre}</h2>
            <p className="ne-centre">{p.choix.corps}</p>
          </div>
        </section>

        {/* ── Les cartes ───────────────────────────────────────────────── */}
        <section className="pp-large ne-section" id="nos-etudes">
          <h2 className="ne-titre-cartes">{p.cartes.titre}</h2>

          {erreur && (
            <p className="ne-erreur" role="alert">
              {erreur} Écrivez-nous à{" "}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          )}
          {etudes === null && !erreur && (
            <p className="ne-attente">Chargement du catalogue…</p>
          )}
          {etudes !== null && (
            <div className="ne-grille">
              {ordonnees(etudes).map((etude) => (
                <Carte key={etude.slug} etude={etude} />
              ))}
            </div>
          )}
        </section>

        {/* ── Les questions du porteur ─────────────────────────────────── */}
        <section className="pp-large ne-section">
          <h2 className="ne-titre-cartes">{p.interrogations.titre}</h2>
          <ul className="ne-interrogations">
            {p.interrogations.liste.map((question) => (
              <li key={question}>
                <span className="pp-coche" aria-hidden="true">
                  ✓
                </span>
                <span>{question}</span>
              </li>
            ))}
          </ul>
          <p className="ne-centre ne-interrogations-pied">
            {p.interrogations.pied}
          </p>

          <p className="ne-liseret">
            {p.liseret.avant} <a href="/partenaires">{p.liseret.lien}</a>{" "}
            {p.liseret.apres}
          </p>
        </section>

        {/* ── Ce n'est pas une étude générique ─────────────────────────── */}
        <section className="ne-comparatif">
          <div className="pp-large">
            <p className="ne-eyebrow ne-eyebrow-clair">{p.comparatif.surtitre}</p>
            <h2>{p.comparatif.titre}</h2>
            <hr className="ne-filet" />
            <p className="ne-centre">{p.comparatif.corps}</p>

            <div className="ne-colonnes">
              <div className="ne-colonne ne-colonne-sombre">
                <h3>{p.comparatif.generique.titre}</h3>
                <ul>
                  {p.comparatif.generique.points.map((point) => (
                    <li key={point}>
                      <span className="ne-croix" aria-hidden="true">
                        ✕
                      </span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="ne-colonne ne-colonne-claire">
                <h3>{p.comparatif.evkha.titre}</h3>
                <ul>
                  {p.comparatif.evkha.points.map((point) => (
                    <li key={point}>
                      <span className="pp-coche" aria-hidden="true">
                        ✓
                      </span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <p className="ne-centre ne-comparatif-pied">{p.comparatif.pied}</p>
          </div>
        </section>

        {/* ── Vos questions ────────────────────────────────────────────── */}
        <section className="pp-large ne-section">
          <p className="ne-eyebrow">{p.faq.surtitre}</p>
          <h2 className="ne-titre-cartes">{p.faq.titre}</h2>
          <div className="pp-faq">
            {p.faq.questions.map((question) => (
              <div className="pp-question" key={question.q}>
                <span className="pp-question-chevron" aria-hidden="true">
                  »
                </span>
                <h3>{question.q}</h3>
                <p>{question.r}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* ── Appel final ────────────────────────────────────────────────── */}
      <section className="ne-appel">
        <h2>{p.appel.titre}</h2>
        <p>{p.appel.sous}</p>
        <a
          className="ne-appel-bouton"
          href={premiere ? lienCommande(premiere.slug) : "#nos-etudes"}
        >
          {p.appel.bouton}
        </a>
      </section>
    </div>
  );
}
