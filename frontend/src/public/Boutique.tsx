/** La boutique publique : le catalogue des études déjà rédigées.
 *
 * Une étude de boutique est écrite depuis des mois et remise telle quelle. Le
 * paiement ne déclenche aucune production — d'où une boutique distincte de la
 * page des études sur mesure.
 *
 * ## Ce que cette page doit faire, et que la première ne faisait pas
 *
 * Elle posait un titre, un paragraphe et une grille. C'est une LISTE, pas une
 * boutique : rien n'y disait ce qu'on achète exactement, ce qui se passe après
 * le paiement, ni pourquoi ces études-là. Un visiteur qui découvre la maison
 * devait tout déduire de neuf vignettes.
 *
 * Elle répond désormais, dans l'ordre où les questions viennent : ce que c'est
 * (bandeau), ce qu'il y a (catalogue), en quoi ça diffère d'une étude sur
 * mesure (comparaison), ce qu'en disent celles qui l'ont lue (avis), et le
 * reste des questions (repères). Chaque bloc existe parce qu'une question
 * existe — aucun n'est là pour remplir.
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
  type AvisALaUne,
  type ProduitResume,
} from "./catalogue";
import "./Partenaires.css";
import "./Boutique.css";

/** Une carte du catalogue. Cliquable en entier — une cible de la taille de la
 *  carte se vise mieux qu'un lien de deux mots. */
export function CarteProduit({ produit }: { produit: ProduitResume }) {
  const maj = moisEtAnnee(produit.mise_a_jour);
  // Le nombre de pages n'est PAS affiché. Il se lit comme une mesure de la
  // valeur — et il la mesure mal : trente-cinq pages utiles valent mieux que
  // soixante délayées, et l'acheteuse qui compare deux nombres compare
  // exactement ce qui ne compte pas. Ce qui la renseigne, c'est le sommaire et
  // l'extrait, tous deux sur la fiche.
  const details = [maj ? `Mise à jour ${maj}` : ""].filter(Boolean);

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
        <span className="bq-prix-pastille">
          {prix(produit.prix_cents, produit.devise)}
        </span>
      </div>
      <div className="bq-corps">
        <h3>{produit.titre}</h3>
        {details.length > 0 && <p className="bq-meta">{details.join(" · ")}</p>}
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
        <span className="bq-voir">Voir l'étude →</span>
      </div>
    </Link>
  );
}

/** Les quatre promesses tenues par la mécanique elle-même.
 *
 *  Chacune décrit ce que le code fait vraiment : l'accès est ouvert par
 *  l'encaissement, le fichier est remis dans la seconde, il reste accessible
 *  tant que l'achat existe, et rien n'est prélevé ensuite. Écrire ici une
 *  promesse que le système ne tient pas serait un mensonge de vitrine. */
const PROMESSES = [
  {
    signe: "↓",
    titre: "Disponible tout de suite",
    texte: "Le document se télécharge sur la page qui suit le paiement.",
  },
  {
    signe: "€",
    titre: "Paiement unique",
    texte: "Aucun abonnement, aucun prélèvement ensuite.",
  },
  {
    signe: "▤",
    titre: "PDF prêt à imprimer",
    texte: "Et la version Word quand elle existe, pour reprendre le document.",
  },
  {
    signe: "◈",
    titre: "Gardée dans votre espace",
    texte: "Un espace s'ouvre à votre nom. L'étude y reste, retéléchargeable.",
  },
] as const;

/** Les questions qu'on se pose avant de payer quatre-vingt-neuf euros.
 *
 *  Elles sont écrites à partir de ce qui est vrai du système — la première dit
 *  la différence avec une étude sur mesure, qui est LA confusion possible
 *  entre les deux pages publiques. */
type Repere = {
  question: string;
  reponse: string;
  /** Facultatif : seule la première question renvoie ailleurs. */
  lien?: { vers: "/etudes"; libelle: string };
};

const REPERES: Repere[] = [
  {
    question: "Ces études sont-elles faites sur mon projet ?",
    reponse:
      "Non, et c'est ce qui permet ce prix. Ce sont des études de secteur, " +
      "écrites une fois puis vendues telles quelles : le marché, les clients, " +
      "la réglementation, les coûts. Pour une étude bâtie sur VOTRE projet, " +
      "avec votre zone et vos chiffres, ce sont nos études sur mesure.",
    lien: { vers: "/etudes", libelle: "Voir les études sur mesure" },
  },
  {
    question: "Que reçois-je exactement ?",
    reponse:
      "Le document complet en PDF, et sa version Word lorsqu'elle existe. " +
      "Le sommaire de chaque étude est affiché sur sa fiche, et un extrait " +
      "est consultable avant l'achat quand il est disponible.",
  },
  {
    question: "Dois-je créer un compte avant de payer ?",
    reponse:
      "Non. Vous réglez, et votre espace s'ouvre tout seul avec l'étude " +
      "dedans. Vous y choisirez un mot de passe depuis le courriel reçu.",
  },
  {
    question: "Les études sont-elles à jour ?",
    reponse:
      "Chaque fiche affiche la date de sa dernière mise à jour. Le catalogue " +
      "s'élargit et se met à jour régulièrement.",
  },
  {
    question: "Et si je me trompe d'étude ?",
    reponse:
      "Écrivez-nous à contact@evkha.fr. Un document remis immédiatement ne se " +
      "reprend pas, mais nous trouvons toujours une solution.",
  },
];

function AvisALaUneCarte({ avis }: { avis: AvisALaUne }) {
  return (
    <figure className="bq-temoignage">
      <span className="bq-etoiles" aria-label={`${avis.note} sur 5`}>
        {etoiles(avis.note)}
      </span>
      <blockquote>{avis.texte}</blockquote>
      <figcaption>
        <b>{avis.auteur}</b>
        {avis.qualite && <span>{avis.qualite}</span>}
        <Link to="/boutique/$slug" params={{ slug: avis.slug }}>
          {avis.etude}
        </Link>
      </figcaption>
    </figure>
  );
}

export function Boutique() {
  const [produits, setProduits] = useState<ProduitResume[] | null>(null);
  const [themes, setThemes] = useState<string[]>([]);
  const [avis, setAvis] = useState<AvisALaUne[]>([]);
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
        setAvis(donnees.avis ?? []);
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

  // Le prix le plus bas, dit tel quel. « À partir de » suppose un plancher, et
  // l'écrire en dur mentirait le jour où la cliente change un tarif.
  const plancher = useMemo(
    () =>
      produits && produits.length > 0
        ? Math.min(...produits.map((p) => p.prix_cents))
        : null,
    [produits],
  );

  return (
    <div className="pp bq">
      <MenuSite />

      <header className="bq-entete">
        <div className="pp-large bq-entete-grille">
          <div>
            <p className="bq-eyebrow">Téléchargement immédiat</p>
            <h1>
              Des études de marché déjà écrites,
              <br />
              disponibles dans la minute
            </h1>
            <p className="bq-chapeau">
              Chaque étude couvre un secteur : sa taille, ses clients, ses
              règles, ses coûts et sa rentabilité. Vous réglez une fois, vous
              téléchargez, c'est à vous.
            </p>
            <div className="bq-entete-actions">
              <a className="bq-bouton bq-bouton-large" href="#catalogue">
                Voir le catalogue
              </a>
              {plancher !== null && (
                <span className="bq-entete-prix">
                  à partir de <b>{prix(plancher)}</b> TTC
                </span>
              )}
            </div>
          </div>

          {/* Trois couvertures en éventail : la vitrine d'une boutique montre
              ce qu'elle vend avant de l'expliquer. Purement décoratif — la
              grille juste dessous porte l'information. */}
          <div className="bq-eventail" aria-hidden="true">
            {(produits ?? []).slice(0, 3).map((p, index) => (
              <div key={p.slug} className={`bq-eventail-carte bq-eventail-${index}`}>
                {p.image ? (
                  <img src={p.image} alt="" loading="lazy" />
                ) : (
                  <span>{initiale(p.titre)}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </header>

      <section className="bq-promesses" aria-label="Ce qui est compris">
        <div className="pp-large bq-promesses-grille">
          {PROMESSES.map((p) => (
            <div key={p.titre} className="bq-promesse">
              <span className="bq-promesse-signe" aria-hidden="true">
                {p.signe}
              </span>
              <div>
                <p className="bq-promesse-titre">{p.titre}</p>
                <p className="bq-promesse-texte">{p.texte}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <main className="pp-large">
        <section id="catalogue" className="bq-catalogue">
          <div className="bq-section-tete">
            <h2>Le catalogue</h2>
            {produits !== null && produits.length > 0 && (
              <p className="bq-section-note">
                {produits.length} étude{produits.length > 1 ? "s" : ""}{" "}
                disponible{produits.length > 1 ? "s" : ""}
                {themes.length > 1 ? `, ${themes.length} secteurs` : ""}.
              </p>
            )}
          </div>

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
        </section>

        {avis.length > 0 && (
          <section className="bq-temoignages">
            <div className="bq-section-tete">
              <h2>Ce qu'en disent celles qui les ont lues</h2>
            </div>
            <div className="bq-temoignages-grille">
              {avis.map((a) => (
                <AvisALaUneCarte key={`${a.slug}-${a.auteur}-${a.date}`} avis={a} />
              ))}
            </div>
          </section>
        )}

        <section className="bq-reperes">
          <div className="bq-section-tete">
            <h2>Bon à savoir</h2>
          </div>
          <div className="bq-reperes-liste">
            {REPERES.map((r) => (
              <details key={r.question} className="bq-repere">
                <summary>{r.question}</summary>
                <p>
                  {r.reponse}
                  {r.lien && (
                    <>
                      {" "}
                      <Link to={r.lien.vers}>{r.lien.libelle}</Link>.
                    </>
                  )}
                </p>
              </details>
            ))}
          </div>
        </section>

        <section className="bq-appel">
          <h2>Une question avant d'acheter ?</h2>
          <p>
            Écrivez-nous, nous répondons nous-mêmes — et nous vous dirons
            franchement si l'étude que vous visez répond à votre besoin.
          </p>
          <a className="bq-bouton bq-bouton-large" href="mailto:contact@evkha.fr">
            contact@evkha.fr
          </a>
        </section>
      </main>
    </div>
  );
}
