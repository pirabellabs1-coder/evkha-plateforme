/** Le pied des pages publiques refondues : le plan du site, la signature, les
 * réseaux de la cliente, les informations légales.
 *
 * Toutes les pages refondues le montent. Son plan reprend les rubriques du
 * menu, une colonne chacune, lues dans `contenuSite.NAVIGATION` — la MÊME
 * liste que la barre et le menu plein écran d'`EnTeteSite` (règle 5) : une
 * page ajoutée au menu est dans le pied sans qu'on y pense. Le reste (réseaux,
 * pages légales, signature) vient de `contenuSite.PIED`.
 *
 * Pas de titre `<h2>` au-dessus des colonnes : chaque page tient sa hiérarchie
 * de titres, que ses tests vérifient ; le pied ne s'y invite pas. Le nom de
 * chaque colonne est un paragraphe, auquel sa liste est rattachée par
 * `aria-labelledby`.
 *
 * Son fond doré prolonge la section qui le précède : chaque page le fait
 * suivre de sa fin dorée (`.acc-fin`, `Site.css`).
 */
import { NAVIGATION, PIED } from "./contenuSite";

/** Lue une fois au chargement du module : un rendu ne doit pas dépendre de
 *  l'horloge. */
const ANNEE = new Date().getFullYear();

/** `inerte` : le menu plein écran est ouvert par-dessus. Le pied ne doit
 *  alors prendre ni le focus ni la voix d'un lecteur d'écran. */
export function PiedSite({ inerte }: { inerte: boolean }) {
  return (
    <footer className="acc-pied" inert={inerte}>
      <div className="acc-w">
        <nav className="acc-pied-plan" aria-label={PIED.plan}>
          <ul className="acc-pied-colonnes">
            {NAVIGATION.map((rubrique) => {
              const titre = `acc-pied-${rubrique.id}`;
              return (
                <li key={rubrique.id}>
                  <p className="acc-pied-titre" id={titre}>
                    {rubrique.libelle}
                  </p>
                  <ul aria-labelledby={titre}>
                    {rubrique.liens.map((lien) => (
                      <li key={lien.lien}>
                        <a
                          href={lien.lien}
                          rel={lien.lien.startsWith("/") ? undefined : "noopener"}
                        >
                          {lien.libelle}
                        </a>
                      </li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="acc-pied-bas">
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
      </div>
    </footer>
  );
}
