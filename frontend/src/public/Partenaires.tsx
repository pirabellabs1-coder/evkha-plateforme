/** Page partenaires publique — reprise de `evkha.fr/partenairespro`.
 *
 * Elle remplace la page systeme.io : c'est ici que le visiteur choisit sa
 * formule, crée son compte et accède à ses crédits.
 *
 * **Pas de barre de navigation.** Le menu reste celui du site vitrine, qui
 * pointera vers cette adresse : en reconstruire une copie ici ferait deux
 * menus à tenir à jour, et le nôtre serait faux dès la première page ajoutée
 * sur systeme.io (règle 5).
 *
 * Deux principes de construction :
 *
 * 1. **Les chiffres viennent du serveur.** Prix, crédits inclus, crédit
 *    supplémentaire, coût par livrable : tout est lu dans la table `Formule`.
 *    Recopier « 129 € » dans ce fichier ferait deux sources de vérité pour un
 *    même tarif, et la page publique finirait par contredire l'espace client
 *    (règle 5). Le texte éditorial, lui, vit dans `contenu.ts`.
 *
 * 2. **Aucun tarif n'est affiché tant qu'il n'est pas chargé.** Une page qui
 *    montrerait des prix de repli en attendant l'API afficherait un prix faux
 *    à qui a une connexion lente — sur une page de vente, c'est inacceptable.
 */
import { useEffect, useState } from "react";
import {
  APPEL_FINAL,
  CALCUL,
  CONTACT_EMAIL,
  FAQ,
  FONDATRICE,
  FORMULES_SOUS_TITRES,
  HERO,
  POUR_QUI,
  PREUVES,
  PRINCIPE,
} from "./contenu";
import { chargerFormules, euros, type FormulePublique } from "./donnees";
import "./Partenaires.css";

/** Destination du bouton « Souscrire ».
 *
 * Vers la création de compte, pas vers la connexion : le visiteur qui clique
 * n'a par définition pas encore de compte, et lui présenter un écran de
 * connexion est le meilleur moyen de le perdre.
 *
 * La formule voyage dans l'adresse. Le prestataire de paiement n'étant pas
 * branché, l'inscription enregistre l'intention sans rien encaisser ni
 * créditer — voir `organisations/inscription.py`. Le jour où Stripe arrive,
 * c'est cette fonction qui mènera au paiement.
 */
function lienSouscription(code: string): string {
  return `/inscription?formule=${encodeURIComponent(code)}`;
}

function Formules({ formules }: { formules: FormulePublique[] }) {
  return (
    <div className="pp-formules">
      {formules.map((formule) => (
        <article
          key={formule.code}
          className={
            formule.mise_en_avant ? "pp-formule pp-avant" : "pp-formule"
          }
        >
          <div className="pp-formule-sous-titre">
            {FORMULES_SOUS_TITRES[formule.code] ?? " "}
          </div>
          <h3>{formule.libelle}</h3>
          <div className="pp-formule-prix">
            {euros(formule.prix_mensuel_cents)} <span>/ mois</span>
          </div>

          <div className="pp-formule-quoi">Ce que vous obtenez :</div>
          <ul>
            <li>
              {formule.credits_par_echeance} crédit
              {formule.credits_par_echeance > 1 ? "s" : ""} inclus chaque mois
            </li>
            <li>
              Crédit supplémentaire&nbsp;:{" "}
              {euros(formule.prix_credit_supplementaire_cents)}
            </li>
            <li>
              Soit {euros(formule.cout_par_livrable_cents)} par livrable inclus
            </li>
            {formule.avantages.map((avantage) => (
              <li key={avantage}>{avantage}</li>
            ))}
          </ul>

          <a
            className="pp-formule-souscrire"
            href={lienSouscription(formule.code)}
          >
            Souscrire à {formule.libelle}
          </a>
        </article>
      ))}
    </div>
  );
}

export function Partenaires() {
  const [formules, setFormules] = useState<FormulePublique[] | null>(null);
  const [erreur, setErreur] = useState("");

  // Le gabarit HTML annonce « EVKHA — Espace client » : juste pour les deux
  // espaces connectes, faux pour une page publique que l'on partage par lien
  // et que les moteurs indexent.
  useEffect(() => {
    const precedent = document.title;
    document.title = "Partenaires PRO et abonnements — EVKHA";
    return () => {
      document.title = precedent;
    };
  }, []);

  useEffect(() => {
    let vivant = true;
    chargerFormules()
      .then((liste) => vivant && setFormules(liste))
      .catch((e: unknown) => {
        if (vivant) setErreur(e instanceof Error ? e.message : String(e));
      });
    return () => {
      vivant = false;
    };
  }, []);

  // La fourchette « 42,90 à 64,50 € » est DÉDUITE des formules chargées. Elle
  // était écrite en dur sur la page d'origine : au premier changement de
  // tarif, elle serait devenue fausse sans que personne ne le remarque.
  const couts = (formules ?? [])
    .map((f) => f.cout_par_livrable_cents)
    .filter((c) => c > 0);
  const fourchette =
    couts.length > 0
      ? `${euros(Math.min(...couts))} à ${euros(Math.max(...couts))}`
      : "";

  return (
    <div className="pp">
      {/* ── Ouverture ────────────────────────────────────────────────── */}
      <header className="pp-large pp-hero">
        <div>
          <h1>{HERO.titre}</h1>
          <p className="pp-hero-accroche">{HERO.accroche}</p>
          {HERO.corps.map((p) => (
            <p key={p}>{p}</p>
          ))}
          <p className="pp-hero-signature">{HERO.signature}</p>
        </div>
        <img
          className="pp-hero-image"
          src="/partenaires/reunion.jpg"
          alt="Trois personnes en réunion de travail autour d'un ordinateur portable"
          loading="lazy"
        />
      </header>

      <div className="pp-large pp-preuves">
        {PREUVES.map((preuve) => (
          <div key={preuve.libelle}>
            <div className="pp-preuve-valeur">{preuve.valeur}</div>
            <div className="pp-preuve-libelle">{preuve.libelle}</div>
          </div>
        ))}
      </div>

      {/* ── Le principe ──────────────────────────────────────────────── */}
      <section className="pp-section pp-section-creme">
        <div className="pp-large">
          <p className="pp-surtitre">{PRINCIPE.surtitre}</p>
          <h2 className="pp-titre">{PRINCIPE.titre}</h2>
          <div className="pp-etapes">
            {PRINCIPE.etapes.map((etape, rang) => (
              <article className="pp-etape" key={etape.titre}>
                <div className="pp-etape-rang">{rang + 1}</div>
                <h3>{etape.titre}</h3>
                <p>{etape.corps}</p>
              </article>
            ))}
          </div>
          <p className="pp-bandeau-noir">
            <strong>1 crédit = 1 livrable au choix</strong>
            {PRINCIPE.bandeau.replace("1 crédit = 1 livrable au choix", "")}
          </p>
        </div>
      </section>

      {/* ── Formules ─────────────────────────────────────────────────── */}
      <section className="pp-section">
        <div className="pp-large">
          <h2 className="pp-titre">Quatre formules, zéro droit d'entrée</h2>
          <p className="pp-formules-intro">
            Abonnement mensuel avec crédits inclus. Engagement minimum de
            3&nbsp;mois, puis sans engagement. Crédits supplémentaires à tarif
            dégressif.
          </p>

          {erreur && (
            <p className="pp-erreur">
              Les tarifs ne peuvent pas être affichés pour le moment ({erreur}).
              Écrivez-nous à {CONTACT_EMAIL}, nous vous les communiquons.
            </p>
          )}
          {!erreur && formules === null && (
            <p className="pp-attente">Chargement des formules…</p>
          )}
          {formules !== null && formules.length > 0 && (
            <Formules formules={formules} />
          )}
        </div>
      </section>

      {/* ── Pour qui ─────────────────────────────────────────────────── */}
      <section className="pp-section">
        <div className="pp-large">
          <h2 className="pp-titre">{POUR_QUI.titre}</h2>
          <div className="pp-cibles">
            {POUR_QUI.cibles.map((cible) => (
              <article className="pp-cible" key={cible.titre}>
                <h3>{cible.titre}</h3>
                <p>{cible.corps}</p>
                <p className="pp-cible-avec">{cible.avec}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Le calcul ────────────────────────────────────────────────── */}
      <section className="pp-section pp-section-creme">
        <div className="pp-large">
          <p className="pp-surtitre">{CALCUL.surtitre}</p>
          <h2 className="pp-titre">{CALCUL.titre}</h2>
          <div className="pp-calcul">
            {CALCUL.colonnes.map((colonne) => (
              <div key={colonne.titre}>
                <div className="pp-calcul-valeur">
                  {colonne.valeur ?? fourchette ?? ""}
                </div>
                <h3>{colonne.titre}</h3>
                <p>{colonne.corps}</p>
              </div>
            ))}
          </div>
          <p className="pp-lisere">
            Vous êtes un particulier, un porteur de projet ? Découvrez nos{" "}
            <a href="https://www.evkha.fr/etudes">ÉTUDES</a> et autres livrables{" "}
            <a href="https://www.evkha.fr/etudes">À L'UNITÉ</a>.
          </p>
        </div>
      </section>

      {/* ── La fondatrice ────────────────────────────────────────────── */}
      <section className="pp-section">
        <div className="pp-large pp-fondatrice">
          <img
            className="pp-fondatrice-portrait"
            src="/partenaires/evangeline.jpg"
            alt="Evangeline Khaili, fondatrice d'Evkha"
            loading="lazy"
          />
          <div>
            <p className="pp-fondatrice-surtitre">{FONDATRICE.surtitre}</p>
            <h2>{FONDATRICE.titre}</h2>
            <div className="pp-fondatrice-trait" />
            <p>{FONDATRICE.corps}</p>
          </div>
        </div>
      </section>

      {/* ── Questions ────────────────────────────────────────────────── */}
      <section className="pp-section">
        <div className="pp-large">
          <p className="pp-surtitre">{FAQ.surtitre}</p>
          <h2 className="pp-titre">{FAQ.titre}</h2>
          <div className="pp-faq">
            {FAQ.questions.map((question) => (
              <div className="pp-question" key={question.q}>
                <span className="pp-question-chevron" aria-hidden="true">
                  »
                </span>
                <h3>{question.q}</h3>
                <p>{question.r}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Appel final ──────────────────────────────────────────────── */}
      <section className="pp-appel">
        <p className="pp-appel-surtitre">{APPEL_FINAL.surtitre}</p>
        <h2>{APPEL_FINAL.titre}</h2>
        {APPEL_FINAL.corps.map((p) => (
          <p key={p}>{p}</p>
        ))}
      </section>

      <div style={{ textAlign: "center", padding: "2rem 1rem" }}>
        <a className="pp-appel-bouton" href={lienSouscription("pro")}>
          CHOISIR LA FORMULE PRO
        </a>
      </div>

      <footer className="pp-pied">
        <div>
          <a href="https://www.evkha.fr/confidentialite">
            Politique de confidentialité
          </a>
          <a href="https://www.evkha.fr/mentions-legales">
            Mentions légales RGPD Evkha
          </a>
          <a href="https://www.evkha.fr/cgv">CGV / CGU Evkha</a>
        </div>
        <div className="pp-pied-copyright">
          © 2026 EVKHA. Tous droits réservés.
        </div>
      </footer>
    </div>
  );
}
