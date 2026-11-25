/** Page d'accueil publique — la maquette validée par la cliente, portée dans
 *  la plateforme et complétée des sections de son site actuel.
 *
 * Elle remplace `Partenaires` à la racine du site (`router.tsx`). Elle
 * s'adresse d'abord au porteur de projet, et dit dès l'ouverture où va le
 * professionnel qui accompagne des créateurs : `/partenaires`.
 *
 * ## Les deux principes de `NosEtudes`, repris à l'identique
 *
 * 1. **Les prix viennent du serveur.** Trois catalogues, trois appels :
 *    `/api/public/livrables/` (les quatre livrables sur mesure),
 *    `/api/public/formules/` (les abonnements professionnels) et
 *    `/api/public/boutique/` (les études prêtes). Les « dès », les fourchettes
 *    et le tarif de chaque marche sont CALCULÉS sur ce qu'ils rendent. Aucun
 *    montant n'est écrit ici ni dans `contenuAccueil.ts` : il ferait une
 *    seconde source, qui contredirait le paiement au premier changement de
 *    tarif (règle 5). La carte de la formule des structures prend aussi son
 *    titre et ses avantages au serveur.
 *
 * 2. **Aucun tarif n'est affiché tant qu'il n'est pas chargé**, et une panne
 *    ne se lit pas comme un vide : chaque emplacement de prix dit s'il attend,
 *    s'il a échoué ou si le catalogue ne porte pas l'offre (règle 1). Une
 *    seule région d'alerte, en haut de page, annonce les pannes. Le reste de
 *    la page — titre, parcours, avis — ne dépend d'aucun de ces appels.
 *
 * ## La maquette, et ce qui s'en écarte
 *
 * La structure et les interactions sont celles de
 * `maquette-evkha/accueil.html`. Son script est porté en crochets, chacun
 * défaisant ce qu'il a branché. Les textes et les offres suivent la stratégie
 * commerciale : voir `contenuAccueil.ts`. La lettre d'information a disparu —
 * aucun service ne la reçoit.
 *
 * ## Le socle partagé avec la page des études
 *
 * La barre, le menu plein écran, le pied, le bouton-pilule, le bouton de
 * pause, le chargement d'un catalogue et les boutons aimantés servent aussi à
 * `NosEtudes`. Ils ne sont pas écrits ici : `EnTeteSite`, `PiedSite`,
 * `PiecesSite`, `site.ts`, `contenuSite.ts` et `Site.css` (règle 5). Ce
 * fichier ne garde que ce qui est propre à l'accueil.
 *
 * ## Le mouvement réduit RÉDUIT, il ne supprime pas
 *
 * Décision du client du 19/11/2026, propre à cette page : sous
 * `prefers-reduced-motion`, les blocs apparaissent encore au défilement (en
 * fondu, sans translation), les bandes et les orbites tournent au ralenti, le
 * mot du titre tourne. La parallaxe et les boutons aimantés, eux, sont coupés
 * dans leurs crochets. Deux boutons de pause arrêtent tout ce qui boucle
 * (WCAG 2.2.2). La révélation passe par `useReveler`, avec l'option qui lui
 * fait observer les blocs même dans ce mode : pas de second observateur.
 */
import { useEffect, useRef, useState, type RefObject } from "react";

import { chargerCatalogue, prix, type ProduitResume } from "./catalogue";
import { CONTACT_EMAIL } from "./contenu";
import {
  AILLEURS,
  ATELIER,
  AVIS,
  CHIFFRES,
  COMMENT,
  CONFIANCE,
  DESCRIPTION_DE_LA_PAGE,
  ETUDES_PRETES,
  FIN,
  FONDATRICE_ACCUEIL,
  IMAGES_ACCUEIL,
  METHODE,
  OFFRES,
  OUTILS,
  OUVERTURE,
  PARCOURS,
  POUR_QUI,
  POURQUOI,
  QUESTIONS,
  RUBAN,
  TITRE_DE_LA_PAGE,
  type AvisClient,
  type Offre,
  type TypeDeLivrable,
} from "./contenuAccueil";
import { carteDEtude, ID_DU_CONTENU, LIENS, TARIFS } from "./contenuSite";
import {
  chargerFormules,
  chargerLivrables,
  euros,
  type FormulePublique,
  type LivrablePublic,
} from "./donnees";
import { EnTeteSite } from "./EnTeteSite";
import { Bouton, BoutonPause } from "./PiecesSite";
import { PiedSite } from "./PiedSite";
import { useReveler } from "./reveler";
import {
  bornes,
  lisible,
  mouvementReduit,
  tarifDe,
  useAimants,
  useChargement,
  useMedia,
  useMenu,
  usePause,
  useDonneesStructurees,
  useQuestionsStructurees,
  useTitreDePage,
  variables,
  type Chargement,
  type Tarif,
} from "./site";
import { organisationEtSite } from "./referencement";
// Le socle d'abord, la feuille de la page ensuite : à spécificité égale, c'est
// la page qui a le dernier mot.
import "./Site.css";
import "./Accueil.css";

/** Lue une fois au chargement du module : un rendu ne doit pas dépendre de
 *  l'horloge. */
const ANNEE = new Date().getFullYear();

// ── Chargement des catalogues ───────────────────────────────────────────────

/** Les études prêtes de la boutique. Le catalogue rend aussi des thèmes et
 *  des avis, dont l'accueil n'a pas l'usage.
 *
 *  Pas de `?? []` ici : `chargerCatalogue` LÈVE une erreur quand la réponse ne
 *  porte pas la liste des produits. La rattraper par une liste vide ferait
 *  disparaître la section au lieu de dire la panne. */
function chargerEtudesPretes(): Promise<ProduitResume[]> {
  return chargerCatalogue().then((catalogue) => catalogue.produits);
}

type Catalogues = {
  livrables: Chargement<LivrablePublic[]>;
  formules: Chargement<FormulePublique[]>;
  boutique: Chargement<ProduitResume[]>;
};

// ── Les prix, calculés sur ce que l'API rend ────────────────────────────────

/** Le livrable d'un type donné, s'il est au catalogue avec un prix lisible. */
function livrableDe(
  livrables: Chargement<LivrablePublic[]>,
  type: TypeDeLivrable,
): LivrablePublic | null {
  if (livrables.etat !== "recu") return null;
  return (
    livrables.donnees.find((l) => l.type === type && lisible(l.prix_cents)) ??
    null
  );
}

function prixDuLivrable(
  livrables: Chargement<LivrablePublic[]>,
  type: TypeDeLivrable,
): Tarif {
  return tarifDe(livrables, (liste) => {
    const livrable = liste.find((l) => l.type === type);
    return livrable && lisible(livrable.prix_cents)
      ? euros(livrable.prix_cents)
      : null;
  });
}

/** Le « dès » de l'atelier : le livrable sur mesure le moins cher. */
function plancherDesLivrables(livrables: Chargement<LivrablePublic[]>): Tarif {
  return tarifDe(livrables, (liste) => {
    const b = bornes(liste.map((l) => l.prix_cents));
    return b ? `dès ${euros(b.bas)}` : null;
  });
}

/** Le montant d'une étude prête. `prix` formate dans la devise du produit ;
 *  une devise que `Intl` ne connaît pas lève une erreur, qui ne doit pas
 *  emporter la page : on retombe alors sur le format en euros. */
function prixDuProduit(produit: ProduitResume): string {
  try {
    return prix(produit.prix_cents, produit.devise || undefined);
  } catch {
    return euros(produit.prix_cents);
  }
}

/** Ce qu'une carte d'offre affiche : son prix, et — pour une formule nommée —
 *  le titre et les points que le serveur rend. */
type Affichage = {
  tarif: Tarif;
  mention: string;
  titre: string;
  points: string[];
};

function affichageDeLOffre(offre: Offre, catalogues: Catalogues): Affichage {
  const base = { titre: offre.titre, points: offre.points };
  switch (offre.prix) {
    case "boutique-plancher":
      return {
        ...base,
        mention: "TTC",
        tarif: tarifDe(catalogues.boutique, (produits) => {
          const b = bornes(produits.map((p) => p.prix_cents));
          return b ? `dès ${euros(b.bas)}` : null;
        }),
      };
    case "livrables-fourchette":
      return {
        ...base,
        mention: "TTC",
        tarif: tarifDe(catalogues.livrables, (liste) => {
          const b = bornes(liste.map((l) => l.prix_cents));
          if (!b) return null;
          return b.bas === b.haut
            ? euros(b.bas)
            : `de ${euros(b.bas)} à ${euros(b.haut)}`;
        }),
      };
    case "formule-plancher":
      return {
        ...base,
        mention: "par mois",
        tarif: tarifDe(catalogues.formules, (formules) => {
          const b = bornes(formules.map((f) => f.prix_mensuel_cents));
          return b ? `dès ${euros(b.bas)}` : null;
        }),
      };
    case "formule-nommee": {
      // UNE formule, par son code — et non « la plus chère » : le jour où une
      // formule au-dessus est créée, la carte afficherait son prix sous un
      // titre et des avantages qui ne sont pas les siens.
      const formule =
        catalogues.formules.etat === "recu"
          ? catalogues.formules.donnees.find(
              (f) => f.code === offre.codeFormule && lisible(f.prix_mensuel_cents),
            )
          : undefined;
      return {
        mention: "par mois",
        titre: formule?.libelle || offre.titre,
        // Les points écrits ici d'abord, puis les avantages rendus par le
        // serveur — sans doublon si le serveur en vient à dire la même chose.
        points: Array.isArray(formule?.avantages)
          ? [
              ...offre.points,
              ...formule.avantages.filter(
                (a) => typeof a === "string" && a !== "" && !offre.points.includes(a),
              ),
            ]
          : offre.points,
        tarif: tarifDe(catalogues.formules, () =>
          formule ? euros(formule.prix_mensuel_cents) : null,
        ),
      };
    }
  }
}

/** Un prix, ou la phrase qui dit pourquoi il manque. */
function Montant({ tarif, mention }: { tarif: Tarif; mention?: string }) {
  if (tarif.etat !== "connu") {
    return <p className="acc-prix-absent">{TARIFS[tarif.etat]}</p>;
  }
  return (
    <p className="acc-prix">
      {tarif.texte}
      {mention && <span className="acc-prix-mention"> {mention}</span>}
    </p>
  );
}

// ── Petites pièces ──────────────────────────────────────────────────────────

/** Surtitre, titre en deux temps (le second en italique), paragraphe. */
function Intro({
  surtitre,
  titre,
  corps,
}: {
  surtitre: string;
  titre: { avant: string; fin: string };
  corps: string;
}) {
  return (
    <div className="acc-intro" data-reveal="">
      <div>
        <span className="acc-tag">{surtitre}</span>
        <h2>
          {titre.avant} <span className="acc-s">{titre.fin}</span>
        </h2>
      </div>
      <p>{corps}</p>
    </div>
  );
}

// ── Les mouvements de la maquette, en crochets ──────────────────────────────

/** Le mot qui tourne dans le titre.
 *
 *  Il continue sous mouvement réduit (c'est un échange de mots, pas un
 *  déplacement), et s'arrête avec les boutons de pause.
 *
 *  AUCUNE durée n'est écrite ici : celle du glissement vit dans la feuille
 *  (`--duree-acc-glisse`), et le crochet n'a pas à la connaître. Le mot qui
 *  vient de sortir reste en haut jusqu'au battement suivant ; c'est alors
 *  seulement qu'il retourne attendre en bas, d'un coup et hors de vue (la
 *  classe d'attente n'a pas de transition). Un minuteur réglé sur la durée du
 *  glissement en aurait fait une seconde écriture, fausse dès que la feuille
 *  en change — sous mouvement réduit, par exemple.
 *
 *  Le premier mot seul est exposé aux lecteurs d'écran : le titre se lit
 *  « Faites de votre idée une vraie entreprise. », une fois, et ne change pas sous
 *  l'oreille toutes les deux secondes. */
function MotQuiTourne({ mots, fige }: { mots: string[]; fige: boolean }) {
  const [etat, setEtat] = useState({ courant: 0, sortant: -1 });

  useEffect(() => {
    if (fige || mots.length < 2) return undefined;
    const battement = window.setInterval(() => {
      setEtat((e) => ({
        courant: (e.courant + 1) % mots.length,
        sortant: e.courant,
      }));
    }, 2400);
    return () => window.clearInterval(battement);
  }, [fige, mots.length]);

  return (
    <span className="acc-roule">
      {mots.map((mot, k) => (
        <b
          key={mot}
          aria-hidden={k === 0 ? undefined : true}
          className={
            k === etat.courant
              ? "acc-roule-entre"
              : k === etat.sortant
                ? "acc-roule-sort"
                : "acc-roule-attend"
          }
        >
          {mot}
        </b>
      ))}
    </span>
  );
}

/** Le disque de l'ouverture suit doucement la souris. Coupé sous mouvement
 *  réduit. Une seule écriture par image, et rien une fois l'ouverture
 *  dépassée. */
function useParallaxe(disque: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    if (mouvementReduit()) return undefined;
    let image = 0;
    function auDeplacement(evenement: PointerEvent) {
      if (image !== 0 || window.scrollY > window.innerHeight) return;
      image = window.requestAnimationFrame(() => {
        image = 0;
        const cible = disque.current;
        if (!cible) return;
        const x = (evenement.clientX / window.innerWidth - 0.5) * -30;
        const y = (evenement.clientY / window.innerHeight - 0.5) * -30;
        cible.style.transform = `translate(${x}px, ${y}px)`;
      });
    }
    window.addEventListener("pointermove", auDeplacement, { passive: true });
    return () => {
      window.removeEventListener("pointermove", auDeplacement);
      if (image !== 0) window.cancelAnimationFrame(image);
    };
  }, [disque]);
}

/** Les chiffres qui comptent, de zéro à leur valeur, quand leur carte est
 *  révélée.
 *
 *  Pas de second `IntersectionObserver` : `useReveler` pose `est-revele` sur
 *  la carte, et c'est ce changement de classe qu'on écoute. Le nombre est
 *  écrit dans le DOM image par image, sans repasser par React — douze cents
 *  millisecondes de rendus pour quatre chiffres n'apporteraient rien. Sans
 *  `requestAnimationFrame`, la valeur finale, déjà rendue, reste en place. */
function useCompteurs(grille: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const conteneur = grille.current;
    if (!conteneur || typeof window.requestAnimationFrame !== "function") {
      return undefined;
    }
    const cartes = Array.from(
      conteneur.querySelectorAll<HTMLElement>("[data-compteur]"),
    );
    const lances = new Set<HTMLElement>();
    const images = new Map<HTMLElement, number>();

    function lancer(carte: HTMLElement) {
      const nombre = carte.querySelector<HTMLElement>(".acc-nombre-valeur");
      const fin = Number(carte.dataset.compteur);
      if (!nombre || !Number.isFinite(fin)) return;
      const depart = performance.now();
      const pas = (instant: number) => {
        const p = Math.min(1, (instant - depart) / 1200);
        nombre.textContent = String(Math.round(fin * (1 - (1 - p) ** 3)));
        if (p < 1) images.set(carte, window.requestAnimationFrame(pas));
        else images.delete(carte);
      };
      images.set(carte, window.requestAnimationFrame(pas));
    }

    function verifier() {
      for (const carte of cartes) {
        if (lances.has(carte) || !carte.classList.contains("est-revele")) {
          continue;
        }
        lances.add(carte);
        lancer(carte);
      }
    }

    verifier();
    const temoin =
      typeof MutationObserver === "undefined"
        ? null
        : new MutationObserver(verifier);
    temoin?.observe(conteneur, {
      attributes: true,
      attributeFilter: ["class"],
      subtree: true,
    });
    return () => {
      temoin?.disconnect();
      for (const image of images.values()) window.cancelAnimationFrame(image);
    };
  }, [grille]);
}

// ── Sections à état ─────────────────────────────────────────────────────────

/** L'atelier : le visiteur choisit un document et une couleur, la feuille
 *  suit. La couleur est une propriété posée sur l'atelier ; sa valeur est un
 *  jeton de `tokens.css`, jamais un code écrit ici. */
function Atelier({ plancher }: { plancher: Tarif }) {
  const [choix, setChoix] = useState(0);
  const [teinte, setTeinte] = useState(0);
  const courant = ATELIER.documents[choix];

  return (
    <div
      className="acc-atelier"
      data-reveal=""
      style={variables({ "--acc-marque": ATELIER.teintes[teinte].jeton })}
    >
      <div className="acc-atelier-choix">
        <div
          className="acc-onglets"
          role="group"
          aria-label={ATELIER.groupeDocuments}
        >
          {ATELIER.documents.map((doc, k) => (
            <button
              key={doc.type}
              type="button"
              className="acc-onglet"
              aria-pressed={k === choix}
              onClick={() => setChoix(k)}
            >
              <span className="acc-onglet-numero" aria-hidden="true">
                {String(k + 1).padStart(2, "0")}
              </span>
              {doc.titre}
              <span className="acc-onglet-fleche" aria-hidden="true">
                →
              </span>
            </button>
          ))}
        </div>

        <div
          className="acc-teintes"
          role="group"
          aria-label={ATELIER.groupeTeintes}
        >
          {ATELIER.invitationTeinte}
          {ATELIER.teintes.map((t, k) => (
            <button
              key={t.nom}
              type="button"
              className="acc-teinte"
              style={variables({ "--acc-c": t.jeton })}
              aria-pressed={k === teinte}
              aria-label={t.nom}
              onClick={() => setTeinte(k)}
            />
          ))}
        </div>

        <Bouton
          lien={ATELIER.bouton.lien}
          aspect="or"
          className="acc-atelier-bouton"
        >
          {ATELIER.bouton.libelle}
        </Bouton>
      </div>

      <div className="acc-atelier-scene">
        <div className="acc-bulle">
          {plancher.etat === "connu" ? (
            <b>{plancher.texte}</b>
          ) : (
            <span className="acc-bulle-absent">{TARIFS[plancher.etat]}</span>
          )}
          {ATELIER.bulle.delai}
          <span className="acc-bulle-formats">{ATELIER.bulle.formats}</span>
        </div>

        <div className="acc-feuille" aria-live="polite">
          <div className="acc-feuille-tete">
            <small>{ATELIER.feuille.logo}</small>
            <span className="acc-sceau" aria-hidden="true" />
          </div>
          <div className="acc-feuille-titre">{courant.titre}</div>
          <small>{courant.sous}</small>
          <div className="acc-filet" aria-hidden="true" />
          <div className="acc-ligne" aria-hidden="true" />
          <div className="acc-ligne acc-ligne-2" aria-hidden="true" />
          <div className="acc-ligne acc-ligne-3" aria-hidden="true" />
          <div className="acc-graphe" aria-hidden="true">
            {courant.barres.map((hauteur, k) => (
              <span key={k} style={{ height: `${hauteur}%` }} />
            ))}
          </div>
          <div className="acc-feuille-pied">
            {/* Le nombre vient de `contenu.ETUDES` ; une clé manquante y
                lève une erreur au chargement, elle ne rend pas un vide. */}
            <span>{courant.chapitres} chapitres</span>
            <span>
              {ATELIER.feuille.signature} · {ANNEE}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Cinq volets, un seul ouvert : à la souris, au doigt ou au clavier. Sous
 *  900 px la feuille les empile tous ouverts, et cet état ne sert plus. */
function Volets() {
  const [ouvert, setOuvert] = useState(0);

  return (
    <div className="acc-volets" data-reveal="">
      {POUR_QUI.profils.map((profil, k) => (
        <article
          key={profil.titre}
          className={k === ouvert ? "acc-volet acc-volet-ouvert" : "acc-volet"}
          onPointerEnter={() => setOuvert(k)}
          onClick={() => setOuvert(k)}
          onFocus={() => setOuvert(k)}
        >
          <span className="acc-volet-numero" aria-hidden="true">
            {String(k + 1).padStart(2, "0")}
          </span>
          <span className="acc-volet-tranche" aria-hidden="true">
            {profil.titre}
          </span>
          <div className="acc-volet-contenu">
            <div>
              <h3>{profil.titre}</h3>
              <p>{profil.corps}</p>
              <Bouton lien={profil.lien} aspect="noir">
                {profil.bouton}
              </Bouton>
            </div>
            <img
              className="acc-volet-image"
              src={profil.image}
              alt=""
              loading="lazy"
              decoding="async"
            />
          </div>
        </article>
      ))}
    </div>
  );
}

/** Les études prêtes : les produits RÉELS de la boutique — le même appel et
 *  le même état que la carte « Étude prête » des offres.
 *
 *  Quatre issues, quatre rendus : en attente, des gabarits sans montant ; en
 *  panne, la section le dit (l'alerte du haut de page l'a annoncé) ; reçu et
 *  vide, la section n'existe pas — une vitrine vide n'apprend rien ; reçu,
 *  jusqu'à six cartes. */
function EtudesPretes({ boutique }: { boutique: Chargement<ProduitResume[]> }) {
  const produits =
    boutique.etat === "recu"
      ? boutique.donnees
          .filter((p) => lisible(p.prix_cents) && p.slug && p.titre)
          .slice(0, ETUDES_PRETES.maximum)
      : [];
  if (boutique.etat === "recu" && produits.length === 0) return null;

  return (
    <section className="acc-section acc-section-suite" id="etudes-pretes">
      <div className="acc-w">
        <Intro
          surtitre={ETUDES_PRETES.surtitre}
          titre={ETUDES_PRETES.titre}
          corps={ETUDES_PRETES.corps}
        />

        {boutique.etat === "panne" && (
          <p className="acc-panne">{ETUDES_PRETES.panne}</p>
        )}

        {boutique.etat === "attente" && (
          <>
            <p className="visuellement-cache" role="status">
              {ETUDES_PRETES.attente}
            </p>
            <div className="acc-pretes" aria-hidden="true">
              {[0, 1, 2].map((k) => (
                <div key={k} className="acc-prete acc-prete-gabarit">
                  <span />
                  <span />
                  <span />
                </div>
              ))}
            </div>
          </>
        )}

        {boutique.etat === "recu" && (
          <ul className="acc-pretes">
            {produits.map((produit, k) => (
              <li key={produit.slug} data-reveal="" style={variables({ "--i": k })}>
                <a
                  className="acc-prete"
                  href={`${LIENS.boutique}/${encodeURIComponent(produit.slug)}`}
                >
                  {produit.theme && <small>{produit.theme}</small>}
                  <h3>{produit.titre}</h3>
                  <span className="acc-prete-pied">
                    <b>{prixDuProduit(produit)}</b>
                    <span className="acc-prete-suite">
                      {ETUDES_PRETES.carte}
                      <span aria-hidden="true"> →</span>
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}

        {boutique.etat !== "panne" && (
          <Bouton
            lien={ETUDES_PRETES.bouton.lien}
            aspect="clair"
            className="acc-suite"
          >
            {ETUDES_PRETES.bouton.libelle}
          </Bouton>
        )}
      </div>
    </section>
  );
}

function CarteAvis({ avis, double }: { avis: AvisClient; double?: boolean }) {
  return (
    <figure
      className={avis.dore ? "acc-mot acc-mot-dore" : "acc-mot"}
      aria-hidden={double ? true : undefined}
    >
      <p>{avis.texte}</p>
      <figcaption>
        <span className="acc-mot-initiale" aria-hidden="true">
          {avis.auteur.charAt(0).toUpperCase()}
        </span>
        <span>
          {avis.auteur}
          <span className="acc-mot-contexte">{avis.contexte}</span>
        </span>
      </figcaption>
    </figure>
  );
}

/** Une colonne du mur : ses avis, puis les mêmes une seconde fois pour que la
 *  boucle ne montre pas de couture. Les doublons sont masqués aux lecteurs
 *  d'écran — sans cela, chaque avis serait lu deux fois. */
function ColonneAvis({ colonne }: { colonne: 1 | 2 }) {
  const avis = AVIS.liste.filter((a) => a.colonne === colonne);
  return (
    <div className="acc-colonne">
      {avis.map((a) => (
        <CarteAvis key={`${a.auteur}-${a.contexte}`} avis={a} />
      ))}
      {avis.map((a) => (
        <CarteAvis key={`${a.auteur}-${a.contexte}-double`} avis={a} double />
      ))}
    </div>
  );
}

// ── La page ─────────────────────────────────────────────────────────────────

/** Calculé une fois : rien n'y dépend d'un rendu. */
const ORGANISATION_ET_SITE = organisationEtSite(DESCRIPTION_DE_LA_PAGE);

export function Accueil() {
  const catalogues: Catalogues = {
    livrables: useChargement(chargerLivrables),
    formules: useChargement(chargerFormules),
    boutique: useChargement(chargerEtudesPretes),
  };

  const menu = useMenu();
  const { fige, basculer: basculerLaPause } = usePause();

  const page = useRef<HTMLDivElement>(null);
  const disque = useRef<HTMLDivElement>(null);
  const chiffres = useRef<HTMLDivElement>(null);

  // Sous 600 px, le mur d'avis devient une file que l'on fait défiler à
  // l'horizontale : il doit alors pouvoir prendre le focus, sinon le clavier
  // n'a aucun moyen de la parcourir. Au-dessus, il ne défile pas — un arrêt
  // de tabulation de plus n'y servirait à rien.
  const murDefilable = useMedia("(max-width: 600px)");

  // La clé : les cartes des études prêtes sont montées quand la boutique
  // répond, et doivent être observées à leur tour. L'option : sur cette
  // page, le mouvement réduit garde la révélation (en fondu seul, voir la
  // feuille) au lieu de tout afficher d'emblée.
  useReveler(page, catalogues.boutique.etat, { memeEnMouvementReduit: true });
  useCompteurs(chiffres);
  useParallaxe(disque);
  useAimants(page);

  // Le titre de l'onglet et la description de la page, rendus en partant
  // (`site.useTitreDePage`).
  useTitreDePage(TITRE_DE_LA_PAGE, DESCRIPTION_DE_LA_PAGE);
  // L'entreprise et le site, déclarés une fois : sur la page d'accueil.
  useDonneesStructurees(ORGANISATION_ET_SITE);
  // Les questions de la page, déclarées telles qu'elle les affiche.
  useQuestionsStructurees(page);

  const livrablesEnPanne = catalogues.livrables.etat === "panne";
  const tarifsEnPanne =
    livrablesEnPanne ||
    catalogues.formules.etat === "panne" ||
    catalogues.boutique.etat === "panne";

  return (
    <div className={fige ? "acc acc-fige" : "acc"} ref={page}>
      {/* Le lien d'évitement, la barre et le menu plein écran : le socle
          partagé avec la page des études (`EnTeteSite`). */}
      <EnTeteSite menu={menu} />

      {/* `tabIndex={-1}` : la cible du lien d'évitement doit pouvoir recevoir
          le focus, sinon certains navigateurs font défiler sans le déplacer. */}
      <main id={ID_DU_CONTENU} tabIndex={-1} inert={menu.ouvert}>
        {/* UNE région d'alerte, toujours dans le DOM, pour toutes les pannes
            de tarifs. Stable : un lecteur d'écran annonce ce qui y ARRIVE.
            Montée avec son message, elle pouvait ne pas être lue ; répétée
            dans chaque section, elle l'était trois fois. */}
        <div className="acc-alerte" role="alert">
          {tarifsEnPanne && (
            <p className="acc-w">
              {TARIFS.alerte} {TARIFS.alerteSuite}{" "}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          )}
        </div>

        {/* ── Ouverture ────────────────────────────────────────────────── */}
        <div className="acc-hero">
          <div className="acc-halo" aria-hidden="true" ref={disque} />
          {/* Le premier des deux boutons de pause : dès l'ouverture, là où
              tournent les orbites et le mot, sans attendre la section des
              avis où se trouve le second. */}
          <div className="acc-w acc-pause-rang">
            <BoutonPause
              fige={fige}
              basculer={basculerLaPause}
              className="acc-pause-haut"
            />
          </div>
          <div className="acc-w acc-hero-grille">
            <div>
              <span className="acc-tag acc-entre">{OUVERTURE.surtitre}</span>
              <h1>
                <span className="acc-ligne-titre">
                  <span>
                    {OUVERTURE.titre.avant}{" "}
                    <MotQuiTourne mots={OUVERTURE.titre.mots} fige={fige} />
                  </span>
                </span>
                <span className="acc-ligne-titre">
                  <span>
                    {OUVERTURE.titre.milieu}{" "}
                    <span className="acc-s">{OUVERTURE.titre.fin}</span>
                  </span>
                </span>
              </h1>
              <p
                className="acc-promesse acc-entre"
                style={variables({ "--i": 1 })}
              >
                {OUVERTURE.promesse}
              </p>
              <div className="acc-appels acc-entre" style={variables({ "--i": 2 })}>
                <Bouton lien={OUVERTURE.boutonPrincipal.lien} aspect="noir">
                  {OUVERTURE.boutonPrincipal.libelle}
                </Bouton>
                <Bouton
                  lien={OUVERTURE.boutonSecondaire.lien}
                  aspect="clair"
                  externe
                >
                  {OUVERTURE.boutonSecondaire.libelle}
                </Bouton>
              </div>
              <div className="acc-gens acc-entre" style={variables({ "--i": 3 })}>
                <div className="acc-visages" aria-hidden="true">
                  {["-2px", "-47px", "-93px", "-140px"].map((x) => (
                    <span
                      key={x}
                      style={{
                        backgroundImage: `url(${IMAGES_ACCUEIL.visages})`,
                        backgroundPositionX: x,
                      }}
                    />
                  ))}
                </div>
                <span>
                  <strong>{OUVERTURE.preuve.valeur}</strong>{" "}
                  {OUVERTURE.preuve.libelle}
                </span>
              </div>
            </div>

            <div className="acc-astre">
              {/* Sous 900 px, le grand disque est remplacé par celui-ci,
                  centré derrière le portrait (voir la feuille). */}
              <div className="acc-halo-proche" aria-hidden="true" />
              <div className="acc-photo">
                <img
                  className="acc-photo-image"
                  src={IMAGES_ACCUEIL.portrait}
                  alt={OUVERTURE.altPortrait}
                  fetchPriority="high"
                />
              </div>
              {OUVERTURE.pastilles.map((pastille, k) => {
                const tarif = prixDuLivrable(catalogues.livrables, pastille.type);
                return (
                  <div
                    key={pastille.type}
                    className={
                      k === 0 ? "acc-orbite" : "acc-orbite acc-orbite-inverse"
                    }
                    aria-hidden="true"
                  >
                    <div className="acc-pastille">
                      <span className="acc-pastille-texte">
                        {pastille.libelle}
                        {tarif.etat === "connu" && ` · ${tarif.texte}`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="acc-ruban" aria-hidden="true">
          <div className="acc-ruban-piste">
            {[...RUBAN, ...RUBAN].map((mot, k) => (
              <span key={k}>{mot}</span>
            ))}
          </div>
        </div>

        {/* ── Ils me font confiance ────────────────────────────────────── */}
        <section className="acc-confiance" aria-labelledby="acc-confiance-titre">
          <div className="acc-w" data-reveal="">
            <h2 className="acc-confiance-titre" id="acc-confiance-titre">
              {CONFIANCE.titre}
            </h2>
            {/* Les logos DÉFILENT (demande du client, 19/11/2026). La liste est
                rendue trois fois bout à bout pour que la bande reste pleine sur
                un grand écran ; seule la première est lue (les copies sont
                `aria-hidden`, leurs images sans texte). Elle s'arrête au survol,
                au focus et avec le bouton de pause, comme le ruban.
                Une référence SANS logo s'affiche par son nom, en texte : dans
                une copie, c'est le `aria-hidden` de sa case qui la tait. */}
            <div className="acc-confiance-bande">
              <ul className="acc-confiance-logos">
                {[0, 1, 2].flatMap((copie) =>
                  CONFIANCE.logos.map((logo) => (
                    <li key={`${copie}-${logo.nom}`} aria-hidden={copie > 0 ? true : undefined}>
                      {logo.image ? (
                        <img
                          className="acc-confiance-logo"
                          src={logo.image.src}
                          alt={copie > 0 ? "" : logo.nom}
                          width={logo.image.largeur}
                          height={logo.image.hauteur}
                          loading="lazy"
                          decoding="async"
                        />
                      ) : (
                        <span className="acc-confiance-nom">{logo.nom}</span>
                      )}
                    </li>
                  )),
                )}
              </ul>
            </div>
          </div>
        </section>
        {/* Sous « Ils me font confiance », et non plus à l'ouverture (demande
            de la cliente du 24/11/2026). Hors de la section : la bande qui
            défile ne porte aucun lien. */}
        <div className="acc-w">
          <p className="acc-pros acc-pros-confiance">
            {OUVERTURE.professionnels.question}{" "}
            <a href={OUVERTURE.professionnels.lien}>
              {OUVERTURE.professionnels.reponse}
            </a>
          </p>
        </div>

        {/* ── Le parcours : un projet, quatre documents ────────────────── */}
        <section className="acc-section" id="parcours">
          <div className="acc-w">
            <Intro
              surtitre={PARCOURS.surtitre}
              titre={PARCOURS.titre}
              corps={PARCOURS.corps}
            />
            {livrablesEnPanne && <p className="acc-panne">{TARIFS.rappel}</p>}
            <div className="acc-marches">
              {PARCOURS.marches.map((marche, k) => {
                const livrable = livrableDe(catalogues.livrables, marche.type);
                const tarif = prixDuLivrable(catalogues.livrables, marche.type);
                const derniere = k === PARCOURS.marches.length - 1;
                // Le catalogue a répondu et ne porte pas ce livrable : la
                // marche reste (le parcours garde ses quatre temps) mais ce
                // n'est plus un lien — il ne mènerait à rien d'achetable.
                const hors = tarif.etat === "absent";
                const classes = [
                  "acc-marche",
                  derniere ? "acc-marche-sommet" : "",
                  hors ? "acc-marche-hors" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                const contenu = (
                  <>
                    <div className="acc-marche-haut">
                      <span className="acc-marche-numero" aria-hidden="true">
                        {String(k + 1).padStart(2, "0")}
                      </span>
                      {!hors && (
                        <span className="acc-marche-fleche" aria-hidden="true">
                          →
                        </span>
                      )}
                    </div>
                    <div className="acc-marche-corps">
                      <small>
                        {PARCOURS.etiquetteQuestion} {k + 1}
                      </small>
                      <h3>{marche.question}</h3>
                      <p>{marche.corps}</p>
                      <div className="acc-marche-reponse">
                        <small>{PARCOURS.etiquetteDocument}</small>
                        <strong>{marche.document}</strong>
                        {tarif.etat === "connu" ? (
                          <b>{tarif.texte}</b>
                        ) : (
                          <span className="acc-marche-sans-prix">
                            {TARIFS[tarif.etat]}
                          </span>
                        )}
                      </div>
                    </div>
                  </>
                );
                const style = variables({ "--n": k, "--i": k });
                return hors ? (
                  <div
                    key={marche.type}
                    className={classes}
                    style={style}
                    data-reveal=""
                  >
                    {contenu}
                  </div>
                ) : (
                  <a
                    key={marche.type}
                    className={classes}
                    // Vers la DESCRIPTION du document sur la page des études,
                    // pas vers la commande : « les clients aiment lire quelque
                    // chose avant de se lancer » (cliente, 24/11/2026). Tant
                    // que le slug n'est pas connu, le haut de la page.
                    href={livrable ? carteDEtude(livrable.slug) : LIENS.etudes}
                    style={style}
                    data-reveal=""
                  >
                    {contenu}
                  </a>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Comment ça marche ────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="comment">
          <div className="acc-w">
            <Intro
              surtitre={COMMENT.surtitre}
              titre={COMMENT.titre}
              corps={COMMENT.corps}
            />
            <ol className="acc-comment">
              {COMMENT.etapes.map((etape, k) => (
                <li key={etape.titre} data-reveal="" style={variables({ "--i": k })}>
                  <span className="acc-comment-numero" aria-hidden="true">
                    {k + 1}
                  </span>
                  <h3>{etape.titre}</h3>
                  <p>{etape.corps}</p>
                </li>
              ))}
            </ol>
            <Bouton lien={COMMENT.bouton.lien} aspect="noir" className="acc-suite">
              {COMMENT.bouton.libelle}
            </Bouton>
          </div>
        </section>

        {/* ── L'atelier ────────────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="atelier">
          <div className="acc-w">
            <Intro
              surtitre={ATELIER.surtitre}
              titre={ATELIER.titre}
              corps={ATELIER.corps}
            />
            <Atelier plancher={plancherDesLivrables(catalogues.livrables)} />
          </div>
        </section>

        {/* ── Chiffres ─────────────────────────────────────────────────── */}
        <div className="acc-section acc-section-suite">
          <div className="acc-w acc-nombres" ref={chiffres}>
            {CHIFFRES.map((chiffre, k) => (
              <div
                key={chiffre.libelle}
                className="acc-nombre"
                data-reveal=""
                data-compteur={chiffre.valeur}
                style={variables({ "--i": k })}
              >
                <b>
                  {chiffre.avant && (
                    <span className="acc-nombre-avant">{chiffre.avant} </span>
                  )}
                  <span className="acc-nombre-valeur">{chiffre.valeur}</span>
                  {chiffre.apres}
                </b>
                <span>{chiffre.libelle}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── À qui ça s'adresse ───────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="pour-qui">
          <div className="acc-w">
            <Intro
              surtitre={POUR_QUI.surtitre}
              titre={POUR_QUI.titre}
              corps={POUR_QUI.corps}
            />
            <Volets />
          </div>
        </section>

        {/* ── Les offres réellement vendues ────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="formules">
          <div className="acc-w">
            <Intro
              surtitre={OFFRES.surtitre}
              titre={OFFRES.titre}
              corps={OFFRES.corps}
            />
            {tarifsEnPanne && <p className="acc-panne">{TARIFS.rappel}</p>}
            <div className="acc-formules">
              {OFFRES.cartes.map((offre, k) => {
                const affichage = affichageDeLOffre(offre, catalogues);
                return (
                  <article
                    key={offre.prix}
                    className={
                      offre.etiquette
                        ? "acc-formule acc-formule-phare"
                        : "acc-formule"
                    }
                    data-reveal=""
                    style={variables({ "--i": k })}
                  >
                    {offre.etiquette && (
                      <span className="acc-formule-etiquette">
                        {offre.etiquette}
                      </span>
                    )}
                    <small>{offre.surtitre}</small>
                    <h3>{affichage.titre}</h3>
                    <Montant tarif={affichage.tarif} mention={affichage.mention} />
                    <p>{offre.corps}</p>
                    {affichage.points.length > 0 && (
                      <ul>
                        {affichage.points.map((point) => (
                          <li key={point}>{point}</li>
                        ))}
                      </ul>
                    )}
                    <Bouton
                      lien={offre.lien}
                      aspect={offre.etiquette ? "noir" : "clair"}
                      inactif={affichage.tarif.etat === "absent"}
                      className="acc-formule-bouton"
                    >
                      {offre.bouton}
                    </Bouton>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Études prêtes : les produits de la boutique ──────────────── */}
        <EtudesPretes boutique={catalogues.boutique} />

        {/* ── La méthode ───────────────────────────────────────────────── */}
        <section className="acc-section acc-methode" id="methode">
          <div className="acc-w">
            <Intro
              surtitre={METHODE.surtitre}
              titre={METHODE.titre}
              corps={METHODE.corps}
            />
            <div className="acc-temps" data-reveal="">
              <svg
                className="acc-fil"
                viewBox="0 0 1200 90"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path
                  pathLength={1}
                  d="M30 50 C 220 -20, 300 110, 440 72 S 700 -10, 840 38 S 1080 100, 1180 20"
                />
              </svg>
              {METHODE.temps.map((temps, k) => (
                <div className="acc-etape" key={temps.titre}>
                  <span className="acc-etape-point" aria-hidden="true">
                    {k + 1}
                  </span>
                  <h3>{temps.titre}</h3>
                  <p>{temps.corps}</p>
                  <p className="acc-etape-livrables">
                    <span aria-hidden="true">→ </span>
                    {temps.lien ? (
                      <a href={temps.lien} rel="noopener">
                        {temps.livrables}
                      </a>
                    ) : (
                      temps.livrables
                    )}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Formations et accompagnement (sur evkha.fr, sans prix) ───── */}
        <section className="acc-section" id="formations">
          <div className="acc-w">
            <Intro
              surtitre={AILLEURS.surtitre}
              titre={AILLEURS.titre}
              corps={AILLEURS.corps}
            />
            <div className="acc-ailleurs">
              {AILLEURS.cartes.map((carte, k) => (
                <article
                  key={carte.titre}
                  className="acc-ailleurs-carte"
                  data-reveal=""
                  style={variables({ "--i": k })}
                >
                  <div>
                    <h3>{carte.titre}</h3>
                    <p>{carte.corps}</p>
                    <ul>
                      {carte.points.map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                    <Bouton lien={carte.lien} aspect="clair" externe>
                      {carte.bouton}
                    </Bouton>
                  </div>
                  {carte.image && (
                    // Décorative : un visuel d'ambiance, dont le texte de la
                    // carte dit déjà tout ce qu'il y a à savoir.
                    <img
                      className="acc-ailleurs-image"
                      src={carte.image.src}
                      alt=""
                      width={carte.image.largeur}
                      height={carte.image.hauteur}
                      loading="lazy"
                      decoding="async"
                    />
                  )}
                </article>
              ))}
            </div>
            <p className="acc-ailleurs-mention">{AILLEURS.mention}</p>
          </div>
        </section>

        {/* ── La fondatrice ────────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="elle">
          <div className="acc-w acc-elle">
            <div className="acc-elle-cadre" data-reveal="">
              <figure>
                {/* Décorative ici : le nom figure juste à côté. Une autre
                    photo que celle de l'ouverture (cliente, 24/11/2026). */}
                <img
                  className="acc-elle-image"
                  src={IMAGES_ACCUEIL.portraitFondatrice}
                  alt=""
                  loading="lazy"
                  decoding="async"
                />
              </figure>
            </div>
            <div data-reveal="">
              <span className="acc-tag">{FONDATRICE_ACCUEIL.surtitre}</span>
              <p className="acc-citation">
                {FONDATRICE_ACCUEIL.citation.avant}{" "}
                <mark>{FONDATRICE_ACCUEIL.citation.appui}</mark>{" "}
                {FONDATRICE_ACCUEIL.citation.apres}
              </p>
              <h2 className="acc-elle-nom">{FONDATRICE_ACCUEIL.nom}</h2>
              <p className="acc-elle-corps">{FONDATRICE_ACCUEIL.corps}</p>
              <ul className="acc-references">
                {FONDATRICE_ACCUEIL.references.map((reference) => (
                  <li key={reference.texte}>
                    <span className="acc-reference-nom">{reference.texte}</span>
                    {/* Décoratif : le nom du réseau est écrit juste au-dessus. */}
                    <img
                      className="acc-reference-logo"
                      src={reference.logo.src}
                      alt=""
                      width={reference.logo.largeur}
                      height={reference.logo.hauteur}
                      loading="lazy"
                      decoding="async"
                    />
                  </li>
                ))}
              </ul>
              <Bouton lien={FONDATRICE_ACCUEIL.bouton.lien} aspect="noir">
                {FONDATRICE_ACCUEIL.bouton.libelle}
              </Bouton>
            </div>
          </div>
        </section>

        {/* ── Pourquoi EVKHA ───────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="pourquoi">
          <div className="acc-w">
            <Intro
              surtitre={POURQUOI.surtitre}
              titre={POURQUOI.titre}
              corps={POURQUOI.corps}
            />
            <div className="acc-mosaique">
              {POURQUOI.cases.map((c, k) => (
                <div
                  key={c.titre}
                  className={
                    c.forme ? `acc-case acc-case-${c.forme}` : "acc-case"
                  }
                  data-reveal=""
                  style={variables({ "--i": k })}
                >
                  <span className="acc-case-signe" aria-hidden="true">
                    {c.signe}
                  </span>
                  <h3>{c.titre}</h3>
                  <p>{c.corps}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Les avis ─────────────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="avis">
          <div className="acc-w acc-avis">
            <div data-reveal="">
              <span className="acc-tag">{AVIS.surtitre}</span>
              <h2 className="acc-titre-cote">
                {AVIS.titre.avant}{" "}
                <span className="acc-s">{AVIS.titre.fin}</span>
              </h2>
              <p>{AVIS.corps}</p>
              <Bouton
                lien={AVIS.bouton.lien}
                aspect="or"
                className="acc-avis-bouton"
              >
                {AVIS.bouton.libelle}
              </Bouton>
              {/* WCAG 2.2.2 : tout ce qui bouge en boucle peut être arrêté.
                  Le second bouton de pause ; il reste là sous mouvement
                  réduit ET sur téléphone, où les bandes défilent encore. */}
              <p>
                <BoutonPause fige={fige} basculer={basculerLaPause} />
              </p>
            </div>
            <div
              className="acc-mur"
              role="group"
              aria-label={AVIS.groupe}
              tabIndex={murDefilable ? 0 : undefined}
            >
              <ColonneAvis colonne={1} />
              <ColonneAvis colonne={2} />
            </div>
          </div>
        </section>

        {/* ── Boîte à outils ───────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="outils">
          <div className="acc-w">
            <Intro
              surtitre={OUTILS.surtitre}
              titre={OUTILS.titre}
              corps={OUTILS.corps}
            />
            <ul className="acc-outils">
              {OUTILS.ressources.map((ressource, k) => (
                <li key={ressource.titre} data-reveal="" style={variables({ "--i": k })}>
                  <span className="acc-outil-etiquette">{OUTILS.etiquette}</span>
                  <h3>{ressource.titre}</h3>
                  <p>{ressource.corps}</p>
                  <Bouton
                    lien={ressource.lien}
                    aspect="clair"
                    externe
                    className="acc-outil-bouton"
                  >
                    {ressource.bouton}
                  </Bouton>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Questions fréquentes ─────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="questions">
          <div className="acc-w acc-faq">
            <div data-reveal="">
              <span className="acc-tag">{QUESTIONS.surtitre}</span>
              <h2 className="acc-titre-cote">
                {QUESTIONS.titre.avant}{" "}
                <span className="acc-s">{QUESTIONS.titre.fin}</span>
              </h2>
              <p>{QUESTIONS.corps}</p>
            </div>
            <div data-reveal="">
              {QUESTIONS.liste.map((question, k) => (
                <details key={question.q} open={k === 0}>
                  <summary>{question.q}</summary>
                  <p>{question.r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ── Fin ──────────────────────────────────────────────────────── */}
        <section className="acc-fin" id="contact">
          <div className="acc-w">
            <h2>{FIN.titre}</h2>
            <p className="acc-fin-corps">{FIN.corps}</p>
            <Bouton lien={FIN.bouton.lien} aspect="noir" externe>
              {FIN.bouton.libelle}
            </Bouton>
            <div className="acc-question">
              <div>
                <h3>{FIN.question.titre}</h3>
                <p>{FIN.question.corps}</p>
              </div>
              <Bouton
                lien={FIN.question.lien}
                aspect="clair"
                className="acc-question-bouton"
              >
                {FIN.question.adresse}
              </Bouton>
            </div>
          </div>
          <div className="acc-grand" aria-hidden="true">
            <div className="acc-grand-piste">
              {[0, 1, 2, 3].map((k) => (
                <span key={k}>{FIN.bande}</span>
              ))}
            </div>
          </div>
        </section>
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}
