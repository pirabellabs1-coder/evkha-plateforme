/** Page publique des partenaires professionnels (`/partenaires`) — reprise de
 *  `evkha.fr/partenairespro`, dans le langage visuel de l'accueil et de la
 *  page des études.
 *
 * C'est la page qui vend les abonnements aux professionnels (coachs, agences,
 * cabinets, réseaux d'accompagnement) : le visiteur y choisit sa formule, puis
 * crée son compte.
 *
 * ## Refonte du 19/11/2026 : la forme change, pas ce que la page dit
 *
 * Tous les blocs d'avant sont là, avec leur texte de `contenu.ts` : ouverture
 * (titre en trois lignes, accroche, corps, signature), preuves chiffrées, le
 * principe en quatre étapes et son bandeau « 1 crédit = 1 livrable », les
 * formules, « pour qui », le calcul, la fondatrice, les questions, l'appel
 * final, le renvoi vers les études à l'unité. Ce que la nouvelle forme ajoute
 * — l'italique d'un titre, les surtitres, les phrases d'état — et les courtes
 * phrases que l'ancienne page écrivait dans son TSX sont dans
 * `contenuPartenaires.ts`. La barre, le menu, le pied (liens légaux compris),
 * les boutons et la feuille de base sont ceux du socle commun (`EnTeteSite`,
 * `PiedSite`, `PiecesSite`, `site.ts`, `Site.css`) : l'ancien menu et le
 * pied propre à la page ont disparu (règle 5).
 *
 * L'ancienne feuille de la page (classes `pp-`) n'existe plus : le portail et
 * le tunnel d'achat, qui s'en servaient encore, sont passés au socle. Celle
 * de cette page est `PartenairesPro.css`, classes `pro-`.
 *
 * ## Deux principes de construction, inchangés
 *
 * 1. **Les chiffres viennent du serveur.** Prix mensuel, crédits inclus,
 *    crédit supplémentaire, coût par livrable : tout est lu dans
 *    `/api/public/formules/`, qui le tient de la table `Formule`. Le coût par
 *    livrable est CALCULÉ PAR LE SERVEUR et jamais recalculé ici — deux
 *    formules de calcul finiraient par diverger (règle 5). La fourchette du
 *    « calcul » est déduite des formules reçues, pas écrite.
 *
 * 2. **Aucun tarif n'est affiché tant qu'il n'est pas chargé**, et une panne
 *    ne se lit pas comme un vide. Chaque emplacement de prix dit s'il attend,
 *    s'il a échoué ou si le catalogue ne porte rien ; une seule région
 *    d'alerte, en haut de page et toujours dans le DOM, annonce la panne
 *    (règle 1). Une réponse 200 mal formée est une panne : `chargerFormules`
 *    lève alors une erreur. Une formule dont le prix n'est pas un montant
 *    strictement positif n'affiche pas « 0 € » : elle se dit indisponible et
 *    son bouton est neutralisé.
 *
 * ## Où mènent les boutons
 *
 * Voir `lienSouscription` : vers la création de compte, la formule dans
 * l'adresse — exactement comme avant. Le bouton de l'appel final souscrit à
 * la formule que le SERVEUR met en avant (`mise_en_avant`) ; l'ancienne page
 * y écrivait le code `pro` en dur. Sans formule mise en avant connue, il
 * renvoie aux formules plutôt que vers une formule devinée.
 *
 * ## Le mouvement réduit RÉDUIT, il ne supprime pas
 *
 * Même politique que l'accueil (décision du client du 19/11/2026) : sous
 * `prefers-reduced-motion`, les blocs apparaissent encore au défilement, en
 * fondu et sans translation — d'où l'option passée à `useReveler` —, le ruban
 * défile au ralenti. Deux boutons de pause l'arrêtent (WCAG 2.2.2). Jamais de
 * révélation sur l'ouverture ni sur le `h1` : le texte que les moteurs et le
 * lecteur d'écran lisent en premier n'attend personne.
 */
import { useRef, type ReactNode } from "react";

import {
  APPEL_FINAL,
  CALCUL,
  CONTACT_EMAIL,
  FAQ,
  FONDATRICE,
  FORMULES_SOUS_TITRES,
  HERO,
  POUR_QUI,
  PREUVES,
  PRINCIPE,
} from "./contenu";
import {
  BANDEAU_DU_PRINCIPE,
  DEMONSTRATION,
  DESCRIPTION_DE_LA_PAGE_PRO,
  FIN_PRO,
  FORMULES_PRO,
  ID_DES_FORMULES,
  OUVERTURE_PRO,
  PASSERELLE_PRO,
  PORTRAIT_PRO,
  RUBAN_PRO,
  TITRES_PRO,
  TITRE_DE_LA_PAGE_PRO,
  type DeuxTemps,
} from "./contenuPartenaires";
import { ID_DU_CONTENU, LIENS, TARIFS } from "./contenuSite";
import { chargerFormules, euros, type FormulePublique } from "./donnees";
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
  useTitreDePage,
  variables,
  type Tarif,
} from "./site";
// Le socle d'abord, la feuille de la page ensuite : à spécificité égale, c'est
// la page qui a le dernier mot.
import "./Site.css";
import "./PartenairesPro.css";

/** Destination du bouton « Souscrire ».
 *
 * Vers la création de compte, pas vers la connexion : le visiteur qui clique
 * n'a par définition pas encore de compte, et lui présenter un écran de
 * connexion est le meilleur moyen de le perdre.
 *
 * La formule voyage dans l'adresse. Le prestataire de paiement n'étant pas
 * branché, l'inscription enregistre l'intention sans rien encaisser ni
 * créditer — voir `organisations/inscription.py`. Le jour où Stripe arrive,
 * c'est cette fonction qui mènera au paiement.
 */
function lienSouscription(code: string): string {
  return `/inscription?formule=${encodeURIComponent(code)}`;
}

/** Les formules que la page peut montrer, dans l'ordre du serveur.
 *
 * Une entrée sans code ni libellé n'est pas une formule : on ne saurait ni la
 * nommer ni y souscrire. Tout le reste s'affiche — y compris une formule sans
 * prix, qui se dit indisponible (voir `Formule`). */
function presentables(formules: FormulePublique[]): FormulePublique[] {
  return formules.filter(
    (f) =>
      typeof f?.code === "string" &&
      f.code !== "" &&
      typeof f.libelle === "string" &&
      f.libelle !== "",
  );
}

/** « de 42,90 € à 64,50 € » : le coût par livrable, du plus bas au plus haut,
 *  sur les formules qui SE VENDENT.
 *
 * La fourchette était écrite en dur sur la page d'origine : au premier
 * changement de tarif, elle serait devenue fausse sans que personne ne le
 * remarque. Les coûts sont ceux que le serveur a calculés ; ici on ne fait
 * que prendre le plus petit et le plus grand (`site.bornes`, qui écarte un
 * coût à zéro). `null` si aucune formule n'en porte. */
function fourchette(formules: FormulePublique[]): string | null {
  const b = bornes(
    formules
      .filter((f) => lisible(f.prix_mensuel_cents))
      .map((f) => f.cout_par_livrable_cents),
  );
  if (!b) return null;
  return b.bas === b.haut
    ? euros(b.bas)
    : `de ${euros(b.bas)} à ${euros(b.haut)}`;
}

function numero(rang: number): string {
  return String(rang + 1).padStart(2, "0");
}

/** La première colonne du calcul est le coût par livrable, rempli à
 *  l'exécution (`valeur: null` dans `contenu.ts`) ; les autres sont les gains
 *  que la cliente chiffre elle-même. */
const [COLONNE_DU_COUT, ...AUTRES_GAINS] = CALCUL.colonnes;

/** Le courriel de l'appel final, objet prérempli. */
const COURRIEL = `${LIENS.courriel}?subject=${encodeURIComponent(FIN_PRO.objetDuCourriel)}`;

/** Pastille à coche dorée. La coche est décorative : elle double une
 *  information déjà portée par le texte, et un lecteur d'écran qui
 *  l'annoncerait dirait « coche » avant chaque ligne sans rien apporter. */
function Coche() {
  return (
    <span className="pro-coche" aria-hidden="true">
      ✓
    </span>
  );
}

/** Un titre en deux temps : la fin en italique (Fraunces). */
function EnDeuxTemps({ titre }: { titre: DeuxTemps }) {
  return (
    <>
      {titre.avant} <span className="acc-s">{titre.fin}</span>
    </>
  );
}

/** L'introduction d'une section : surtitre, titre, puis le texte. Même
 *  habillage que sur l'accueil (`.acc-intro`, `Site.css`). */
function Entree({
  surtitre,
  titre,
  children,
}: {
  surtitre: string;
  titre: DeuxTemps;
  children?: ReactNode;
}) {
  return (
    <div className="acc-intro" data-reveal="">
      <div>
        <span className="acc-tag">{surtitre}</span>
        <h2>
          <EnDeuxTemps titre={titre} />
        </h2>
      </div>
      {children}
    </div>
  );
}

/** Une formule. Quatre étages, les mêmes d'une carte à l'autre et alignés par
 *  la grille (voir `.pro-formules`) : à qui elle s'adresse et son nom ; son
 *  prix et ce que coûte un livrable ; ce qu'elle comprend ; le bouton. On
 *  compare donc les quatre formules en lisant une ligne.
 *
 *  Tous les nombres viennent de `formule` — du serveur. Un montant qui n'est
 *  pas strictement positif n'est pas affiché : sans prix, la formule se dit
 *  indisponible et son bouton est neutralisé ; sans coût ou sans tarif de
 *  crédit supplémentaire, la ligne correspondante est omise plutôt que
 *  d'annoncer « 0 € ». */
function Formule({ formule, rang }: { formule: FormulePublique; rang: number }) {
  const enAvant = formule.mise_en_avant === true;
  const vendable = lisible(formule.prix_mensuel_cents);
  const cible = FORMULES_SOUS_TITRES[formule.code];
  const credits = formule.credits_par_echeance;
  const avantages = Array.isArray(formule.avantages) ? formule.avantages : [];

  return (
    <li
      className={enAvant ? "pro-formule pro-formule-avant" : "pro-formule"}
      data-code={formule.code}
      data-reveal=""
      style={variables({ "--i": rang })}
    >
      <div className="pro-formule-tete">
        {/* La mise en avant ne tient pas à la seule couleur de la carte :
            elle est écrite. */}
        {enAvant && <p className="pro-formule-marque">{FORMULES_PRO.enAvant}</p>}
        {cible && <small className="pro-formule-cible">{cible}</small>}
        <h3>{formule.libelle}</h3>
      </div>

      <div className="pro-formule-prix">
        {vendable ? (
          <p className="pro-prix">
            {euros(formule.prix_mensuel_cents)}{" "}
            <span className="pro-prix-mention">{FORMULES_PRO.parMois}</span>
          </p>
        ) : (
          <p className="pro-prix-absent">{TARIFS.absent}</p>
        )}
        {vendable && lisible(formule.cout_par_livrable_cents) && (
          <p className="pro-cout">
            {FORMULES_PRO.coutAvant}{" "}
            <b>{euros(formule.cout_par_livrable_cents)}</b>{" "}
            {FORMULES_PRO.coutApres}
          </p>
        )}
      </div>

      <div className="pro-formule-corps">
        <p className="pro-quoi">{FORMULES_PRO.quoi}</p>
        <ul className="pro-points">
          {Number.isInteger(credits) && credits > 0 && (
            <li>
              <Coche />
              <span>
                <b>{FORMULES_PRO.credits(credits)}</b> {FORMULES_PRO.chaqueMois}
              </span>
            </li>
          )}
          {lisible(formule.prix_credit_supplementaire_cents) && (
            <li>
              <Coche />
              <span>
                {FORMULES_PRO.creditSupplementaire}{" "}
                {euros(formule.prix_credit_supplementaire_cents)}
              </span>
            </li>
          )}
          {avantages.map((avantage) => (
            <li key={avantage}>
              <Coche />
              <span>{avantage}</span>
            </li>
          ))}
        </ul>
      </div>

      <Bouton
        lien={lienSouscription(formule.code)}
        aspect={enAvant ? "or" : "noir"}
        inactif={!vendable}
        className="pro-formule-bouton"
      >
        {FORMULES_PRO.souscrire(formule.libelle)}
      </Bouton>
    </li>
  );
}

/** Le coût par livrable de la démonstration, ou la phrase qui dit pourquoi il
 *  manque : attente, panne, ou aucune formule à vendre. */
function CoutParLivrable({ tarif }: { tarif: Tarif }) {
  if (tarif.etat !== "connu") {
    return <p className="pro-demo-absent">{TARIFS[tarif.etat]}</p>;
  }
  return (
    <>
      <p className="pro-demo-valeur">{tarif.texte}</p>
      <p className="pro-demo-mention">{DEMONSTRATION.mentionDuCout}</p>
    </>
  );
}

export function Partenaires() {
  const chargement = useChargement(chargerFormules);
  const menu = useMenu();
  const { fige, basculer: basculerLaPause } = usePause();
  const page = useRef<HTMLDivElement>(null);

  // La clé : les cartes de formule arrivent après le premier rendu, et
  // doivent être observées à leur tour. L'option : sur cette page comme sur
  // l'accueil, le mouvement réduit garde la révélation (en fondu seul, voir
  // `Site.css`) au lieu de tout afficher d'emblée.
  useReveler(page, chargement.etat, { memeEnMouvementReduit: true });
  useAimants(page);
  useTitreDePage(TITRE_DE_LA_PAGE_PRO, DESCRIPTION_DE_LA_PAGE_PRO);

  const formules =
    chargement.etat === "recu" ? presentables(chargement.donnees) : [];
  const enPanne = chargement.etat === "panne";
  // Sur les formules AFFICHÉES : la fourchette ne compte pas une entrée que
  // la page ne montre pas.
  const cout = tarifDe(chargement, (liste) => fourchette(presentables(liste)));
  // L'appel final souscrit à la formule que le serveur met en avant, si elle
  // se vend. Sinon il renvoie aux formules plutôt que vers un lien deviné.
  const conseillee =
    formules.find(
      (f) => f.mise_en_avant === true && lisible(f.prix_mensuel_cents),
    ) ?? null;

  return (
    <div className={fige ? "acc pro acc-fige" : "acc pro"} ref={page}>
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
              {TARIFS.alerte} {TARIFS.alerteSuite}{" "}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          )}
        </div>

        {/* ── Ouverture ────────────────────────────────────────────────── */}
        <div className="pro-ouverture">
          <div className="acc-w acc-pause-rang">
            <BoutonPause
              fige={fige}
              basculer={basculerLaPause}
              className="acc-pause-haut"
            />
          </div>
          <div className="acc-w pro-ouverture-grille">
            <div className="pro-ouverture-texte">
              <span className="acc-tag acc-entre">{OUVERTURE_PRO.surtitre}</span>
              {/* Trois lignes, coupées comme la cliente les a écrites ; la
                  dernière en italique. L'espace entre deux lignes garde les
                  mots séparés pour un lecteur d'écran. */}
              <h1>
                {HERO.titre.map((ligne, k) => (
                  <span className="acc-ligne-titre" key={ligne}>
                    <span className={k === HERO.titre.length - 1 ? "acc-s" : undefined}>
                      {ligne}
                    </span>{" "}
                  </span>
                ))}
              </h1>
              <p className="pro-accroche acc-entre" style={variables({ "--i": 1 })}>
                {HERO.accroche}
              </p>
              <p className="pro-corps acc-entre" style={variables({ "--i": 2 })}>
                {HERO.corps[0]}
              </p>
              {/* La promesse faite au professionnel, dans les mots de la
                  cliente : il reste l'interlocuteur de son client. */}
              {HERO.corps.slice(1).map((paragraphe) => (
                <p
                  key={paragraphe}
                  className="pro-promesse acc-entre"
                  style={variables({ "--i": 3 })}
                >
                  {paragraphe}
                </p>
              ))}
              {/* Deux gestes, deux poids. Le visiteur nouveau va aux formules
                  — c'est l'action que la page existe pour obtenir. L'abonné
                  qui revient se connecte — action secondaire. Une ancre et
                  non un défilement scripté : le lien marche aussi depuis un
                  partage direct de l'URL. */}
              <div className="pro-appels acc-entre" style={variables({ "--i": 4 })}>
                <Bouton lien={OUVERTURE_PRO.formules.lien} aspect="noir" className="pro-btn">
                  {OUVERTURE_PRO.formules.libelle}
                </Bouton>
                <Bouton lien={OUVERTURE_PRO.espace.lien} aspect="clair" className="pro-btn">
                  {OUVERTURE_PRO.espace.libelle}
                </Bouton>
              </div>
            </div>

            {/* Le cadre fixe la place de l'image : ses attributs donnent le
                ratio, la feuille la taille — rien ne saute au chargement. La
                signature de la cliente est posée sur le cadre. */}
            <div className="pro-cadre acc-entre" style={variables({ "--i": 2 })}>
              <div className="pro-cadre-bord">
                <img
                  className="pro-image"
                  src={OUVERTURE_PRO.image.adresse}
                  alt={OUVERTURE_PRO.image.alt}
                  width={OUVERTURE_PRO.image.largeur}
                  height={OUVERTURE_PRO.image.hauteur}
                  decoding="async"
                />
              </div>
              <p className="pro-signature">{HERO.signature}</p>
            </div>

            {/* Les preuves chiffrées, telles que la cliente les écrit. */}
            <ul
              className="pro-preuves acc-entre"
              aria-label={OUVERTURE_PRO.nomDesPreuves}
              style={variables({ "--i": 5 })}
            >
              {PREUVES.map((preuve) => (
                <li key={preuve.libelle}>
                  <b>{preuve.valeur}</b>
                  <span className="pro-preuve-libelle">{preuve.libelle}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* ── Le principe ──────────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="principe">
          <div className="acc-w">
            <Entree surtitre={PRINCIPE.surtitre} titre={TITRES_PRO.principe} />

            {/* Une liste ORDONNÉE : la numérotation encode une vraie séquence
                — choisir, cadrer, produire, livrer. Le numéro affiché est
                donc décoratif : la liste dit déjà l'ordre. */}
            <ol className="pro-etapes" data-reveal="">
              {PRINCIPE.etapes.map((etape, k) => (
                <li key={etape.titre}>
                  <span className="pro-etape-numero" aria-hidden="true">
                    {numero(k)}
                  </span>
                  <h3>{etape.titre}</h3>
                  <p>{etape.corps}</p>
                </li>
              ))}
            </ol>

            <p className="pro-bandeau" data-reveal="">
              <strong>{BANDEAU_DU_PRINCIPE.fort}</strong>
              {BANDEAU_DU_PRINCIPE.suite}
            </p>
          </div>
        </section>

        {/* ── Les formules ─────────────────────────────────────────────── */}
        {/* `id` : cible du bouton de l'ouverture. La marge de défilement du
            socle (`scroll-padding-top`) garde le titre sous la barre fixe. */}
        <section className="acc-section acc-section-suite" id={ID_DES_FORMULES}>
          <div className="acc-w">
            <Entree surtitre={FORMULES_PRO.surtitre} titre={TITRES_PRO.formules}>
              <p>{FORMULES_PRO.intro}</p>
            </Entree>

            {enPanne && <p className="acc-panne">{TARIFS.rappel}</p>}

            {chargement.etat === "attente" && (
              <>
                <p className="pro-attente" role="status">
                  {FORMULES_PRO.attente}
                </p>
                {/* La forme des cartes, sans un seul chiffre. Immobile. */}
                <div className="pro-gabarit" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              </>
            )}

            {chargement.etat === "recu" && formules.length === 0 && (
              <p className="pro-vide">
                {FORMULES_PRO.vide} {TARIFS.alerteSuite}{" "}
                <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
              </p>
            )}

            {formules.length > 0 && (
              <ul className="pro-formules">
                {formules.map((formule, k) => (
                  <Formule key={formule.code} formule={formule} rang={k} />
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* ── Ruban ────────────────────────────────────────────────────── */}
        <div className="acc-ruban pro-ruban" aria-hidden="true">
          <div className="acc-ruban-piste">
            {[...RUBAN_PRO, ...RUBAN_PRO].map((mot, k) => (
              <span key={k}>{mot}</span>
            ))}
          </div>
        </div>
        {/* WCAG 2.2.2 : ce qui bouge en boucle peut être arrêté là où il
            bouge. Le second bouton de pause, même état que le premier. */}
        <p className="acc-w pro-pause-rang">
          <BoutonPause fige={fige} basculer={basculerLaPause} />
        </p>

        {/* ── Pour qui ─────────────────────────────────────────────────── */}
        <section className="acc-section pro-section-apres-ruban" id="pour-qui">
          <div className="acc-w">
            <h2 className="pro-titre-seul" data-reveal="">
              <EnDeuxTemps titre={TITRES_PRO.pourQui} />
            </h2>
            <ul className="pro-cibles">
              {POUR_QUI.cibles.map((cible, k) => (
                <li key={cible.titre} data-reveal="" style={variables({ "--i": k })}>
                  <span className="pro-ornement" aria-hidden="true">
                    ✦
                  </span>
                  <h3>{cible.titre}</h3>
                  <p>{cible.corps}</p>
                  <p className="pro-cible-avec">{cible.avec}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Le calcul : une démonstration ────────────────────────────── */}
        <section className="acc-section pro-bande" id="calcul">
          <div className="acc-w">
            <Entree surtitre={CALCUL.surtitre} titre={TITRES_PRO.calcul} />

            {/* À gauche ce qu'un livrable coûte à l'abonné — calculé sur les
                formules reçues ; en face ce qu'un cabinet le facture — lu
                dans la phrase de la cliente, qui suit en toutes lettres. */}
            <div
              className={DEMONSTRATION.cabinet ? "pro-demo" : "pro-demo pro-demo-seul"}
              data-reveal=""
            >
              <div className="pro-demo-cout">
                <h3>{COLONNE_DU_COUT.titre}</h3>
                <CoutParLivrable tarif={cout} />
              </div>
              {DEMONSTRATION.cabinet && (
                <>
                  <span className="pro-demo-signe" aria-hidden="true">
                    →
                  </span>
                  <div className="pro-demo-cabinet">
                    <p className="pro-demo-etiquette">
                      {DEMONSTRATION.etiquetteDuCabinet}
                    </p>
                    <p className="pro-demo-valeur">
                      <span className="pro-demo-avant">
                        {DEMONSTRATION.cabinet.avant}
                      </span>{" "}
                      {DEMONSTRATION.cabinet.montant}
                    </p>
                    <p className="pro-demo-mention">
                      {DEMONSTRATION.mentionDuCabinet}
                    </p>
                  </div>
                </>
              )}
              <p className="pro-demo-corps">{COLONNE_DU_COUT.corps}</p>
            </div>

            <ul className="pro-gains" aria-label={DEMONSTRATION.nomDesGains}>
              {AUTRES_GAINS.map((gain, k) => (
                <li key={gain.titre} data-reveal="" style={variables({ "--i": k })}>
                  <b className="pro-gain-valeur">{gain.valeur}</b>
                  <h3>{gain.titre}</h3>
                  <p>{gain.corps}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── La fondatrice ────────────────────────────────────────────── */}
        <section className="acc-section" id="fondatrice">
          <div className="acc-w pro-fondatrice">
            <div className="pro-cadre pro-cadre-portrait" data-reveal="">
              <div className="pro-cadre-bord">
                <img
                  className="pro-portrait"
                  src={PORTRAIT_PRO.adresse}
                  alt={PORTRAIT_PRO.alt}
                  width={PORTRAIT_PRO.largeur}
                  height={PORTRAIT_PRO.hauteur}
                  loading="lazy"
                  decoding="async"
                />
              </div>
            </div>
            <div className="pro-fondatrice-texte" data-reveal="">
              <span className="acc-tag">{FONDATRICE.surtitre}</span>
              <h2 className="acc-titre-cote">
                <EnDeuxTemps titre={TITRES_PRO.fondatrice} />
              </h2>
              <p className="pro-fondatrice-corps">{FONDATRICE.corps}</p>
            </div>
          </div>
        </section>

        {/* ── Vos questions ────────────────────────────────────────────── */}
        <section className="acc-section acc-section-suite" id="questions">
          <div className="acc-w acc-faq">
            <div data-reveal="">
              <span className="acc-tag">{FAQ.surtitre}</span>
              <h2 className="acc-titre-cote">
                <EnDeuxTemps titre={TITRES_PRO.faq} />
              </h2>
            </div>
            <div data-reveal="">
              {FAQ.questions.map((question, k) => (
                <details key={question.q} open={k === 0}>
                  <summary>{question.q}</summary>
                  <p>{question.r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ── Passerelle : les études à l'unité ────────────────────────── */}
        <section className="acc-section acc-section-suite" id="a-l-unite">
          <div className="acc-w">
            <article className="pro-porte" data-reveal="">
              <div>
                <span className="acc-tag">{PASSERELLE_PRO.surtitre}</span>
                <h2>
                  <EnDeuxTemps titre={PASSERELLE_PRO.titre} />
                </h2>
              </div>
              <div className="pro-porte-suite">
                <p>{PASSERELLE_PRO.corps}</p>
                <Bouton lien={PASSERELLE_PRO.lien} aspect="clair" className="pro-btn">
                  {PASSERELLE_PRO.bouton}
                </Bouton>
              </div>
            </article>
          </div>
        </section>

        {/* ── Appel final ──────────────────────────────────────────────── */}
        <section className="acc-fin pro-fin" id="souscrire">
          <div className="acc-w">
            <span className="acc-tag">{APPEL_FINAL.surtitre}</span>
            <h2>
              <EnDeuxTemps titre={TITRES_PRO.appel} />
            </h2>
            {APPEL_FINAL.corps.map((paragraphe) => (
              <p key={paragraphe} className="acc-fin-corps">
                {paragraphe}
              </p>
            ))}
            <div className="pro-appels pro-appels-centre">
              <Bouton
                lien={
                  conseillee
                    ? lienSouscription(conseillee.code)
                    : `#${ID_DES_FORMULES}`
                }
                aspect="noir"
                className="pro-btn"
              >
                {conseillee
                  ? FIN_PRO.choisir(conseillee.libelle)
                  : FIN_PRO.voirLesFormules}
              </Bouton>
              <Bouton lien={COURRIEL} aspect="clair" className="pro-btn">
                {FIN_PRO.ecrire}
              </Bouton>
            </div>
          </div>
        </section>
      </main>

      <PiedSite inerte={menu.ouvert} />
    </div>
  );
}
