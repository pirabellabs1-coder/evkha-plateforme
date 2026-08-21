/** Les études de boutique achetées.
 *
 * Page distincte de « Livrables », et ce n'est pas un détail de rangement :
 * une étude sur mesure a un questionnaire, une progression et des contrôles ;
 * une étude de boutique est un fichier acheté une fois. Les mêler ferait une
 * liste où « en cours de production » côtoie « téléchargé », sans qu'on sache
 * lequel attend quoi.
 *
 * Des cartes avec couverture, et non des lignes. Ce bloc est une bibliothèque,
 * pas un tableau de suivi : on y revient pour retrouver une étude parmi
 * d'autres, et une couverture se reconnaît plus vite qu'un titre lu.
 *
 * ## Aucune étude n'est PROPOSÉE ici
 *
 * La page affichait « Le reste du catalogue » avec un bouton d'achat par
 * étude. C'était une suggestion, et une suggestion suppose qu'on connaisse le
 * besoin de la personne — on ne le connaît pas. Qui cherche une autre étude va
 * au catalogue, où il les voit toutes, filtrées par thème, avec leur fiche.
 * Ne reste ici qu'un lien vers cette boutique.
 */
import { useQuery } from "@tanstack/react-query";

import { espaceApi } from "../api";
import * as f from "../format";
import { Carte, Squelette, Vide } from "../composants/Interface";

/** L'initiale du titre, pour les études sans couverture. L'article est retiré,
 *  sans quoi toutes les études du catalogue donneraient « L ». */
function initiale(titre: string): string {
  const mot = titre.replace(/^(le|la|les|l'|un|une|du|de|des)\s+/i, "").trim();
  return (mot[0] ?? "?").toUpperCase();
}

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

export function MesAchats() {
  const { data, isPending } = useQuery({
    queryKey: ["espace", "achats"],
    queryFn: espaceApi.mesAchats,
  });
  if (isPending) return <Squelette lignes={3} />;

  const achats = data?.achats ?? [];
  const catalogue = data?.catalogue ?? [];

  return (
    <>
      <Carte
        titre="Mes études"
        note={
          achats.length > 0
            ? "Téléchargeables à tout moment, autant de fois que vous le souhaitez."
            : undefined
        }
      >
        {achats.length === 0 ? (
          <Vide
            titre="Aucune étude achetée"
            texte="Les études que vous achetez dans la boutique apparaissent ici, et y restent."
          />
        ) : (
          <ul className="achats-grille">
            {achats.map((a) => (
              <li key={a.id} className="achat-carte">
                <Couverture image={a.image} titre={a.titre} />
                <div className="achat-corps">
                  <p className="achat-titre">{a.titre}</p>
                  <p className="carte-note">
                    Acheté le {f.date(a.achete_le)}
                    {a.pages > 0 ? ` · ${a.pages} pages` : ""}
                  </p>
                  <div className="achat-liens">
                    {a.telechargement && (
                      <a
                        className="bouton bouton-contour bouton-sm"
                        href={a.telechargement}
                      >
                        Télécharger le PDF
                      </a>
                    )}
                    {a.editable && (
                      <a className="bouton bouton-discret bouton-sm" href={a.editable}>
                        Word
                      </a>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Carte>

      {catalogue.length > 0 && (
        <Carte titre="Le catalogue">
          <p className="carte-note">
            {catalogue.length} autre{catalogue.length > 1 ? "s" : ""} étude
            {catalogue.length > 1 ? "s" : ""} en téléchargement immédiat.
          </p>
          <p className="achat-vers-boutique">
            <a className="bouton bouton-contour bouton-sm" href="/boutique">
              Ouvrir la boutique
            </a>
          </p>
        </Carte>
      )}
    </>
  );
}
