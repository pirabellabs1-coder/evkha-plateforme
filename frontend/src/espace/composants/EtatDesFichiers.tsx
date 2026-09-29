/** Ce que la colonne « Fichiers » dit d'une étude — l'état vient du serveur.
 *
 * Avant le 29/09/2026, la bibliothèque et le tableau de bord n'avaient qu'un
 * mot pour « aucun fichier » : « En préparation ». Il s'affichait pour une
 * étude annulée, et pour des documents livrés six semaines plus tôt dont les
 * fichiers avaient été supprimés au terme de leur conservation. L'écran ne
 * déduit plus rien : il lit `fichiers_etat`, calculé une seule fois par le
 * serveur (`organisations.suivi.etat_des_fichiers`). */
import type { Livrable } from "../api";
import * as f from "../format";

export function CelluleFichiers({
  livrable,
  classeBouton,
}: {
  livrable: Pick<Livrable, "fichiers" | "fichiers_etat">;
  classeBouton: string;
}) {
  if (livrable.fichiers.length > 0) {
    return (
      <span style={{ display: "flex", gap: "var(--e-2)" }}>
        {livrable.fichiers.map((fichier) => (
          <a key={fichier.kind} className={classeBouton} href={fichier.url}>
            {fichier.kind.toUpperCase()}
          </a>
        ))}
      </span>
    );
  }
  const etat = livrable.fichiers_etat;
  switch (etat?.etat) {
    case "en_preparation":
      return <span className="carte-note">En préparation</span>;
    case "mise_en_forme":
      return <span className="carte-note">Mise en forme</span>;
    case "supprimes":
      return (
        <span
          className="carte-note"
          title="Les fichiers ont été supprimés au terme de leur durée de conservation."
        >
          Supprimés le {f.date(etat.supprimes_le)}
        </span>
      );
    default:
      return <span className="carte-note">—</span>;
  }
}
