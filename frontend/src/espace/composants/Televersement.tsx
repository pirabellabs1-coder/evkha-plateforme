/** Dépôt de fichiers — glisser-déposer ou sélection.
 *
 * Le contrôle de format qui fait autorité est **côté serveur**, sur les octets.
 * Celui d'ici n'est qu'une commodité : il évite un aller-retour réseau pour un
 * fichier manifestement trop lourd. Un fichier qui passe ici peut encore être
 * refusé — et c'est normal.
 */
import { useRef, useState } from "react";
import { poids } from "./poids";

export interface FichierDepose {
  id: string;
  categorie: string;
  nom: string;
  taille_octets: number;
  type_mime: string;
  date: string;
  url: string;
}

export function ZoneDepot({
  libelle,
  aide,
  accepte,
  tailleMax,
  desactive = false,
  onDeposer,
  enCours = false,
}: {
  libelle: string;
  aide: string;
  accepte: string;
  tailleMax: number;
  desactive?: boolean;
  enCours?: boolean;
  onDeposer: (fichier: File) => void;
}) {
  const champ = useRef<HTMLInputElement>(null);
  const [survol, setSurvol] = useState(false);
  const [erreur, setErreur] = useState("");

  function traiter(fichier: File | undefined) {
    if (!fichier) return;
    if (fichier.size > tailleMax) {
      setErreur(
        `Ce fichier pèse ${poids(fichier.size)}, le maximum est ${poids(tailleMax)}.`,
      );
      return;
    }
    setErreur("");
    onDeposer(fichier);
  }

  return (
    <div className="champ">
      <span className="champ-libelle">{libelle}</span>
      {/* Un bouton et non un div : la zone doit être atteignable au clavier et
          annoncée comme actionnable. Le champ fichier reste dans le DOM pour
          les lecteurs d'écran, simplement masqué visuellement. */}
      <button
        type="button"
        className={survol ? "depot survol" : "depot"}
        disabled={desactive || enCours}
        onClick={() => champ.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setSurvol(true);
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={(e) => {
          e.preventDefault();
          setSurvol(false);
          traiter(e.dataTransfer.files[0]);
        }}
      >
        <span className="depot-icone" aria-hidden="true">
          ↑
        </span>
        <span className="depot-texte">
          {enCours ? "Envoi en cours…" : "Cliquez ou glissez un fichier ici"}
        </span>
        <span className="depot-aide">{aide}</span>
      </button>
      <input
        ref={champ}
        type="file"
        accept={accepte}
        className="visuellement-cache"
        aria-label={libelle}
        onChange={(e) => {
          traiter(e.target.files?.[0]);
          // Réinitialisation : sans cela, redéposer le même fichier après une
          // suppression ne déclencherait aucun événement.
          e.target.value = "";
        }}
      />
      {erreur && (
        <span className="champ-aide" style={{ color: "var(--evkha-echec)" }}>
          {erreur}
        </span>
      )}
    </div>
  );
}

/** Date de dépôt, courte et française. Une date ISO ne se lit pas d'un œil. */
function dateCourte(iso: string): string {
  const quand = new Date(iso);
  if (Number.isNaN(quand.getTime())) return "";
  return quand.toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function ListeFichiers({
  fichiers,
  onSupprimer,
  peutSupprimer = true,
}: {
  fichiers: FichierDepose[];
  onSupprimer: (id: string) => void;
  peutSupprimer?: boolean;
}) {
  if (fichiers.length === 0) {
    return <p className="carte-note">Aucun fichier déposé.</p>;
  }
  return (
    <ul className="liste-fichiers">
      {fichiers.map((fichier) => (
        <li key={fichier.id}>
          <span className="fichier-nom">{fichier.nom}</span>
          <span className="carte-note">{poids(fichier.taille_octets)}</span>
          {/* La DATE, et pas seulement le nom. Le dépôt est rattaché à
              l'organisation, jamais à une commande : un bilan déposé pour
              l'étude de mars réapparaît sur la commande de septembre, à
              l'identique. Cliente, 12/08/2026 : « j'ai cliqué sur commander un
              business plan et il reste les fichiers de la stratégie […] au cas
              où un client ne fasse pas attention et lance un nouveau projet
              avec d'anciens docs ». Sans la date, rien à l'écran ne distingue
              le document d'aujourd'hui de celui d'il y a six mois. */}
          <span className="carte-note">{dateCourte(fichier.date)}</span>
          {peutSupprimer && (
            <button
              type="button"
              className="bouton bouton-discret bouton-sm"
              onClick={() => onSupprimer(fichier.id)}
            >
              Retirer
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
