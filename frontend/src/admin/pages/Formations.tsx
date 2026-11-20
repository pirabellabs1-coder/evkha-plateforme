/** Les formations vues de l'administration : la fiche, les modules, les leçons.
 *
 * Les modules vivaient dans un outil externe et les prix dans le code des
 * pages : la gérante ne pouvait rien changer sans développeur. Cet écran est
 * le chemin par lequel elle crée une formation, écrit sa fiche, y range des
 * modules, des leçons dans chaque module, puis la met en ligne.
 *
 * ## Une seule source : la réponse du serveur
 *
 * Toute écriture rend la formation ENTIÈRE, relue en base
 * (`dashboard/formations._reponse`). L'écran range cette fiche à la place de
 * l'ancienne (`ranger`) et ne recompose jamais un état à la main : ni un ordre
 * deviné après un déplacement, ni un compteur ajusté après un retrait. La
 * liste entière n'est pas rechargée — la réponse suffit.
 *
 * ## Rien ne s'efface
 *
 * Le serveur n'a aucune route d'effacement : un module ou une leçon se RETIRE
 * (`{"retire": true}`) et se rétablit, une formation se met hors ligne. Le
 * geste est donc discret, jamais rouge, et ce qui est retiré reste visible
 * sous « Retirés ».
 *
 * ## Deux natures de refus, deux affichages
 *
 * - un champ ILLISIBLE (« abc » dans une durée) ne fait pas échouer l'envoi :
 *   le reste est enregistré, et la réponse le nomme dans `refuses` ;
 * - une saisie contraire à une RÈGLE (adresse sans `https://`, vidéo sans
 *   adresse) fait échouer l'envoi entier, avec le `champ` en cause.
 *
 * Dans les deux cas le message du serveur est posé CONTRE le champ, relié par
 * `aria-describedby`, et la saisie reste en place. Un champ que l'écran ne
 * montre pas se dit dans un bandeau : il ne se tait jamais (règle 1).
 *
 * Les valeurs vivent dans l'état de React, par formulaire : une écriture
 * faite ailleurs sur l'écran (un module déplacé) ne reprend pas ce qui est en
 * cours de saisie dans la fiche.
 *
 * ## Les écritures d'une formation partent l'une après l'autre
 *
 * La fiche, l'état en ligne, le programme et les fenêtres ont chacun leur
 * envoi. Toutes portent la même file (`enFile`) : une seconde écriture attend
 * la réponse de la première, et l'écran ne range jamais une fiche plus
 * ancienne par-dessus une plus récente. Hors connexion, l'envoi part quand
 * même et échoue tout de suite : la panne se dit, et la main est rendue.
 *
 * ## Un écran périmé se relit
 *
 * Un refus qui dit que l'écran n'est plus à jour — un ordre que le serveur ne
 * reconnaît pas, un élément qu'il ne trouve plus — fait relire la liste
 * (`useRelecture`) : sans cela, chaque geste suivant échouerait pareil.
 *
 * ## Le suivi des élèves
 *
 * La gérante est certifiée Qualiopi : elle doit montrer qui a suivi quoi.
 * Sous la fiche et le programme, deux cartes repliées :
 *
 * - « Élèves » (`Eleves`) : une ligne par personne et par achat — son accès,
 *   sa dernière connexion, sa progression, son temps de présentiel signé — et
 *   le même tableau en fichier pour l'auditeur. Un accès se retire, avec un
 *   motif, et se rétablit ; son dernier jour se change. L'achat reste ;
 * - « Séances en présentiel » (`Seances`) : les rendez-vous en salle, leurs
 *   signatures, et la feuille d'émargement à imprimer. Une séance s'annule et
 *   se rétablit ; une signature, elle, ne se retire pas.
 *
 * ## Ce que cet écran ne porte pas
 *
 * Aucun lien d'achat : une formation ne se vend pas par un lien de paiement
 * extérieur, mais par le paiement de la plateforme.
 */
import {
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adminApi,
  type AchatDeFormationAdmin,
  type ChampRefuse,
  type ChangementDAcces,
  type CorpsDeFormation,
  type EcritureDeFormation,
  type EleveDeFormation,
  type EtatDeLAcces,
  type FormationAdmin,
  type LeconAdmin,
  type ModuleAdmin,
  type NatureDeLecon,
  RefusDuServeur,
  type SeanceAdmin,
} from "../api";
import { ActionsDePage } from "../ActionsDePage";
import { Icone } from "../icones";
import {
  Carte,
  Chiffre,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";
import * as f from "../../espace/format";
import "./Formations.css";

const CLE = ["admin", "formations"] as const;

/** L'espace insécable, écrite UNE fois et par son échappement. */
const INSECABLE = "\u00a0";

/** Les natures d'une leçon : la valeur du serveur, le mot de la gérante. */
const NATURES: { valeur: NatureDeLecon; libelle: string }[] = [
  { valeur: "video", libelle: "Vidéo" },
  { valeur: "texte", libelle: "Texte" },
  { valeur: "document", libelle: "Document" },
  { valeur: "quiz", libelle: "Quiz" },
];

const AIDE_VIDEO =
  "Collez l'adresse https:// de la vidéo hébergée chez votre service de vidéo. " +
  "Aucune vidéo n'est stockée sur la plateforme.";

/** Ce que la durée d'accès veut dire, et ce qu'elle ne ferme pas. */
const AIDE_DE_DUREE_D_ACCES =
  "Un nombre entier de mois. 0, ou vide : sans limite de durée. Cette durée vaut pour les " +
  "achats à venir ; pour une personne déjà inscrite, changez sa date de fin dans la carte " +
  "« Élèves ». Au terme de l'accès, le programme, les textes et les documents ne s'ouvrent " +
  "plus dans l'espace de l'élève. Une vidéo hébergée ailleurs reste lisible par qui en a " +
  "gardé l'adresse : réglez sa confidentialité chez votre hébergeur vidéo.";

/** Les formats d'image que le serveur accepte pour une formation
 *  (`catalog/formations.py`). UNE liste : l'aide du champ et son attribut
 *  `accept` la lisent tous les deux. */
const FORMATS_D_IMAGE = [
  { nom: "JPEG", type: "image/jpeg" },
  { nom: "PNG", type: "image/png" },
  { nom: "WebP", type: "image/webp" },
  { nom: "GIF", type: "image/gif" },
] as const;

const ACCEPT_D_IMAGE = FORMATS_D_IMAGE.map((format) => format.type).join(",");

/** « JPEG, PNG, WebP ou GIF. Format paysage de préférence. » */
const AIDE_D_IMAGE = `${FORMATS_D_IMAGE.slice(0, -1)
  .map((format) => format.nom)
  .join(", ")} ou ${FORMATS_D_IMAGE[FORMATS_D_IMAGE.length - 1].nom}. Format paysage de préférence.`;

// ── Les envois ──────────────────────────────────────────────────────────────

/** Les réglages communs à TOUTES les écritures d'une même formation.
 *
 *  - `scope` : les envois d'une même file s'exécutent l'un après l'autre.
 *    Sans lui, « Mettre hors ligne » cliqué pendant l'envoi d'une image
 *    partait en même temps, et la réponse arrivée en dernier — pas forcément
 *    la plus récente — restait à l'écran.
 *  - `networkMode: "always"` : hors connexion, l'envoi part quand même et
 *    échoue aussitôt. Par défaut il se mettrait en pause : le bouton resterait
 *    sur « Enregistrement… » et la fenêtre verrouillée, sans un mot. */
function enFile(formationId: string) {
  return { scope: { id: `formation-${formationId}` }, networkMode: "always" as const };
}

/** La file des créations : elles n'ont pas encore de formation. */
const FILE_DES_CREATIONS = "nouvelle";

/** Ce refus dit-il que l'écran n'est plus à jour ? Un ordre que le serveur ne
 *  reconnaît pas (tous ses codes `ordre_…`), ou un élément qu'il ne trouve
 *  plus (404) : la formation a changé ailleurs, dans un autre onglet. */
function ecranPerime(cause: unknown): boolean {
  return (
    cause instanceof RefusDuServeur &&
    (cause.statut === 404 || cause.code.startsWith("ordre_"))
  );
}

const DIT_RELU =
  "Cet écran n'était plus à jour : il est relu en ce moment. Vérifiez, puis refaites votre geste.";

/** Relit la liste quand un refus dit que l'écran est périmé — et rend alors
 *  la phrase à ajouter au message du serveur (vide sinon). */
function useRelecture(): (cause: unknown) => string {
  const cache = useQueryClient();
  return useCallback(
    (cause: unknown) => {
      if (!ecranPerime(cause)) return "";
      void cache.invalidateQueries({ queryKey: CLE });
      return DIT_RELU;
    },
    [cache],
  );
}

function avecSuite(message: string, suite: string): string {
  return suite ? `${message} ${suite}` : message;
}

/** L'élément qu'une fenêtre écrit, tel que le serveur le tient — la garde
 *  commune aux fenêtres de module et de leçon.
 *
 *  Un élément AJOUTÉ dont un champ a été écarté EXISTE déjà : la fenêtre
 *  reste ouverte pour corriger, et le second envoi doit le MODIFIER, pas en
 *  créer un second. `retenir` relit donc l'élément dans la fiche rendue, par
 *  l'identifiant que la réponse porte (`module_id`, `lecon_id`). Il rend
 *  `null` si l'élément n'y est pas : la fenêtre doit alors se fermer plutôt
 *  que de rester sur un formulaire qui recréerait. */
function useEnPlace<E extends { id: string }>(
  initial: E | null,
  trouver: (rendue: FormationAdmin, identifiant: string) => E | null,
): [E | null, (rendue: FormationAdmin, identifiant: string | undefined) => E | null] {
  const [enPlace, setEnPlace] = useState<E | null>(initial);
  const retenir = (rendue: FormationAdmin, identifiant: string | undefined) => {
    const cible = identifiant ?? enPlace?.id ?? "";
    const trouve = cible ? trouver(rendue, cible) : null;
    if (trouve) setEnPlace(trouve);
    return trouve;
  };
  return [enPlace, retenir];
}

/** Dit quand un élément ajouté n'a pas pu être relu dans la réponse. */
const A_VERIFIER = "Tout n'a pas été enregistré : ouvrez-le pour vérifier ses champs.";

// ── Petits outils ───────────────────────────────────────────────────────────

function montant(cents: number, devise: string): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: devise || "EUR",
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

/** Le prix tel qu'il se retape : « 1490 », « 1490,50 », ou rien à zéro euro. */
function prixEnSaisie(cents: number): string {
  if (cents <= 0) return "";
  const euros = Math.floor(cents / 100);
  const reste = cents % 100;
  return reste === 0 ? String(euros) : `${euros},${String(reste).padStart(2, "0")}`;
}

function nombreEnSaisie(valeur: number): string {
  return valeur > 0 ? String(valeur) : "";
}

function pluriel(nombre: number, mot: string): string {
  return `${nombre} ${mot}${nombre > 1 ? "s" : ""}`;
}

/** « un prix », « un prix et un titre », « a, b et c ». */
function enumerer(elements: string[]): string {
  if (elements.length <= 1) return elements.join("");
  return `${elements.slice(0, -1).join(", ")} et ${elements[elements.length - 1]}`;
}

function presents<E extends { retire: boolean }>(elements: E[]): E[] {
  return elements.filter((element) => !element.retire);
}

function retires<E extends { retire: boolean }>(elements: E[]): E[] {
  return elements.filter((element) => element.retire);
}

/** « 3 inscrits », « 1 inscrit », « Aucun inscrit pour l'instant » — ou
 *  `null` quand le serveur n'a pas rendu le nombre d'achats (ou l'a rendu
 *  illisible) : l'écran n'affiche alors rien, plutôt qu'un zéro qu'il aurait
 *  inventé (règle 1). */
function inscrits(formation: FormationAdmin): string | null {
  const nombre = formation.nombre_d_achats;
  if (typeof nombre !== "number" || !Number.isInteger(nombre) || nombre < 0) {
    return null;
  }
  if (nombre === 0) return "Aucun inscrit pour l'instant";
  return `${nombre}${INSECABLE}inscrit${nombre > 1 ? "s" : ""}`;
}

function leconsPresentes(formation: FormationAdmin): number {
  return presents(formation.modules).reduce(
    (somme, module) => somme + presents(module.lecons).length,
    0,
  );
}

function libelleDeNature(nature: string): string {
  return NATURES.find((n) => n.valeur === nature)?.libelle ?? nature;
}

/** La liste des identifiants, l'élément `index` déplacé d'un cran. */
function deplacer(identifiants: string[], index: number, sens: -1 | 1): string[] {
  const cible = index + sens;
  if (cible < 0 || cible >= identifiants.length) return identifiants;
  const copie = [...identifiants];
  [copie[index], copie[cible]] = [copie[cible], copie[index]];
  return copie;
}

// ── Lire un refus ───────────────────────────────────────────────────────────

type ErreursParChamp = Record<string, string>;

/** Le serveur nomme le prix `prix_cents` dans ses règles ; l'écran le saisit
 *  en euros, dans le champ `prix_euros`. */
const CHAMP_A_L_ECRAN: Record<string, string> = { prix_cents: "prix_euros" };

function champALEcran(champ: string): string {
  return CHAMP_A_L_ECRAN[champ] ?? champ;
}

/** Les champs écartés par le serveur, rangés contre ceux que l'écran montre.
 *  Les autres sont rendus en clair : un champ écarté ne se tait pas. */
function repartir(
  refuses: ChampRefuse[],
  affiches: readonly string[],
): { parChamp: ErreursParChamp; ailleurs: string } {
  const parChamp: ErreursParChamp = {};
  const ailleurs: string[] = [];
  for (const { champ, raison } of refuses) {
    const cible = champALEcran(champ);
    if (affiches.includes(cible)) parChamp[cible] = raison;
    else ailleurs.push(`« ${champ} » : ${raison}`);
  }
  return { parChamp, ailleurs: ailleurs.join(" ") };
}

/** Un envoi qui a échoué : contre son champ si le serveur en désigne un que
 *  l'écran montre, en bandeau sinon. */
function lireLEchec(
  cause: unknown,
  affiches: readonly string[],
): { parChamp: ErreursParChamp; general: string } {
  const message =
    cause instanceof Error && cause.message
      ? cause.message
      : "L'envoi a échoué : rien n'a été enregistré. Réessayez.";
  if (cause instanceof RefusDuServeur && cause.champ) {
    const cible = champALEcran(cause.champ);
    if (affiches.includes(cible)) return { parChamp: { [cible]: message }, general: "" };
  }
  return { parChamp: {}, general: message };
}

/** Un corps d'envoi : JSON tant qu'aucun fichier ne part, multipart sinon. */
function corpsAvecFichier(
  champs: Record<string, unknown>,
  nom: string,
  fichier: File | null,
): CorpsDeFormation {
  if (!fichier) return champs;
  const donnees = new FormData();
  for (const [cle, valeur] of Object.entries(champs)) {
    donnees.set(cle, typeof valeur === "boolean" ? (valeur ? "true" : "false") : String(valeur));
  }
  donnees.set(nom, fichier);
  return donnees;
}

// ── Briques ─────────────────────────────────────────────────────────────────

interface Relie {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

/** Un champ : son libellé visible, la saisie, son aide, puis le message du
 *  serveur — tous deux reliés à la saisie. L'aide reste sous l'erreur : pour
 *  l'adresse d'une vidéo, c'est elle qui dit quoi coller. */
function ChampRelie({
  id,
  libelle,
  aide,
  erreur,
  children,
}: {
  id: string;
  libelle: string;
  aide?: string;
  erreur?: string;
  children: (relie: Relie) => ReactNode;
}) {
  const decrit =
    [erreur ? `${id}-erreur` : "", aide ? `${id}-aide` : ""].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className="champ">
      <label className="champ-libelle" htmlFor={id}>
        {libelle}
      </label>
      {children({ id, "aria-describedby": decrit, "aria-invalid": erreur ? true : undefined })}
      {erreur && (
        <span className="champ-erreur" id={`${id}-erreur`}>
          {erreur}
        </span>
      )}
      {aide && (
        <span className="champ-aide" id={`${id}-aide`}>
          {aide}
        </span>
      )}
    </div>
  );
}

/** Une fenêtre du langage commun (`console-fenetre`), ouverte par
 *  `showModal()` : le reste de la page devient inerte et Échap ferme.
 *
 *  Elle est montée quand on l'ouvre et démontée quand on la ferme. Le focus
 *  est rendu à ce qui l'avait en l'ouvrant — le bouton « Modifier » de la
 *  leçon, par exemple —, s'il est encore à l'écran.
 *
 *  Un clic sur le voile ne ferme PAS : ces fenêtres portent une saisie, et un
 *  clic à côté la perdrait. */
function Fenetre({
  titre,
  onFermer,
  verrouillee = false,
  classe,
  children,
}: {
  titre: string;
  onFermer: () => void;
  /** Une classe de plus sur la fenêtre (la feuille imprimable). */
  classe?: string;
  /** Un envoi est en cours : la fenêtre attend sa réponse. */
  verrouillee?: boolean;
  children: ReactNode;
}) {
  const fenetre = useRef<HTMLDialogElement>(null);
  /** Les fermetures que NOUS provoquons au démontage : leur événement
   *  `close` arrive après coup et ne doit pas se lire comme un geste. Le mode
   *  strict de React monte, démonte, puis remonte chaque composant. */
  const fermeturesAIgnorer = useRef(0);
  const idTitre = useId();

  useLayoutEffect(() => {
    const element = fenetre.current;
    if (!element) return;
    const ouvreur =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    // Sans `showModal` (un navigateur ancien), la fenêtre s'ouvre quand même,
    // dans le fil de la page : moins bien, mais la saisie reste possible.
    if (!element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    }
    return () => {
      if (element.open) {
        if (typeof element.close === "function") {
          fermeturesAIgnorer.current += 1;
          element.close();
        } else {
          element.removeAttribute("open");
        }
      }
      if (ouvreur?.isConnected) ouvreur.focus();
    };
  }, []);

  return (
    <dialog
      ref={fenetre}
      className={classe ? `console-fenetre frm-fenetre ${classe}` : "console-fenetre frm-fenetre"}
      aria-labelledby={idTitre}
      onCancel={(evenement) => {
        // Échap : c'est l'état de React qui ferme, pas le navigateur.
        evenement.preventDefault();
        if (!verrouillee) onFermer();
      }}
      onClose={() => {
        if (fermeturesAIgnorer.current > 0) {
          fermeturesAIgnorer.current -= 1;
          return;
        }
        // Fermée par le navigateur malgré tout : sous Chrome, un second
        // Échap ferme sans passer par `cancel`.
        if (verrouillee) {
          // Un envoi est en cours : la fenêtre se ROUVRE. Fermée, elle
          // emporterait les champs que la réponse va peut-être refuser.
          const element = fenetre.current;
          if (element && !element.open) {
            if (typeof element.showModal === "function") element.showModal();
            else element.setAttribute("open", "");
          }
          return;
        }
        // Sinon l'état suit : la fenêtre resterait « ouverte » et invisible.
        onFermer();
      }}
    >
      <div className="console-fenetre-corps">
        <h2 id={idTitre} className="carte-titre">
          {titre}
        </h2>
        {children}
      </div>
    </dialog>
  );
}

/** L'identifiant d'un champ dans son formulaire (`base` vient de `useId`). */
function idDuChamp(base: string, champ: string): string {
  return `${base}-${champ}`;
}

/** Pose le focus sur le premier champ en erreur, dans l'ordre de l'écran.
 *
 *  `ordre` est une constante du module : un tableau refait à chaque rendu
 *  rejouerait l'effet, et le focus sauterait à chaque touche frappée. */
function useFocusSurLErreur(erreurs: ErreursParChamp, ordre: readonly string[], base: string) {
  useEffect(() => {
    const premier = ordre.find((champ) => erreurs[champ]);
    if (premier) document.getElementById(idDuChamp(base, premier))?.focus();
  }, [erreurs, ordre, base]);
}

const SEUL_LE_TITRE = ["titre"] as const;

// ── Créer une formation ─────────────────────────────────────────────────────

function FenetreDeCreation({
  onCreee,
  onFermer,
}: {
  onCreee: (reponse: EcritureDeFormation) => void;
  onFermer: () => void;
}) {
  const base = useId();
  const [titre, setTitre] = useState("");
  const [erreurs, setErreurs] = useState<ErreursParChamp>({});
  const [general, setGeneral] = useState("");
  const idDe = (champ: string) => idDuChamp(base, champ);
  useFocusSurLErreur(erreurs, SEUL_LE_TITRE, base);

  const creation = useMutation({
    ...enFile(FILE_DES_CREATIONS),
    mutationFn: () => adminApi.creerUneFormation({ titre }),
    onSuccess: onCreee,
    onError: (cause: unknown) => {
      const lu = lireLEchec(cause, SEUL_LE_TITRE);
      setErreurs(lu.parChamp);
      setGeneral(lu.general);
    },
  });

  return (
    <Fenetre titre="Ajouter une formation" onFermer={onFermer} verrouillee={creation.isPending}>
      <form
        className="console-formulaire"
        noValidate
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (creation.isPending) return;
          setErreurs({});
          setGeneral("");
          creation.mutate();
        }}
      >
        {general && (
          <p className="bandeau bandeau-echec" role="alert">
            {general}
          </p>
        )}
        <ChampRelie
          id={idDe("titre")}
          libelle="Titre de la formation"
          aide="Vous pourrez le modifier ensuite. La formation est créée hors ligne : personne ne la voit tant que vous ne l'avez pas mise en ligne."
          erreur={erreurs.titre}
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              value={titre}
              onChange={(e) => setTitre(e.currentTarget.value)}
              aria-required="true"
              autoComplete="off"
            />
          )}
        </ChampRelie>
        <footer className="console-formulaire-pied">
          <button
            type="button"
            className="bouton bouton-discret"
            disabled={creation.isPending}
            onClick={onFermer}
          >
            Annuler
          </button>
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={creation.isPending}
            aria-busy={creation.isPending || undefined}
          >
            {creation.isPending ? "Création…" : "Créer la formation"}
          </button>
        </footer>
      </form>
    </Fenetre>
  );
}

// ── La fiche ────────────────────────────────────────────────────────────────

const CHAMPS_DE_FICHE = [
  "titre",
  "sous_titre",
  "accroche",
  "description",
  "prix_euros",
  "duree_heures",
  "heures_de_coaching",
  "duree_d_acces_mois",
] as const;

type ChampDeFiche = (typeof CHAMPS_DE_FICHE)[number];
type SaisieDeFiche = Record<ChampDeFiche, string>;

/** Les champs où une case vidée veut dire « zéro ». */
const NOMBRES_DE_FICHE: readonly ChampDeFiche[] = [
  "prix_euros",
  "duree_heures",
  "heures_de_coaching",
  "duree_d_acces_mois",
];

const AFFICHES_DE_FICHE: readonly string[] = [...CHAMPS_DE_FICHE, "image"];

function saisieDeFiche(formation: FormationAdmin): SaisieDeFiche {
  return {
    titre: formation.titre,
    sous_titre: formation.sous_titre,
    accroche: formation.accroche,
    description: formation.description,
    prix_euros: prixEnSaisie(formation.prix_cents),
    duree_heures: nombreEnSaisie(formation.duree_heures),
    heures_de_coaching: nombreEnSaisie(formation.heures_de_coaching),
    duree_d_acces_mois: nombreEnSaisie(formation.duree_d_acces_mois ?? 0),
  };
}

function Fiche({
  formation,
  onEcrit,
}: {
  formation: FormationAdmin;
  onEcrit: (reponse: EcritureDeFormation) => void;
}) {
  const base = useId();
  const idDe = (champ: string) => idDuChamp(base, champ);
  const enPlace = useMemo(() => saisieDeFiche(formation), [formation]);
  const [saisie, setSaisie] = useState<SaisieDeFiche>(enPlace);
  const [image, setImage] = useState<File | null>(null);
  /** Change à chaque image enregistrée : le sélecteur de fichier se vide. */
  const [tourDImage, setTourDImage] = useState(0);
  const [erreurs, setErreurs] = useState<ErreursParChamp>({});
  const [general, setGeneral] = useState("");
  const [etat, setEtat] = useState("");
  const relire = useRelecture();
  useFocusSurLErreur(erreurs, AFFICHES_DE_FICHE, base);

  // L'aperçu est DÉRIVÉ du fichier choisi ; l'effet ne sert qu'à relâcher
  // l'adresse, qui retient le fichier en mémoire (voir `BoutiqueAdmin`).
  const apercu = useMemo(() => (image ? URL.createObjectURL(image) : ""), [image]);
  useEffect(() => {
    if (!apercu) return;
    return () => URL.revokeObjectURL(apercu);
  }, [apercu]);

  const modifies = CHAMPS_DE_FICHE.filter((champ) => saisie[champ] !== enPlace[champ]);

  const enregistrement = useMutation({
    ...enFile(formation.id),
    mutationFn: (envoi: { saisie: SaisieDeFiche; champs: ChampDeFiche[]; image: File | null }) => {
      const corps: Record<string, unknown> = {};
      for (const champ of envoi.champs) {
        const valeur = envoi.saisie[champ];
        corps[champ] = NOMBRES_DE_FICHE.includes(champ) ? valeur.trim() || "0" : valeur;
      }
      return adminApi.modifierLaFormation(
        formation.id,
        corpsAvecFichier(corps, "image", envoi.image),
      );
    },
    onSuccess: (reponse, envoi) => {
      onEcrit(reponse);
      const { parChamp, ailleurs } = repartir(reponse.refuses, AFFICHES_DE_FICHE);
      const rendue = saisieDeFiche(reponse.formation);
      // La fiche reprend ce que le serveur a enregistré — sauf les champs
      // qu'il a écartés (la saisie reste, à corriger) et ceux qu'on a
      // retouchés pendant l'envoi.
      setSaisie((courante) => {
        const suivante = { ...rendue };
        for (const champ of CHAMPS_DE_FICHE) {
          if (parChamp[champ] || courante[champ] !== envoi.saisie[champ]) {
            suivante[champ] = courante[champ];
          }
        }
        return suivante;
      });
      if (envoi.image && !parChamp.image) {
        setImage(null);
        setTourDImage((tour) => tour + 1);
      }
      setErreurs(parChamp);
      setGeneral(ailleurs);
      setEtat(
        reponse.refuses.length > 0
          ? "La fiche est enregistrée, sauf ce qui est signalé : la valeur précédente a été gardée."
          : "La fiche est enregistrée.",
      );
    },
    onError: (cause: unknown) => {
      const lu = lireLEchec(cause, AFFICHES_DE_FICHE);
      const suite = relire(cause);
      setErreurs(lu.parChamp);
      setGeneral(lu.general ? avecSuite(lu.general, suite) : suite);
      setEtat("");
    },
  });

  const champ = (nom: ChampDeFiche) => ({
    value: saisie[nom],
    onChange: (e: { currentTarget: { value: string } }) => {
      const valeur = e.currentTarget.value;
      setSaisie((courante) => ({ ...courante, [nom]: valeur }));
    },
  });

  return (
    <Carte
      titre="La fiche"
      note="Le prix, les durées et le programme sont repris sur votre site. Le titre, le sous-titre, l'accroche et l'image s'affichent dans l'espace de vos apprenants ; la description vous sert ici."
    >
      <form
        className="console-formulaire"
        noValidate
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (enregistrement.isPending) return;
          if (modifies.length === 0 && !image) {
            setEtat("Aucune modification à enregistrer.");
            return;
          }
          setEtat("");
          setGeneral("");
          setErreurs({});
          enregistrement.mutate({ saisie, champs: modifies, image });
        }}
      >
        {general && (
          <p className="bandeau bandeau-echec" role="alert">
            {general}
          </p>
        )}

        <ChampRelie id={idDe("titre")} libelle="Titre" erreur={erreurs.titre}>
          {(relie) => (
            <input {...relie} className="champ-saisie" aria-required="true" {...champ("titre")} />
          )}
        </ChampRelie>

        <ChampRelie
          id={idDe("sous_titre")}
          libelle="Sous-titre"
          aide="Une ligne, sous le titre."
          erreur={erreurs.sous_titre}
        >
          {(relie) => <input {...relie} className="champ-saisie" {...champ("sous_titre")} />}
        </ChampRelie>

        <ChampRelie
          id={idDe("accroche")}
          libelle="Accroche"
          aide="Deux ou trois phrases qui donnent envie d'en savoir plus."
          erreur={erreurs.accroche}
        >
          {(relie) => (
            <textarea
              {...relie}
              className="champ-saisie champ-zone"
              rows={3}
              {...champ("accroche")}
            />
          )}
        </ChampRelie>

        <ChampRelie
          id={idDe("description")}
          libelle="Description"
          aide="Votre présentation complète : à qui elle s'adresse, ce qu'on y apprend. Elle est gardée ici pour vous : elle n'est pas encore affichée sur le site."
          erreur={erreurs.description}
        >
          {(relie) => (
            <textarea
              {...relie}
              className="champ-saisie champ-zone"
              rows={7}
              {...champ("description")}
            />
          )}
        </ChampRelie>

        <div className="console-champs">
          <ChampRelie
            id={idDe("prix_euros")}
            libelle="Prix, en euros"
            aide="Par exemple 1 490 ou 89,90. Sans prix, la formation ne peut pas être mise en ligne."
            erreur={erreurs.prix_euros}
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                inputMode="decimal"
                autoComplete="off"
                {...champ("prix_euros")}
              />
            )}
          </ChampRelie>

          <ChampRelie
            id={idDe("duree_heures")}
            libelle="Durée, en heures"
            aide="Un nombre entier."
            erreur={erreurs.duree_heures}
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                inputMode="numeric"
                autoComplete="off"
                {...champ("duree_heures")}
              />
            )}
          </ChampRelie>

          <ChampRelie
            id={idDe("heures_de_coaching")}
            libelle="Heures de coaching"
            aide="Un nombre entier. Laissez vide s'il n'y en a pas."
            erreur={erreurs.heures_de_coaching}
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                inputMode="numeric"
                autoComplete="off"
                {...champ("heures_de_coaching")}
              />
            )}
          </ChampRelie>
        </div>

        <ChampRelie
          id={idDe("duree_d_acces_mois")}
          libelle="Durée d'accès, en mois"
          aide={AIDE_DE_DUREE_D_ACCES}
          erreur={erreurs.duree_d_acces_mois}
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie frm-court"
              inputMode="numeric"
              autoComplete="off"
              {...champ("duree_d_acces_mois")}
            />
          )}
        </ChampRelie>

        <div className="frm-couverture">
          <div className="frm-couverture-cadre">
            {apercu || formation.image ? (
              <img
                className="frm-couverture-image"
                src={apercu || formation.image}
                alt={apercu ? "Aperçu de la nouvelle image" : "Image actuelle de la formation"}
              />
            ) : (
              <span className="frm-couverture-vide">
                <Icone nom="formations" taille={28} />
                <span>Aucune image</span>
              </span>
            )}
          </div>
          <ChampRelie
            id={idDe("image")}
            libelle={formation.image ? "Remplacer l'image" : "Image de la formation"}
            aide={
              image
                ? `« ${image.name} » remplacera l'image actuelle à l'enregistrement.`
                : AIDE_D_IMAGE
            }
            erreur={erreurs.image}
          >
            {(relie) => (
              <input
                {...relie}
                key={tourDImage}
                className="frm-fichier"
                type="file"
                accept={ACCEPT_D_IMAGE}
                onChange={(e) => setImage(e.currentTarget.files?.[0] ?? null)}
              />
            )}
          </ChampRelie>
        </div>

        <ChampRelie
          id={idDe("adresse")}
          libelle="Adresse publique"
          aide="Fixée à la création : cette adresse ne change plus, même si vous modifiez le titre. Les liens déjà diffusés restent valables."
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              readOnly
              value={`/formations/${formation.slug}`}
            />
          )}
        </ChampRelie>

        <footer className="console-formulaire-pied">
          <p className="carte-note" role="status">
            {etat}
          </p>
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={enregistrement.isPending}
            aria-busy={enregistrement.isPending || undefined}
          >
            {enregistrement.isPending ? "Enregistrement…" : "Enregistrer la fiche"}
          </button>
        </footer>
      </form>
    </Carte>
  );
}

// ── En ligne, hors ligne ────────────────────────────────────────────────────

function EtatDeLaFormation({
  formation,
  onEcrit,
}: {
  formation: FormationAdmin;
  onEcrit: (reponse: EcritureDeFormation) => void;
}) {
  const base = useId();
  const titre = useRef<HTMLHeadingElement>(null);
  const bouton = useRef<HTMLButtonElement>(null);
  const [confirme, setConfirme] = useState(false);
  const [explique, setExplique] = useState(false);
  const [erreur, setErreur] = useState("");
  const relire = useRelecture();

  // En arrivant sur une formation, le focus va à son titre : la carte sur
  // laquelle on a cliqué n'est plus à l'écran.
  useEffect(() => {
    titre.current?.focus();
  }, []);

  const bascule = useMutation({
    ...enFile(formation.id),
    mutationFn: (enLigne: boolean) =>
      adminApi.modifierLaFormation(formation.id, { en_ligne: enLigne }),
    onSuccess: (reponse) => {
      setErreur("");
      setConfirme(false);
      setExplique(false);
      onEcrit(reponse);
      bouton.current?.focus();
    },
    onError: (cause: unknown) => {
      setConfirme(false);
      // Le refus du serveur, tel qu'il l'a écrit (« il lui manque un prix »).
      setErreur(
        avecSuite(
          cause instanceof Error && cause.message
            ? cause.message
            : "Le changement n'a pas pu être fait. Réessayez.",
          relire(cause),
        ),
      );
      bouton.current?.focus();
    },
  });

  const incomplete = !formation.en_ligne && !formation.publiable;
  const manque = enumerer(formation.manque);

  function basculer() {
    if (bascule.isPending) return;
    setErreur("");
    if (formation.en_ligne) {
      // Elle disparaît du site : on demande avant.
      setConfirme(true);
      return;
    }
    if (incomplete) {
      // On explique AVANT d'appeler : le serveur refuserait, et un refus
      // sans explication se lit comme une panne.
      setExplique(true);
      return;
    }
    bascule.mutate(true);
  }

  function renoncer() {
    setConfirme(false);
    bouton.current?.focus();
  }

  return (
    <section className="carte frm-etat" aria-labelledby={`${base}-titre`}>
      <div className="frm-etat-ligne">
        <div className="frm-etat-texte">
          <h2 id={`${base}-titre`} ref={titre} tabIndex={-1} className="frm-etat-titre">
            {formation.titre}
          </h2>
          <p className="frm-etat-ou">
            <span
              className={
                formation.en_ligne ? "pastille pastille-succes" : "pastille pastille-neutre"
              }
            >
              {formation.en_ligne ? "En ligne" : "Hors ligne"}
            </span>
            <span className="carte-note">
              {formation.en_ligne
                ? "Vos visiteurs la voient sur le site."
                : "Vos visiteurs ne la voient pas."}
            </span>
          </p>
          {inscrits(formation) !== null && (
            <p className="carte-note frm-inscrits">{inscrits(formation)}</p>
          )}
          {incomplete && (
            <p className="frm-manque" id={`${base}-manque`}>
              Pour la mettre en ligne, il manque {manque}.
            </p>
          )}
        </div>
        {/* `aria-disabled` plutôt que `disabled` : le bouton garde le focus
            pendant l'envoi, et on le lui rend après. Le clic, lui, est sans
            effet (`basculer`). */}
        <button
          ref={bouton}
          type="button"
          className={formation.en_ligne ? "bouton bouton-contour" : "bouton bouton-principal"}
          aria-disabled={bascule.isPending || undefined}
          aria-busy={bascule.isPending || undefined}
          aria-describedby={incomplete ? `${base}-manque` : undefined}
          onClick={basculer}
        >
          {bascule.isPending
            ? "Un instant…"
            : formation.en_ligne
              ? "Mettre hors ligne"
              : "Mettre en ligne"}
        </button>
      </div>

      {explique && incomplete && (
        <p className="bandeau bandeau-alerte" role="alert">
          Cette formation ne peut pas encore être mise en ligne : il lui manque {manque}.
          Complétez la fiche, enregistrez-la, puis revenez à ce bouton.
        </p>
      )}

      {erreur && (
        <p className="bandeau bandeau-echec" role="alert">
          {erreur}
        </p>
      )}

      {confirme && (
        <div
          className="console-confirmation"
          role="alertdialog"
          aria-labelledby={`${base}-question`}
          aria-describedby={`${base}-consequence`}
          onKeyDown={(evenement) => {
            if (evenement.key === "Escape" && !bascule.isPending) renoncer();
          }}
        >
          <p id={`${base}-question`}>
            <b>Mettre « {formation.titre} » hors ligne ?</b>
          </p>
          <p className="carte-note" id={`${base}-consequence`}>
            Elle disparaîtra de votre site jusqu'à ce que vous la remettiez en ligne. Rien
            n'est effacé : sa fiche et son programme restent ici.
          </p>
          <div className="console-gestes">
            <button
              type="button"
              className="bouton bouton-discret"
              autoFocus
              disabled={bascule.isPending}
              onClick={renoncer}
            >
              Annuler
            </button>
            <button
              type="button"
              className="bouton bouton-principal"
              disabled={bascule.isPending}
              aria-busy={bascule.isPending || undefined}
              onClick={() => bascule.mutate(false)}
            >
              {bascule.isPending ? "Mise hors ligne…" : "Oui, la mettre hors ligne"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Un module, dans une fenêtre ─────────────────────────────────────────────

const AFFICHES_DE_MODULE = ["titre", "description"] as const;

function FenetreDeModule({
  formation,
  module,
  onEcrit,
  onFermer,
}: {
  formation: FormationAdmin;
  /** Absent : on ajoute un module. */
  module: ModuleAdmin | null;
  onEcrit: (reponse: EcritureDeFormation, annonce: string) => void;
  onFermer: () => void;
}) {
  const base = useId();
  const idDe = (champ: string) => idDuChamp(base, champ);
  /** Le module tel que le serveur le tient (voir `useEnPlace`). */
  const [enPlace, retenir] = useEnPlace<ModuleAdmin>(module, trouverLeModule);
  const [titre, setTitre] = useState(module?.titre ?? "");
  const [description, setDescription] = useState(module?.description ?? "");
  const [erreurs, setErreurs] = useState<ErreursParChamp>({});
  const [general, setGeneral] = useState("");
  const [etat, setEtat] = useState("");
  const relire = useRelecture();
  useFocusSurLErreur(erreurs, AFFICHES_DE_MODULE, base);

  const envoi = useMutation({
    ...enFile(formation.id),
    mutationFn: (champs: Record<string, unknown>) =>
      enPlace
        ? adminApi.modifierLeModule(enPlace.id, champs)
        : adminApi.ajouterUnModule(formation.id, champs),
    onSuccess: (reponse) => {
      const annonce = enPlace
        ? `Le module « ${titre.trim()} » est enregistré.`
        : `Le module « ${titre.trim()} » est ajouté, en fin de programme.`;
      if (reponse.refuses.length === 0) {
        onEcrit(reponse, annonce);
        onFermer();
        return;
      }
      if (!retenir(reponse.formation, reponse.module_id)) {
        onEcrit(reponse, `${annonce} ${A_VERIFIER}`);
        onFermer();
        return;
      }
      onEcrit(reponse, annonce);
      const { parChamp, ailleurs } = repartir(reponse.refuses, AFFICHES_DE_MODULE);
      setErreurs(parChamp);
      setGeneral(ailleurs);
      setEtat(
        "Le module est enregistré, sauf ce qui est signalé : corrigez, puis enregistrez de nouveau.",
      );
    },
    onError: (cause: unknown) => {
      const lu = lireLEchec(cause, AFFICHES_DE_MODULE);
      const suite = relire(cause);
      setErreurs(lu.parChamp);
      setGeneral(lu.general ? avecSuite(lu.general, suite) : suite);
      setEtat("");
    },
  });

  return (
    <Fenetre
      titre={enPlace ? "Modifier le module" : "Ajouter un module"}
      onFermer={onFermer}
      verrouillee={envoi.isPending}
    >
      <form
        className="console-formulaire"
        noValidate
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (envoi.isPending) return;
          const champs: Record<string, unknown> = {};
          if (!enPlace || titre !== enPlace.titre) champs.titre = titre;
          if (!enPlace || description !== enPlace.description) champs.description = description;
          if (Object.keys(champs).length === 0) {
            onFermer();
            return;
          }
          setErreurs({});
          setGeneral("");
          setEtat("");
          envoi.mutate(champs);
        }}
      >
        {general && (
          <p className="bandeau bandeau-echec" role="alert">
            {general}
          </p>
        )}
        <ChampRelie id={idDe("titre")} libelle="Titre du module" erreur={erreurs.titre}>
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              value={titre}
              onChange={(e) => setTitre(e.currentTarget.value)}
              aria-required="true"
              autoComplete="off"
            />
          )}
        </ChampRelie>
        <ChampRelie
          id={idDe("description")}
          libelle="Description"
          aide="Ce que l'on apprend dans ce module, en quelques lignes. Facultatif."
          erreur={erreurs.description}
        >
          {(relie) => (
            <textarea
              {...relie}
              className="champ-saisie champ-zone"
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.currentTarget.value)}
            />
          )}
        </ChampRelie>
        <footer className="console-formulaire-pied">
          <p className="carte-note" role="status">
            {etat}
          </p>
          <button
            type="button"
            className="bouton bouton-discret"
            disabled={envoi.isPending}
            onClick={onFermer}
          >
            {etat ? "Fermer" : "Annuler"}
          </button>
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={envoi.isPending}
            aria-busy={envoi.isPending || undefined}
          >
            {envoi.isPending
              ? "Enregistrement…"
              : enPlace
                ? "Enregistrer le module"
                : "Ajouter le module"}
          </button>
        </footer>
      </form>
    </Fenetre>
  );
}

// ── Une leçon, dans une fenêtre ─────────────────────────────────────────────

interface SaisieDeLecon {
  titre: string;
  nature: NatureDeLecon;
  adresse_video: string;
  texte: string;
  duree_minutes: string;
  en_apercu_libre: boolean;
}

function saisieDeLecon(lecon: LeconAdmin | null): SaisieDeLecon {
  return {
    titre: lecon?.titre ?? "",
    nature: lecon?.nature ?? "video",
    adresse_video: lecon?.adresse_video ?? "",
    texte: lecon?.texte ?? "",
    duree_minutes: nombreEnSaisie(lecon?.duree_minutes ?? 0),
    en_apercu_libre: lecon?.en_apercu_libre ?? false,
  };
}

/** Tous les champs d'une leçon, dans l'ordre de la fenêtre. */
const ORDRE_DE_LECON = [
  "titre",
  "nature",
  "adresse_video",
  "texte",
  "fichier",
  "duree_minutes",
  "en_apercu_libre",
] as const;

/** Les champs que la fenêtre montre pour une nature : une erreur du serveur
 *  sur un champ masqué va au bandeau, pas dans le vide. */
function affichesDeLecon(nature: NatureDeLecon): string[] {
  const masques: Record<NatureDeLecon, string[]> = {
    video: ["texte", "fichier"],
    texte: ["adresse_video", "fichier"],
    document: ["adresse_video", "texte"],
    quiz: ["adresse_video", "texte", "fichier"],
  };
  return ORDRE_DE_LECON.filter((champ) => !masques[nature].includes(champ));
}

/** Ce qui part au serveur : tout pour une leçon nouvelle, ce qui a changé
 *  pour une leçon en place — et seulement le contenu de SA nature. */
function champsDeLecon(saisie: SaisieDeLecon, enPlace: LeconAdmin | null): Record<string, unknown> {
  const avant = saisieDeLecon(enPlace);
  const nouvelle = enPlace === null;
  const champs: Record<string, unknown> = {};
  if (nouvelle || saisie.titre !== avant.titre) champs.titre = saisie.titre;
  if (nouvelle || saisie.nature !== avant.nature) champs.nature = saisie.nature;
  if (saisie.nature === "video" && (nouvelle || saisie.adresse_video !== avant.adresse_video)) {
    champs.adresse_video = saisie.adresse_video;
  }
  if (saisie.nature === "texte" && (nouvelle || saisie.texte !== avant.texte)) {
    champs.texte = saisie.texte;
  }
  if (saisie.duree_minutes !== avant.duree_minutes) {
    champs.duree_minutes = saisie.duree_minutes.trim() || "0";
  }
  if (nouvelle || saisie.en_apercu_libre !== avant.en_apercu_libre) {
    champs.en_apercu_libre = saisie.en_apercu_libre;
  }
  return champs;
}

function trouverLeModule(formation: FormationAdmin, moduleId: string): ModuleAdmin | null {
  return formation.modules.find((module) => module.id === moduleId) ?? null;
}

function trouverLaLecon(formation: FormationAdmin, leconId: string): LeconAdmin | null {
  for (const module of formation.modules) {
    const trouvee = module.lecons.find((lecon) => lecon.id === leconId);
    if (trouvee) return trouvee;
  }
  return null;
}

/** Le lien d'un document est SIGNÉ et expire : on le relit au serveur au
 *  moment d'ouvrir, on ne se sert pas de celui qu'on a en mémoire.
 *
 *  L'onglet est ouvert AVANT la lecture : ouvert après, il ne répond plus à
 *  un clic et le navigateur le bloque comme une fenêtre intempestive. */
async function ouvrirLeDocument(leconId: string): Promise<void> {
  const onglet = window.open("", "_blank");
  try {
    const { formations } = await adminApi.formations();
    let lien = "";
    for (const formation of formations) {
      lien = trouverLaLecon(formation, leconId)?.fichier ?? "";
      if (lien) break;
    }
    if (!lien) throw new Error("document introuvable");
    if (onglet) {
      onglet.opener = null;
      onglet.location.replace(lien);
    } else {
      window.location.assign(lien);
    }
  } catch (cause) {
    onglet?.close();
    throw cause;
  }
}

function FenetreDeLecon({
  formation,
  module,
  lecon,
  onEcrit,
  onFermer,
}: {
  formation: FormationAdmin;
  module: ModuleAdmin;
  /** Absente : on ajoute une leçon au module. */
  lecon: LeconAdmin | null;
  onEcrit: (reponse: EcritureDeFormation, annonce: string) => void;
  onFermer: () => void;
}) {
  const base = useId();
  const idDe = (champ: string) => idDuChamp(base, champ);
  /** La leçon telle que le serveur la tient (voir `useEnPlace`). */
  const [enPlace, retenir] = useEnPlace<LeconAdmin>(lecon, trouverLaLecon);
  const [saisie, setSaisie] = useState<SaisieDeLecon>(() => saisieDeLecon(lecon));
  const [fichier, setFichier] = useState<File | null>(null);
  const [tourDeFichier, setTourDeFichier] = useState(0);
  const [erreurs, setErreurs] = useState<ErreursParChamp>({});
  const [general, setGeneral] = useState("");
  const [etat, setEtat] = useState("");
  const affiches = affichesDeLecon(saisie.nature);
  const relire = useRelecture();
  useFocusSurLErreur(erreurs, ORDRE_DE_LECON, base);

  const envoi = useMutation({
    ...enFile(formation.id),
    mutationFn: (corps: CorpsDeFormation) =>
      enPlace
        ? adminApi.modifierLaLecon(enPlace.id, corps)
        : adminApi.ajouterUneLecon(module.id, corps),
    onSuccess: (reponse) => {
      const annonce =
        enPlace === null
          ? `La leçon « ${saisie.titre.trim()} » est ajoutée, en fin de module.`
          : `La leçon « ${saisie.titre.trim()} » est enregistrée.`;
      if (reponse.refuses.length === 0) {
        onEcrit(reponse, annonce);
        onFermer();
        return;
      }
      if (!retenir(reponse.formation, reponse.lecon_id)) {
        onEcrit(reponse, `${annonce} ${A_VERIFIER}`);
        onFermer();
        return;
      }
      onEcrit(reponse, annonce);
      const { parChamp, ailleurs } = repartir(reponse.refuses, affiches);
      if (fichier && !parChamp.fichier) {
        setFichier(null);
        setTourDeFichier((tour) => tour + 1);
      }
      setErreurs(parChamp);
      setGeneral(ailleurs);
      setEtat(
        "La leçon est enregistrée, sauf ce qui est signalé : corrigez, puis enregistrez de nouveau.",
      );
    },
    onError: (cause: unknown) => {
      const lu = lireLEchec(cause, affiches);
      const suite = relire(cause);
      setErreurs(lu.parChamp);
      setGeneral(lu.general ? avecSuite(lu.general, suite) : suite);
      setEtat("");
    },
  });

  // Une LECTURE : hors de la file des écritures, mais sans pause non plus.
  const ouverture = useMutation({
    networkMode: "always",
    mutationFn: (leconId: string) => ouvrirLeDocument(leconId),
    onSuccess: () => setGeneral(""),
    onError: () =>
      setGeneral(
        "Le document n'a pas pu être ouvert. Réessayez dans un instant ; s'il reste introuvable, déposez-le de nouveau.",
      ),
  });

  const occupe = envoi.isPending;

  return (
    <Fenetre
      titre={enPlace ? "Modifier la leçon" : `Ajouter une leçon au module « ${module.titre} »`}
      onFermer={onFermer}
      verrouillee={occupe}
    >
      <form
        className="console-formulaire"
        noValidate
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (occupe) return;
          const champs = champsDeLecon(saisie, enPlace);
          const joint = saisie.nature === "document" ? fichier : null;
          if (Object.keys(champs).length === 0 && !joint) {
            onFermer();
            return;
          }
          setErreurs({});
          setGeneral("");
          setEtat("");
          envoi.mutate(corpsAvecFichier(champs, "fichier", joint));
        }}
      >
        {general && (
          <p className="bandeau bandeau-echec" role="alert">
            {general}
          </p>
        )}

        <ChampRelie id={idDe("titre")} libelle="Titre de la leçon" erreur={erreurs.titre}>
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              value={saisie.titre}
              onChange={(e) => {
                const valeur = e.currentTarget.value;
                setSaisie((courante) => ({ ...courante, titre: valeur }));
              }}
              aria-required="true"
              autoComplete="off"
            />
          )}
        </ChampRelie>

        <ChampRelie
          id={idDe("nature")}
          libelle="Nature de la leçon"
          aide={
            saisie.nature === "quiz"
              ? "Un quiz n'a pour l'instant que son titre et sa durée : ses questions ne se saisissent pas encore ici."
              : undefined
          }
          erreur={erreurs.nature}
        >
          {(relie) => (
            <select
              {...relie}
              className="champ-saisie"
              value={saisie.nature}
              onChange={(e) => {
                const valeur = e.currentTarget.value as NatureDeLecon;
                setSaisie((courante) => ({ ...courante, nature: valeur }));
              }}
            >
              {NATURES.map((nature) => (
                <option key={nature.valeur} value={nature.valeur}>
                  {nature.libelle}
                </option>
              ))}
            </select>
          )}
        </ChampRelie>

        {saisie.nature === "video" && (
          <ChampRelie
            id={idDe("adresse_video")}
            libelle="Adresse de la vidéo"
            aide={AIDE_VIDEO}
            erreur={erreurs.adresse_video}
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                type="url"
                inputMode="url"
                autoComplete="off"
                placeholder="https://"
                value={saisie.adresse_video}
                onChange={(e) => {
                  const valeur = e.currentTarget.value;
                  setSaisie((courante) => ({ ...courante, adresse_video: valeur }));
                }}
              />
            )}
          </ChampRelie>
        )}

        {saisie.nature === "texte" && (
          <ChampRelie
            id={idDe("texte")}
            libelle="Texte de la leçon"
            aide="Ce que la personne lira une fois la formation achetée."
            erreur={erreurs.texte}
          >
            {(relie) => (
              <textarea
                {...relie}
                className="champ-saisie champ-zone"
                rows={8}
                value={saisie.texte}
                onChange={(e) => {
                  const valeur = e.currentTarget.value;
                  setSaisie((courante) => ({ ...courante, texte: valeur }));
                }}
              />
            )}
          </ChampRelie>
        )}

        {saisie.nature === "document" && (
          <div className="frm-document">
            {enPlace?.fichier_nom ? (
              <p className="frm-document-en-place">
                <span>
                  Document en place : <b>{enPlace.fichier_nom}</b>
                </span>
                <button
                  type="button"
                  className="bouton bouton-contour"
                  disabled={ouverture.isPending}
                  aria-busy={ouverture.isPending || undefined}
                  aria-label={`Ouvrir le document “${enPlace.fichier_nom}”`}
                  onClick={() => ouverture.mutate(enPlace.id)}
                >
                  {ouverture.isPending ? "Ouverture…" : "Ouvrir"}
                </button>
              </p>
            ) : (
              <p className="carte-note">Aucun document déposé pour cette leçon.</p>
            )}
            <ChampRelie
              id={idDe("fichier")}
              libelle={enPlace?.fichier_nom ? "Remplacer le document" : "Document de la leçon"}
              aide={
                fichier
                  ? `« ${fichier.name} » sera déposé à l'enregistrement.`
                  : "Un PDF ou un document Word, Excel ou PowerPoint. Une vidéo ne se dépose pas ici : choisissez la nature « Vidéo » et collez son adresse."
              }
              erreur={erreurs.fichier}
            >
              {(relie) => (
                <input
                  {...relie}
                  key={tourDeFichier}
                  className="frm-fichier"
                  type="file"
                  onChange={(e) => setFichier(e.currentTarget.files?.[0] ?? null)}
                />
              )}
            </ChampRelie>
          </div>
        )}

        <ChampRelie
          id={idDe("duree_minutes")}
          libelle="Durée, en minutes"
          aide="Un nombre entier. Laissez vide si vous ne l'indiquez pas."
          erreur={erreurs.duree_minutes}
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie frm-court"
              inputMode="numeric"
              autoComplete="off"
              value={saisie.duree_minutes}
              onChange={(e) => {
                const valeur = e.currentTarget.value;
                setSaisie((courante) => ({ ...courante, duree_minutes: valeur }));
              }}
            />
          )}
        </ChampRelie>

        <div className="frm-case-bloc">
          <label className="frm-case" htmlFor={idDe("en_apercu_libre")}>
            <input
              id={idDe("en_apercu_libre")}
              type="checkbox"
              checked={saisie.en_apercu_libre}
              aria-describedby={
                erreurs.en_apercu_libre ? `${idDe("en_apercu_libre")}-erreur` : undefined
              }
              onChange={(e) => {
                const coche = e.currentTarget.checked;
                setSaisie((courante) => ({ ...courante, en_apercu_libre: coche }));
              }}
            />
            <span>Visible avant achat (aperçu libre)</span>
          </label>
          {erreurs.en_apercu_libre && (
            <span className="champ-erreur" id={`${idDe("en_apercu_libre")}-erreur`}>
              {erreurs.en_apercu_libre}
            </span>
          )}
        </div>

        <footer className="console-formulaire-pied">
          <p className="carte-note" role="status">
            {etat}
          </p>
          <button
            type="button"
            className="bouton bouton-discret"
            disabled={occupe}
            onClick={onFermer}
          >
            {etat ? "Fermer" : "Annuler"}
          </button>
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={occupe}
            aria-busy={occupe || undefined}
          >
            {occupe ? "Enregistrement…" : enPlace ? "Enregistrer la leçon" : "Ajouter la leçon"}
          </button>
        </footer>
      </form>
    </Fenetre>
  );
}

// ── Le programme ────────────────────────────────────────────────────────────

/** Un geste du programme fait d'un seul clic : déplacer, retirer, rétablir. */
interface Geste {
  /** Le bouton cliqué : lui seul se montre occupé. */
  cle: string;
  envoyer: () => Promise<EcritureDeFormation>;
  /** Ce qui est annoncé, lu sur la fiche que le serveur vient de rendre. */
  annonce: (rendue: FormationAdmin) => string;
  /** Où poser le focus une fois l'écran mis à jour (un sélecteur). */
  focus: string;
}

type FenetreOuverte =
  | { quoi: "module"; module: ModuleAdmin | null }
  | { quoi: "lecon"; module: ModuleAdmin; lecon: LeconAdmin | null }
  | null;

/** « 2 sur 5 », lu sur la fiche rendue — ou rien si l'élément n'y est plus. */
function placeDuModule(rendue: FormationAdmin, moduleId: string): string {
  const liste = presents(rendue.modules);
  const index = liste.findIndex((module) => module.id === moduleId);
  return index < 0 ? "" : `${index + 1} sur ${liste.length}`;
}

function placeDeLaLecon(rendue: FormationAdmin, moduleId: string, leconId: string): string {
  const module = rendue.modules.find((m) => m.id === moduleId);
  const liste = presents(module?.lecons ?? []);
  const index = liste.findIndex((lecon) => lecon.id === leconId);
  return index < 0 ? "" : `${index + 1} sur ${liste.length}`;
}

/** Monter ou descendre d'un cran. Deux boutons, pas de glisser-déposer : le
 *  clavier, le doigt et la souris font le même geste.
 *
 *  `aria-disabled` et non `disabled` : en bout de liste ou pendant l'envoi,
 *  le bouton reste atteignable et GARDE le focus — on enchaîne « monter,
 *  monter » sans le rechercher. */
function BoutonDeRang({
  sens,
  nom,
  cle,
  auBout,
  occupe,
  enCours,
  onClick,
}: {
  sens: -1 | 1;
  /** « le module “Poser son offre” ». */
  nom: string;
  cle: string;
  auBout: boolean;
  occupe: boolean;
  enCours: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="console-bouton-icone frm-rang"
      data-frm={cle}
      aria-label={`${sens === -1 ? "Monter" : "Descendre"} ${nom}`}
      aria-disabled={auBout || occupe || undefined}
      aria-busy={enCours || undefined}
      onClick={() => {
        if (!auBout && !occupe) onClick();
      }}
    >
      <span className={sens === -1 ? "frm-fleche frm-fleche-haut" : "frm-fleche frm-fleche-bas"}>
        <Icone nom="fleche" taille={18} />
      </span>
    </button>
  );
}

function Programme({
  formation,
  onEcrit,
}: {
  formation: FormationAdmin;
  onEcrit: (reponse: EcritureDeFormation) => void;
}) {
  const conteneur = useRef<HTMLDivElement>(null);
  /** Le focus à poser quand la fiche rendue sera à l'écran. */
  const focusVoulu = useRef<string | null>(null);
  const [replies, setReplies] = useState<ReadonlySet<string>>(new Set());
  const [fenetre, setFenetre] = useState<FenetreOuverte>(null);
  const [annonce, setAnnonce] = useState("");
  const [erreur, setErreur] = useState("");
  const relire = useRelecture();

  const geste = useMutation({
    ...enFile(formation.id),
    mutationFn: (voulu: Geste) => voulu.envoyer(),
    onSuccess: (reponse, voulu) => {
      focusVoulu.current = voulu.focus;
      setErreur(repartir(reponse.refuses, []).ailleurs);
      setAnnonce(voulu.annonce(reponse.formation));
      onEcrit(reponse);
    },
    onError: (cause: unknown) => {
      focusVoulu.current = null;
      setAnnonce("");
      setErreur(avecSuite(lireLEchec(cause, []).general, relire(cause)));
    },
  });

  // Un seul geste à la fois : un ordre envoyé pendant qu'un autre voyage
  // serait calculé sur une liste déjà dépassée.
  const occupe = geste.isPending;
  const cleEnCours = geste.isPending ? geste.variables?.cle : undefined;

  // Un élément déplacé change de place dans la page, et le navigateur lui
  // retire le focus ; un élément retiré n'est plus là du tout. On le repose
  // donc nous-mêmes, une fois la nouvelle fiche dessinée ET l'envoi clos :
  // tant qu'il court, les boutons sont inactifs et refuseraient le focus.
  useEffect(() => {
    if (occupe) return;
    const selecteur = focusVoulu.current;
    if (!selecteur) return;
    focusVoulu.current = null;
    conteneur.current?.querySelector<HTMLElement>(selecteur)?.focus();
  }, [formation, occupe]);

  function faire(voulu: Geste) {
    if (occupe) return;
    setErreur("");
    geste.mutate(voulu);
  }

  function basculer(moduleId: string) {
    setReplies((avant) => {
      const apres = new Set(avant);
      if (apres.has(moduleId)) apres.delete(moduleId);
      else apres.add(moduleId);
      return apres;
    });
  }

  const modules = presents(formation.modules);
  const modulesRetires = retires(formation.modules);
  const ordreDesModules = modules.map((module) => module.id);

  return (
    <Carte
      titre="Le programme"
      note="Les modules dans l'ordre où ils sont suivis, et leurs leçons."
      action={
        <button
          type="button"
          className="bouton bouton-contour"
          disabled={occupe}
          onClick={() => setFenetre({ quoi: "module", module: null })}
        >
          <Icone nom="plus" taille={16} />
          Ajouter un module
        </button>
      }
    >
      <div className="frm-programme" ref={conteneur}>
        {erreur && (
          <p className="bandeau bandeau-echec" role="alert">
            {erreur}
          </p>
        )}
        {/* Toujours présent, même vide : une zone d'annonce posée en même
            temps que son texte n'est pas lue. */}
        <p className="frm-annonce" role="status">
          {annonce}
        </p>

        {modules.length === 0 && (
          <p className="frm-programme-vide">
            Aucun module pour l'instant. Ajoutez le premier, puis rangez-y ses leçons.
          </p>
        )}

        <ol className="frm-modules">
          {modules.map((module, index) => {
            const ouvert = !replies.has(module.id);
            const lecons = presents(module.lecons);
            const leconsRetirees = retires(module.lecons);
            const ordreDesLecons = lecons.map((lecon) => lecon.id);
            const nom = `le module “${module.titre}”`;
            return (
              <li key={module.id} className="frm-module">
                <div className="frm-module-entete">
                  <h3 className="frm-module-titre">
                    <button
                      type="button"
                      className="frm-bascule"
                      aria-expanded={ouvert}
                      aria-controls={`frm-corps-${module.id}`}
                      onClick={() => basculer(module.id)}
                    >
                      <span className={ouvert ? "frm-fleche frm-fleche-bas" : "frm-fleche"}>
                        <Icone nom="chevron" taille={16} />
                      </span>
                      <span className="frm-module-texte">
                        <span className="frm-module-rang">Module {index + 1}</span>
                        <span className="frm-module-nom">{module.titre}</span>
                        <span className="frm-module-compte">
                          {lecons.length === 0 ? "Aucune leçon" : pluriel(lecons.length, "leçon")}
                        </span>
                      </span>
                    </button>
                  </h3>
                  <div className="console-gestes">
                    <BoutonDeRang
                      sens={-1}
                      nom={nom}
                      cle={`monter-${module.id}`}
                      auBout={index === 0}
                      occupe={occupe}
                      enCours={cleEnCours === `monter-${module.id}`}
                      onClick={() =>
                        faire({
                          cle: `monter-${module.id}`,
                          envoyer: () =>
                            adminApi.ordonnerLesModules(
                              formation.id,
                              deplacer(ordreDesModules, index, -1),
                            ),
                          annonce: (rendue) =>
                            `« ${module.titre} » est maintenant le module ${placeDuModule(rendue, module.id)}.`,
                          focus: `[data-frm="monter-${module.id}"]`,
                        })
                      }
                    />
                    <BoutonDeRang
                      sens={1}
                      nom={nom}
                      cle={`descendre-${module.id}`}
                      auBout={index === modules.length - 1}
                      occupe={occupe}
                      enCours={cleEnCours === `descendre-${module.id}`}
                      onClick={() =>
                        faire({
                          cle: `descendre-${module.id}`,
                          envoyer: () =>
                            adminApi.ordonnerLesModules(
                              formation.id,
                              deplacer(ordreDesModules, index, 1),
                            ),
                          annonce: (rendue) =>
                            `« ${module.titre} » est maintenant le module ${placeDuModule(rendue, module.id)}.`,
                          focus: `[data-frm="descendre-${module.id}"]`,
                        })
                      }
                    />
                    <button
                      type="button"
                      className="bouton bouton-contour"
                      data-frm={`modifier-${module.id}`}
                      aria-label={`Modifier ${nom}`}
                      disabled={occupe}
                      onClick={() => setFenetre({ quoi: "module", module })}
                    >
                      Modifier
                    </button>
                    <button
                      type="button"
                      className="bouton bouton-discret"
                      aria-label={`Retirer ${nom}`}
                      disabled={occupe}
                      aria-busy={cleEnCours === `retirer-${module.id}` || undefined}
                      onClick={() =>
                        faire({
                          cle: `retirer-${module.id}`,
                          envoyer: () => adminApi.modifierLeModule(module.id, { retire: true }),
                          annonce: () =>
                            `Le module « ${module.titre} » est retiré du programme. Vous le retrouvez sous « Retirés », d'où il se rétablit.`,
                          focus: `[data-frm="retires-${formation.id}"] > summary`,
                        })
                      }
                    >
                      Retirer
                    </button>
                  </div>
                </div>

                <div id={`frm-corps-${module.id}`} className="frm-module-corps" hidden={!ouvert}>
                  {module.description && (
                    <p className="frm-module-description">{module.description}</p>
                  )}

                  {lecons.length > 0 && (
                    <ol className="frm-lecons">
                      {lecons.map((lecon, rang) => {
                        const nomDeLecon = `la leçon “${lecon.titre}”`;
                        const deplacee = (sens: -1 | 1): Geste => {
                          const cle = `${sens === -1 ? "monter" : "descendre"}-${lecon.id}`;
                          return {
                            cle,
                            envoyer: () =>
                              adminApi.ordonnerLesLecons(
                                module.id,
                                deplacer(ordreDesLecons, rang, sens),
                              ),
                            annonce: (rendue) =>
                              `« ${lecon.titre} » est maintenant la leçon ${placeDeLaLecon(rendue, module.id, lecon.id)} du module.`,
                            focus: `[data-frm="${cle}"]`,
                          };
                        };
                        return (
                          <li key={lecon.id} className="frm-lecon">
                            <div className="frm-lecon-corps">
                              <p className="frm-lecon-titre">{lecon.titre}</p>
                              <p className="carte-note">
                                {[
                                  libelleDeNature(lecon.nature),
                                  lecon.duree_minutes > 0
                                    ? `${lecon.duree_minutes}${INSECABLE}min`
                                    : "",
                                  lecon.en_apercu_libre ? "Aperçu libre" : "",
                                  lecon.nature === "document" && !lecon.fichier_nom
                                    ? "Document à déposer"
                                    : "",
                                  lecon.nature === "texte" && !lecon.texte
                                    ? "Texte à écrire"
                                    : "",
                                ]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </p>
                            </div>
                            <div className="console-gestes">
                              <BoutonDeRang
                                sens={-1}
                                nom={nomDeLecon}
                                cle={`monter-${lecon.id}`}
                                auBout={rang === 0}
                                occupe={occupe}
                                enCours={cleEnCours === `monter-${lecon.id}`}
                                onClick={() => faire(deplacee(-1))}
                              />
                              <BoutonDeRang
                                sens={1}
                                nom={nomDeLecon}
                                cle={`descendre-${lecon.id}`}
                                auBout={rang === lecons.length - 1}
                                occupe={occupe}
                                enCours={cleEnCours === `descendre-${lecon.id}`}
                                onClick={() => faire(deplacee(1))}
                              />
                              <button
                                type="button"
                                className="bouton bouton-contour"
                                data-frm={`modifier-${lecon.id}`}
                                aria-label={`Modifier ${nomDeLecon}`}
                                disabled={occupe}
                                onClick={() => setFenetre({ quoi: "lecon", module, lecon })}
                              >
                                Modifier
                              </button>
                              <button
                                type="button"
                                className="bouton bouton-discret"
                                aria-label={`Retirer ${nomDeLecon}`}
                                disabled={occupe}
                                aria-busy={cleEnCours === `retirer-${lecon.id}` || undefined}
                                onClick={() =>
                                  faire({
                                    cle: `retirer-${lecon.id}`,
                                    envoyer: () =>
                                      adminApi.modifierLaLecon(lecon.id, { retire: true }),
                                    annonce: () =>
                                      `La leçon « ${lecon.titre} » est retirée du module. Vous la retrouvez sous « Retirés », d'où elle se rétablit.`,
                                    focus: `[data-frm="retires-${module.id}"] > summary`,
                                  })
                                }
                              >
                                Retirer
                              </button>
                            </div>
                          </li>
                        );
                      })}
                    </ol>
                  )}

                  <button
                    type="button"
                    className="bouton bouton-discret frm-ajout"
                    aria-label={`Ajouter une leçon au module “${module.titre}”`}
                    disabled={occupe}
                    onClick={() => setFenetre({ quoi: "lecon", module, lecon: null })}
                  >
                    <Icone nom="plus" taille={16} />
                    Ajouter une leçon
                  </button>

                  {leconsRetirees.length > 0 && (
                    <details className="frm-retires" data-frm={`retires-${module.id}`}>
                      <summary>Retirés ({leconsRetirees.length})</summary>
                      <ul className="frm-retires-liste">
                        {leconsRetirees.map((lecon) => (
                          <li key={lecon.id} className="frm-retire">
                            <span className="frm-retire-nom">
                              {lecon.titre}
                              <span className="carte-note"> · {libelleDeNature(lecon.nature)}</span>
                            </span>
                            <button
                              type="button"
                              className="bouton bouton-contour"
                              aria-label={`Rétablir la leçon “${lecon.titre}”`}
                              disabled={occupe}
                              aria-busy={cleEnCours === `retablir-${lecon.id}` || undefined}
                              onClick={() =>
                                faire({
                                  cle: `retablir-${lecon.id}`,
                                  envoyer: () =>
                                    adminApi.modifierLaLecon(lecon.id, { retire: false }),
                                  annonce: () =>
                                    `La leçon « ${lecon.titre} » est rétablie, en fin de module.`,
                                  focus: `[data-frm="modifier-${lecon.id}"]`,
                                })
                              }
                            >
                              Rétablir
                            </button>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        {modulesRetires.length > 0 && (
          <details className="frm-retires" data-frm={`retires-${formation.id}`}>
            <summary>Retirés ({modulesRetires.length})</summary>
            <ul className="frm-retires-liste">
              {modulesRetires.map((module) => (
                <li key={module.id} className="frm-retire">
                  <span className="frm-retire-nom">
                    {module.titre}
                    <span className="carte-note">
                      {" · "}
                      {pluriel(module.lecons.length, "leçon")}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="bouton bouton-contour"
                    aria-label={`Rétablir le module “${module.titre}”`}
                    disabled={occupe}
                    aria-busy={cleEnCours === `retablir-${module.id}` || undefined}
                    onClick={() =>
                      faire({
                        cle: `retablir-${module.id}`,
                        envoyer: () => adminApi.modifierLeModule(module.id, { retire: false }),
                        annonce: () =>
                          `Le module « ${module.titre} » est rétabli, en fin de programme.`,
                        focus: `[data-frm="modifier-${module.id}"]`,
                      })
                    }
                  >
                    Rétablir
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>

      {fenetre?.quoi === "module" && (
        <FenetreDeModule
          formation={formation}
          module={fenetre.module}
          onEcrit={(reponse, dit) => {
            setErreur("");
            setAnnonce(dit);
            onEcrit(reponse);
          }}
          onFermer={() => setFenetre(null)}
        />
      )}
      {fenetre?.quoi === "lecon" && (
        <FenetreDeLecon
          formation={formation}
          module={fenetre.module}
          lecon={fenetre.lecon}
          onEcrit={(reponse, dit) => {
            setErreur("");
            setAnnonce(dit);
            onEcrit(reponse);
          }}
          onFermer={() => setFenetre(null)}
        />
      )}
    </Carte>
  );
}

// ── Le suivi : ce qui est commun aux élèves et aux séances ──────────────────

/** Les clés du suivi d'une formation. HORS de `CLE`, à dessein : `ranger`
 *  abandonne toute lecture en vol sous `CLE`, et emporterait celles-ci. */
function cleDesInscrits(formationId: string) {
  return ["admin", "inscrits-d-une-formation", formationId] as const;
}

function cleDesEleves(formationId: string) {
  return ["admin", "eleves-d-une-formation", formationId] as const;
}

function cleDesSeances(formationId: string) {
  return ["admin", "seances-d-une-formation", formationId] as const;
}

type LectureDesEleves = Awaited<ReturnType<typeof adminApi.elevesDeLaFormation>>;

/** Comment nommer un élève : son nom, à défaut son adresse. */
function nomDeLEleve(ligne: { nom: string; email?: string }): string {
  return (ligne.nom ?? "").trim() || (ligne.email ?? "").trim() || "cet élève";
}

/** Une ligne du tableau : UNE personne pour UN achat. */
function cleDeLigne(ligne: { achat_id: string; eleve_id: string | null }): string {
  return `${ligne.achat_id}:${ligne.eleve_id ?? "sans-compte"}`;
}

/** L'état d'un accès : le mot de la gérante, et sa pastille. Le mot est
 *  écrit : l'état ne se lit jamais à la seule teinte. */
const ACCES: Record<EtatDeLAcces, { libelle: string; pastille: string }> = {
  ouvert: { libelle: "Ouvert", pastille: "pastille pastille-succes" },
  echu: { libelle: "Échu", pastille: "pastille pastille-alerte" },
  retire: { libelle: "Retiré", pastille: "pastille pastille-neutre" },
};

function etatConnu(valeur: unknown): valeur is EtatDeLAcces {
  return typeof valeur === "string" && Object.prototype.hasOwnProperty.call(ACCES, valeur);
}

/** « jusqu'au 20 mai 2027 », ou « sans limite ». */
function finDeLAcces(dernierJour: string | null | undefined): string {
  return dernierJour ? `jusqu'au ${f.jour(dernierJour)}` : "sans limite";
}

/** L'achat est-il retiré ? Le serveur le dit par la date du retrait. */
function accesRetire(achat: AchatDeFormationAdmin): boolean {
  return typeof achat.revoque_le === "string" && achat.revoque_le !== "";
}

/** « 45 min », « 2 h », « 1 h 30 » — et « 0 min » pour un vrai zéro. */
function heuresEtMinutes(minutes: number): string {
  const entieres = Number.isFinite(minutes) && minutes > 0 ? Math.round(minutes) : 0;
  const heures = Math.floor(entieres / 60);
  const reste = entieres % 60;
  if (heures === 0) return `${reste}${INSECABLE}min`;
  if (reste === 0) return `${heures}${INSECABLE}h`;
  return `${heures}${INSECABLE}h${INSECABLE}${String(reste).padStart(2, "0")}`;
}

/** La phrase d'un envoi qui a échoué, ou un repli. */
function ditDuRefus(cause: unknown, repli: string): string {
  return cause instanceof Error && cause.message ? cause.message : repli;
}

/** Remet un fichier reçu au navigateur, qui l'enregistre dans les
 *  téléchargements. L'adresse retient le fichier en mémoire : elle est
 *  relâchée une fois l'enregistrement parti. */
function enregistrerLeFichier(blob: Blob, nom: string): void {
  const adresse = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = adresse;
  lien.download = nom;
  lien.hidden = true;
  document.body.append(lien);
  lien.click();
  lien.remove();
  window.setTimeout(() => URL.revokeObjectURL(adresse), 10_000);
}

// ── Les élèves ──────────────────────────────────────────────────────────────

/** Un motif COURT : de quoi s'en souvenir, pas un compte rendu. La limite qui
 *  fait foi est celle du serveur (`AchatFormation.motif_de_revocation`, 200
 *  le 20/11/2026) : au-delà il refuse (`motif_trop_long`), et sa phrase se
 *  pose contre le champ. Celle-ci ne fait qu'arrêter la saisie avant. */
const LONGUEUR_DU_MOTIF = 200;

const MOTIF_MANQUANT = "Indiquez le motif, en quelques mots.";

const DATE_MANQUANTE = "Choisissez une date, ou cliquez sur « Sans limite ».";

/** La progression d'un élève : une barre, et la même chose en toutes
 *  lettres. Sans leçon au programme, le pourcentage ne se calcule pas : on le
 *  dit, on n'affiche pas un zéro (règle 1). */
function Progression({ ligne }: { ligne: EleveDeFormation }) {
  if (typeof ligne.pourcent !== "number" || !Number.isFinite(ligne.pourcent)) {
    return (
      <span className="frm-progression-vide">non calculable : aucune leçon au programme</span>
    );
  }
  const pourcent = Math.min(100, Math.max(0, Math.round(ligne.pourcent)));
  const lu =
    `${ligne.lecons_terminees}${INSECABLE}/${INSECABLE}${ligne.lecons_total}${INSECABLE}` +
    `leçon${ligne.lecons_total > 1 ? "s" : ""} — ${pourcent}${INSECABLE}%`;
  return (
    <div className="frm-progression">
      <div
        className="jauge"
        role="progressbar"
        aria-valuenow={pourcent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={lu}
        aria-label={`Progression de ${nomDeLEleve(ligne)}`}
      >
        {/* Toute la largeur, décalée de ce qui manque : un `transform` se
            compose sans refaire la mise en page (voir `.jauge`). */}
        <span
          className="jauge-remplissage"
          style={{ transform: `translateX(-${100 - pourcent}%)` }}
        />
      </div>
      <span className="frm-progression-texte">{lu}</span>
    </div>
  );
}

/** Ce que la gérante est en train de décider pour une ligne. */
type PanneauDAcces = { genre: "retrait" | "date"; ligne: EleveDeFormation } | null;

/** Un changement d'accès demandé : retirer, rétablir, ou fixer le dernier
 *  jour. `bouton` : celui qui reprend le focus une fois la réponse rangée. */
interface ChangementVoulu {
  ligne: EleveDeFormation;
  corps: ChangementDAcces;
  bouton: "acces" | "date";
}

/** Les élèves d'une formation : ce que la gérante montre à un auditeur.
 *
 *  Une ligne par personne et par achat — l'accès, la dernière connexion, la
 *  dernière activité sur la formation, la progression, le temps de présentiel
 *  signé. Le serveur calcule tout (`catalog/suivi.py`) : l'écran n'additionne
 *  ni ne déduit rien.
 *
 *  Repliée par défaut : rien n'est lu avant l'ouverture, et tout est relu à
 *  chaque ouverture. Trois états se disent — le chargement, la panne (jamais
 *  « aucun élève » sur une lecture ratée, règle 1) et la liste REÇUE vide.
 *
 *  Un accès se RETIRE, avec un motif, et se rétablit ; son dernier jour se
 *  change, ou se lève (« Sans limite »). L'achat et son paiement restent.
 *  L'accès est celui de l'ACHAT : quand plusieurs personnes le partagent, le
 *  geste vaut pour toutes, et la confirmation le dit. L'état affiché après
 *  coup est celui que le serveur rend — l'écran n'annonce pas un changement
 *  que la réponse ne montre pas.
 *
 *  Le motif et la date d'un retrait viennent de la liste des achats, lue à
 *  côté : si elle manque, la ligne dit « Retiré » sans son détail, et la panne
 *  se dit. */
function Eleves({ formation }: { formation: FormationAdmin }) {
  const base = useId();
  const cache = useQueryClient();
  const conteneur = useRef<HTMLDivElement>(null);
  const [ouvert, setOuvert] = useState(false);
  const [panneau, setPanneau] = useState<PanneauDAcces>(null);
  const [motif, setMotif] = useState("");
  const [dernierJour, setDernierJour] = useState("");
  const [erreurDuChamp, setErreurDuChamp] = useState("");
  const [annonce, setAnnonce] = useState("");
  const [erreur, setErreur] = useState("");
  const cle = cleDesEleves(formation.id);
  const cleDesAchats = cleDesInscrits(formation.id);
  const idDuMotif = `${base}-motif`;
  const idDuJour = `${base}-jour`;

  const lecture = useQuery({
    queryKey: cle,
    queryFn: () => adminApi.elevesDeLaFormation(formation.id),
    enabled: ouvert,
  });
  const detail = useQuery({
    queryKey: cleDesAchats,
    queryFn: () => adminApi.inscritsDeLaFormation(formation.id),
    enabled: ouvert,
  });

  function boutonDe(voulu: { ligne: EleveDeFormation; bouton: "acces" | "date" }) {
    return (
      conteneur.current?.querySelector<HTMLElement>(
        `[data-frm="${voulu.bouton}-${cleDeLigne(voulu.ligne)}"]`,
      ) ?? null
    );
  }

  function fermerLePanneau() {
    setPanneau(null);
    setMotif("");
    setDernierJour("");
    setErreurDuChamp("");
  }

  const changement = useMutation({
    ...enFile(formation.id),
    mutationFn: (voulu: ChangementVoulu) =>
      adminApi.changerLAccesALaFormation(voulu.ligne.achat_id, voulu.corps),
    onSuccess: (rendue: AchatDeFormationAdmin | null, voulu) => {
      const nom = nomDeLEleve(voulu.ligne);
      fermerLePanneau();
      // Le nombre d'inscrits de la bande d'état vient de la fiche : on la
      // relit, plutôt que de deviner si un accès retiré compte encore.
      void cache.invalidateQueries({ queryKey: CLE });
      if (rendue === null || rendue.id !== voulu.ligne.achat_id) {
        // Réponse illisible : on ne déduit rien, on relit les listes.
        void cache.invalidateQueries({ queryKey: cle });
        void cache.invalidateQueries({ queryKey: cleDesAchats });
        setErreur("");
        setAnnonce("Le changement est envoyé : la liste est relue, vérifiez l'état affiché.");
        boutonDe(voulu)?.focus();
        return;
      }
      // L'achat que le serveur vient de rendre prend la place de l'ancien…
      cache.setQueryData<{ achats: AchatDeFormationAdmin[] }>(cleDesAchats, (avant) =>
        avant
          ? { achats: avant.achats.map((achat) => (achat.id === rendue.id ? rendue : achat)) }
          : avant,
      );
      // … et son état se reporte sur chaque personne qui le partage.
      const etat = rendue.acces;
      if (etatConnu(etat)) {
        cache.setQueryData<LectureDesEleves>(cle, (avant) =>
          avant
            ? {
                ...avant,
                eleves: avant.eleves.map((ligne) =>
                  ligne.achat_id === rendue.id
                    ? { ...ligne, acces: etat, acces_jusqu_au: rendue.acces_jusqu_au ?? null }
                    : ligne,
                ),
              }
            : avant,
        );
      } else {
        // Un serveur qui ne dit pas l'état : la liste est relue.
        void cache.invalidateQueries({ queryKey: cle });
      }

      const { revoque } = voulu.corps;
      const conforme =
        revoque === undefined
          ? (rendue.acces_jusqu_au ?? null) === (voulu.corps.acces_jusqu_au ?? null)
          : accesRetire(rendue) === revoque;
      if (!conforme) {
        setAnnonce("");
        setErreur(
          `Le changement demandé pour « ${nom} » n'apparaît pas dans la réponse du serveur : vérifiez l'état affiché, puis réessayez.`,
        );
      } else if (revoque === true) {
        setErreur("");
        setAnnonce(
          `L'accès de « ${nom} » est retiré. Rien n'est effacé : vous pouvez le rétablir d'ici.`,
        );
      } else if (revoque === false) {
        setErreur("");
        setAnnonce(
          avecSuite(
            `L'accès de « ${nom} » est rétabli.`,
            etat === "echu"
              ? "Son dernier jour est passé : l'accès reste échu tant que vous ne changez pas sa date de fin."
              : "",
          ),
        );
      } else {
        setErreur("");
        setAnnonce(
          avecSuite(
            rendue.acces_jusqu_au
              ? `L'accès de « ${nom} » court maintenant jusqu'au ${f.jour(rendue.acces_jusqu_au)} inclus.`
              : `L'accès de « ${nom} » est maintenant sans limite de durée.`,
            etat === "echu" ? "Cette date est passée : l'accès est échu." : "",
          ),
        );
      }
      boutonDe(voulu)?.focus();
    },
    onError: (cause: unknown, voulu) => {
      setAnnonce("");
      // Un refus qui désigne le champ ouvert (`motif_trop_long`,
      // `date_illisible`) se pose CONTRE lui, tant que le panneau le montre.
      const champ = cause instanceof RefusDuServeur ? cause.champ : "";
      if (voulu.corps.revoque === true && champ === "motif") {
        setErreur("");
        setErreurDuChamp(ditDuRefus(cause, MOTIF_MANQUANT));
        document.getElementById(idDuMotif)?.focus();
        return;
      }
      if (voulu.bouton === "date" && champ === "acces_jusqu_au") {
        setErreur("");
        setErreurDuChamp(ditDuRefus(cause, DATE_MANQUANTE));
        document.getElementById(idDuJour)?.focus();
        return;
      }
      // Un achat que le serveur ne trouve plus : la liste a changé ailleurs.
      const perime = ecranPerime(cause);
      if (perime) {
        void cache.invalidateQueries({ queryKey: cle });
        void cache.invalidateQueries({ queryKey: cleDesAchats });
      }
      setErreur(
        avecSuite(
          ditDuRefus(cause, "Le changement n'a pas pu être fait. Réessayez."),
          perime ? DIT_RELU : "",
        ),
      );
    },
  });

  // Une LECTURE : hors de la file des écritures, et sans pause hors connexion.
  const exportation = useMutation({
    networkMode: "always",
    mutationFn: () => adminApi.exporterLesEleves(formation.id, formation.slug),
    onSuccess: (fichier) => {
      enregistrerLeFichier(fichier.blob, fichier.nom);
      setErreur("");
      setAnnonce(
        `Le fichier « ${fichier.nom} » est prêt : votre navigateur l'enregistre dans vos téléchargements.`,
      );
    },
    onError: (cause: unknown) => {
      setAnnonce("");
      setErreur(ditDuRefus(cause, "Le fichier n'a pas pu être préparé. Réessayez."));
    },
  });

  const occupe = changement.isPending;
  const enCours = occupe && changement.variables ? cleDeLigne(changement.variables.ligne) : "";
  const lignes = lecture.data?.eleves ?? [];
  const achatsParId = new Map((detail.data?.achats ?? []).map((achat) => [achat.id, achat]));

  /** Combien de personnes partagent l'achat de cette ligne. */
  function partage(ligne: EleveDeFormation): number {
    return lignes.filter((autre) => autre.achat_id === ligne.achat_id).length;
  }

  function renoncer() {
    const ouvertSur = panneau;
    fermerLePanneau();
    if (ouvertSur) {
      boutonDe({
        ligne: ouvertSur.ligne,
        bouton: ouvertSur.genre === "date" ? "date" : "acces",
      })?.focus();
    }
  }

  function ouvrirLePanneau(genre: "retrait" | "date", ligne: EleveDeFormation) {
    setErreur("");
    setAnnonce("");
    setMotif("");
    setErreurDuChamp("");
    setDernierJour(genre === "date" ? (ligne.acces_jusqu_au ?? "").slice(0, 10) : "");
    setPanneau({ genre, ligne });
  }

  function retablir(ligne: EleveDeFormation) {
    setErreur("");
    setAnnonce("");
    fermerLePanneau();
    changement.mutate({ ligne, corps: { revoque: false }, bouton: "acces" });
  }

  function confirmerLeRetrait() {
    if (occupe || panneau?.genre !== "retrait") return;
    const dit = motif.trim();
    if (dit === "") {
      setErreurDuChamp(MOTIF_MANQUANT);
      document.getElementById(idDuMotif)?.focus();
      return;
    }
    setErreurDuChamp("");
    setErreur("");
    changement.mutate({
      ligne: panneau.ligne,
      corps: { revoque: true, motif: dit },
      bouton: "acces",
    });
  }

  /** `jour` : un jour `AAAA-MM-JJ`, ou `null` pour « sans limite ». */
  function fixerLeDernierJour(jour: string | null) {
    if (occupe || panneau?.genre !== "date") return;
    if (jour === "") {
      setErreurDuChamp(DATE_MANQUANTE);
      document.getElementById(idDuJour)?.focus();
      return;
    }
    setErreurDuChamp("");
    setErreur("");
    changement.mutate({
      ligne: panneau.ligne,
      corps: { acces_jusqu_au: jour },
      bouton: "date",
    });
  }

  const partageDuPanneau = panneau ? partage(panneau.ligne) : 0;
  const ditLePartage =
    panneau && partageDuPanneau > 1
      ? `Cet achat est partagé par ${partageDuPanneau} personnes${
          panneau.ligne.organisation ? ` de « ${panneau.ligne.organisation} »` : ""
        } : le changement vaut pour toutes.`
      : "";

  return (
    <Carte
      titre="Élèves"
      note="Les personnes inscrites à cette formation : leur accès, leur avancée et leur présence."
      action={
        <button
          type="button"
          className="bouton bouton-contour"
          aria-expanded={ouvert}
          aria-controls={`${base}-corps`}
          onClick={() => setOuvert((avant) => !avant)}
        >
          {ouvert ? "Masquer les élèves" : "Afficher les élèves"}
        </button>
      }
    >
      <div id={`${base}-corps`} hidden={!ouvert} ref={conteneur}>
        {ouvert && (
          <div className="frm-inscrits-corps">
            {erreur && (
              <p className="bandeau bandeau-echec" role="alert">
                {erreur}
              </p>
            )}
            {/* Toujours présent, même vide : une zone d'annonce posée en même
                temps que son texte n'est pas lue. */}
            <p className="frm-annonce" role="status">
              {annonce}
            </p>

            {lecture.isError && (
              <ErreurDeChargement
                quoi="les élèves"
                erreur={lecture.error}
                perimees={lecture.isRefetchError}
              />
            )}
            {/* Le détail des retraits manque : les lignes restent, et on le
                dit — un accès retiré s'affiche alors sans sa date ni son
                motif. */}
            {detail.isError && !lecture.isError && lignes.length > 0 && (
              <ErreurDeChargement
                quoi="le détail des accès retirés"
                erreur={detail.error}
                perimees={detail.isRefetchError}
              />
            )}

            {lecture.isPending && <Squelette lignes={3} />}

            {/* Sous une mise à jour ratée, « aucun » ne se redit pas. */}
            {lecture.data && lignes.length === 0 && !lecture.isError && (
              <Vide
                icone={<Icone nom="formations" />}
                titre="Aucun élève pour l'instant"
                texte="Les personnes qui achètent cette formation apparaissent ici, avec leur accès et leur avancée."
              />
            )}

            {lignes.length > 0 && (
              <>
                <div className="frm-eleves-outils">
                  <p className="carte-note">
                    {pluriel(lignes.length, "ligne")} — une par personne et par achat.
                  </p>
                  <button
                    type="button"
                    className={
                      exportation.isPending
                        ? "bouton bouton-contour bouton-chargement"
                        : "bouton bouton-contour"
                    }
                    aria-disabled={exportation.isPending || undefined}
                    aria-busy={exportation.isPending || undefined}
                    onClick={() => {
                      if (!exportation.isPending) exportation.mutate();
                    }}
                  >
                    <Icone nom="telecharger" taille={16} />
                    {exportation.isPending ? "Préparation…" : "Exporter (CSV)"}
                  </button>
                </div>

                {/* Les rôles sont écrits : sur téléphone les lignes deviennent
                    des cartes (`display: block`), et un navigateur qui voit
                    un tableau sans sa mise en forme cesse de l'annoncer comme
                    tel. */}
                <div className="tableau-cadre tableau-defile frm-eleves-cadre">
                  <table className="tableau frm-eleves" role="table">
                    <thead role="rowgroup">
                      <tr role="row">
                        <th scope="col" role="columnheader">
                          Élève
                        </th>
                        <th scope="col" role="columnheader">
                          Organisation
                        </th>
                        <th scope="col" role="columnheader">
                          Acheté le
                        </th>
                        <th scope="col" role="columnheader">
                          Accès
                        </th>
                        <th scope="col" role="columnheader">
                          Dernière connexion
                        </th>
                        <th scope="col" role="columnheader">
                          Dernière activité
                        </th>
                        <th scope="col" role="columnheader">
                          Progression
                        </th>
                        <th scope="col" role="columnheader">
                          Présentiel signé
                        </th>
                        <th scope="col" role="columnheader">
                          <span className="visuellement-cache">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody role="rowgroup">
                      {lignes.map((ligne) => {
                        const cleLigne = cleDeLigne(ligne);
                        const retire = ligne.acces === "retire";
                        const nom = nomDeLEleve(ligne);
                        const achat = achatsParId.get(ligne.achat_id);
                        const motifDuRetrait = (achat?.motif_de_revocation ?? "").trim();
                        const etat = etatConnu(ligne.acces) ? ACCES[ligne.acces] : null;
                        return (
                          <tr key={cleLigne} role="row">
                            <th scope="row" role="rowheader" className="frm-eleve-nom">
                              <strong>{nom}</strong>
                              {ligne.nom.trim() !== "" && ligne.email && (
                                <span className="frm-eleve-adresse">{ligne.email}</span>
                              )}
                            </th>
                            <td role="cell" data-libelle="Organisation">
                              {ligne.organisation || "—"}
                            </td>
                            <td role="cell" data-libelle="Acheté le">
                              {f.date(ligne.achete_le)}
                            </td>
                            <td role="cell" data-libelle="Accès">
                              <span className="frm-acces">
                                {etat && <span className={etat.pastille}>{etat.libelle}</span>}
                                <span>{finDeLAcces(ligne.acces_jusqu_au)}</span>
                                {retire && achat && accesRetire(achat) && (
                                  <span className="frm-acces-detail">
                                    Accès retiré le {f.date(achat.revoque_le)}
                                    {motifDuRetrait ? ` — ${motifDuRetrait}` : ""}
                                  </span>
                                )}
                              </span>
                            </td>
                            <td role="cell" data-libelle="Dernière connexion">
                              {ligne.derniere_connexion
                                ? f.dateHeure(ligne.derniere_connexion)
                                : "jamais"}
                            </td>
                            <td role="cell" data-libelle="Dernière activité">
                              {ligne.derniere_activite
                                ? f.dateHeure(ligne.derniere_activite)
                                : "aucune"}
                            </td>
                            <td role="cell" data-libelle="Progression">
                              <Progression ligne={ligne} />
                            </td>
                            <td role="cell" data-libelle="Présentiel signé">
                              {heuresEtMinutes(ligne.minutes_en_presentiel_signees)}
                            </td>
                            <td role="cell" className="frm-eleve-gestes">
                              {/* `aria-disabled` plutôt que `disabled` : le
                                  bouton garde le focus pendant l'envoi. Le
                                  clic, lui, est alors sans effet. */}
                              <div className="console-gestes">
                                <button
                                  type="button"
                                  className="bouton bouton-contour"
                                  data-frm={`date-${cleLigne}`}
                                  aria-label={`Changer la date de fin d'accès de “${nom}”`}
                                  aria-disabled={occupe || undefined}
                                  onClick={() => {
                                    if (!occupe) ouvrirLePanneau("date", ligne);
                                  }}
                                >
                                  Changer la date de fin
                                </button>
                                <button
                                  type="button"
                                  className={
                                    retire ? "bouton bouton-contour" : "bouton bouton-discret"
                                  }
                                  data-frm={`acces-${cleLigne}`}
                                  aria-label={`${retire ? "Rétablir" : "Retirer"} l'accès de “${nom}”`}
                                  aria-disabled={occupe || undefined}
                                  aria-busy={enCours === cleLigne || undefined}
                                  onClick={() => {
                                    if (occupe) return;
                                    if (retire) retablir(ligne);
                                    else ouvrirLePanneau("retrait", ligne);
                                  }}
                                >
                                  {retire ? "Rétablir l'accès" : "Retirer l'accès"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {panneau?.genre === "retrait" && (
              <div
                className="console-confirmation"
                role="alertdialog"
                aria-labelledby={`${base}-question`}
                aria-describedby={`${base}-consequence`}
                onKeyDown={(evenement) => {
                  if (evenement.key === "Escape" && !occupe) renoncer();
                }}
              >
                <p id={`${base}-question`}>
                  <b>Retirer l'accès de « {nomDeLEleve(panneau.ligne)} » à cette formation ?</b>
                </p>
                <p className="carte-note" id={`${base}-consequence`}>
                  Cette personne ne pourra plus ouvrir la formation depuis son espace. Rien
                  n'est effacé : son achat, son paiement et son suivi restent enregistrés, et
                  vous pouvez rétablir l'accès à tout moment.{ditLePartage && ` ${ditLePartage}`}
                </p>
                <form
                  className="frm-retrait"
                  noValidate
                  onSubmit={(evenement) => {
                    evenement.preventDefault();
                    confirmerLeRetrait();
                  }}
                >
                  <ChampRelie
                    id={idDuMotif}
                    libelle="Motif du retrait"
                    aide="Quelques mots : un remboursement, un achat fait par erreur…"
                    erreur={erreurDuChamp || undefined}
                  >
                    {(relie) => (
                      <input
                        {...relie}
                        className="champ-saisie"
                        value={motif}
                        maxLength={LONGUEUR_DU_MOTIF}
                        aria-required="true"
                        autoComplete="off"
                        autoFocus
                        onChange={(e) => {
                          setMotif(e.currentTarget.value);
                          if (erreurDuChamp) setErreurDuChamp("");
                        }}
                      />
                    )}
                  </ChampRelie>
                  <div className="console-gestes">
                    <button
                      type="button"
                      className="bouton bouton-discret"
                      disabled={occupe}
                      onClick={renoncer}
                    >
                      Annuler
                    </button>
                    <button
                      type="submit"
                      className="bouton bouton-principal"
                      disabled={occupe}
                      aria-busy={occupe || undefined}
                    >
                      {occupe ? "Retrait…" : "Oui, retirer l'accès"}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {panneau?.genre === "date" && (
              <form
                className="console-confirmation"
                role="group"
                aria-labelledby={`${base}-date-titre`}
                aria-describedby={`${base}-date-note`}
                noValidate
                onKeyDown={(evenement) => {
                  if (evenement.key === "Escape" && !occupe) renoncer();
                }}
                onSubmit={(evenement) => {
                  evenement.preventDefault();
                  fixerLeDernierJour(dernierJour);
                }}
              >
                <p id={`${base}-date-titre`}>
                  <b>Date de fin d'accès de « {nomDeLEleve(panneau.ligne)} »</b>
                </p>
                <p className="carte-note" id={`${base}-date-note`}>
                  Aujourd'hui : {finDeLAcces(panneau.ligne.acces_jusqu_au)}. Le jour choisi est
                  le dernier où la formation reste ouverte ; une date déjà passée ferme l'accès
                  tout de suite.{ditLePartage && ` ${ditLePartage}`}
                </p>
                <ChampRelie
                  id={idDuJour}
                  libelle="Dernier jour d'accès"
                  erreur={erreurDuChamp || undefined}
                >
                  {(relie) => (
                    <input
                      {...relie}
                      className="champ-saisie frm-jour"
                      type="date"
                      value={dernierJour}
                      autoFocus
                      onChange={(e) => {
                        setDernierJour(e.currentTarget.value);
                        if (erreurDuChamp) setErreurDuChamp("");
                      }}
                    />
                  )}
                </ChampRelie>
                <div className="console-gestes">
                  <button
                    type="button"
                    className="bouton bouton-discret"
                    disabled={occupe}
                    onClick={renoncer}
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    className="bouton bouton-contour"
                    disabled={occupe}
                    onClick={() => fixerLeDernierJour(null)}
                  >
                    Sans limite
                  </button>
                  <button
                    type="submit"
                    className="bouton bouton-principal"
                    disabled={occupe}
                    aria-busy={occupe || undefined}
                  >
                    {occupe ? "Enregistrement…" : "Enregistrer la date"}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </Carte>
  );
}

// ── Les séances en présentiel ───────────────────────────────────────────────

type EtatDeSeance = "a_venir" | "a_signer" | "signee" | "annulee";

const ETATS_DE_SEANCE: Record<EtatDeSeance, { libelle: string; pastille: string }> = {
  a_venir: { libelle: "À venir", pastille: "pastille pastille-info" },
  a_signer: { libelle: "À signer", pastille: "pastille pastille-alerte" },
  signee: { libelle: "Signée par la formatrice", pastille: "pastille pastille-succes" },
  annulee: { libelle: "Annulée", pastille: "pastille pastille-neutre" },
};

/** Où en est une séance. `maintenant` vient de l'appelant : une horloge lue
 *  pendant le dessin donnerait deux réponses à deux dessins du même état. */
function etatDeLaSeance(seance: SeanceAdmin, maintenant: number): EtatDeSeance {
  if (seance.annulee_le) return "annulee";
  if (seance.signee_par_la_formatrice_le) return "signee";
  const debut = new Date(seance.debut).getTime();
  return Number.isFinite(debut) && debut > maintenant ? "a_venir" : "a_signer";
}

/** Une séance qui porte une signature — celle de la formatrice ou d'un
 *  élève — ne se décrit plus autrement : le serveur le refuse. */
function porteUneSignature(seance: SeanceAdmin): boolean {
  return Boolean(seance.signee_par_la_formatrice_le) || seance.emargements.length > 0;
}

const DIT_FIGEE =
  "Une séance qui porte une signature — la vôtre ou celle d'un élève — ne se modifie plus : " +
  "ni son intitulé, ni sa date, ni sa durée, ni son lieu, ni le nom de la formatrice. " +
  "Vous pouvez encore l'annuler, et en créer une autre.";

function modeDeSignature(mode: string): string {
  return mode === "papier" ? "sur papier" : "en ligne";
}

const CHAMPS_DE_SEANCE = [
  "intitule",
  "debut",
  "duree_minutes",
  "lieu",
  "nom_de_la_formatrice",
] as const;

type ChampDeSeance = (typeof CHAMPS_DE_SEANCE)[number];
type SaisieDeSeance = Record<ChampDeSeance, string>;

/** Le début d'une séance tel que le champ le montre : `AAAA-MM-JJTHH:MM`, À
 *  L'HEURE DE PARIS — celle que le serveur attend en retour. */
function debutEnSaisie(iso: string): string {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return "";
  const morceaux = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const lu = (genre: string) => morceaux.find((morceau) => morceau.type === genre)?.value ?? "";
  return `${lu("year")}-${lu("month")}-${lu("day")}T${lu("hour")}:${lu("minute")}`;
}

function saisieDeSeance(seance: SeanceAdmin | null): SaisieDeSeance {
  return {
    intitule: seance?.intitule ?? "",
    debut: seance ? debutEnSaisie(seance.debut) : "",
    duree_minutes: nombreEnSaisie(seance?.duree_minutes ?? 0),
    lieu: seance?.lieu ?? "",
    nom_de_la_formatrice: seance?.nom_de_la_formatrice ?? "",
  };
}

/** Créer une séance, ou corriger celle qui n'est pas encore signée. */
function FenetreDeSeance({
  formation,
  seance,
  onEcrit,
  onFermer,
}: {
  formation: FormationAdmin;
  /** Absente : on ajoute une séance. */
  seance: SeanceAdmin | null;
  onEcrit: (rendue: SeanceAdmin, annonce: string) => void;
  onFermer: () => void;
}) {
  const base = useId();
  const idDe = (champ: string) => idDuChamp(base, champ);
  /** La séance telle que le serveur la tient : créée avec un champ écarté,
   *  elle EXISTE déjà, et le second envoi doit la modifier. */
  const [enPlace, setEnPlace] = useState<SeanceAdmin | null>(seance);
  const [saisie, setSaisie] = useState<SaisieDeSeance>(() => saisieDeSeance(seance));
  const [erreurs, setErreurs] = useState<ErreursParChamp>({});
  const [general, setGeneral] = useState("");
  const [etat, setEtat] = useState("");
  useFocusSurLErreur(erreurs, CHAMPS_DE_SEANCE, base);

  const envoi = useMutation({
    ...enFile(formation.id),
    mutationFn: (champs: Record<string, unknown>) =>
      enPlace
        ? adminApi.modifierLaSeance(enPlace.id, champs)
        : adminApi.creerUneSeance(formation.id, champs),
    onSuccess: (reponse) => {
      const annonce = enPlace
        ? `La séance « ${reponse.seance.intitule} » est enregistrée.`
        : `La séance « ${reponse.seance.intitule} » est ajoutée.`;
      onEcrit(reponse.seance, annonce);
      if (reponse.refuses.length === 0) {
        onFermer();
        return;
      }
      setEnPlace(reponse.seance);
      const { parChamp, ailleurs } = repartir(reponse.refuses, CHAMPS_DE_SEANCE);
      setErreurs(parChamp);
      setGeneral(ailleurs);
      setEtat(
        "La séance est enregistrée, sauf ce qui est signalé : corrigez, puis enregistrez de nouveau.",
      );
    },
    onError: (cause: unknown) => {
      const lu = lireLEchec(cause, CHAMPS_DE_SEANCE);
      setErreurs(lu.parChamp);
      setGeneral(lu.general);
      setEtat("");
    },
  });

  const champ = (nom: ChampDeSeance) => ({
    value: saisie[nom],
    onChange: (e: { currentTarget: { value: string } }) => {
      const valeur = e.currentTarget.value;
      setSaisie((courante) => ({ ...courante, [nom]: valeur }));
    },
  });

  return (
    <Fenetre
      titre={enPlace ? "Modifier la séance" : "Ajouter une séance en présentiel"}
      onFermer={onFermer}
      verrouillee={envoi.isPending}
    >
      <form
        className="console-formulaire"
        noValidate
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (envoi.isPending) return;
          const avant = saisieDeSeance(enPlace);
          const champs: Record<string, unknown> = {};
          for (const nom of CHAMPS_DE_SEANCE) {
            if (!enPlace || saisie[nom] !== avant[nom]) champs[nom] = saisie[nom].trim();
          }
          if (Object.keys(champs).length === 0) {
            onFermer();
            return;
          }
          setErreurs({});
          setGeneral("");
          setEtat("");
          envoi.mutate(champs);
        }}
      >
        {general && (
          <p className="bandeau bandeau-echec" role="alert">
            {general}
          </p>
        )}
        <ChampRelie
          id={idDe("intitule")}
          libelle="Intitulé de la séance"
          aide="Par exemple : « Journée 1 — poser son offre »."
          erreur={erreurs.intitule}
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              maxLength={200}
              aria-required="true"
              autoComplete="off"
              {...champ("intitule")}
            />
          )}
        </ChampRelie>
        <div className="console-champs">
          <ChampRelie
            id={idDe("debut")}
            libelle="Date et heure de début"
            aide="À l'heure de Paris."
            erreur={erreurs.debut}
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                type="datetime-local"
                aria-required="true"
                {...champ("debut")}
              />
            )}
          </ChampRelie>
          <ChampRelie
            id={idDe("duree_minutes")}
            libelle="Durée, en minutes"
            aide="Un nombre entier : 210 pour 3 h 30."
            erreur={erreurs.duree_minutes}
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                inputMode="numeric"
                aria-required="true"
                autoComplete="off"
                {...champ("duree_minutes")}
              />
            )}
          </ChampRelie>
        </div>
        <ChampRelie
          id={idDe("lieu")}
          libelle="Lieu"
          aide="L'adresse ou le nom de la salle."
          erreur={erreurs.lieu}
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              maxLength={200}
              autoComplete="off"
              {...champ("lieu")}
            />
          )}
        </ChampRelie>
        <ChampRelie
          id={idDe("nom_de_la_formatrice")}
          libelle="Nom de la formatrice"
          aide="Il figure sur la feuille d'émargement, et il est demandé pour signer la séance."
          erreur={erreurs.nom_de_la_formatrice}
        >
          {(relie) => (
            <input
              {...relie}
              className="champ-saisie"
              maxLength={120}
              autoComplete="off"
              {...champ("nom_de_la_formatrice")}
            />
          )}
        </ChampRelie>
        <p className="carte-note">{DIT_FIGEE}</p>
        <footer className="console-formulaire-pied">
          <p className="carte-note" role="status">
            {etat}
          </p>
          <button
            type="button"
            className="bouton bouton-discret"
            disabled={envoi.isPending}
            onClick={onFermer}
          >
            {etat ? "Fermer" : "Annuler"}
          </button>
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={envoi.isPending}
            aria-busy={envoi.isPending || undefined}
          >
            {envoi.isPending
              ? "Enregistrement…"
              : enPlace
                ? "Enregistrer la séance"
                : "Ajouter la séance"}
          </button>
        </footer>
      </form>
    </Fenetre>
  );
}

/** Noter une signature recueillie sur la feuille imprimée : on choisit
 *  l'élève dans la liste de la formation, et on recopie le nom signé.
 *
 *  Ne sont proposées que les personnes qui ont un compte d'élève et n'ont pas
 *  encore signé cette séance. La liste est celle de la carte « Élèves » : la
 *  même lecture, sous la même clé. */
function SignaturePapier({
  formation,
  seance,
  occupe,
  onNoter,
  onFermer,
}: {
  formation: FormationAdmin;
  seance: SeanceAdmin;
  occupe: boolean;
  onNoter: (ligne: EleveDeFormation, nom: string) => void;
  onFermer: () => void;
}) {
  const base = useId();
  const [choisie, setChoisie] = useState("");
  const [nom, setNom] = useState("");
  const [erreurDuChoix, setErreurDuChoix] = useState("");
  const { data, isPending, isError, isRefetchError, error } = useQuery({
    queryKey: cleDesEleves(formation.id),
    queryFn: () => adminApi.elevesDeLaFormation(formation.id),
  });

  const dejaSignes = new Set(seance.emargements.map((emargement) => emargement.eleve_id));
  const candidats = (data?.eleves ?? []).filter(
    (ligne) => ligne.eleve_id !== null && !dejaSignes.has(ligne.eleve_id),
  );

  return (
    <form
      className="console-confirmation"
      role="group"
      aria-labelledby={`${base}-titre`}
      noValidate
      onKeyDown={(evenement) => {
        if (evenement.key === "Escape" && !occupe) onFermer();
      }}
      onSubmit={(evenement) => {
        evenement.preventDefault();
        if (occupe) return;
        const ligne = candidats.find((candidat) => cleDeLigne(candidat) === choisie);
        if (!ligne) {
          setErreurDuChoix("Choisissez l'élève qui a signé la feuille.");
          document.getElementById(`${base}-eleve`)?.focus();
          return;
        }
        onNoter(ligne, nom.trim());
      }}
    >
      <p id={`${base}-titre`}>
        <b>Noter une signature papier — « {seance.intitule} »</b>
      </p>
      <p className="carte-note">
        Pour une personne qui a signé la feuille imprimée. Une signature notée ne se retire
        pas : vérifiez le nom avant d'enregistrer.
      </p>
      {isError && (
        <ErreurDeChargement quoi="les élèves" erreur={error} perimees={isRefetchError} />
      )}
      {isPending && <Squelette lignes={2} />}
      {data && candidats.length === 0 && !isError && (
        <p className="frm-programme-vide">
          Aucun élève à noter : tous ont déjà signé cette séance, ou personne n'a encore de
          compte d'élève sur cette formation.
        </p>
      )}
      {candidats.length > 0 && (
        <>
          <ChampRelie
            id={`${base}-eleve`}
            libelle="Élève"
            erreur={erreurDuChoix || undefined}
          >
            {(relie) => (
              <select
                {...relie}
                className="champ-saisie"
                value={choisie}
                aria-required="true"
                autoFocus
                onChange={(e) => {
                  const valeur = e.currentTarget.value;
                  setChoisie(valeur);
                  setErreurDuChoix("");
                  // Le nom de la fiche est proposé : il reste à corriger si la
                  // feuille porte une autre écriture.
                  const ligne = candidats.find((candidat) => cleDeLigne(candidat) === valeur);
                  if (ligne) setNom(ligne.nom.trim());
                }}
              >
                <option value="">Choisir un élève…</option>
                {candidats.map((ligne) => (
                  <option key={cleDeLigne(ligne)} value={cleDeLigne(ligne)}>
                    {nomDeLEleve(ligne)}
                    {ligne.organisation ? ` — ${ligne.organisation}` : ""}
                  </option>
                ))}
              </select>
            )}
          </ChampRelie>
          <ChampRelie
            id={`${base}-nom`}
            libelle="Nom signé sur la feuille"
            aide="Le nom et le prénom, tels qu'ils sont écrits sur la feuille."
          >
            {(relie) => (
              <input
                {...relie}
                className="champ-saisie"
                value={nom}
                maxLength={120}
                aria-required="true"
                autoComplete="off"
                onChange={(e) => setNom(e.currentTarget.value)}
              />
            )}
          </ChampRelie>
        </>
      )}
      <div className="console-gestes">
        <button type="button" className="bouton bouton-discret" disabled={occupe} onClick={onFermer}>
          Annuler
        </button>
        {candidats.length > 0 && (
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={occupe}
            aria-busy={occupe || undefined}
          >
            {occupe ? "Enregistrement…" : "Enregistrer la signature"}
          </button>
        )}
      </div>
    </form>
  );
}

/** La feuille d'émargement d'une séance, prête à imprimer.
 *
 *  Elle est posée DIRECTEMENT sous `body` (un portail), et `body` porte une
 *  classe tant qu'elle est ouverte : la feuille de style d'impression peut
 *  ainsi écarter tout le reste de la page sans rien connaître de sa
 *  structure (`Formations.css`, « Impression »).
 *
 *  Une ligne par élève : sa signature, avec sa date et son mode, ou une case
 *  vide à signer à la main. */
function FeuilleImprimable({ seance, onFermer }: { seance: SeanceAdmin; onFermer: () => void }) {
  const base = useId();
  const { data, isPending, isError, isRefetchError, error } = useQuery({
    queryKey: ["admin", "feuille-d-emargement", seance.id] as const,
    queryFn: () => adminApi.feuilleDEmargement(seance.id),
  });

  useEffect(() => {
    document.body.classList.add("frm-impression");
    return () => document.body.classList.remove("frm-impression");
  }, []);

  return createPortal(
    <Fenetre titre="Feuille d'émargement" onFermer={onFermer} classe="frm-feuille-fenetre">
      {isError && (
        <ErreurDeChargement quoi="la feuille" erreur={error} perimees={isRefetchError} />
      )}
      {isPending && <Squelette lignes={4} />}
      {data && (
        <div className="frm-feuille">
          <p className="frm-feuille-formation">{data.formation.titre}</p>
          <h3 className="frm-feuille-titre">{data.seance.intitule}</h3>
          {data.seance.annulee_le && (
            <p className="frm-feuille-annulee">
              <strong>Séance annulée le {f.dateHeureDeParis(data.seance.annulee_le)}.</strong>
            </p>
          )}
          <dl className="frm-seance-faits">
            <div>
              <dt>Date et heure</dt>
              <dd>{f.dateHeureDeParis(data.seance.debut)}</dd>
            </div>
            <div>
              <dt>Durée</dt>
              <dd>{heuresEtMinutes(data.seance.duree_minutes)}</dd>
            </div>
            <div>
              <dt>Lieu</dt>
              <dd>{data.seance.lieu || "—"}</dd>
            </div>
            <div>
              <dt>Formatrice</dt>
              <dd>{data.formatrice?.nom || "—"}</dd>
            </div>
          </dl>

          {data.lignes.length === 0 ? (
            <p className="frm-programme-vide">Aucun élève n'est inscrit à cette formation.</p>
          ) : (
            <table className="frm-feuille-table">
              <caption className="visuellement-cache">Signatures des élèves</caption>
              <thead>
                <tr>
                  <th scope="col">Nom</th>
                  <th scope="col">Organisation</th>
                  <th scope="col">Signature</th>
                </tr>
              </thead>
              <tbody>
                {data.lignes.map((ligne) => (
                  <tr key={cleDeLigne(ligne)}>
                    <th scope="row">{ligne.nom || "—"}</th>
                    <td>{ligne.organisation || "—"}</td>
                    <td>
                      {ligne.signature ? (
                        <>
                          <span className="frm-feuille-signe">{ligne.signature.nom_signe}</span>
                          <span className="frm-feuille-preuve">
                            Signé le {f.dateHeureDeParis(ligne.signature.signe_le)},{" "}
                            {modeDeSignature(ligne.signature.mode)}
                          </span>
                        </>
                      ) : (
                        <span className="frm-feuille-case">
                          <span className="visuellement-cache">Case à signer à la main</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="frm-feuille-formatrice">
            <p id={`${base}-formatrice`} className="frm-feuille-intertitre">
              Signature de la formatrice
            </p>
            {data.formatrice?.signee_le ? (
              <p aria-labelledby={`${base}-formatrice`}>
                <span className="frm-feuille-signe">{data.formatrice.nom}</span>
                <span className="frm-feuille-preuve">
                  Signée le {f.dateHeureDeParis(data.formatrice.signee_le)}
                </span>
              </p>
            ) : (
              <span className="frm-feuille-case frm-feuille-case-large">
                <span className="visuellement-cache">Case à signer à la main</span>
              </span>
            )}
          </div>
        </div>
      )}
      <div className="console-gestes frm-feuille-gestes">
        <button type="button" className="bouton bouton-discret" onClick={onFermer}>
          Fermer
        </button>
        <button
          type="button"
          className="bouton bouton-principal"
          disabled={!data}
          onClick={() => window.print()}
        >
          Imprimer
        </button>
      </div>
    </Fenetre>,
    document.body,
  );
}

/** Un geste sur une séance, fait d'un seul envoi : annuler, rétablir, signer,
 *  noter une signature papier. */
interface GesteDeSeance {
  seance: SeanceAdmin;
  /** Le bouton cliqué : lui seul se montre occupé. */
  cle: string;
  corps: Record<string, unknown>;
  /** La séance RENDUE montre-t-elle ce qui a été demandé ? */
  conforme: (rendue: SeanceAdmin) => boolean;
  annonce: string;
  /** La liste des élèves change aussi (leur temps de présentiel signé). */
  touchLesEleves?: boolean;
}

type PanneauDeSeance = { genre: "signer" | "papier"; seanceId: string } | null;

type FenetreDeSuivi =
  | { quoi: "seance"; seance: SeanceAdmin | null }
  | { quoi: "feuille"; seance: SeanceAdmin }
  | null;

/** Les séances en présentiel d'une formation, et leurs signatures.
 *
 *  Repliée par défaut, comme les élèves. Une séance s'ANNULE et se rétablit :
 *  elle ne disparaît pas, et les signatures déjà posées restent. Une signature,
 *  elle, ne se retire pas — signer demande donc une confirmation.
 *
 *  Tant que la séance n'a pas commencé, les gestes de signature ne sont pas
 *  proposés : le serveur les refuserait (`seance_pas_commencee`), et une phrase
 *  vaut mieux qu'un bouton qui refuse. Le serveur reste juge : son refus, s'il
 *  vient, s'affiche contre la séance. */
function Seances({ formation }: { formation: FormationAdmin }) {
  const base = useId();
  const cache = useQueryClient();
  const conteneur = useRef<HTMLDivElement>(null);
  /** Le focus à poser quand la séance rendue sera à l'écran. */
  const focusVoulu = useRef<string | null>(null);
  const [ouvert, setOuvert] = useState(false);
  /** L'heure du poste, relevée à l'ouverture de la carte. */
  const [maintenant, setMaintenant] = useState(() => Date.now());
  const [fenetre, setFenetre] = useState<FenetreDeSuivi>(null);
  const [panneau, setPanneau] = useState<PanneauDeSeance>(null);
  const [annonce, setAnnonce] = useState("");
  const [erreur, setErreur] = useState<{ seanceId: string; message: string } | null>(null);
  const cle = cleDesSeances(formation.id);

  const { data, isPending, isError, isRefetchError, error } = useQuery({
    queryKey: cle,
    queryFn: () => adminApi.seancesDeLaFormation(formation.id),
    enabled: ouvert,
  });

  /** Range la séance que le serveur vient de rendre : à la place de
   *  l'ancienne, ou à son rang parmi les autres, dans l'ordre des débuts. */
  const ranger = useCallback(
    (rendue: SeanceAdmin) => {
      cache.setQueryData<{ seances: SeanceAdmin[] }>(cleDesSeances(formation.id), (avant) => {
        if (!avant) return avant;
        const connue = avant.seances.some((seance) => seance.id === rendue.id);
        const liste = connue
          ? avant.seances.map((seance) => (seance.id === rendue.id ? rendue : seance))
          : [...avant.seances, rendue];
        return {
          seances: [...liste].sort(
            (a, b) => new Date(a.debut).getTime() - new Date(b.debut).getTime(),
          ),
        };
      });
    },
    [cache, formation.id],
  );

  const geste = useMutation({
    ...enFile(formation.id),
    mutationFn: (voulu: GesteDeSeance) => adminApi.modifierLaSeance(voulu.seance.id, voulu.corps),
    onSuccess: (reponse, voulu) => {
      ranger(reponse.seance);
      setPanneau(null);
      if (voulu.touchLesEleves) {
        void cache.invalidateQueries({ queryKey: cleDesEleves(formation.id) });
      }
      const ecartes = repartir(reponse.refuses, []).ailleurs;
      if (!voulu.conforme(reponse.seance)) {
        setAnnonce("");
        setErreur({
          seanceId: voulu.seance.id,
          message: avecSuite(
            "Le changement demandé n'apparaît pas dans la réponse du serveur : vérifiez l'état affiché, puis réessayez.",
            ecartes,
          ),
        });
      } else {
        setErreur(ecartes ? { seanceId: voulu.seance.id, message: ecartes } : null);
        setAnnonce(voulu.annonce);
      }
      focusVoulu.current = `[data-frm="seance-${voulu.seance.id}"]`;
    },
    onError: (cause: unknown, voulu) => {
      setAnnonce("");
      // Une séance ou un élève que le serveur ne trouve plus : l'écran a
      // changé ailleurs, on le relit.
      const perime = ecranPerime(cause);
      if (perime) {
        void cache.invalidateQueries({ queryKey: cle });
        void cache.invalidateQueries({ queryKey: cleDesEleves(formation.id) });
      }
      setErreur({
        seanceId: voulu.seance.id,
        message: avecSuite(
          ditDuRefus(cause, "Le changement n'a pas pu être fait. Réessayez."),
          perime ? DIT_RELU : "",
        ),
      });
    },
  });

  const occupe = geste.isPending;
  const cleEnCours = occupe ? geste.variables?.cle : undefined;
  const seances = data?.seances ?? [];

  // Un geste change les boutons de la séance (« Annuler » devient
  // « Rétablir ») : celui qu'on vient de cliquer n'est plus là. Le focus va
  // donc au titre de la séance, une fois la réponse dessinée.
  useEffect(() => {
    if (occupe) return;
    const selecteur = focusVoulu.current;
    if (!selecteur) return;
    focusVoulu.current = null;
    conteneur.current?.querySelector<HTMLElement>(selecteur)?.focus();
  }, [data, occupe]);

  function faire(voulu: GesteDeSeance) {
    if (occupe) return;
    setErreur(null);
    setAnnonce("");
    geste.mutate(voulu);
  }

  function ouvrirLePanneau(genre: "signer" | "papier", seance: SeanceAdmin) {
    if (occupe) return;
    setErreur(null);
    setAnnonce("");
    setPanneau({ genre, seanceId: seance.id });
  }

  function fermerLePanneau(seance: SeanceAdmin) {
    setPanneau(null);
    conteneur.current?.querySelector<HTMLElement>(`[data-frm="seance-${seance.id}"]`)?.focus();
  }

  return (
    <Carte
      titre="Séances en présentiel"
      note="Les rendez-vous en salle de cette formation, et les signatures de présence."
      action={
        <button
          type="button"
          className="bouton bouton-contour"
          aria-expanded={ouvert}
          aria-controls={`${base}-corps`}
          onClick={() => {
            setMaintenant(Date.now());
            setOuvert((avant) => !avant);
          }}
        >
          {ouvert ? "Masquer les séances" : "Afficher les séances"}
        </button>
      }
    >
      <div id={`${base}-corps`} hidden={!ouvert} ref={conteneur}>
        {ouvert && (
          <div className="frm-inscrits-corps">
            <p className="carte-note">{DIT_FIGEE}</p>
            {/* Toujours présent, même vide : une zone d'annonce posée en même
                temps que son texte n'est pas lue. */}
            <p className="frm-annonce" role="status">
              {annonce}
            </p>

            {isError && (
              <ErreurDeChargement quoi="les séances" erreur={error} perimees={isRefetchError} />
            )}
            {isPending && <Squelette lignes={3} />}

            {data && (
              <button
                type="button"
                className="bouton bouton-contour frm-ajout"
                disabled={occupe}
                onClick={() => setFenetre({ quoi: "seance", seance: null })}
              >
                <Icone nom="plus" taille={16} />
                Ajouter une séance
              </button>
            )}

            {/* Sous une mise à jour ratée, « aucune » ne se redit pas. */}
            {data && seances.length === 0 && !isError && (
              <Vide
                icone={<Icone nom="formations" />}
                titre="Aucune séance en présentiel"
                texte="Ajoutez la première : vos élèves la verront dans leur espace, et pourront y signer leur présence."
              />
            )}

            {seances.length > 0 && (
              <ul className="frm-seances">
                {seances.map((seance) => {
                  const etat = etatDeLaSeance(seance, maintenant);
                  const signable = etat === "a_signer" || etat === "signee";
                  const nombre = seance.emargements.length;
                  const nomDeSeance = `la séance “${seance.intitule}”`;
                  return (
                    <li key={seance.id} className="frm-seance">
                      <div className="frm-seance-tete">
                        <h3
                          className="frm-seance-titre"
                          tabIndex={-1}
                          data-frm={`seance-${seance.id}`}
                        >
                          {seance.intitule}
                        </h3>
                        <span className={ETATS_DE_SEANCE[etat].pastille}>
                          {ETATS_DE_SEANCE[etat].libelle}
                        </span>
                      </div>
                      <dl className="frm-seance-faits">
                        <div>
                          <dt>Date et heure</dt>
                          <dd>{f.dateHeureDeParis(seance.debut)}</dd>
                        </div>
                        <div>
                          <dt>Durée</dt>
                          <dd>{heuresEtMinutes(seance.duree_minutes)}</dd>
                        </div>
                        <div>
                          <dt>Lieu</dt>
                          <dd>{seance.lieu || "—"}</dd>
                        </div>
                        <div>
                          <dt>Formatrice</dt>
                          <dd>{seance.nom_de_la_formatrice || "à indiquer"}</dd>
                        </div>
                        <div>
                          <dt>Signatures</dt>
                          <dd>
                            {nombre === 0
                              ? "Aucune signature d'élève"
                              : `${pluriel(nombre, "signature")} d'élève${nombre > 1 ? "s" : ""}`}
                          </dd>
                        </div>
                      </dl>
                      {seance.annulee_le && (
                        <p className="carte-note">
                          Annulée le {f.dateHeureDeParis(seance.annulee_le)}. Les signatures déjà
                          posées restent.
                        </p>
                      )}
                      {seance.signee_par_la_formatrice_le && (
                        <p className="carte-note">
                          Signée par la formatrice le{" "}
                          {f.dateHeureDeParis(seance.signee_par_la_formatrice_le)}.
                        </p>
                      )}
                      {etat === "a_venir" && (
                        <p className="carte-note">
                          Les signatures s'ouvriront au début de la séance.
                        </p>
                      )}

                      {nombre > 0 && (
                        <details className="frm-retires">
                          <summary>Signatures des élèves ({nombre})</summary>
                          <ul className="frm-retires-liste">
                            {seance.emargements.map((emargement) => (
                              <li key={emargement.id} className="frm-retire">
                                <span className="frm-retire-nom">
                                  {emargement.nom || emargement.nom_signe}
                                  <span className="carte-note">
                                    {" · "}signé le {f.dateHeureDeParis(emargement.signe_le)},{" "}
                                    {modeDeSignature(emargement.mode)}
                                    {emargement.nom_signe &&
                                    emargement.nom_signe !== emargement.nom
                                      ? `, sous le nom « ${emargement.nom_signe} »`
                                      : ""}
                                  </span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}

                      {erreur?.seanceId === seance.id && (
                        <p className="bandeau bandeau-echec" role="alert">
                          {erreur.message}
                        </p>
                      )}

                      <div className="console-gestes">
                        <button
                          type="button"
                          className="bouton bouton-contour"
                          aria-label={`Feuille d'émargement de ${nomDeSeance}`}
                          onClick={() => setFenetre({ quoi: "feuille", seance })}
                        >
                          Feuille d'émargement
                        </button>
                        {signable && !seance.signee_par_la_formatrice_le && (
                          <button
                            type="button"
                            className="bouton bouton-contour"
                            aria-label={`Signer ${nomDeSeance} en tant que formatrice`}
                            disabled={occupe}
                            onClick={() => ouvrirLePanneau("signer", seance)}
                          >
                            Signer en tant que formatrice
                          </button>
                        )}
                        {signable && (
                          <button
                            type="button"
                            className="bouton bouton-contour"
                            aria-label={`Noter une signature papier pour ${nomDeSeance}`}
                            disabled={occupe}
                            onClick={() => ouvrirLePanneau("papier", seance)}
                          >
                            Noter une signature papier
                          </button>
                        )}
                        {!porteUneSignature(seance) && (
                          <button
                            type="button"
                            className="bouton bouton-contour"
                            aria-label={`Modifier ${nomDeSeance}`}
                            disabled={occupe}
                            onClick={() => setFenetre({ quoi: "seance", seance })}
                          >
                            Modifier
                          </button>
                        )}
                        {seance.annulee_le ? (
                          <button
                            type="button"
                            className="bouton bouton-contour"
                            aria-label={`Rétablir ${nomDeSeance}`}
                            disabled={occupe}
                            aria-busy={cleEnCours === `retablir-${seance.id}` || undefined}
                            onClick={() =>
                              faire({
                                seance,
                                cle: `retablir-${seance.id}`,
                                corps: { annulee: false },
                                conforme: (rendue) => !rendue.annulee_le,
                                annonce: `La séance « ${seance.intitule} » est rétablie.`,
                              })
                            }
                          >
                            Rétablir
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="bouton bouton-discret"
                            aria-label={`Annuler ${nomDeSeance}`}
                            disabled={occupe}
                            aria-busy={cleEnCours === `annuler-${seance.id}` || undefined}
                            onClick={() =>
                              faire({
                                seance,
                                cle: `annuler-${seance.id}`,
                                corps: { annulee: true },
                                conforme: (rendue) => Boolean(rendue.annulee_le),
                                annonce: `La séance « ${seance.intitule} » est annulée. Rien n'est effacé : vous pouvez la rétablir d'ici.`,
                              })
                            }
                          >
                            Annuler la séance
                          </button>
                        )}
                      </div>

                      {panneau?.seanceId === seance.id && panneau.genre === "signer" && (
                        <div
                          className="console-confirmation"
                          role="alertdialog"
                          aria-labelledby={`${base}-signer-question`}
                          aria-describedby={`${base}-signer-consequence`}
                          onKeyDown={(evenement) => {
                            if (evenement.key === "Escape" && !occupe) fermerLePanneau(seance);
                          }}
                        >
                          <p id={`${base}-signer-question`}>
                            <b>
                              Signer « {seance.intitule} »
                              {seance.nom_de_la_formatrice
                                ? ` au nom de ${seance.nom_de_la_formatrice}`
                                : " en tant que formatrice"}{" "}
                              ?
                            </b>
                          </p>
                          <p className="carte-note" id={`${base}-signer-consequence`}>
                            Vous attestez que la séance a bien eu lieu. Une signature ne se retire
                            pas, et la séance ne pourra plus être modifiée.
                          </p>
                          <div className="console-gestes">
                            <button
                              type="button"
                              className="bouton bouton-discret"
                              autoFocus
                              disabled={occupe}
                              onClick={() => fermerLePanneau(seance)}
                            >
                              Ne pas signer
                            </button>
                            <button
                              type="button"
                              className="bouton bouton-principal"
                              disabled={occupe}
                              aria-busy={cleEnCours === `signer-${seance.id}` || undefined}
                              onClick={() =>
                                faire({
                                  seance,
                                  cle: `signer-${seance.id}`,
                                  corps: { signer: true },
                                  conforme: (rendue) =>
                                    Boolean(rendue.signee_par_la_formatrice_le),
                                  annonce: `La séance « ${seance.intitule} » est signée par la formatrice.`,
                                })
                              }
                            >
                              {cleEnCours === `signer-${seance.id}` ? "Signature…" : "Oui, signer"}
                            </button>
                          </div>
                        </div>
                      )}

                      {panneau?.seanceId === seance.id && panneau.genre === "papier" && (
                        <SignaturePapier
                          formation={formation}
                          seance={seance}
                          occupe={occupe}
                          onFermer={() => fermerLePanneau(seance)}
                          onNoter={(ligne, nom) =>
                            faire({
                              seance,
                              cle: `papier-${seance.id}`,
                              corps: {
                                emargement_papier: {
                                  achat_id: ligne.achat_id,
                                  eleve_id: ligne.eleve_id,
                                  nom,
                                },
                              },
                              conforme: (rendue) =>
                                rendue.emargements.some(
                                  (emargement) => emargement.eleve_id === ligne.eleve_id,
                                ),
                              annonce: `La signature papier de « ${nomDeLEleve(ligne)} » est notée pour « ${seance.intitule} ».`,
                              touchLesEleves: true,
                            })
                          }
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>

      {fenetre?.quoi === "seance" && (
        <FenetreDeSeance
          formation={formation}
          seance={fenetre.seance}
          onEcrit={(rendue, dit) => {
            ranger(rendue);
            setErreur(null);
            setAnnonce(dit);
          }}
          onFermer={() => setFenetre(null)}
        />
      )}
      {fenetre?.quoi === "feuille" && (
        <FeuilleImprimable seance={fenetre.seance} onFermer={() => setFenetre(null)} />
      )}
    </Carte>
  );
}

// ── La liste ────────────────────────────────────────────────────────────────

function CarteDeFormation({
  formation,
  onOuvrir,
}: {
  formation: FormationAdmin;
  onOuvrir: () => void;
}) {
  const modules = presents(formation.modules).length;
  const lecons = leconsPresentes(formation);
  return (
    <li className={formation.en_ligne ? "frm-carte" : "frm-carte frm-carte-hors-ligne"}>
      <div className="frm-carte-image">
        {formation.image ? (
          <img src={formation.image} alt="" loading="lazy" />
        ) : (
          <Icone nom="formations" taille={32} />
        )}
        <span
          className={
            formation.en_ligne
              ? "frm-fanion pastille pastille-succes"
              : "frm-fanion pastille pastille-neutre"
          }
        >
          {formation.en_ligne ? "En ligne" : "Hors ligne"}
        </span>
      </div>
      <div className="frm-carte-corps">
        <h2 className="frm-carte-titre">{formation.titre}</h2>
        {formation.sous_titre && <p className="carte-note">{formation.sous_titre}</p>}
        <dl className="frm-mesures">
          <div>
            <dt>Prix</dt>
            <dd>
              {formation.prix_cents > 0
                ? montant(formation.prix_cents, formation.devise)
                : "À fixer"}
            </dd>
          </div>
          <div>
            <dt>Durée</dt>
            <dd>
              {formation.duree_heures > 0 ? `${formation.duree_heures}${INSECABLE}h` : "—"}
            </dd>
          </div>
          <div>
            <dt>Modules</dt>
            <dd>{modules}</dd>
          </div>
          <div>
            <dt>Leçons</dt>
            <dd>{lecons}</dd>
          </div>
        </dl>
        {inscrits(formation) !== null && (
          <p className="carte-note frm-inscrits">{inscrits(formation)}</p>
        )}
        {formation.manque.length > 0 && (
          <p className="frm-manque">
            Pour la mettre en ligne, il manque {enumerer(formation.manque)}.
          </p>
        )}
        <button
          type="button"
          className="bouton bouton-contour frm-carte-ouvrir"
          data-frm={`ouvrir-${formation.id}`}
          aria-label={`Ouvrir la formation “${formation.titre}”`}
          onClick={onOuvrir}
        >
          Ouvrir
        </button>
      </div>
    </li>
  );
}

// ── La page ─────────────────────────────────────────────────────────────────

export function FormationsAdmin() {
  const cache = useQueryClient();
  const { data, isPending, isError, isRefetchError, error } = useQuery({
    queryKey: CLE,
    queryFn: adminApi.formations,
  });
  const [ouverteId, setOuverteId] = useState<string | null>(null);
  const [creation, setCreation] = useState(false);
  const racine = useRef<HTMLElement>(null);
  /** La formation qu'on vient de quitter : sa carte reprend le focus. */
  const quittee = useRef<string | null>(null);

  useEffect(() => {
    if (ouverteId !== null || quittee.current === null) return;
    const identifiant = quittee.current;
    quittee.current = null;
    racine.current?.querySelector<HTMLElement>(`[data-frm="ouvrir-${identifiant}"]`)?.focus();
  }, [ouverteId]);

  /** Range la fiche que le serveur vient de rendre à la place de l'ancienne —
   *  ou à la suite, pour une formation nouvelle. Aucun rechargement : la
   *  réponse est la formation entière, relue en base. Une lecture de la liste
   *  encore en vol est abandonnée : partie avant l'écriture, elle remettrait
   *  l'ancienne fiche à l'écran. */
  const ranger = useCallback(
    (reponse: EcritureDeFormation) => {
      const rendue = reponse.formation;
      void cache.cancelQueries({ queryKey: CLE });
      cache.setQueryData<{ formations: FormationAdmin[] }>(CLE, (avant) => {
        const liste = avant?.formations ?? [];
        return {
          ...avant,
          formations: liste.some((f) => f.id === rendue.id)
            ? liste.map((f) => (f.id === rendue.id ? rendue : f))
            : [...liste, rendue],
        };
      });
    },
    [cache],
  );

  if (isPending) return <Squelette lignes={5} />;
  // Rien reçu : on le dit, et on s'arrête là. Ni « 0 formation », ni « Aucune
  // formation » sur une lecture qui a échoué (règle 1).
  if (!data) return <ErreurDeChargement quoi="les formations" erreur={error} />;

  const formations = data.formations ?? [];
  const ouverte = formations.find((f) => f.id === ouverteId) ?? null;
  const enLigne = formations.filter((f) => f.en_ligne).length;
  const modules = formations.reduce((somme, f) => somme + presents(f.modules).length, 0);
  const lecons = formations.reduce((somme, f) => somme + leconsPresentes(f), 0);

  return (
    <section className="frm" ref={racine}>
      {isError && (
        <ErreurDeChargement quoi="les formations" erreur={error} perimees={isRefetchError} />
      )}

      {ouverte ? (
        <div className="frm-detail" key={ouverte.id}>
          <button
            type="button"
            className="bouton bouton-discret frm-retour"
            onClick={() => {
              quittee.current = ouverte.id;
              setOuverteId(null);
            }}
          >
            <Icone nom="retour" taille={16} />
            Toutes les formations
          </button>
          <EtatDeLaFormation formation={ouverte} onEcrit={ranger} />
          <div className="frm-zones">
            <Fiche formation={ouverte} onEcrit={ranger} />
            <Programme formation={ouverte} onEcrit={ranger} />
          </div>
          <Eleves formation={ouverte} />
          <Seances formation={ouverte} />
        </div>
      ) : (
        <>
          {/* Le geste principal de l'écran vit dans l'en-tête de la page. */}
          <ActionsDePage>
            <button
              type="button"
              className="bouton bouton-principal"
              onClick={() => setCreation(true)}
            >
              <Icone nom="plus" taille={16} />
              Ajouter une formation
            </button>
          </ActionsDePage>

          <div className="grille-chiffres">
            <Chiffre
              libelle="Formations"
              valeur={formations.length}
              detail={`${formations.length - enLigne} hors ligne`}
            />
            <Chiffre libelle="En ligne" valeur={enLigne} detail="Visibles sur votre site" accent />
            <Chiffre libelle="Modules" valeur={modules} detail="Dans vos programmes" />
            <Chiffre libelle="Leçons" valeur={lecons} detail="Dans vos modules" />
          </div>

          {/* Sous une mise à jour ratée, « aucune » ne se redit pas. */}
          {formations.length === 0 && !isError && (
            <Carte>
              <Vide
                icone={<Icone nom="formations" />}
                titre="Aucune formation"
                texte="Ajoutez votre première formation. Elle restera hors ligne tant que vous ne l'aurez pas mise en ligne vous-même."
              />
            </Carte>
          )}

          <ul className="frm-grille">
            {formations.map((formation) => (
              <CarteDeFormation
                key={formation.id}
                formation={formation}
                onOuvrir={() => setOuverteId(formation.id)}
              />
            ))}
          </ul>

          {creation && (
            <FenetreDeCreation
              onCreee={(reponse) => {
                ranger(reponse);
                setCreation(false);
                setOuverteId(reponse.formation.id);
              }}
              onFermer={() => setCreation(false)}
            />
          )}
        </>
      )}
    </section>
  );
}
