/** Les formations achetées, et la lecture de l'une d'elles.
 *
 * Deux écrans, un seul appel (`GET /api/espace/formations/`) : la liste
 * (`/espace/formations`) et une formation ouverte
 * (`/espace/formations/$slug`). Le serveur ne rend que les formations que
 * l'organisation a ACHETÉES, avec le contenu de leurs leçons : il n'existe
 * aucun paramètre par lequel demander celle d'un autre. Un slug qui n'est pas
 * dans la réponse est donc dit « pas dans votre espace », jamais deviné.
 *
 * ## Une panne n'est pas une absence
 *
 * « Vous n'avez pas encore de formation » ne s'affiche que sur une liste
 * REÇUE et vide. Un appel en échec, ou une réponse sans la liste attendue
 * (`espaceApi.mesFormations` la lève comme une erreur), se dit comme une
 * panne (règle 1).
 *
 * ## Ce que montre une leçon
 *
 * - vidéo : le lecteur de l'hébergeur quand on sait le construire (YouTube,
 *   Vimeo), le lecteur du navigateur pour un fichier, sinon un lien — voir
 *   `lecteurVideo.ts`, qui n'accepte que `https://` ;
 * - texte : des paragraphes, retours à la ligne respectés. Le texte est rendu
 *   par React comme du TEXTE : une balise saisie s'affiche, elle ne
 *   s'exécute pas. Aucun HTML n'est injecté ;
 * - document : un bouton qui RELIT la liste au serveur avant d'ouvrir le
 *   fichier. Le lien est signé pour une heure : celui de la page affichée
 *   depuis ce matin ne vaut plus rien, et on ne le garde pas ;
 * - quiz : pas encore lisible ici, et dit comme tel.
 *
 * ## Le suivi : progression, traces, présence
 *
 * Le serveur tient le suivi de chaque personne (`catalog/suivi.py`), et c'est
 * lui qui compte : la barre et « X leçons sur Y terminées » affichent la
 * progression qu'il rend, jamais un calcul de l'écran. Une leçon ouverte
 * envoie `{"ouverte": true}` une fois ; « Marquer comme terminée » envoie
 * `terminee`, et la réponse met à jour la barre et la coche du programme. Une
 * trace qui ne s'enregistre pas se dit, et ne bloque pas la lecture.
 *
 * Un accès a un dernier jour (« Accès jusqu'au … »), ou n'en a pas. Échu, la
 * formation reste affichée — sans programme —, avec la date de fin, sa page
 * pour la racheter et le contact.
 *
 * Les séances en présentiel de la formation se signent ici : le formulaire
 * n'apparaît que si le serveur dit la séance `signable`.
 *
 * La dernière leçon ouverte, elle, reste retenue dans le stockage de CE
 * navigateur (`localStorage`, lecture et écriture sous `try/catch`), pour
 * rouvrir la formation où on l'a laissée.
 *
 * ## Titres
 *
 * Le `h1` est celui de la coquille (`ENTETES`, `Coquille.tsx`). Dans la
 * liste, la carte n'a pas de titre — il redirait le `h1` — et chaque formation
 * est un `h2`. Dans une formation ouverte : le titre de la formation en `h2`
 * (la carte), « Programme » et le titre de la leçon en `h3`. Au changement de
 * leçon, le focus va au titre de la leçon — sur
 * téléphone, où le programme est AU-DESSUS, c'est aussi ce qui l'amène à
 * l'écran.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";

import {
  ErreurApi,
  espaceApi,
  type FormationAchetee,
  type LeconAchetee,
  type ModuleAchete,
  type ProgressionDeFormation,
  type SeanceDeLEleve,
  type SuiviDeLecon,
} from "../api";
import * as f from "../format";
import { Carte, ErreurDeChargement, Squelette, Vide } from "../composants/Interface";
import { lecteurDe, lienDeDocument } from "../lecteurVideo";
import "./MesFormations.css";

/** La clé de cache des deux écrans : ouvrir une formation depuis la liste ne
 *  refait pas l'appel. */
const CLE = ["espace", "formations"] as const;

const INSECABLE = "\u00a0";

// ── Petits outils ───────────────────────────────────────────────────────────

/** « 1 module », « 3 modules ». */
function compte(nombre: number, mot: string): string {
  return `${nombre}${INSECABLE}${mot}${nombre > 1 ? "s" : ""}`;
}

/** Les modules d'une formation, tels qu'on peut les afficher. Une réponse
 *  sans la liste attendue vaut « aucun module ». */
function modulesDe(formation: FormationAchetee): ModuleAchete[] {
  return Array.isArray(formation.modules) ? formation.modules : [];
}

function leconsDe(module: ModuleAchete): LeconAchetee[] {
  return Array.isArray(module.lecons) ? module.lecons : [];
}

/** Une leçon, avec le module qui la porte. */
type Etape = { lecon: LeconAchetee; module: ModuleAchete };

/** Toutes les leçons d'une formation, dans l'ordre du programme : c'est la
 *  suite que parcourent « Leçon précédente » et « Leçon suivante ». */
function etapesDe(formation: FormationAchetee): Etape[] {
  return modulesDe(formation).flatMap((module) =>
    leconsDe(module).map((lecon) => ({ lecon, module })),
  );
}

/** La nature d'une leçon, en français. Une nature inconnue n'affiche pas le
 *  code du serveur à la place. */
const NATURES: Record<string, string> = {
  video: "Vidéo",
  texte: "Texte",
  document: "Document",
  quiz: "Quiz",
};

function nature(lecon: LeconAchetee): string | null {
  return Object.prototype.hasOwnProperty.call(NATURES, lecon.nature)
    ? NATURES[lecon.nature]
    : null;
}

/** « 12 min », « 1 h 05 » — ou rien quand le serveur n'en rend pas : une
 *  leçon s'affiche sans durée, pas avec une durée nulle. */
function duree(minutes: unknown): string | null {
  if (typeof minutes !== "number" || !Number.isFinite(minutes) || minutes <= 0) {
    return null;
  }
  const entieres = Math.round(minutes);
  if (entieres < 60) return `${entieres}${INSECABLE}min`;
  const heures = Math.floor(entieres / 60);
  const reste = entieres % 60;
  return reste === 0
    ? `${heures}${INSECABLE}h`
    : `${heures}${INSECABLE}h${INSECABLE}${String(reste).padStart(2, "0")}`;
}

/** L'initiale du titre, pour une formation sans image. */
function initiale(titre: string): string {
  const mot = titre.replace(/^(le|la|les|l'|un|une|du|de|des)\s+/i, "").trim();
  return (mot[0] ?? "?").toUpperCase();
}

// ── La dernière leçon ouverte ───────────────────────────────────────────────
//
// Le suivi, lui, est tenu par le serveur ; ceci n'est qu'un marque-page de ce
// navigateur. Le stockage peut être refusé — navigation privée, quota,
// réglage du navigateur : la lecture rend alors `null`, l'écriture ne fait
// rien, et la formation s'ouvre sur sa première leçon.

function cleDeLaDerniere(slug: string): string {
  return `evkha_formation_derniere_lecon:${slug}`;
}

function lireLaDerniere(slug: string): string | null {
  try {
    return window.localStorage.getItem(cleDeLaDerniere(slug));
  } catch {
    return null;
  }
}

function retenirLaDerniere(slug: string, leconId: string): void {
  try {
    window.localStorage.setItem(cleDeLaDerniere(slug), leconId);
  } catch {
    // Stockage indisponible : on ne retient rien, la lecture continue.
  }
}

// ── Le suivi : progression, fin d'accès, traces ─────────────────────────────
//
// Tout vient du serveur (`catalog/suivi.py`) : l'écran ne compte pas les
// leçons terminées lui-même, il range la progression que chaque réponse rend.
// Le cache de la liste reste la SEULE source : une leçon marquée ici est
// cochée dans le programme et comptée dans la barre par le même objet.

type ListeDesFormations = { formations: FormationAchetee[] };

/** L'accès est-il échu ? Un serveur qui ne le dit pas n'a rien fermé. */
function estEchue(formation: FormationAchetee): boolean {
  return formation.acces === "echu";
}

/** La progression telle que le serveur la rend, ou `null` s'il n'en dit rien
 *  de lisible : l'écran n'affiche alors aucune barre, plutôt qu'un zéro qu'il
 *  aurait inventé (règle 1). */
function progressionDe(formation: FormationAchetee): ProgressionDeFormation | null {
  const lue = formation.progression;
  if (
    !lue ||
    typeof lue.terminees !== "number" ||
    typeof lue.total !== "number" ||
    lue.total <= 0
  ) {
    return null;
  }
  return lue;
}

/** La phrase d'un refus du serveur, telle qu'il l'a écrite — ou le repli
 *  quand il n'a rien dit (coupure, panne) : « Erreur 500 » n'apprend rien. */
function ditDuRefus(cause: unknown, repli: string): string {
  return cause instanceof ErreurApi && cause.statut < 500 && cause.message
    ? cause.message
    : repli;
}

/** La barre de progression, et la même chose en toutes lettres. */
function Avancee({ formation }: { formation: FormationAchetee }) {
  const progression = progressionDe(formation);
  if (progression === null) return null;
  const { terminees, total } = progression;
  const pourcent = Math.min(
    100,
    Math.max(
      0,
      Math.round(
        typeof progression.pourcent === "number"
          ? progression.pourcent
          : (terminees / total) * 100,
      ),
    ),
  );
  const lu = `${terminees}${INSECABLE}leçon${terminees > 1 ? "s" : ""} sur ${total} terminée${
    terminees > 1 ? "s" : ""
  }`;
  return (
    <div className="frs-avancee">
      <div
        className="jauge"
        role="progressbar"
        aria-valuenow={pourcent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={lu}
        aria-label={`Votre progression dans «${INSECABLE}${formation.titre}${INSECABLE}»`}
      >
        {/* Toute la largeur, décalée de ce qui manque : un `transform` se
            compose sans refaire la mise en page (voir `.jauge`). */}
        <span
          className="jauge-remplissage"
          style={{ transform: `translateX(-${100 - pourcent}%)` }}
        />
      </div>
      <p className="frs-avancee-texte">{lu}</p>
    </div>
  );
}

/** « Accès jusqu'au 20 mai 2027 » — et rien quand l'accès est sans limite. */
function FinDAcces({ formation }: { formation: FormationAchetee }) {
  if (!formation.acces_jusqu_au) return null;
  return <p className="carte-note">Accès jusqu'au {f.jour(formation.acces_jusqu_au)}</p>;
}

/** Un accès échu : la formation reste affichée, sans son programme. On dit
 *  quand il s'est terminé, et par où revenir — la racheter sur sa page, ou
 *  nous écrire. */
function AccesEchu({ formation }: { formation: FormationAchetee }) {
  return (
    <div className="frs-echu">
      <p className="bandeau bandeau-alerte">
        {formation.acces_jusqu_au
          ? `Votre accès à cette formation s'est terminé le ${f.jour(formation.acces_jusqu_au)}.`
          : "Votre accès à cette formation s'est terminé."}{" "}
        Son programme ne s'ouvre plus depuis votre espace.
      </p>
      <div className="frs-echu-liens">
        <a
          className="bouton bouton-principal"
          href={`/formations/${formation.slug}`}
          aria-label={`Racheter la formation «${INSECABLE}${formation.titre}${INSECABLE}»`}
        >
          Racheter cette formation
        </a>
        <a className="bouton bouton-contour" href="/contact">
          Nous contacter
        </a>
      </div>
    </div>
  );
}

/** Range ce qu'une trace de lecture vient de rendre : la leçon cochée ou
 *  décochée, et la progression de SA formation. */
function rangerLeSuivi(avant: ListeDesFormations | undefined, rendu: SuiviDeLecon) {
  if (!avant) return avant;
  return {
    ...avant,
    formations: avant.formations.map((formation) =>
      formation.slug !== rendu.formation
        ? formation
        : {
            ...formation,
            progression: rendu.progression,
            modules: modulesDe(formation).map((module) => ({
              ...module,
              lecons: leconsDe(module).map((lecon) =>
                lecon.id === rendu.lecon.id
                  ? { ...lecon, terminee: rendu.lecon.terminee }
                  : lecon,
              ),
            })),
          },
    ),
  };
}

const PASSAGE_NON_NOTE =
  "Votre passage sur cette leçon n'a pas pu être enregistré. Vous pouvez continuer votre lecture : il sera noté à votre prochaine visite.";

/** Ce que le serveur retient d'une leçon ouverte : qu'elle a été ouverte —
 *  envoyé UNE fois, à l'ouverture — et qu'elle est terminée, quand la personne
 *  le dit.
 *
 *  Une trace qui ne s'enregistre pas se DIT, et ne bloque rien : la leçon
 *  reste lisible, le bouton reste là. Un accès échu entre-temps fait relire
 *  la liste — la page devient alors celle d'un accès terminé. */
function SuiviDeLaLecon({ lecon }: { lecon: LeconAchetee }) {
  const cache = useQueryClient();
  const [erreur, setErreur] = useState("");
  const [annonce, setAnnonce] = useState("");
  /** L'ouverture est déjà partie : le mode strict de React rejoue l'effet. */
  const ouvertureEnvoyee = useRef(false);
  const leconId = lecon.id;
  const terminee = lecon.terminee === true;

  const refuser = useCallback(
    (cause: unknown, repli: string) => {
      setAnnonce("");
      setErreur(ditDuRefus(cause, repli));
      if (cause instanceof ErreurApi && cause.code === "acces_echu") {
        void cache.invalidateQueries({ queryKey: CLE });
      }
    },
    [cache],
  );

  useEffect(() => {
    if (ouvertureEnvoyee.current) return;
    ouvertureEnvoyee.current = true;
    espaceApi.suivreUneLecon(leconId, { ouverte: true }).then(
      (rendu) => cache.setQueryData<ListeDesFormations>(CLE, (avant) => rangerLeSuivi(avant, rendu)),
      (cause: unknown) => refuser(cause, PASSAGE_NON_NOTE),
    );
  }, [cache, leconId, refuser]);

  const bascule = useMutation({
    // Hors connexion, l'envoi part quand même et échoue tout de suite : la
    // panne se dit, le bouton ne reste pas sur « Enregistrement… ».
    networkMode: "always",
    mutationFn: (voulue: boolean) => espaceApi.suivreUneLecon(leconId, { terminee: voulue }),
    onSuccess: (rendu) => {
      cache.setQueryData<ListeDesFormations>(CLE, (avant) => rangerLeSuivi(avant, rendu));
      setErreur("");
      setAnnonce(
        rendu.lecon.terminee
          ? "Leçon marquée comme terminée."
          : "Cette leçon n'est plus marquée comme terminée.",
      );
    },
    onError: (cause: unknown) =>
      refuser(
        cause,
        "Votre choix n'a pas pu être enregistré. Vérifiez votre connexion et réessayez : vous pouvez continuer votre lecture.",
      ),
  });

  return (
    <div className="frs-suivi">
      {/* `aria-disabled` plutôt que `disabled` : le bouton garde le focus
          pendant l'envoi. Le clic, lui, est alors sans effet. */}
      <button
        type="button"
        className={terminee ? "bouton bouton-contour" : "bouton bouton-principal"}
        aria-disabled={bascule.isPending || undefined}
        aria-busy={bascule.isPending || undefined}
        onClick={() => {
          if (bascule.isPending) return;
          setErreur("");
          setAnnonce("");
          bascule.mutate(!terminee);
        }}
      >
        {bascule.isPending
          ? "Enregistrement…"
          : terminee
            ? "Terminée — annuler"
            : "Marquer comme terminée"}
      </button>
      {/* Toujours présent, même vide : une zone d'annonce posée en même temps
          que son texte n'est pas lue. */}
      <p className="frs-suivi-annonce" role="status">
        {annonce}
      </p>
      {erreur && (
        <p className="bandeau bandeau-alerte" role="alert">
          {erreur}
        </p>
      )}
    </div>
  );
}

// ── Les séances en présentiel ───────────────────────────────────────────────

function seancesDe(formation: FormationAchetee): SeanceDeLEleve[] {
  return Array.isArray(formation.seances) ? formation.seances : [];
}

/** Une séance, et ce que la personne peut y faire.
 *
 *  C'est le SERVEUR qui dit si elle peut signer maintenant (`signable`) :
 *  l'écran ne le recalcule pas. L'heure du poste ne sert qu'à choisir la
 *  phrase d'une séance qui ne se signe pas — pas encore, ou plus. */
function Seance({
  slug,
  seance,
  maintenant,
}: {
  slug: string;
  seance: SeanceDeLEleve;
  maintenant: number;
}) {
  const base = useId();
  const cache = useQueryClient();
  const [nom, setNom] = useState("");
  const [erreur, setErreur] = useState("");
  const confirmation = useRef<HTMLParagraphElement>(null);
  /** Vrai entre la signature envoyée d'ici et son affichage : le focus va
   *  alors à la confirmation, le formulaire ayant quitté l'écran. */
  const vientDeSigner = useRef(false);
  const signee = Boolean(seance.signee_le);

  useEffect(() => {
    if (!signee || !vientDeSigner.current) return;
    vientDeSigner.current = false;
    confirmation.current?.focus();
  }, [signee]);

  const signature = useMutation({
    networkMode: "always",
    mutationFn: (dit: string) => espaceApi.signerMaPresence(seance.id, dit),
    onSuccess: ({ emargement }) => {
      vientDeSigner.current = true;
      setErreur("");
      // La date affichée est celle que le serveur a enregistrée.
      cache.setQueryData<ListeDesFormations>(CLE, (avant) =>
        avant
          ? {
              ...avant,
              formations: avant.formations.map((formation) =>
                formation.slug !== slug
                  ? formation
                  : {
                      ...formation,
                      seances: seancesDe(formation).map((autre) =>
                        autre.id === seance.id
                          ? { ...autre, signee_le: emargement.signe_le, signable: false }
                          : autre,
                      ),
                    },
              ),
            }
          : avant,
      );
    },
    onError: (cause: unknown) => {
      // Le refus du serveur, tel qu'il l'a écrit.
      setErreur(
        ditDuRefus(
          cause,
          "Votre signature n'a pas pu être enregistrée. Vérifiez votre connexion et réessayez.",
        ),
      );
      // Un refus sur l'ÉTAT de la séance (déjà signée, annulée, fermée) :
      // l'écran n'est plus à jour, on le relit.
      if (cause instanceof ErreurApi && (cause.statut === 409 || cause.statut === 404)) {
        void cache.invalidateQueries({ queryKey: CLE });
      }
      document.getElementById(`${base}-nom`)?.focus();
    },
  });

  const debut = new Date(seance.debut).getTime();
  const aVenir = Number.isFinite(debut) && debut > maintenant;
  const reperes = [
    f.dateHeureDeParis(seance.debut),
    duree(seance.duree_minutes),
    seance.lieu || null,
  ]
    .filter((repere): repere is string => repere !== null)
    .join(" · ");

  return (
    <li className="frs-seance">
      <h4 className="frs-seance-titre">{seance.intitule}</h4>
      <p className="frs-seance-reperes">{reperes}</p>

      {seance.annulee_le && <p className="frs-seance-etat">Cette séance est annulée.</p>}

      {signee && (
        <p className="frs-seance-etat frs-seance-signee" ref={confirmation} tabIndex={-1}>
          <span aria-hidden="true">✓</span>
          {INSECABLE}Présence signée le {f.dateHeureDeParis(seance.signee_le)}
        </p>
      )}

      {!signee && !seance.annulee_le && seance.signable === true && (
        <form
          className="frs-signature"
          noValidate
          onSubmit={(evenement) => {
            evenement.preventDefault();
            if (signature.isPending) return;
            const dit = nom.trim();
            if (dit === "") {
              setErreur("Écrivez votre nom et votre prénom pour signer.");
              document.getElementById(`${base}-nom`)?.focus();
              return;
            }
            setErreur("");
            signature.mutate(dit);
          }}
        >
          <div className="champ">
            <label className="champ-libelle" htmlFor={`${base}-nom`}>
              Votre nom et prénom
            </label>
            <input
              id={`${base}-nom`}
              className="champ-saisie"
              value={nom}
              maxLength={120}
              autoComplete="name"
              aria-required="true"
              aria-invalid={erreur ? true : undefined}
              aria-describedby={
                erreur ? `${base}-erreur ${base}-aide` : `${base}-aide`
              }
              onChange={(e) => {
                setNom(e.currentTarget.value);
                if (erreur) setErreur("");
              }}
            />
            {erreur && (
              <span className="champ-erreur" id={`${base}-erreur`} role="alert">
                {erreur}
              </span>
            )}
            <span className="champ-aide" id={`${base}-aide`}>
              En signant, vous attestez avoir assisté à cette séance. Une signature ne se
              retire pas.
            </span>
          </div>
          <button
            type="submit"
            className="bouton bouton-principal"
            aria-disabled={signature.isPending || undefined}
            aria-busy={signature.isPending || undefined}
          >
            {signature.isPending ? "Signature…" : "Je signe ma présence"}
          </button>
        </form>
      )}

      {!signee && !seance.annulee_le && seance.signable !== true && (
        <p className="frs-seance-etat">
          {aVenir
            ? "La signature s'ouvrira au début de la séance."
            : "La signature en ligne est fermée. Votre formatrice peut reporter votre signature sur la feuille d'émargement."}
        </p>
      )}
    </li>
  );
}

function SeancesEnPresentiel({ formation }: { formation: FormationAchetee }) {
  const base = useId();
  /** L'heure du poste, relevée une fois à l'arrivée sur l'écran. */
  const [maintenant] = useState(() => Date.now());
  const seances = seancesDe(formation);
  if (seances.length === 0) return null;
  return (
    <section className="frs-seances-bloc" aria-labelledby={`${base}-seances`}>
      <h3 id={`${base}-seances`} className="frs-intertitre">
        Séances en présentiel
      </h3>
      <ul className="frs-seances">
        {seances.map((seance) => (
          <Seance key={seance.id} slug={formation.slug} seance={seance} maintenant={maintenant} />
        ))}
      </ul>
    </section>
  );
}

// ── Le chargement, commun aux deux écrans ───────────────────────────────────

function useMesFormations() {
  return useQuery({ queryKey: CLE, queryFn: espaceApi.mesFormations });
}

// ── La liste ────────────────────────────────────────────────────────────────

function Couverture({ image, titre }: { image: string; titre: string }) {
  return (
    <div className="achat-couverture">
      {image ? (
        <img src={image} alt="" loading="lazy" />
      ) : (
        <span aria-hidden="true">{initiale(titre)}</span>
      )}
    </div>
  );
}

export function MesFormations() {
  const { data, isPending, isError, isRefetchError, error } = useMesFormations();
  if (isPending) return <Squelette lignes={3} />;
  // Rien reçu : on le dit, et on s'arrête là. Surtout pas « aucune
  // formation » à quelqu'un qui en a payé une.
  if (!data) return <ErreurDeChargement quoi="vos formations" erreur={error} />;

  const formations = data.formations;

  return (
    <>
      {isError && (
        <ErreurDeChargement
          quoi="vos formations"
          erreur={error}
          perimees={isRefetchError}
        />
      )}
      {/* Pas de titre de carte : la coquille dit déjà « Mes formations » en
          `h1`, et le redire juste dessous n'apprenait rien. Chaque formation
          est donc un `h2`, sans niveau sauté. */}
      <Carte>
        {formations.length > 0 && (
          <p className="carte-note frs-introduction">
            Accessibles à tout moment, à votre rythme.
          </p>
        )}
        {formations.length === 0 ? (
          // Sous une mise à jour ratée, « aucune » ne se redit pas.
          !isError && (
            <Vide
              titre="Vous n'avez pas encore de formation"
              texte="Les formations auxquelles vous vous inscrivez apparaissent ici, avec tout leur programme, et y restent."
              action={
                <a className="bouton bouton-contour" href="/formations">
                  Découvrir les formations
                </a>
              }
            />
          )
        ) : (
          <ul className="achats-grille">
            {formations.map((formation) => {
              const etapes = etapesDe(formation);
              return (
                <li key={formation.slug} className="achat-carte">
                  <Couverture image={formation.image} titre={formation.titre} />
                  <div className="achat-corps">
                    <h2 className="achat-titre frs-carte-titre">{formation.titre}</h2>
                    {formation.sous_titre && (
                      <p className="carte-note">{formation.sous_titre}</p>
                    )}
                    <p className="carte-note">
                      Achetée le {f.date(formation.achetee_le)}
                    </p>
                    {estEchue(formation) ? (
                      // Échu : le serveur ne rend plus le programme. On ne
                      // compte donc pas « 0 module », on dit ce qui est.
                      <AccesEchu formation={formation} />
                    ) : (
                      <>
                        <p className="carte-note">
                          {compte(modulesDe(formation).length, "module")} ·{" "}
                          {compte(etapes.length, "leçon")}
                        </p>
                        <Avancee formation={formation} />
                        <FinDAcces formation={formation} />
                        <div className="achat-liens">
                          <Link
                            className="bouton bouton-contour frs-ouvrir"
                            to="/espace/formations/$slug"
                            params={{ slug: formation.slug }}
                            aria-label={`Ouvrir la formation «${INSECABLE}${formation.titre}${INSECABLE}»`}
                          >
                            Ouvrir la formation
                          </Link>
                        </div>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Carte>
    </>
  );
}

// ── Une formation ouverte ───────────────────────────────────────────────────

/** Le lien de retour à la liste, en tête de l'écran. */
function Retour() {
  return (
    <p className="frs-retour">
      <Link className="bouton bouton-discret" to="/espace/formations">
        <span aria-hidden="true">←</span>{"\u00a0"}Mes formations
      </Link>
    </p>
  );
}

export function FormationSuivie() {
  const { slug } = useParams({ from: "/espace/formations/$slug" });
  const { data, isPending, isError, isRefetchError, error } = useMesFormations();

  if (isPending) return <Squelette lignes={4} />;
  if (!data) {
    return (
      <>
        <Retour />
        <ErreurDeChargement quoi="votre formation" erreur={error} />
      </>
    );
  }

  const formation = data.formations.find((candidate) => candidate.slug === slug);

  return (
    <>
      <Retour />
      {isError && (
        <ErreurDeChargement
          quoi="votre formation"
          erreur={error}
          perimees={isRefetchError}
        />
      )}
      {formation ? (
        // La clé : passer d'une formation à l'autre repart d'un lecteur neuf
        // (sa dernière leçon, ses modules dépliés).
        <Lecteur key={formation.slug} formation={formation} />
      ) : (
        // La liste est REÇUE, et cette formation n'y est pas : elle n'a pas
        // été achetée par ce compte, ou l'adresse est fausse.
        <Carte>
          <Vide
            titre="Cette formation n'est pas dans votre espace"
            texte="Elle n'a pas été achetée avec ce compte, ou son adresse a changé. Si vous venez de la régler avec une autre adresse e-mail, connectez-vous avec celle-ci."
            action={
              <div className="frs-sorties">
                <Link className="bouton bouton-contour" to="/espace/formations">
                  Voir mes formations
                </Link>
                <a className="bouton bouton-discret" href="/formations">
                  Découvrir les formations
                </a>
              </div>
            }
          />
        </Carte>
      )}
    </>
  );
}

function Lecteur({ formation }: { formation: FormationAchetee }) {
  const base = useId();
  const etapes = useMemo(() => etapesDe(formation), [formation]);
  // La leçon choisie ici, sinon la dernière ouverte dans ce navigateur, sinon
  // la première. Une leçon retirée depuis n'est plus dans la suite : on
  // retombe sur la première.
  const [choisie, setChoisie] = useState<string | null>(() =>
    lireLaDerniere(formation.slug),
  );
  const [replies, setReplies] = useState<ReadonlySet<number>>(() => new Set());
  const titre = useRef<HTMLHeadingElement>(null);
  /** Vrai entre un changement de leçon DEMANDÉ et son affichage : à
   *  l'ouverture de l'écran, le focus ne bouge pas. */
  const aAnnoncer = useRef(false);

  const position = Math.max(
    0,
    etapes.findIndex((etape) => etape.lecon.id === choisie),
  );
  const courante = etapes[position] ?? null;
  const idCourant = courante?.lecon.id;

  useEffect(() => {
    if (!aAnnoncer.current) return;
    aAnnoncer.current = false;
    titre.current?.focus();
  }, [idCourant]);

  function ouvrir(etape: Etape) {
    aAnnoncer.current = etape.lecon.id !== idCourant;
    setChoisie(etape.lecon.id);
    retenirLaDerniere(formation.slug, etape.lecon.id);
    // Le module de la leçon ouverte se déplie : « suivante » ne doit pas
    // mener à une leçon dont la ligne est cachée.
    setReplies((avant) => {
      if (!avant.has(etape.module.rang)) return avant;
      const apres = new Set(avant);
      apres.delete(etape.module.rang);
      return apres;
    });
    // Leçon inchangée (clic sur la leçon courante) : rien ne se redessine,
    // le focus va quand même à son titre.
    if (!aAnnoncer.current) titre.current?.focus();
  }

  function basculer(rang: number, ouvert: boolean) {
    setReplies((avant) => {
      if (avant.has(rang) === !ouvert) return avant;
      const apres = new Set(avant);
      if (ouvert) apres.delete(rang);
      else apres.add(rang);
      return apres;
    });
  }

  const modules = modulesDe(formation);
  const echue = estEchue(formation);
  const precedente = position > 0 ? etapes[position - 1] : null;
  const suivante = position < etapes.length - 1 ? etapes[position + 1] : null;

  return (
    <Carte
      titre={formation.titre}
      note={
        echue
          ? `achetée le ${f.date(formation.achetee_le)}`
          : [
              compte(modules.length, "module"),
              compte(etapes.length, "leçon"),
              `achetée le ${f.date(formation.achetee_le)}`,
            ].join(" · ")
      }
    >
      {!echue && (
        <div className="frs-reperes">
          <Avancee formation={formation} />
          <FinDAcces formation={formation} />
        </div>
      )}
      {echue ? (
        <AccesEchu formation={formation} />
      ) : courante === null ? (
        <Vide
          titre="Le programme arrive"
          texte="Les leçons de cette formation sont en cours de mise en ligne. Elles apparaîtront ici dès leur publication."
        />
      ) : (
        <>
          {(formation.sous_titre || formation.accroche) && (
            <p className="frs-accroche">
              {[formation.sous_titre, formation.accroche].filter(Boolean).join(" — ")}
            </p>
          )}
          <div className="frs-lecteur">
          <nav className="frs-programme" aria-labelledby={`${base}-programme`}>
            <h3 id={`${base}-programme`} className="frs-intertitre">
              Programme
            </h3>
            <ol className="frs-modules">
              {modules.map((module) => {
                const lecons = leconsDe(module);
                return (
                  <li key={module.rang}>
                    <details
                      className="frs-module"
                      open={!replies.has(module.rang)}
                      onToggle={(evenement) =>
                        basculer(module.rang, evenement.currentTarget.open)
                      }
                    >
                      <summary className="frs-module-tete">
                        <span className="frs-module-rang">Module {module.rang}</span>
                        <span className="frs-module-titre">{module.titre}</span>
                        <span className="frs-module-compte">
                          {compte(lecons.length, "leçon")}
                        </span>
                      </summary>
                      {module.description && (
                        <p className="frs-module-description">{module.description}</p>
                      )}
                      <ol className="frs-lecons">
                        {lecons.map((lecon) => {
                          const reperes = [nature(lecon), duree(lecon.duree_minutes)]
                            .filter((repere): repere is string => repere !== null)
                            .join(" · ");
                          return (
                            <li key={lecon.id}>
                              <button
                                type="button"
                                className="frs-lecon"
                                aria-current={lecon.id === idCourant ? "true" : undefined}
                                onClick={() => ouvrir({ lecon, module })}
                              >
                                <span className="frs-lecon-titre">{lecon.titre}</span>
                                {lecon.terminee === true && (
                                  <span className="frs-lecon-coche">
                                    <span aria-hidden="true">✓</span>
                                    {INSECABLE}Terminée
                                  </span>
                                )}
                                {reperes !== "" && (
                                  <span className="frs-lecon-reperes">{reperes}</span>
                                )}
                              </button>
                            </li>
                          );
                        })}
                      </ol>
                    </details>
                  </li>
                );
              })}
            </ol>
          </nav>

          <section className="frs-lecon-ouverte" aria-labelledby={`${base}-lecon`}>
            <p className="frs-fil">
              Module {courante.module.rang} · Leçon {courante.lecon.rang}
              {nature(courante.lecon) !== null && ` · ${nature(courante.lecon)}`}
              {duree(courante.lecon.duree_minutes) !== null &&
                ` · ${duree(courante.lecon.duree_minutes)}`}
            </p>
            <h3
              id={`${base}-lecon`}
              ref={titre}
              tabIndex={-1}
              className="frs-lecon-titre-ouvert"
            >
              {courante.lecon.titre}
            </h3>

            {/* La clé : chaque leçon a SON contenu — un lecteur, un état de
                téléchargement — qui ne survit pas au changement de leçon. */}
            <Contenu key={courante.lecon.id} slug={formation.slug} lecon={courante.lecon} />

            {/* La même clé : chaque leçon ouverte envoie SA trace, une fois. */}
            <SuiviDeLaLecon key={`suivi-${courante.lecon.id}`} lecon={courante.lecon} />

            <div className="frs-pas">
              <button
                type="button"
                className="bouton bouton-contour"
                disabled={precedente === null}
                onClick={() => precedente && ouvrir(precedente)}
              >
                <span aria-hidden="true">←</span>{"\u00a0"}Leçon précédente
              </button>
              <button
                type="button"
                className="bouton bouton-principal"
                disabled={suivante === null}
                onClick={() => suivante && ouvrir(suivante)}
              >
                Leçon suivante{"\u00a0"}<span aria-hidden="true">→</span>
              </button>
            </div>
          </section>
          </div>
        </>
      )}
      <SeancesEnPresentiel formation={formation} />
    </Carte>
  );
}

// ── Le contenu d'une leçon ──────────────────────────────────────────────────

/** Un texte saisi par la gérante, en paragraphes. Une ligne vide sépare deux
 *  paragraphes ; un simple retour à la ligne est gardé (`white-space:
 *  pre-line`, dans la feuille). Rendu comme du TEXTE : aucune balise n'est
 *  interprétée. */
function Texte({ texte }: { texte: string }) {
  const paragraphes = texte
    .replace(/\r\n?/g, "\n")
    .split(/\n[ \t]*\n+/)
    .map((paragraphe) => paragraphe.trim())
    .filter((paragraphe) => paragraphe !== "");
  if (paragraphes.length === 0) return null;
  return (
    <div className="frs-texte">
      {paragraphes.map((paragraphe, rang) => (
        <p key={rang}>{paragraphe}</p>
      ))}
    </div>
  );
}

function Video({ lecon }: { lecon: LeconAchetee }) {
  const lecteur = lecteurDe(lecon.adresse_video);
  if (lecteur.genre === "integre") {
    return (
      // Le cadre réserve le rapport 16/9 : rien ne bouge à l'arrivée du
      // lecteur.
      //
      // `sandbox` : le lecteur de l'hébergeur garde ses scripts, son origine
      // (sans elle il ne lit rien) et la diffusion sur un autre écran — et
      // rien d'autre : ni fenêtre ouverte, ni formulaire, ni navigation de
      // NOTRE page. Le plein écran ne dépend pas de `sandbox` : il reste
      // demandable par `allow="fullscreen"` et `allowFullScreen`.
      <div className="frs-video">
        <iframe
          src={lecteur.adresse}
          title={`Vidéo de la leçon «${INSECABLE}${lecon.titre}${INSECABLE}» (${lecteur.hebergeur})`}
          loading="lazy"
          sandbox="allow-scripts allow-same-origin allow-presentation"
          allow="fullscreen; picture-in-picture"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </div>
    );
  }
  if (lecteur.genre === "fichier") {
    return (
      <div className="frs-video">
        <video
          src={lecteur.adresse}
          controls
          preload="metadata"
          aria-label={`Vidéo de la leçon «${INSECABLE}${lecon.titre}${INSECABLE}»`}
        />
      </div>
    );
  }
  if (lecteur.genre === "lien") {
    return (
      <p className="frs-geste">
        <a
          className="bouton bouton-principal"
          href={lecteur.adresse}
          target="_blank"
          rel="noopener noreferrer"
        >
          Ouvrir la vidéo
          <span className="visuellement-cache"> (nouvel onglet)</span>
        </a>
      </p>
    );
  }
  return (
    <p className="frs-absent">
      La vidéo de cette leçon n'est pas disponible pour le moment.
    </p>
  );
}

type EtatDuDocument = "repos" | "preparation" | "echec" | "absent";

/** Le document d'une leçon. Le lien affiché à l'arrivée n'est PAS suivi : il
 *  est signé pour une heure. Au clic, la liste est relue au serveur, et c'est
 *  le lien frais de cette leçon qui est ouvert — puis oublié. */
function DocumentDeLecon({ slug, lecon }: { slug: string; lecon: LeconAchetee }) {
  const cache = useQueryClient();
  const [etat, setEtat] = useState<EtatDuDocument>("repos");
  const enVol = useRef(false);
  const nom = lecon.fichier_nom || "le document";

  if (!lecon.fichier) {
    return (
      <p className="frs-absent">
        Le document de cette leçon n'est pas disponible pour le moment.
      </p>
    );
  }

  async function telecharger() {
    if (enVol.current) return;
    enVol.current = true;
    setEtat("preparation");
    try {
      const fraiches = await espaceApi.mesFormations();
      const lien = lienDeDocument(
        fraiches.formations
          .find((formation) => formation.slug === slug)
          ?.modules.flatMap((module) => leconsDe(module))
          .find((candidate) => candidate.id === lecon.id)?.fichier,
      );
      if (lien === null) {
        setEtat("absent");
      } else {
        setEtat("repos");
        // Le serveur sert les documents en pièce jointe : la page reste.
        window.location.href = lien;
      }
      // L'écran repart de ce qui vient d'être lu (une leçon retirée
      // disparaît du programme).
      cache.setQueryData(CLE, fraiches);
    } catch {
      setEtat("echec");
    } finally {
      enVol.current = false;
    }
  }

  return (
    <div className="frs-geste">
      <button
        type="button"
        className={
          etat === "preparation"
            ? "bouton bouton-principal bouton-chargement"
            : "bouton bouton-principal"
        }
        disabled={etat === "preparation"}
        aria-busy={etat === "preparation" || undefined}
        onClick={() => void telecharger()}
      >
        {etat === "preparation" ? "Préparation…" : `Télécharger ${nom}`}
      </button>
      {etat === "echec" && (
        <p className="bandeau bandeau-echec" role="alert">
          Le document n'a pas pu être préparé. Vérifiez votre connexion et
          réessayez.
        </p>
      )}
      {etat === "absent" && (
        <p className="bandeau bandeau-alerte" role="alert">
          Ce document n'est plus disponible. Signalez-le nous depuis «{INSECABLE}
          Signaler un problème{INSECABLE}».
        </p>
      )}
    </div>
  );
}

function Contenu({ slug, lecon }: { slug: string; lecon: LeconAchetee }) {
  switch (lecon.nature) {
    case "video":
      return (
        <>
          <Video lecon={lecon} />
          {/* Les notes qui accompagnent la vidéo, s'il y en a. */}
          <Texte texte={lecon.texte ?? ""} />
        </>
      );
    case "texte":
      return (lecon.texte ?? "").trim() === "" ? (
        <p className="frs-absent">
          Le texte de cette leçon n'est pas disponible pour le moment.
        </p>
      ) : (
        <Texte texte={lecon.texte} />
      );
    case "document":
      return (
        <>
          <Texte texte={lecon.texte ?? ""} />
          <DocumentDeLecon slug={slug} lecon={lecon} />
        </>
      );
    case "quiz":
      return <p className="frs-absent">Ce quiz sera bientôt disponible.</p>;
    default:
      // Une nature que cet écran ne connaît pas encore : on le dit, on
      // n'affiche pas le code du serveur.
      return (
        <p className="frs-absent">
          Le contenu de cette leçon n'est pas encore lisible ici.
        </p>
      );
  }
}
