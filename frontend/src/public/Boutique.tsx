/** La boutique publique : le catalogue des études déjà rédigées.
 *
 * Une étude de boutique est écrite depuis des mois et remise telle quelle. Le
 * paiement ne déclenche aucune production — d'où une boutique distincte de la
 * page des études sur mesure.
 *
 * ## Deux principes, communs aux pages publiques
 *
 * 1. **Les prix viennent du serveur.** Ils sont lus dans
 *    `/api/public/boutique/`, qui les tient de la base. Un montant écrit ici
 *    ferait une seconde source, qui contredirait le paiement au premier
 *    changement de tarif.
 * 2. **Aucun prix n'est affiché tant qu'il n'est pas chargé.** Un prix de
 *    repli afficherait un montant faux à qui a une connexion lente.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";

import { MenuSite } from "./MenuSite";
import {
  chargerCatalogue,
  etoiles,
  initiale,
  moisEtAnnee,
  prix,
  type ProduitResume,
} from "./catalogue";
import "./Partenaires.css";
import "./Boutique.css";

/** Une carte du catalogue. Cliquable en entier — une cible de la taille de la
 *  carte se vise mieux qu'un lien de deux mots. */
export function CarteProduit({ produit }: { produit: ProduitResume }) {
  const maj = moisEtAnnee(produit.mise_a_jour);
  const details = [
    produit.pages > 0 ? `${produit.pages} pages` : "",
    maj ? `mise à jour ${maj}` : "",
  ].filter(Boolean);

  return (
    <Link
      className="bq-carte"
      to="/boutique/$slug"
      params={{ slug: produit.slug }}
    >
      <div className="bq-couverture">
        {produit.image ? (
          <img src={produit.image} alt="" loading="lazy" />
        ) : (
          // Pas de cadre vide : une couverture absente affiche l'initiale de
          // l'étude, qui se lit comme un choix et non comme une image qui
          // n'aurait pas chargé.
          <span className="bq-couverture-vide" aria-hidden="true">
            {initiale(produit.titre)}
          </span>
        )}
        {produit.theme && <span className="bq-fanion">{produit.theme}</span>}
      </div>
      <div className="bq-corps">
        <h2>{produit.titre}</h2>
        <p className="bq-meta">{details.join(" · ") || "Étude complète"}</p>
        {produit.nombre_d_avis > 0 && (
          <p className="bq-note">
            <span className="bq-etoiles" aria-hidden="true">
              {etoiles(produit.note)}
            </span>
            <span>
              {produit.note.toFixed(1).replace(".", ",")} · {produit.nombre_d_avis}{" "}
              avis
            </span>
          </p>
        )}
        <div className="bq-pied">
          <span className="bq-prix">
            {prix(produit.prix_cents, produit.devise)}
          </span>
          <span className="bq-voir">Voir l'étude</span>
        </div>
      </div>
    </Link>
  );
}

export function Boutique() {
  const [produits, setProduits] = useState<ProduitResume[] | null>(null);
  const [themes, setThemes] = useState<string[]>([]);
  const [theme, setTheme] = useState("");
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    const precedent = document.title;
    document.title = "Études en téléchargement immédiat — EVKHA";
    return () => {
      document.title = precedent;
    };
  }, []);

  useEffect(() => {
    let vivant = true;
    chargerCatalogue()
      .then((donnees) => {
        if (!vivant) return;
        setProduits(donnees.produits);
        setThemes(donnees.themes);
      })
      .catch(() => {
        if (vivant) setErreur("La boutique est momentanément indisponible.");
      });
    return () => {
      vivant = false;
    };
  }, []);

  // Le filtre s'applique à l'affichage, pas au serveur : le catalogue tient en
  // quelques dizaines d'entrées, et un aller-retour par clic rendrait le
  // filtre poussif pour aucun gain.
  const visibles = useMemo(
    () => (produits ?? []).filter((p) => !theme || p.theme === theme),
    [produits, theme],
  );

  return (
    <div className="pp bq">
      <MenuSite />

      <header className="pp-large bq-entete">
        <p className="bq-eyebrow">Téléchargement immédiat</p>
        <h1>Des études prêtes, disponibles tout de suite</h1>
        <p className="bq-chapeau">
          Des études de marché déjà rédigées sur des secteurs précis, mises à
          jour régulièrement. Vous payez, vous téléchargez : rien à attendre.
        </p>
      </header>

      <main className="pp-large">
        {erreur && (
          <p className="bq-erreur" role="alert">
            {erreur} Écrivez-nous à{" "}
            <a href="mailto:contact@evkha.fr">contact@evkha.fr</a>.
          </p>
        )}

        {produits === null && !erreur && (
          <p className="bq-attente">Chargement du catalogue…</p>
        )}

        {produits !== null && produits.length === 0 && (
          <p className="bq-vide">
            Aucune étude n'est disponible pour le moment. Revenez bientôt : le
            catalogue s'élargit chaque mois.
          </p>
        )}

        {themes.length > 1 && (
          <div className="bq-filtres" role="group" aria-label="Filtrer par thème">
            <button
              type="button"
              className="bq-filtre"
              aria-pressed={theme === ""}
              onClick={() => setTheme("")}
            >
              Toutes
            </button>
            {themes.map((t) => (
              <button
                key={t}
                type="button"
                className="bq-filtre"
                aria-pressed={theme === t}
                onClick={() => setTheme(t)}
              >
                {t}
              </button>
            ))}
          </div>
        )}

        {visibles.length > 0 && (
          <div className="bq-grille">
            {visibles.map((p) => (
              <CarteProduit key={p.slug} produit={p} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
