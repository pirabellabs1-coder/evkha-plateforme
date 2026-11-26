/** L'éditeur enrichi des lettres d'information (Tiptap).
 *
 * Tout ce que la gérante a demandé le 26/11/2026 : titres, gras, italique,
 * souligné, barré, couleur du texte et du fond, taille, alignement, listes,
 * citation, séparateur, liens, et des IMAGES téléversées directement — par le
 * bouton, en collant ou en glissant un fichier.
 *
 * Ce qu'il produit est du HTML que le SERVEUR nettoie à l'enregistrement
 * (`lettre/nettoyage.py`, liste blanche). L'éditeur n'offre donc que ce que
 * le nettoyage garde : un bouton dont l'effet disparaîtrait à l'envoi
 * tromperait la rédactrice. Pas de bloc de code, pas de police exotique.
 *
 * Chargé à part (`React.lazy` dans `Redaction.tsx`) : l'éditeur pèse plus que
 * tout le reste de l'administration, et seul cet écran s'en sert.
 */
import { useEffect, useRef, useState } from "react";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import TextAlign from "@tiptap/extension-text-align";
import { BackgroundColor, Color, FontSize, TextStyle } from "@tiptap/extension-text-style";

import { adminApi } from "../../api";
import { adresseDeLien } from "./outils";
import "./EditeurEnrichi.css";

/** Les teintes proposées d'un clic. Une couleur libre reste possible. */
const COULEURS = [
  { nom: "Encre", valeur: "#1a1a1a" },
  { nom: "Gris", valeur: "#5f5f5f" },
  { nom: "Or", valeur: "#a8800f" },
  { nom: "Rouge", valeur: "#b3261e" },
  { nom: "Vert", valeur: "#18784a" },
  { nom: "Bleu", valeur: "#1c5d99" },
  { nom: "Prune", valeur: "#7b2d8e" },
];

const FONDS = [
  { nom: "Jaune", valeur: "#fdf4d6" },
  { nom: "Vert", valeur: "#e8f5ee" },
  { nom: "Bleu", valeur: "#eaf2fa" },
  { nom: "Rose", valeur: "#fdeceb" },
  { nom: "Gris", valeur: "#f2f0ef" },
];

const TAILLES = [
  { nom: "Petite", valeur: "13px" },
  { nom: "Normale", valeur: "" },
  { nom: "Grande", valeur: "18px" },
  { nom: "Très grande", valeur: "22px" },
];

/** Les pictogrammes de la barre, dessinés comme ceux de la console
 *  (`admin/icones.tsx`) : trait de 1,6 sur une grille de 20. */
const TRACES = {
  gauche: "M3.5 5h13M3.5 8.5h8M3.5 12h13M3.5 15.5h8",
  centre: "M3.5 5h13M6 8.5h8M3.5 12h13M6 15.5h8",
  droite: "M3.5 5h13M8.5 8.5h8M3.5 12h13M8.5 15.5h8",
  justifie: "M3.5 5h13M3.5 8.5h13M3.5 12h13M3.5 15.5h13",
  puces: "M7.5 5.5h9M7.5 10h9M7.5 14.5h9M4 5.5h.1M4 10h.1M4 14.5h.1",
  numeros: "M8 5.5h8.5M8 10h8.5M8 14.5h8.5M3.5 4.5l1-.5v3M3.5 12.5h2l-2 2.5h2",
  citation: "M5 7.5h3v3H5zM5 10.5c0 2 .5 3 2 3.5M11 7.5h3v3h-3zM11 10.5c0 2 .5 3 2 3.5",
  separateur: "M3 10h14",
  annuler: "M6 6.5 3.5 9 6 11.5M3.5 9h8a4 4 0 0 1 0 8H9",
  retablir: "M14 6.5 16.5 9 14 11.5M16.5 9h-8a4 4 0 0 0 0 8H11",
} as const;

function Trace({ nom }: { nom: keyof typeof TRACES }) {
  return (
    <svg
      viewBox="0 0 20 20"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={TRACES[nom]} />
    </svg>
  );
}

function imagesDe(fichiers: FileList | null | undefined): File[] {
  return Array.from(fichiers ?? []).filter((f) => f.type.startsWith("image/"));
}

function Bouton({
  libelle,
  actif,
  desactive,
  onClick,
  children,
}: {
  libelle: string;
  actif?: boolean;
  desactive?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className="ee-bouton"
      aria-label={libelle}
      title={libelle}
      aria-pressed={actif === undefined ? undefined : actif}
      disabled={desactive}
      // La sélection reste dans le texte : sans cela, cliquer un bouton
      // retire le curseur de l'éditeur avant que la commande ne s'applique.
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function Nuancier({
  libelle,
  teintes,
  choisir,
  retirer,
}: {
  libelle: string;
  teintes: { nom: string; valeur: string }[];
  choisir: (valeur: string) => void;
  retirer: () => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const cadre = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !cadre.current?.contains(e.target as Node)) {
        setOuvert(false);
      }
    };
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", fermer);
    return () => {
      document.removeEventListener("mousedown", fermer);
      document.removeEventListener("keydown", fermer);
    };
  }, [ouvert]);
  return (
    <div className="ee-nuancier" ref={cadre}>
      <button
        type="button"
        className="ee-bouton ee-bouton-texte"
        aria-expanded={ouvert}
        aria-haspopup="true"
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => setOuvert((o) => !o)}
      >
        {libelle}
      </button>
      {ouvert && (
        <div className="ee-palette" role="group" aria-label={libelle}>
          {teintes.map((t) => (
            <button
              key={t.valeur}
              type="button"
              className="ee-teinte"
              style={{ background: t.valeur }}
              aria-label={t.nom}
              title={t.nom}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                choisir(t.valeur);
                setOuvert(false);
              }}
            />
          ))}
          <label className="ee-libre">
            <span>Autre</span>
            <input
              type="color"
              onChange={(e) => choisir(e.target.value)}
              aria-label={`${libelle} : couleur au choix`}
            />
          </label>
          <button
            type="button"
            className="ee-bouton ee-bouton-texte"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              retirer();
              setOuvert(false);
            }}
          >
            Aucune
          </button>
        </div>
      )}
    </div>
  );
}

function BarreDOutils({
  editeur,
  envoyerDesImages,
  envoiEnCours,
}: {
  editeur: Editor;
  envoyerDesImages: (fichiers: File[]) => void;
  envoiEnCours: boolean;
}) {
  const fichier = useRef<HTMLInputElement>(null);
  const etat = useEditorState({
    editor: editeur,
    selector: ({ editor: e }) => ({
      niveau: e.isActive("heading", { level: 1 })
        ? "1"
        : e.isActive("heading", { level: 2 })
          ? "2"
          : e.isActive("heading", { level: 3 })
            ? "3"
            : "0",
      gras: e.isActive("bold"),
      italique: e.isActive("italic"),
      souligne: e.isActive("underline"),
      barre: e.isActive("strike"),
      puces: e.isActive("bulletList"),
      numeros: e.isActive("orderedList"),
      citation: e.isActive("blockquote"),
      lien: e.isActive("link"),
      gauche: e.isActive({ textAlign: "left" }),
      centre: e.isActive({ textAlign: "center" }),
      droite: e.isActive({ textAlign: "right" }),
      justifie: e.isActive({ textAlign: "justify" }),
      taille: (e.getAttributes("textStyle").fontSize as string | undefined) ?? "",
      annulable: e.can().undo(),
      retablissable: e.can().redo(),
    }),
  });
  const c = () => editeur.chain().focus();

  function poserUnLien() {
    const actuel = (editeur.getAttributes("link").href as string | undefined) ?? "";
    const saisie = window.prompt("Adresse du lien (site web ou adresse e-mail) :", actuel);
    if (saisie === null) return;
    if (saisie.trim() === "") {
      c().extendMarkRange("link").unsetLink().run();
      return;
    }
    const adresse = adresseDeLien(saisie);
    if (!adresse) {
      window.alert("Cette adresse n'est pas valable. Exemple : https://evkha.fr");
      return;
    }
    c().extendMarkRange("link").setLink({ href: adresse }).run();
  }

  return (
    <div className="ee-barre" role="toolbar" aria-label="Mise en forme du texte">
      <select
        className="ee-choix"
        aria-label="Style du paragraphe"
        value={etat.niveau}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (n === 0) c().setParagraph().run();
          else c().setHeading({ level: n as 1 | 2 | 3 }).run();
        }}
      >
        <option value="0">Texte</option>
        <option value="1">Grand titre</option>
        <option value="2">Titre</option>
        <option value="3">Sous-titre</option>
      </select>
      <select
        className="ee-choix"
        aria-label="Taille du texte"
        value={etat.taille}
        onChange={(e) => {
          if (e.target.value) c().setFontSize(e.target.value).run();
          else c().unsetFontSize().run();
        }}
      >
        {TAILLES.map((t) => (
          <option key={t.nom} value={t.valeur}>
            {t.nom}
          </option>
        ))}
      </select>
      <span className="ee-separateur" aria-hidden="true" />
      <Bouton libelle="Gras" actif={etat.gras} onClick={() => c().toggleBold().run()}>
        <strong>G</strong>
      </Bouton>
      <Bouton libelle="Italique" actif={etat.italique} onClick={() => c().toggleItalic().run()}>
        <em>I</em>
      </Bouton>
      <Bouton libelle="Souligné" actif={etat.souligne} onClick={() => c().toggleUnderline().run()}>
        <span style={{ textDecoration: "underline" }}>S</span>
      </Bouton>
      <Bouton libelle="Barré" actif={etat.barre} onClick={() => c().toggleStrike().run()}>
        <span style={{ textDecoration: "line-through" }}>B</span>
      </Bouton>
      <Nuancier
        libelle="Couleur du texte"
        teintes={COULEURS}
        choisir={(v) => c().setColor(v).run()}
        retirer={() => c().unsetColor().run()}
      />
      <Nuancier
        libelle="Couleur de fond"
        teintes={FONDS}
        choisir={(v) => c().setBackgroundColor(v).run()}
        retirer={() => c().unsetBackgroundColor().run()}
      />
      <span className="ee-separateur" aria-hidden="true" />
      <Bouton libelle="Aligner à gauche" actif={etat.gauche} onClick={() => c().setTextAlign("left").run()}>
        <Trace nom="gauche" />
      </Bouton>
      <Bouton libelle="Centrer" actif={etat.centre} onClick={() => c().setTextAlign("center").run()}>
        <Trace nom="centre" />
      </Bouton>
      <Bouton libelle="Aligner à droite" actif={etat.droite} onClick={() => c().setTextAlign("right").run()}>
        <Trace nom="droite" />
      </Bouton>
      <Bouton libelle="Justifier" actif={etat.justifie} onClick={() => c().setTextAlign("justify").run()}>
        <Trace nom="justifie" />
      </Bouton>
      <span className="ee-separateur" aria-hidden="true" />
      <Bouton libelle="Liste à puces" actif={etat.puces} onClick={() => c().toggleBulletList().run()}>
        <Trace nom="puces" />
      </Bouton>
      <Bouton libelle="Liste numérotée" actif={etat.numeros} onClick={() => c().toggleOrderedList().run()}>
        <Trace nom="numeros" />
      </Bouton>
      <Bouton libelle="Citation" actif={etat.citation} onClick={() => c().toggleBlockquote().run()}>
        <Trace nom="citation" />
      </Bouton>
      <Bouton libelle="Ligne de séparation" onClick={() => c().setHorizontalRule().run()}>
        <Trace nom="separateur" />
      </Bouton>
      <span className="ee-separateur" aria-hidden="true" />
      <Bouton libelle={etat.lien ? "Modifier le lien" : "Ajouter un lien"} actif={etat.lien} onClick={poserUnLien}>
        Lien
      </Bouton>
      <Bouton
        libelle="Insérer une image"
        desactive={envoiEnCours}
        onClick={() => fichier.current?.click()}
      >
        {envoiEnCours ? "Envoi…" : "Image"}
      </Bouton>
      <input
        ref={fichier}
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        hidden
        multiple
        onChange={(e) => {
          envoyerDesImages(imagesDe(e.target.files));
          e.target.value = "";
        }}
      />
      <span className="ee-separateur" aria-hidden="true" />
      <Bouton
        libelle="Retirer la mise en forme"
        onClick={() => c().unsetAllMarks().clearNodes().run()}
      >
        Effacer
      </Bouton>
      <Bouton libelle="Annuler" desactive={!etat.annulable} onClick={() => c().undo().run()}>
        <Trace nom="annuler" />
      </Bouton>
      <Bouton libelle="Rétablir" desactive={!etat.retablissable} onClick={() => c().redo().run()}>
        <Trace nom="retablir" />
      </Bouton>
    </div>
  );
}

export default function EditeurEnrichi({
  valeur,
  changer,
  libelle,
}: {
  valeur: string;
  changer: (html: string) => void;
  libelle: string;
}) {
  const [envoiEnCours, setEnvoiEnCours] = useState(false);
  const [erreur, setErreur] = useState("");
  const changerRef = useRef(changer);
  const editeurRef = useRef<Editor | null>(null);

  async function envoyerDesImages(fichiers: File[]) {
    if (fichiers.length === 0) return;
    setEnvoiEnCours(true);
    setErreur("");
    try {
      for (const image of fichiers) {
        const { url } = await adminApi.televerserUneImage(image);
        editeurRef.current?.chain().focus().setImage({ src: url, alt: "" }).run();
      }
    } catch (cause) {
      setErreur(
        cause instanceof Error && cause.message
          ? cause.message
          : "L'image n'a pas pu être envoyée. Réessayez.",
      );
    } finally {
      setEnvoiEnCours(false);
    }
  }
  const envoyerRef = useRef(envoyerDesImages);

  const editeur = useEditor({
    extensions: [
      StarterKit.configure({
        code: false,
        codeBlock: false,
        heading: { levels: [1, 2, 3] },
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
      }),
      Image.configure({ inline: false, allowBase64: false }),
      TextStyle,
      Color,
      BackgroundColor,
      FontSize,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
    ],
    content: valeur,
    editorProps: {
      attributes: {
        class: "ee-texte",
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": libelle,
      },
      // Une image collée ou glissée part au serveur : jamais de « data: »
      // dans le courriel, que les messageries bloquent.
      handlePaste: (_vue, evenement) => {
        const images = imagesDe(evenement.clipboardData?.files);
        if (images.length === 0) return false;
        void envoyerRef.current(images);
        return true;
      },
      handleDrop: (_vue, evenement) => {
        const images = imagesDe((evenement as DragEvent).dataTransfer?.files);
        if (images.length === 0) return false;
        evenement.preventDefault();
        void envoyerRef.current(images);
        return true;
      },
    },
    onUpdate: ({ editor: e }) => changerRef.current(e.isEmpty ? "" : e.getHTML()),
  });
  // Les gestionnaires de l'éditeur sont posés une fois : ils lisent la
  // dernière version de ces fonctions par une référence, mise à jour après
  // chaque rendu.
  useEffect(() => {
    changerRef.current = changer;
    envoyerRef.current = envoyerDesImages;
    editeurRef.current = editeur;
  });

  // Un contenu remplacé de l'extérieur (un modèle appliqué, une autre lettre
  // ouverte) remplace le texte ; la frappe, elle, ne repasse pas par ici.
  useEffect(() => {
    // Un éditeur DÉTRUIT (démonté puis remonté par React, en ouvrant une
    // newsletter depuis un modèle) n'a plus de schéma : l'interroger fait
    // tomber tout l'écran.
    if (!editeur || editeur.isDestroyed) return;
    const actuel = editeur.isEmpty ? "" : editeur.getHTML();
    if (valeur !== actuel) editeur.commands.setContent(valeur, { emitUpdate: false });
  }, [editeur, valeur]);

  if (!editeur) return null;
  return (
    <div className="ee">
      <BarreDOutils editeur={editeur} envoyerDesImages={envoyerDesImages} envoiEnCours={envoiEnCours} />
      <EditorContent editor={editeur} />
      {erreur && (
        <p className="ee-erreur" role="alert">
          {erreur}
        </p>
      )}
      <p className="ee-aide">
        Images : bouton « Image », ou collez et glissez-les dans le texte (JPEG, PNG, GIF ou WebP,
        5 Mo au plus).
      </p>
    </div>
  );
}
