/** Coquille de l'espace client : barre latérale, en-tête, contenu.
 *
 * La barre ne porte plus le solde. Elle l'affichait en permanence, sur chaque
 * écran — le §9.6 demande de « consulter la formule en cours et le solde », et
 * la lecture d'alors était que la valeur décidant d'une commande ne devait pas
 * se trouver derrière un clic. La cliente l'a retiré le 07/08/2026. Le solde
 * reste consultable là où on va le chercher : la page Crédits, qui le donne
 * avec son historique et son autonomie.
 */
import { useBarreLaterale } from "../theme/useBarreLaterale";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { espaceApi, jeton } from "./api";
import * as f from "./format";
import { useMoi } from "./useMoi";
import { Bandeau } from "./composants/Interface";

const ENTREES = [
  { vers: "/espace", libelle: "Tableau de bord", icone: "◈", exact: true },
  { vers: "/espace/commander", libelle: "Commander", icone: "＋" },
  { vers: "/espace/livrables", libelle: "Livrables", icone: "▤" },
  { vers: "/espace/ma-marque", libelle: "Ma marque", icone: "◉" },
  { vers: "/espace/achats", libelle: "Mes achats", icone: "▣" },
  { vers: "/espace/credits", libelle: "Crédits", icone: "◐" },
  // Réservée aux abonnés : elle propose de souscrire, de changer de formule et
  // d'acheter des crédits au tarif d'une formule. Un acheteur à l'unité n'en a
  // aucune, donc aucun tarif à appliquer — le serveur refuse ces routes, et
  // l'afficher reviendrait à montrer une porte qui se ferme.
  { vers: "/espace/abonnement", libelle: "Abonnement", icone: "◎", abonnesSeuls: true },
  { vers: "/espace/equipe", libelle: "Équipe", icone: "◍" },
  // En dernier, contre le bouton de déconnexion : « Mon compte » n'est pas une
  // section de travail comme les précédentes mais une action personnelle, et
  // c'est là qu'on la cherche.
  { vers: "/espace/mon-compte", libelle: "Mon compte", icone: "⊙" },
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
  "/espace/achats": {
    titre: "Mes achats",
    sous: "Vos études achetées en téléchargement immédiat.",
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
  "/espace/mon-compte": {
    titre: "Mon compte",
    sous: "Votre identité, et le mot de passe qui ouvre cet espace.",
  },
};

export function Coquille() {
  const { data: moi } = useMoi();
  const chemin = useRouterState({ select: (s) => s.location.pathname });
  const barre = useBarreLaterale();
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
  // Abonné par défaut TANT QUE `moi` n'est pas chargé : c'est le cas de la
  // quasi-totalité des comptes, et faire disparaître puis réapparaître une
  // entrée de menu au chargement se voit. Le sens du défaut compte : masquer
  // par défaut clignoterait chez tout le monde, afficher par défaut ne
  // clignote que chez ceux à l'unité — et la porte qu'ils verraient une
  // fraction de seconde leur est de toute façon refusée par le serveur.
  const estAbonne = (moi?.organisation.type_de_compte ?? "abonne") === "abonne";

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
          {ENTREES.filter(
            (entree) =>
              !("abonnesSeuls" in entree && entree.abonnesSeuls) || estAbonne,
          ).map((entree) => (
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

        {/* Le solde n'est plus affiche dans la barre.
            Il y figurait en permanence, sur chaque ecran. La cliente l'a
            retire. Le chiffre reste consultable la ou on va le chercher : la
            page Credits, qui le donne avec son historique et son autonomie. */}

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
          {/* L'adresse e-mail et le rôle figuraient ici, sur deux lignes, en
              haut de chaque écran. Personne n'a besoin qu'on lui rappelle sa
              propre adresse à chaque page — et sur un poste partagé, l'afficher
              en permanence n'aide personne non plus. Les deux restent lisibles
              sur « Mon compte », où l'on va justement pour cela.
              Reste le nom de l'organisation : le document est livré en marque
              blanche, savoir POUR QUI on travaille n'est pas du décor. */}
          {moi && (
            <div className="espace-entete-identite">
              {moi.organisation.raison_sociale}
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
          {/* Abonnement inactif : on le DIT, on ne ferme pas la porte. L'espace
              reste consultable — ses documents, son journal, son équipe. Seule
              la commande est retenue, parce qu'elle seule engage une
              production. */}
          {/* Le bandeau ne s'adresse qu'aux abonnés. Un acheteur à l'unité a
              payé son étude : lui dire d'« activer son abonnement » lui
              annoncerait un manquement qui n'existe pas, et le renverrait vers
              une page que le serveur lui refuse. */}
          {moi && !moi.acces_ouvert && estAbonne && (
            <Bandeau titre="Abonnement à activer">
              Vous pouvez consulter votre espace, mais pas encore commander de
              document.{" "}
              <Link to="/espace/souscription" className="bandeau-lien">
                Activer mon abonnement
              </Link>
            </Bandeau>
          )}
          {/* « Solde bas » n'a rien à dire de plus au compte qui n'a pas encore
              activé son abonnement : le bandeau ci-dessus le couvre, et les
              empiler ferait deux alertes pour une seule situation. */}
          {/* Et rien non plus pour un compte a l'unite. Le seuil d'alerte vaut
              1 par defaut : quelqu'un qui vient de payer SON etude, et qui
              detient donc exactement le credit qu'il a achete, lisait « solde
              bas » trente secondes apres son paiement. L'alerte invite a
              recharger — un geste qui n'existe pas pour lui. Un avertissement
              sur lequel le lecteur ne peut rien est pire qu'aucun (regle 2). */}
          {alerte &&
            estAbonne &&
            moi?.acces_ouvert &&
            moi?.organisation.statut !== "suspendue" && (
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
