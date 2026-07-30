/** Coquille de l'espace administrateur — même charte que l'espace client.
 *
 * Elle réutilise les classes de `theme/espace.css` : une seconde feuille de
 * style pour l'administration finirait par dériver de la première, et deux
 * chartes pour un même produit se voient immédiatement.
 *
 * Deux différences assumées avec l'espace client, parce qu'elles portent du
 * sens et non du goût :
 *
 * - le sceau est **noir sur or** au lieu d'or sur noir, pour qu'on sache d'un
 *   coup d'œil dans lequel des deux espaces on se trouve ;
 * - le bloc de pied affiche le nombre de **demandes à traiter** plutôt qu'un
 *   solde de crédits : c'est ce qui appelle une action ici.
 */
import { useBarreLaterale } from "../theme/useBarreLaterale";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "./api";
import { clearToken } from "../auth";

const ENTREES = [
  { vers: "/admin", libelle: "Tableau de bord", icone: "◈", exact: true },
  { vers: "/admin/organisations", libelle: "Organisations", icone: "◍" },
  { vers: "/admin/demandes", libelle: "Demandes", icone: "◇" },
  { vers: "/admin/jobs", libelle: "Générations", icone: "▤" },
  { vers: "/admin/incidents", libelle: "Incidents", icone: "⚠" },
  { vers: "/admin/orders", libelle: "Commandes", icone: "◐" },
  { vers: "/admin/clients", libelle: "Clients", icone: "◉" },
] as const;

const ENTETES: Record<string, { titre: string; sous: string }> = {
  "/admin": {
    titre: "Tableau de bord",
    sous: "Activité, paiements, consommation de crédits et volumes produits.",
  },
  "/admin/organisations": {
    titre: "Organisations",
    sous: "Formule, solde, consommation et volumes, agence par agence.",
  },
  "/admin/demandes": {
    titre: "Demandes à traiter",
    sous: "Changements de formule et achats de crédits venus des espaces clients.",
  },
  "/admin/jobs": {
    titre: "Générations",
    sous: "Suivi des études en cours et terminées. Relance en cas d'échec.",
  },
  "/admin/incidents": {
    titre: "Incidents",
    sous: "Ce qui demande une intervention.",
  },
  "/admin/orders": { titre: "Commandes", sous: "Les commandes reçues et leur état." },
  "/admin/clients": { titre: "Clients", sous: "Les contacts et leurs abonnements." },
};

/** En-tête de la page courante.
 *
 * La correspondance exacte ne couvrait pas les pages de détail : `/admin/jobs/42`
 * et `/admin/clients/<id>` retombaient sur « Administration », un titre qui ne
 * dit rien de l'écran affiché. On retient donc la clé la PLUS LONGUE qui
 * préfixe le chemin — ainsi une page de détail hérite du titre de sa liste, et
 * une nouvelle sous-route n'a pas à être déclarée pour être correctement
 * titrée. Viser la classe, pas les deux cas connus (règle 4).
 */
function enteteDe(chemin: string): { titre: string; sous: string } {
  const cle = Object.keys(ENTETES)
    .filter((c) => chemin === c || chemin.startsWith(`${c}/`))
    .sort((a, b) => b.length - a.length)[0];
  return (
    (cle ? ENTETES[cle] : undefined) ?? {
      titre: "Administration",
      sous: "Supervision de la plateforme.",
    }
  );
}

export function CoquilleAdmin() {
  const chemin = useRouterState({ select: (etat) => etat.location.pathname });
  const barre = useBarreLaterale();
  const entete = enteteDe(chemin);

  const { data: demandes } = useQuery({
    queryKey: ["admin", "demandes"],
    queryFn: adminApi.demandes,
    staleTime: 60_000,
  });
  const aTraiter = demandes?.ouvertes ?? 0;


  function deconnecter() {
    clearToken();
    window.location.href = "/login";
  }

  return (
    <div className={barre.visible ? "espace" : "espace barre-repliee"}>
      <nav
        id="navigation-admin"
        className={barre.visible ? "espace-barre ouverte" : "espace-barre"}
        aria-label="Navigation de l'administration"
      >
        <div className="espace-marque">
          <span className="espace-sceau inverse" aria-hidden="true">
            E
          </span>
          <div>
            <div className="espace-marque-nom">EVKHA</div>
            <div className="espace-marque-sous">Administration</div>
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
                {entree.vers === "/admin/demandes" && aTraiter > 0 && (
                  <span className="espace-compteur">{aTraiter}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>

        <div className="espace-solde">
          <div className="espace-solde-libelle">Demandes à traiter</div>
          <div className="espace-solde-valeur">{aTraiter}</div>
          <div className="espace-solde-detail">
            {aTraiter === 0 ? "Rien en attente" : "Formules et crédits"}
          </div>
        </div>

        <button type="button" className="bouton bouton-discret" onClick={deconnecter}>
          Se déconnecter
        </button>
      </nav>

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
            aria-controls="navigation-admin"
            onClick={barre.basculer}
          >
            <span className="espace-hamburger-traits" aria-hidden="true" />
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 className="espace-titre">{entete.titre}</h1>
            <p className="espace-sous-titre">{entete.sous}</p>
          </div>
          <a
            href="/espace"
            className="bouton bouton-contour bouton-sm"
            style={{ flex: "0 0 auto" }}
          >
            Espace client ↗
          </a>
        </header>

        <main className="espace-contenu">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
