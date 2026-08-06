/** Coquille de l'espace client : barre latérale, en-tête, contenu.
 *
 * La barre porte le solde de crédits en permanence. C'est délibéré : le §9.6
 * demande de « consulter la formule en cours et le solde », et la valeur qui
 * décide si l'on peut commander ne doit pas se trouver derrière un clic.
 */
import { useBarreLaterale } from "../theme/useBarreLaterale";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { espaceApi, jeton } from "./api";
import * as f from "./format";
import { useMoi } from "./useMoi";
import { Souscription } from "./Souscription";
import { Bandeau } from "./composants/Interface";

const ENTREES = [
  { vers: "/espace", libelle: "Tableau de bord", icone: "◈", exact: true },
  { vers: "/espace/commander", libelle: "Commander", icone: "＋" },
  { vers: "/espace/livrables", libelle: "Livrables", icone: "▤" },
  { vers: "/espace/ma-marque", libelle: "Ma marque", icone: "◉" },
  { vers: "/espace/credits", libelle: "Crédits", icone: "◐" },
  { vers: "/espace/abonnement", libelle: "Abonnement", icone: "◎" },
  { vers: "/espace/equipe", libelle: "Équipe", icone: "◍" },
] as const;

/** Titre et sous-titre de l'en-tête, dérivés de la route courante.
 *  Les écrire dans chaque page les ferait diverger de la navigation. */
const ENTETES: Record<string, { titre: string; sous: string }> = {
  "/espace": {
    titre: "Tableau de bord",
    sous: "Vue d'ensemble de votre activité et de votre consommation.",
  },
  "/espace/commander": {
    titre: "Commander un document",
    sous: "Choisissez le livrable, répondez au questionnaire, la production démarre.",
  },
  "/espace/livrables": {
    titre: "Livrables",
    sous: "Vos documents produits, en Word et en PDF.",
  },
  "/espace/ma-marque": {
    titre: "Ma marque",
    sous: "Votre entreprise et la charte appliquée à vos documents.",
  },
  "/espace/credits": {
    titre: "Crédits et abonnement",
    sous: "Votre solde, votre formule et votre consommation ligne par ligne.",
  },
  "/espace/abonnement": {
    titre: "Abonnement et crédits",
    sous: "Votre formule, les autres formules, et l'achat de crédits additionnels.",
  },
  "/espace/equipe": {
    titre: "Équipe",
    sous: "Les collaborateurs qui partagent votre portefeuille de crédits.",
  },
};

export function Coquille() {
  const { data: moi } = useMoi();
  const chemin = useRouterState({ select: (s) => s.location.pathname });
  const barre = useBarreLaterale();

  // Souscription non réglée : l'espace entier cède la place à l'écran de
  // paiement. Pas un bandeau au-dessus d'un espace vide — chaque page
  // recevrait de toute façon un 402, et la personne collectionnerait les
  // erreurs sans jamais lire ce qu'il faut faire.
  //
  // Placé APRÈS les crochets et non avant : un retour anticipé au-dessus de
  // `useMoi` ou `useBarreLaterale` changerait le nombre de crochets appelés
  // d'un rendu à l'autre, ce que React interdit.
  if (moi && !moi.acces_ouvert) {
    return <Souscription moi={moi} />;
  }
  // Une route à paramètre (`/espace/livrables/<id>`) n'a pas d'entrée fixe :
  // on retombe sur l'en-tête de sa section plutôt que sur celui du tableau de
  // bord, qui annoncerait la mauvaise page.
  const entete =
    ENTETES[chemin] ??
    (chemin.startsWith("/espace/livrables")
      ? { titre: "Suivi de production", sous: "Où en est votre étude, étape par étape." }
      : ENTETES["/espace"]);
  const solde = moi?.credits.solde ?? 0;
  const alerte = moi?.credits.alerte ?? false;

  async function deconnecter() {
    // On tente la révocation côté serveur, mais on efface le jeton local dans
    // tous les cas : une API injoignable ne doit pas laisser une session
    // ouverte sur le poste.
    try {
      await espaceApi.deconnexion();
    } finally {
      jeton.effacer();
      window.location.href = "/espace/connexion";
    }
  }

  return (
    <div className={barre.visible ? "espace" : "espace barre-repliee"}>
      <nav
        id="navigation-espace"
        className={barre.visible ? "espace-barre ouverte" : "espace-barre"}
        aria-label="Navigation de l'espace client"
      >
        <div className="espace-marque">
          <span className="espace-sceau" aria-hidden="true">
            E
          </span>
          <div>
            <div className="espace-marque-nom">EVKHA</div>
            <div className="espace-marque-sous">Espace client</div>
          </div>
        </div>

        <ul className="espace-nav">
          {ENTREES.map((entree) => (
            <li key={entree.vers}>
              <Link
                to={entree.vers}
                className="espace-lien"
                activeProps={{ className: "espace-lien actif" }}
                activeOptions={{ exact: "exact" in entree ? entree.exact : false }}
                onClick={barre.fermer}
              >
                <span className="espace-lien-icone" aria-hidden="true">
                  {entree.icone}
                </span>
                {entree.libelle}
              </Link>
            </li>
          ))}
        </ul>

        <div className={alerte ? "espace-solde bas" : "espace-solde"}>
          <div className="espace-solde-libelle">Solde</div>
          <div className="espace-solde-valeur">{f.nombre(solde)}</div>
          <div className="espace-solde-detail">
            {moi?.abonnement
              ? `Formule ${moi.abonnement.formule}`
              : "Aucun abonnement actif"}
          </div>
        </div>

        <button type="button" className="bouton bouton-discret" onClick={deconnecter}>
          Se déconnecter
        </button>
      </nav>

      {/* Voile de fermeture. Un `button` et non un `div` : cliquable au clavier
          et annonce comme actionnable par un lecteur d'ecran. */}
      <button
        type="button"
        className={barre.visible && !barre.large ? "espace-voile visible" : "espace-voile"}
        aria-label="Fermer la navigation"
        onClick={barre.fermer}
      />

      <div className="espace-corps">
        <header className="espace-entete">
          <button
            type="button"
            className="espace-hamburger"
            aria-label={barre.visible ? "Fermer la navigation" : "Ouvrir la navigation"}
            aria-expanded={barre.visible}
            aria-controls="navigation-espace"
            onClick={barre.basculer}
          >
            <span className="espace-hamburger-traits" aria-hidden="true" />
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 className="espace-titre">{entete.titre}</h1>
            <p className="espace-sous-titre">{entete.sous}</p>
          </div>
          {moi && (
            <div className="espace-entete-identite" style={{ textAlign: "right" }}>
              <div style={{ fontWeight: 600 }}>{moi.organisation.raison_sociale}</div>
              <div className="carte-note">
                {moi.utilisateur.email} · {f.role(moi.utilisateur.role)}
              </div>
            </div>
          )}
        </header>

        <main className="espace-contenu">
          {moi?.organisation.statut === "suspendue" && (
            <Bandeau ton="echec" titre="Organisation suspendue">
              Aucune nouvelle commande n'est possible. Vos documents déjà
              produits restent accessibles. Contactez EVKHA pour rétablir votre
              accès.
            </Bandeau>
          )}
          {alerte && moi?.organisation.statut !== "suspendue" && (
            <Bandeau titre="Solde bas">
              Il vous reste {f.credits(solde)}. Une commande est bloquée si le
              solde ne la couvre pas — aucun découvert n'est possible.
            </Bandeau>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
