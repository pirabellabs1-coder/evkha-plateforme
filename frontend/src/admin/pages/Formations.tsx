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
 * ## Les inscrits
 *
 * Sous la fiche et le programme, une carte repliée : qui a acheté la
 * formation, et l'accès de chacun. Un accès se retire, avec un motif, et se
 * rétablit ; l'achat reste (`Inscrits`).
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adminApi,
  type AchatDeFormationAdmin,
  type ChampRefuse,
  type CorpsDeFormation,
  type EcritureDeFormation,
  type FormationAdmin,
  type LeconAdmin,
  type ModuleAdmin,
  type NatureDeLecon,
  RefusDuServeur,
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
  children,
}: {
  titre: string;
  onFermer: () => void;
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
      className="console-fenetre frm-fenetre"
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
] as const;

type ChampDeFiche = (typeof CHAMPS_DE_FICHE)[number];
type SaisieDeFiche = Record<ChampDeFiche, string>;

/** Les champs où une case vidée veut dire « zéro ». */
const NOMBRES_DE_FICHE: readonly ChampDeFiche[] = [
  "prix_euros",
  "duree_heures",
  "heures_de_coaching",
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

// ── Les inscrits ────────────────────────────────────────────────────────────

/** La clé des inscrits d'une formation. HORS de `CLE`, à dessein : `ranger`
 *  abandonne toute lecture en vol sous `CLE`, et emporterait celle-ci. */
function cleDesInscrits(formationId: string) {
  return ["admin", "inscrits-d-une-formation", formationId] as const;
}

/** Un motif COURT : de quoi s'en souvenir, pas un compte rendu. La limite qui
 *  fait foi est celle du serveur (`AchatFormation.motif_de_revocation`, 200
 *  le 20/11/2026) : au-delà il refuse (`motif_trop_long`), et sa phrase se
 *  pose contre le champ. Celle-ci ne fait qu'arrêter la saisie avant. */
const LONGUEUR_DU_MOTIF = 200;

const MOTIF_MANQUANT = "Indiquez le motif, en quelques mots.";

/** Comment nommer un inscrit : son organisation, à défaut son adresse. */
function nomDeLInscrit(achat: AchatDeFormationAdmin): string {
  return achat.organisation || achat.email || "cet inscrit";
}

/** L'accès est-il retiré ? Le serveur le dit par la date du retrait. */
function accesRetire(achat: AchatDeFormationAdmin): boolean {
  return typeof achat.revoque_le === "string" && achat.revoque_le !== "";
}

/** « Accès ouvert », ou « Accès retiré le 20 novembre 2026 — remboursement ». */
function etatDeLAcces(achat: AchatDeFormationAdmin): string {
  if (!accesRetire(achat)) return "Accès ouvert";
  const motif = (achat.motif_de_revocation ?? "").trim();
  return `Accès retiré le ${f.date(achat.revoque_le)}${motif ? ` — ${motif}` : ""}`;
}

/** Un changement d'accès demandé : retirer (avec son motif) ou rétablir. */
interface ChangementVoulu {
  achat: AchatDeFormationAdmin;
  revoque: boolean;
  motif?: string;
}

/** Les inscrits d'une formation, et l'accès de chacun.
 *
 *  Repliée par défaut : la liste n'est lue qu'à l'ouverture, et relue à
 *  chaque ouverture. Trois états se disent — le chargement, la panne (jamais
 *  « aucun inscrit » sur une lecture ratée, règle 1) et la liste REÇUE vide.
 *
 *  Un accès se RETIRE, avec un motif, et se rétablit : l'achat et son
 *  paiement restent. Le geste est donc discret, et demande confirmation
 *  parce que la personne perd l'accès sur-le-champ. La ligne affichée après
 *  coup est celle que le serveur rend — l'écran n'annonce pas un retrait que
 *  la ligne rendue ne montre pas. */
function Inscrits({ formation }: { formation: FormationAdmin }) {
  const base = useId();
  const cache = useQueryClient();
  const conteneur = useRef<HTMLDivElement>(null);
  const [ouvert, setOuvert] = useState(false);
  /** L'achat dont on confirme le retrait d'accès. */
  const [aRetirer, setARetirer] = useState<AchatDeFormationAdmin | null>(null);
  const [motif, setMotif] = useState("");
  const [erreurDuMotif, setErreurDuMotif] = useState("");
  const [annonce, setAnnonce] = useState("");
  const [erreur, setErreur] = useState("");
  const cle = cleDesInscrits(formation.id);

  const lecture = useQuery({
    queryKey: cle,
    queryFn: () => adminApi.inscritsDeLaFormation(formation.id),
    enabled: ouvert,
  });

  function boutonDe(achatId: string): HTMLElement | null {
    return (
      conteneur.current?.querySelector<HTMLElement>(`[data-frm="acces-${achatId}"]`) ?? null
    );
  }

  const changement = useMutation({
    ...enFile(formation.id),
    mutationFn: (voulu: ChangementVoulu) =>
      adminApi.changerLAccesALaFormation(
        voulu.achat.id,
        voulu.revoque ? { revoque: true, motif: voulu.motif } : { revoque: false },
      ),
    onSuccess: (rendue: AchatDeFormationAdmin | null, voulu) => {
      const nom = nomDeLInscrit(voulu.achat);
      setARetirer(null);
      setMotif("");
      setErreurDuMotif("");
      // Le nombre d'inscrits de la bande d'état vient de la fiche : on la
      // relit, plutôt que de deviner si un accès retiré compte encore.
      void cache.invalidateQueries({ queryKey: CLE });
      if (rendue !== null && rendue.id === voulu.achat.id) {
        // La ligne que le serveur vient de rendre prend la place de l'ancienne.
        cache.setQueryData<{ achats: AchatDeFormationAdmin[] }>(cle, (avant) =>
          avant
            ? { achats: avant.achats.map((achat) => (achat.id === rendue.id ? rendue : achat)) }
            : avant,
        );
        if (accesRetire(rendue) === voulu.revoque) {
          setErreur("");
          setAnnonce(
            voulu.revoque
              ? `L'accès de « ${nom} » est retiré. Rien n'est effacé : vous pouvez le rétablir d'ici.`
              : `L'accès de « ${nom} » est rétabli.`,
          );
        } else {
          setAnnonce("");
          setErreur(
            `Le changement demandé pour « ${nom} » n'apparaît pas dans la réponse du serveur : vérifiez l'état affiché, puis réessayez.`,
          );
        }
      } else {
        // Réponse illisible : on ne déduit rien, on relit la liste.
        void cache.invalidateQueries({ queryKey: cle });
        setErreur("");
        setAnnonce("Le changement est envoyé : la liste est relue, vérifiez l'état affiché.");
      }
      boutonDe(voulu.achat.id)?.focus();
    },
    onError: (cause: unknown, voulu) => {
      setAnnonce("");
      // Un refus qui désigne le motif (`motif_trop_long`, `motif_illisible`)
      // se pose CONTRE le champ, tant que la confirmation le montre.
      if (voulu.revoque && cause instanceof RefusDuServeur && cause.champ === "motif") {
        setErreur("");
        setErreurDuMotif(cause.message);
        document.getElementById(`${base}-motif`)?.focus();
        return;
      }
      // Un achat que le serveur ne trouve plus : la liste a changé ailleurs.
      const perime = ecranPerime(cause);
      if (perime) void cache.invalidateQueries({ queryKey: cle });
      setErreur(
        avecSuite(
          cause instanceof Error && cause.message
            ? cause.message
            : "Le changement n'a pas pu être fait. Réessayez.",
          perime ? DIT_RELU : "",
        ),
      );
    },
  });

  const occupe = changement.isPending;
  const enCours = occupe ? changement.variables?.achat.id : undefined;
  const achats = lecture.data?.achats ?? [];

  function renoncer() {
    const achat = aRetirer;
    setARetirer(null);
    setMotif("");
    setErreurDuMotif("");
    if (achat) boutonDe(achat.id)?.focus();
  }

  function demanderLeRetrait(achat: AchatDeFormationAdmin) {
    setErreur("");
    setAnnonce("");
    setMotif("");
    setErreurDuMotif("");
    setARetirer(achat);
  }

  function retablir(achat: AchatDeFormationAdmin) {
    setErreur("");
    setAnnonce("");
    setARetirer(null);
    changement.mutate({ achat, revoque: false });
  }

  function confirmerLeRetrait() {
    if (occupe || !aRetirer) return;
    const dit = motif.trim();
    if (dit === "") {
      setErreurDuMotif(MOTIF_MANQUANT);
      document.getElementById(`${base}-motif`)?.focus();
      return;
    }
    setErreurDuMotif("");
    setErreur("");
    changement.mutate({ achat: aRetirer, revoque: true, motif: dit });
  }

  return (
    <Carte
      titre="Inscrits"
      note="Les personnes qui ont acheté cette formation, et l'accès de chacune."
      action={
        <button
          type="button"
          className="bouton bouton-contour"
          aria-expanded={ouvert}
          aria-controls={`${base}-corps`}
          onClick={() => setOuvert((avant) => !avant)}
        >
          {ouvert ? "Masquer les inscrits" : "Afficher les inscrits"}
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
                quoi="les inscrits"
                erreur={lecture.error}
                perimees={lecture.isRefetchError}
              />
            )}

            {lecture.isPending && <Squelette lignes={3} />}

            {/* Sous une mise à jour ratée, « aucun » ne se redit pas. */}
            {lecture.data && achats.length === 0 && !lecture.isError && (
              <Vide
                icone={<Icone nom="formations" />}
                titre="Aucun inscrit pour l'instant"
                texte="Les personnes qui achètent cette formation apparaissent ici, avec leur accès."
              />
            )}

            {achats.length > 0 && (
              <div className="tableau-cadre tableau-defile">
                <table className="tableau">
                  <thead>
                    <tr>
                      <th scope="col">Organisation</th>
                      <th scope="col">Adresse</th>
                      <th scope="col" className="nombre">
                        Montant
                      </th>
                      <th scope="col">Date</th>
                      <th scope="col">État</th>
                      <th scope="col">
                        <span className="visuellement-cache">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {achats.map((achat) => {
                      const retire = accesRetire(achat);
                      const nom = nomDeLInscrit(achat);
                      return (
                        <tr key={achat.id}>
                          <td>
                            <strong>{achat.organisation || "—"}</strong>
                          </td>
                          <td>{achat.email || "—"}</td>
                          <td className="nombre">
                            {typeof achat.montant_cents === "number"
                              ? montant(achat.montant_cents, achat.devise)
                              : "—"}
                          </td>
                          <td>{f.date(achat.achete_le)}</td>
                          <td>{etatDeLAcces(achat)}</td>
                          <td>
                            {/* `aria-disabled` plutôt que `disabled` : le
                                bouton garde le focus pendant l'envoi. Le
                                clic, lui, est alors sans effet. */}
                            <button
                              type="button"
                              className={
                                retire ? "bouton bouton-contour" : "bouton bouton-discret"
                              }
                              data-frm={`acces-${achat.id}`}
                              aria-label={`${retire ? "Rétablir" : "Retirer"} l'accès de “${nom}”`}
                              aria-disabled={occupe || undefined}
                              aria-busy={enCours === achat.id || undefined}
                              onClick={() => {
                                if (occupe) return;
                                if (retire) retablir(achat);
                                else demanderLeRetrait(achat);
                              }}
                            >
                              {retire ? "Rétablir l'accès" : "Retirer l'accès"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {aRetirer && (
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
                  <b>Retirer l'accès de « {nomDeLInscrit(aRetirer)} » à cette formation ?</b>
                </p>
                <p className="carte-note" id={`${base}-consequence`}>
                  Cette personne ne pourra plus ouvrir la formation depuis son espace. Rien
                  n'est effacé : son achat et son paiement restent enregistrés, et vous pouvez
                  rétablir l'accès à tout moment.
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
                    id={`${base}-motif`}
                    libelle="Motif du retrait"
                    aide="Quelques mots : un remboursement, un achat fait par erreur…"
                    erreur={erreurDuMotif || undefined}
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
                          if (erreurDuMotif) setErreurDuMotif("");
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
          </div>
        )}
      </div>
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
          <Inscrits formation={ouverte} />
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
