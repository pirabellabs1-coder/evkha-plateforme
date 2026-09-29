/** La liste des chapitres de l'étude, en direct : rédaction, vérification, validé.
 *
 * 29/09/2026 : le client ne voyait qu'une étape « Rédaction des chapitres »
 * pendant une demi-heure. Chaque chapitre du plan s'affiche désormais avec son
 * étape, posée par la boucle de production elle-même (`ChapterGeneration.etape`)
 * — l'écran ne déduit rien. Le nombre de lignes est celui du plan du type
 * d'étude (22, 9, 21, 20), jamais une valeur fixe.
 *
 * Vocabulaire toujours positif : une reprise se lit « Vérifié et ajusté »,
 * jamais « erreur » ni « échec ».
 */
import type { ChapitreEnDirect } from "../api";

const LIBELLE_ETAPE_CHAPITRE: Record<string, string> = {
  "": "À venir",
  redaction: "Rédaction en cours",
  verification: "Vérification en cours",
  ajustement: "Vérification et ajustement",
  valide: "Validé",
  pause: "En pause",
};

export function ChapitresEnDirect({ chapitres }: { chapitres: ChapitreEnDirect[] }) {
  if (chapitres.length === 0) return null;
  const valides = chapitres.filter((c) => c.etape === "valide").length;
  return (
    <div className="chapitres-direct">
      <p className="chapitres-direct-compte" aria-live="polite">
        {valides} chapitre{valides > 1 ? "s" : ""} validé{valides > 1 ? "s" : ""} sur{" "}
        {chapitres.length}
      </p>
      <ol className="chapitres-direct-liste">
        {chapitres.map((chapitre) => (
          <li
            key={chapitre.numero}
            className={`chapitre-direct chapitre-direct-${chapitre.etape || "attente"}`}
          >
            <span className="chapitre-direct-numero">{chapitre.numero}</span>
            <span className="chapitre-direct-titre">{chapitre.titre}</span>
            {/* `key` sur l'étape : le libellé rejoue sa courte arrivée à chaque
                changement, comme les incréments de la frise. */}
            <span key={chapitre.etape} className="chapitre-direct-etape frise-increment">
              {chapitre.ajuste && chapitre.etape === "valide"
                ? "Vérifié et ajusté"
                : LIBELLE_ETAPE_CHAPITRE[chapitre.etape] ?? "À venir"}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
