/** La fiche d'une étude de boutique, et son achat.
 *
 * L'extrait consultable est l'élément qui décide de la vente : un fichier ne
 * se feuillette pas, et sans quelques pages visibles le visiteur engage son
 * argent sur la foi d'un titre. La couverture et les avis jouent le même rôle
 * — ils montrent, là où une description affirme.
 *
 * L'achat ne demande PAS de créer un compte au préalable. Le compte est ouvert
 * par l'encaissement, et l'acheteur arrive directement sur son téléchargement :
 * pour un fichier remis immédiatement, un formulaire d'inscription avant le
 * paiement est une friction sans contrepartie.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "@tanstack/react-router";

import { MenuSite } from "./MenuSite";
import { CarteProduit } from "./Boutique";
import {
  chargerFiche,
  etoiles,
  initiale,
  moisEtAnnee,
  ouvrirLePaiement,
  prix,
  type Avis,
  type ProduitFiche,
  type ProduitResume,
} from "./catalogue";
import "./Partenaires.css";
import "./Boutique.css";

/** « 12 mars 2026 ». Sur un avis, le jour compte : il dit si le témoignage
 *  est récent. C'est l'inverse d'une date de mise à jour, où il n'apporte
 *  rien — d'où deux formats et non un compromis. */
function jourEntier(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function CarteAvis({ avis }: { avis: Avis }) {
  return (
    <li className="bq-avis">
      <p className="bq-avis-tete">
        <span className="bq-etoiles" aria-label={`${avis.note} sur 5`}>
          {etoiles(avis.note)}
        </span>
        <span className="bq-avis-date">{jourEntier(avis.date)}</span>
      </p>
      {avis.texte && <blockquote className="bq-avis-texte">{avis.texte}</blockquote>}
      <p className="bq-avis-signature">
        <b>{avis.auteur}</b>
        {avis.qualite && <span>{avis.qualite}</span>}
      </p>
    </li>
  );
}

export function FicheProduit() {
  const { slug } = useParams({ from: "/boutique/$slug" });
  const [produit, setProduit] = useState<ProduitFiche | null>(null);
  const [proches, setProches] = useState<ProduitResume[]>([]);
  const [email, setEmail] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState("");
  const [introuvable, setIntrouvable] = useState(false);

  useEffect(() => {
    let vivant = true;
    // La remise à zéro passe par la RÉPONSE, pas par le corps de l'effet :
    // remettre l'état à vide de façon synchrone déclenche un rendu en cascade
    // à chaque changement de fiche.
    chargerFiche(slug)
      .then((donnees) => {
        if (!vivant) return;
        setIntrouvable(false);
        setProduit(donnees.produit);
        setProches(donnees.proches);
        document.title = `${donnees.produit.titre} — EVKHA`;
      })
      .catch(() => {
        if (!vivant) return;
        setProduit(null);
        setIntrouvable(true);
      });
    return () => {
      vivant = false;
    };
  }, [slug]);

  async function acheter() {
    if (!produit) return;
    setEnvoi(true);
    setErreur("");
    try {
      const adresse = await ouvrirLePaiement(produit.slug, email.trim());
      // Remplacement et non nouvel onglet : le paiement EST la suite du
      // parcours. Un onglet de plus laisse derrière soi une page morte à
      // laquelle la personne revient, et où elle recliquera.
      window.location.href = adresse;
    } catch (cause) {
      setErreur(
        cause instanceof Error
          ? cause.message
          : "Le paiement n'a pas pu être ouvert. Réessayez dans un instant.",
      );
      setEnvoi(false);
    }
  }

  if (introuvable) {
    return (
      <div className="pp bq">
        <MenuSite />
        <main className="pp-large">
          <p className="bq-erreur" role="alert">
            Cette étude n'est pas disponible.{" "}
            <Link to="/boutique">Revenir à la boutique</Link>.
          </p>
        </main>
      </div>
    );
  }

  if (!produit) {
    return (
      <div className="pp bq">
        <MenuSite />
        <main className="pp-large">
          <p className="bq-attente">Chargement…</p>
        </main>
      </div>
    );
  }

  const maj = moisEtAnnee(produit.mise_a_jour);
  // Sans le nombre de pages : voir `Boutique.tsx`. Le sommaire et l'extrait
  // disent ce que le document contient, ce qu'un nombre ne dit pas.
  const details = [
    maj ? `Mise à jour ${maj}` : "",
    produit.editable ? "PDF et Word" : "PDF",
  ].filter(Boolean);

  return (
    <div className="pp bq">
      <MenuSite />

      <main className="pp-large">
        <Link className="bq-retour" to="/boutique">
          ← Toutes les études
        </Link>

        <div className="bq-fiche">
          <div className="bq-fiche-corps">
            {/* La couverture EN PREMIER, en grand : c'est ce qu'on regarde
                avant de lire, et c'est la seule chose qui donne une idée du
                document tant qu'on n'a pas ouvert l'extrait. */}
            <div className="bq-visuel">
              {produit.image ? (
                <img src={produit.image} alt={`Couverture — ${produit.titre}`} />
              ) : (
                <span className="bq-visuel-vide" aria-hidden="true">
                  {initiale(produit.titre)}
                </span>
              )}
            </div>

            <div className="bq-titraille">
              {produit.theme && <p className="bq-theme">{produit.theme}</p>}
              <h1>{produit.titre}</h1>
              <p className="bq-meta">{details.join(" · ")}</p>
              {produit.avis.length > 0 && (
                <p className="bq-note">
                  <span className="bq-etoiles" aria-hidden="true">
                    {etoiles(produit.note)}
                  </span>
                  <span>
                    {produit.note.toFixed(1).replace(".", ",")} sur 5 ·{" "}
                    <a href="#avis">
                      {produit.avis.length} avis
                    </a>
                  </span>
                </p>
              )}
            </div>

            {produit.description && (
              <section className="bq-bloc">
                <h2>Ce que vous achetez</h2>
                {/* La description est saisie en texte libre : les paragraphes
                    sont ceux de la cliente, on ne les recompose pas. */}
                {produit.description
                  .split(/\n\s*\n/)
                  .filter((p) => p.trim())
                  .map((paragraphe) => (
                    <p key={paragraphe.slice(0, 40)} className="bq-description">
                      {paragraphe}
                    </p>
                  ))}
              </section>
            )}

            {produit.sommaire.length > 0 && (
              <section className="bq-bloc">
                <h2>Le sommaire</h2>
                <ol className="bq-sommaire">
                  {produit.sommaire.map((ligne) => (
                    <li key={ligne}>{ligne}</li>
                  ))}
                </ol>
              </section>
            )}

            <section className="bq-bloc">
              <h2>Comment ça se passe</h2>
              <ol className="bq-etapes">
                <li>
                  <b>Vous réglez</b> — paiement unique par carte, en ligne
                  sécurisée.
                </li>
                <li>
                  <b>Vous téléchargez</b> — le document est disponible dans la
                  seconde qui suit, sur la page de retour.
                </li>
                <li>
                  <b>Vous le retrouvez</b> — un espace s'ouvre à votre nom :
                  l'étude y reste, téléchargeable autant de fois que voulu.
                </li>
              </ol>
            </section>

            {produit.avis.length > 0 && (
              <section className="bq-bloc" id="avis">
                <h2>Ce qu'en disent les lectrices</h2>
                <ul className="bq-avis-liste">
                  {produit.avis.map((a) => (
                    <CarteAvis key={`${a.auteur}-${a.date}`} avis={a} />
                  ))}
                </ul>
              </section>
            )}
          </div>

          <aside className="bq-achat">
            <div className="bq-achat-prix">
              {prix(produit.prix_cents, produit.devise)}
            </div>
            <p className="bq-achat-mention">TTC · paiement unique</p>

            <label htmlFor="bq-email">Votre adresse e-mail</label>
            <input
              id="bq-email"
              type="email"
              autoComplete="email"
              placeholder="vous@exemple.fr"
              value={email}
              onChange={(evenement) => setEmail(evenement.target.value)}
            />

            {erreur && (
              <p className="bq-erreur bq-erreur-achat" role="alert">
                {erreur}
              </p>
            )}

            <button
              type="button"
              className="bq-bouton"
              onClick={() => void acheter()}
              disabled={envoi}
            >
              {envoi
                ? "Ouverture du paiement…"
                : `Acheter — ${prix(produit.prix_cents, produit.devise)}`}
            </button>

            {produit.extrait && (
              <a
                className="bq-extrait"
                href={produit.extrait}
                target="_blank"
                rel="noreferrer"
              >
                Consulter un extrait
              </a>
            )}

            <ul className="bq-rassurance">
              <li>Téléchargement immédiat après paiement</li>
              <li>PDF{produit.editable ? " et version Word" : ""}</li>
              <li>Retrouvable à tout moment dans votre espace</li>
              <li>Aucun abonnement, aucun engagement</li>
            </ul>
          </aside>
        </div>

        {proches.length > 0 && (
          <section className="bq-proches">
            <h2>Ces études peuvent aussi vous intéresser</h2>
            <div className="bq-grille">
              {proches.map((p) => (
                <CarteProduit key={p.slug} produit={p} />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
