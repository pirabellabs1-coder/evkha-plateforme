/** Le pied des pages publiques refondues : la signature, les réseaux de la
 * cliente, les informations légales.
 *
 * Il vivait dans `Accueil.tsx`. L'accueil et la page des études le montent
 * tous deux, et il lit ses entrées dans `contenuSite.PIED` (règle 5).
 *
 * Son fond doré prolonge la section qui le précède : chaque page le fait
 * suivre de sa fin dorée (`.acc-fin`, `Site.css`).
 */
import { PIED } from "./contenuSite";

/** Lue une fois au chargement du module : un rendu ne doit pas dépendre de
 *  l'horloge. */
const ANNEE = new Date().getFullYear();

/** `inerte` : le menu plein écran est ouvert par-dessus. Le pied ne doit
 *  alors prendre ni le focus ni la voix d'un lecteur d'écran. */
export function PiedSite({ inerte }: { inerte: boolean }) {
  return (
    <footer className="acc-pied" inert={inerte}>
      <div className="acc-w">
        <div className="acc-pied-identite">
          <span>{PIED.signature}</span>
          <span>
            © {ANNEE} {PIED.droits}
          </span>
        </div>
        <nav aria-label={PIED.reseauxTitre}>
          {PIED.reseaux.map((reseau) => (
            <a key={reseau.lien} href={reseau.lien} rel="noopener">
              {reseau.libelle}
            </a>
          ))}
        </nav>
        <nav aria-label={PIED.navigation}>
          {PIED.liens.map((lien) => (
            <a key={lien.lien} href={lien.lien}>
              {lien.libelle}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
