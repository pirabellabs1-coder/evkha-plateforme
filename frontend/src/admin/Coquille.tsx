/** Coquille de l'espace administrateur.
 *
 * L'outil de travail quotidien de la gérante : elle y suit ses ventes, ses
 * clients, la production des études, et y tient son catalogue. La coquille
 * précédente alignait quatorze entrées à plat, sous des caractères
 * typographiques en guise d'icônes, et son en-tête ne disait ni où l'on était
 * ni ce qu'on pouvait y faire. Celle-ci pose quatre choses, pour tous les
 * écrans :
 *
 * 1. **Une barre en groupes** (`navigation.ts`) — Pilotage, Catalogue,
 *    Clients, Production, Communication —, chaque entrée sous une icône
 *    dessinée (`icones.tsx`). Repliable en rail d'icônes sur ordinateur,
 *    tiroir sur téléphone et tablette.
 * 2. **Un en-tête de page constant** : fil d'Ariane (groupe › écran › détail),
 *    titre — le seul `h1` de l'écran —, phrase d'aide, et à droite un
 *    emplacement que l'écran remplit avec `ActionsDePage`.
 * 3. **Un pied de barre** : voir le site, l'espace client quand une session
 *    y est ouverte sur ce poste, se déconnecter.
 * 4. **Le langage d'écran** (`console.css`) : tout ce qui est rendu sous
 *    `.console` — cartes, tableaux, chiffres, boutons, champs — prend la même
 *    forme, sans qu'un écran ait à le demander.
 *
 * ## Ce qui distingue l'administration de l'espace client
 *
 * Le sceau : **noir sur or**, là où l'espace client est or sur noir. On sait
 * d'un coup d'œil dans lequel des deux on se trouve — agir dans le mauvais
 * coûte plus cher qu'un regard.
 *
 * ## Ce que la coquille ne fait pas
 *
 * Elle ne charge aucun écran (`ecrans.ts`, `router.tsx`) et ne connaît aucune
 * route : elle lit le chemin courant et le plan. Les adresses restent celles
 * du routeur.
 */
import {
  type FocusEvent,
  type MouseEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { Outlet, useRouter, useRouterState } from "@tanstack/react-router";

import { clearToken } from "../auth";
import { jeton as jetonEspace } from "../espace/jeton";
import { useBarreLaterale } from "../theme/useBarreLaterale";
import { adminApi } from "./api";
import { EmplacementDesActions } from "./emplacement";
import { surveillerLesTableaux } from "./etiqueterTableaux";
import { Icone } from "./icones";
import { ENTETE_PAR_DEFAUT, GROUPES, positionDe } from "./navigation";
import "./console.css";

/** L'identifiant du contenu : la cible du lien d'évitement. */
const ID_DU_CONTENU = "contenu-admin";
const ID_DE_LA_BARRE = "navigation-admin";

/** Un clic qui doit rester au navigateur : bouton du milieu, ou une touche
 *  tenue pour ouvrir dans un onglet, une fenêtre, ou télécharger. */
function clicDetourne(evenement: MouseEvent<HTMLAnchorElement>): boolean {
  return (
    evenement.button !== 0 ||
    evenement.metaKey ||
    evenement.ctrlKey ||
    evenement.shiftKey ||
    evenement.altKey
  );
}

/** `/admin/` et `/admin` sont le même écran. */
function sansBarreFinale(chemin: string): string {
  return chemin.length > 1 ? chemin.replace(/\/+$/, "") : chemin;
}

/** Ce qu'une pastille de la barre a à dire. Trois états, et pas deux : « rien
 *  à traiter » et « je n'ai pas pu compter » ne se ressemblent pas. */
type Compte =
  | { etat: "connu"; nombre: number }
  | { etat: "inconnu" }
  | { etat: "en panne" };

function compteDe(
  lecture: { isError: boolean },
  nombre: number | undefined,
): Compte {
  if (nombre !== undefined) return { etat: "connu", nombre };
  return lecture.isError ? { etat: "en panne" } : { etat: "inconnu" };
}

/** La pastille d'une entrée : un nombre quand il y a quelque chose à traiter,
 *  rien quand il n'y a rien — et un signe distinct quand le compte n'a pas pu
 *  être lu. Une panne qui s'afficherait comme l'absence de pastille se lirait
 *  « zéro demande » : des clients attendraient derrière une barre qui se
 *  déclare à jour (règle 1). */
function PastilleDeBarre({ compte, quoi }: { compte: Compte; quoi: string }) {
  if (compte.etat === "en panne") {
    // Pas de `role="status"` : la pastille est DANS le lien, elle fait partie
    // de son nom (« Demandes — nombre de demandes indisponible »).
    return (
      <span className="console-pastille console-pastille-panne">
        <span aria-hidden="true">?</span>
        <span className="visuellement-cache">
          {" "}
          — nombre de {quoi} indisponible
        </span>
      </span>
    );
  }
  if (compte.etat !== "connu" || compte.nombre <= 0) return null;
  return (
    <span className="console-pastille">
      {compte.nombre}
      <span className="visuellement-cache"> {quoi} à traiter</span>
    </span>
  );
}

export function CoquilleAdmin() {
  const chemin = useRouterState({ select: (etat) => etat.location.pathname });
  const routeur = useRouter();
  const barre = useBarreLaterale();
  const position = positionDe(chemin);

  /** Suivre une entrée du plan sans recharger la page.
   *
   * Les entrées sont de vrais liens (`<a href>`) : ils s'ouvrent dans un
   * onglet, se copient, se lisent comme des liens. Un clic ordinaire, lui,
   * passe par l'historique du routeur — la page ne se recharge pas.
   *
   * Pas de `Link` ici, à dessein. `Link` n'accepte que les chemins que le
   * routeur a déclarés, vérifiés à la compilation ; ceux-ci viennent du plan
   * (`navigation.ts`), une liste de données, qui peut nommer un écran avant
   * que sa route n'existe (« Formations », écrite à part). Ce n'est donc pas
   * le compilateur qui tient ces chemins : c'est
   * `la-coquille-d-administration.test.tsx`, qui parcourt le plan et exige
   * que chaque chemin soit une route de l'arbre RÉEL (`router.creerRouteur`).
   * Et l'entrée courante se déduit du même plan que le titre et le fil
   * d'Ariane (`positionDe`) — une seule réponse à « où suis-je ? », pas deux
   * qui pourraient diverger.
   *
   * Un clic sur l'écran où l'on est déjà ne pousse rien : sinon chaque clic
   * ajouterait à l'historique une entrée identique, et « Précédent » ne
   * ferait plus rien autant de fois. */
  function suivre(evenement: MouseEvent<HTMLAnchorElement>, vers: string) {
    if (evenement.defaultPrevented || clicDetourne(evenement)) return;
    evenement.preventDefault();
    if (sansBarreFinale(routeur.history.location.pathname) === sansBarreFinale(vers)) return;
    routeur.history.push(vers);
  }

  // Sur grand écran, « pas visible » veut dire REPLIÉE EN RAIL : les icônes
  // restent, les libellés se retirent. Sur petit écran, c'est un tiroir, ouvert
  // ou fermé.
  const rail = barre.large && !barre.visible;
  const tiroirOuvert = !barre.large && barre.visible;
  const tiroirFerme = !barre.large && !barre.visible;

  // ── Ce qui attend une réponse ───────────────────────────────────────────
  // Les deux pastilles disent qu'il y a quelqu'un qui attend. Celle des
  // signalements compte les NOUVEAUX et les EN COURS : n'afficher que les
  // nouveaux la ferait tomber à zéro dès qu'on prend un dossier en charge.
  const lectureDemandes = useQuery({
    queryKey: ["admin", "demandes"],
    queryFn: adminApi.demandes,
    staleTime: 60_000,
  });
  const lectureSignalements = useQuery({
    queryKey: ["admin", "signalements"],
    queryFn: adminApi.signalements,
    staleTime: 60_000,
  });
  const comptes: Record<string, { compte: Compte; quoi: string }> = {
    "/admin/demandes": {
      compte: compteDe(lectureDemandes, lectureDemandes.data?.ouvertes),
      quoi: "demandes",
    },
    "/admin/signalements": {
      compte: compteDe(lectureSignalements, lectureSignalements.data?.a_traiter),
      quoi: "signalements",
    },
  };

  // ── Le tiroir : le focus y entre, et revient d'où il est parti ──────────
  const boutonMenu = useRef<HTMLButtonElement>(null);
  const boutonFermer = useRef<HTMLButtonElement>(null);
  const etaitOuvert = useRef(false);
  useEffect(() => {
    if (tiroirOuvert) {
      boutonFermer.current?.focus();
    } else if (etaitOuvert.current) {
      // Échap, le voile, la croix ou un lien choisi : dans tous les cas le
      // focus revient au bouton qui a ouvert, jamais au début du document.
      boutonMenu.current?.focus();
    }
    etaitOuvert.current = tiroirOuvert;
  }, [tiroirOuvert]);

  // ── Le contenu : tableaux étiquetés, emplacement des actions ────────────
  const contenu = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!contenu.current) return;
    return surveillerLesTableaux(contenu.current);
  }, []);
  const [emplacement, setEmplacement] = useState<HTMLElement | null>(null);

  // ── L'infobulle du rail ─────────────────────────────────────────────────
  // En rail, le libellé d'une entrée n'est plus visible : il reste lu par les
  // lecteurs d'écran (il est toujours dans le lien), et il s'affiche ici pour
  // les yeux, au survol COMME au focus du clavier. Elle est posée en
  // `position: fixed`, hors de la barre : dedans, le défilement de la liste la
  // couperait. Échap la retire sans déplacer le focus.
  const [infobulle, setInfobulle] = useState<{ texte: string; haut: number } | null>(null);
  const montrer = (
    evenement: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>,
    texte: string,
  ) => {
    if (!rail) return;
    const cadre = evenement.currentTarget.getBoundingClientRect();
    setInfobulle({ texte, haut: cadre.top + cadre.height / 2 });
  };
  const cacher = () => setInfobulle(null);
  useEffect(() => {
    if (!infobulle) return;
    const surTouche = (evenement: KeyboardEvent) => {
      if (evenement.key === "Escape") setInfobulle(null);
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [infobulle]);
  const infobulleVisible = rail ? infobulle : null;

  function deconnecter() {
    clearToken();
    window.location.href = "/login";
  }

  /** Le lien d'évitement mène au contenu sans passer par l'adresse : un `#…`
   *  ajouté à l'URL serait lu par le routeur comme un changement de page. */
  function allerAuContenu(evenement: MouseEvent<HTMLAnchorElement>) {
    evenement.preventDefault();
    contenu.current?.focus();
    contenu.current?.scrollIntoView?.();
  }

  const titre = position ? (position.detail ?? position.entree.titre) : ENTETE_PAR_DEFAUT.titre;
  const aide = position ? position.entree.aide : ENTETE_PAR_DEFAUT.aide;

  const classes = ["console"];
  if (rail) classes.push("console-en-rail");
  if (tiroirOuvert) classes.push("console-tiroir-ouvert");

  return (
    <div className={classes.join(" ")}>
      {/* Tiroir ouvert, le contenu est inerte : le lien qui y mène l'est
          aussi, sinon il resterait atteignable et viserait une zone morte. */}
      <a
        className="console-saut"
        href={`#${ID_DU_CONTENU}`}
        inert={tiroirOuvert}
        onClick={allerAuContenu}
      >
        Aller au contenu
      </a>

      {/* Fermé, le tiroir est hors écran : `inert` le retire aussi de la
          tabulation et des lecteurs d'écran. Sans cela on tabulait dans
          quinze liens invisibles avant d'atteindre la page. */}
      <nav
        id={ID_DE_LA_BARRE}
        className="console-barre"
        aria-label="Navigation de l'administration"
        inert={tiroirFerme}
      >
        <div className="console-marque">
          <span className="console-sceau" aria-hidden="true">
            E
          </span>
          <div className="console-marque-texte">
            <div className="console-marque-nom">EVKHA</div>
            <div className="console-marque-sous">Administration</div>
          </div>
          <button
            ref={boutonFermer}
            type="button"
            className="console-bouton-icone console-fermer-tiroir"
            aria-label="Fermer le menu"
            onClick={barre.fermer}
          >
            <Icone nom="fermer" />
          </button>
        </div>

        <div className="console-groupes">
          {GROUPES.map((groupe) => (
            <div key={groupe.cle} className="console-groupe">
              <p className="console-groupe-titre" id={`groupe-${groupe.cle}`}>
                {groupe.libelle}
              </p>
              <ul className="console-entrees" aria-labelledby={`groupe-${groupe.cle}`}>
                {groupe.entrees.map((entree) => {
                  const pastille = comptes[entree.vers];
                  const courante = position?.entree.vers === entree.vers;
                  return (
                    <li key={entree.vers}>
                      {/* L'entrée courante : `aria-current` pour qui ne voit pas
                          la plaque d'or, `actif` pour qui la voit. Sur une
                          page de détail, c'est l'écran parent qui l'est. */}
                      <a
                        href={entree.vers}
                        className={courante ? "console-entree actif" : "console-entree"}
                        aria-current={courante ? "page" : undefined}
                        onClick={(evenement) => {
                          suivre(evenement, entree.vers);
                          cacher();
                          barre.fermer();
                        }}
                        onMouseEnter={(evenement) => montrer(evenement, entree.libelle)}
                        onMouseLeave={cacher}
                        onFocus={(evenement) => montrer(evenement, entree.libelle)}
                        onBlur={cacher}
                      >
                        <Icone nom={entree.icone} />
                        <span className="console-entree-libelle">{entree.libelle}</span>
                        {pastille && (
                          <PastilleDeBarre compte={pastille.compte} quoi={pastille.quoi} />
                        )}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        <div className="console-pied">
          {/* Des liens qui RECHARGENT la page, eux : le site public et
              l'espace client sont d'autres morceaux de l'application, avec
              leur propre garde d'accès — on y entre par un vrai chargement. */}
          <a
            className="console-entree"
            href="/"
            onMouseEnter={(evenement) => montrer(evenement, "Voir le site")}
            onMouseLeave={cacher}
            onFocus={(evenement) => montrer(evenement, "Voir le site")}
            onBlur={cacher}
          >
            <Icone nom="site" />
            <span className="console-entree-libelle">Voir le site</span>
          </a>
          {/* Seulement si une session cliente est ouverte sur ce poste (une
              session d'assistance, le plus souvent) : sans elle le lien
              mènerait à un écran de connexion, pas à un espace. */}
          {jetonEspace.present() && (
            <a
              className="console-entree"
              href="/espace"
              onMouseEnter={(evenement) => montrer(evenement, "Espace client")}
              onMouseLeave={cacher}
              onFocus={(evenement) => montrer(evenement, "Espace client")}
              onBlur={cacher}
            >
              <Icone nom="espace" />
              <span className="console-entree-libelle">Espace client</span>
            </a>
          )}
          <button
            type="button"
            className="console-entree console-entree-bouton"
            onClick={deconnecter}
            onMouseEnter={(evenement) => montrer(evenement, "Se déconnecter")}
            onMouseLeave={cacher}
            onFocus={(evenement) => montrer(evenement, "Se déconnecter")}
            onBlur={cacher}
          >
            <Icone nom="deconnexion" />
            <span className="console-entree-libelle">Se déconnecter</span>
          </button>
        </div>
      </nav>

      {/* Décoratif pour le clavier : le tiroir a sa croix, et Échap ferme. Le
          voile sert à qui clique à côté. */}
      <button
        type="button"
        className="console-voile"
        aria-label="Fermer le menu"
        tabIndex={-1}
        hidden={!tiroirOuvert}
        onClick={barre.fermer}
      />

      {infobulleVisible && (
        <div
          className="console-infobulle"
          aria-hidden="true"
          style={{ top: infobulleVisible.haut }}
        >
          {infobulleVisible.texte}
        </div>
      )}

      {/* Tiroir ouvert : tout ce qui est derrière devient inerte — ni clic,
          ni tabulation, ni lecture. Le tiroir est alors la seule chose à
          l'écran pour tout le monde. */}
      <div className="console-corps" inert={tiroirOuvert}>
        <div className="console-haut">
          <button
            ref={boutonMenu}
            type="button"
            className="console-bouton-icone console-bouton-menu"
            aria-label={
              barre.large
                ? barre.visible
                  ? "Replier le menu"
                  : "Déplier le menu"
                : "Ouvrir le menu"
            }
            aria-expanded={barre.visible}
            aria-controls={ID_DE_LA_BARRE}
            onClick={barre.basculer}
          >
            <Icone nom={barre.large ? (barre.visible ? "replier" : "deplier") : "menu"} />
          </button>

          <nav aria-label="Fil d'Ariane" className="console-fil">
            <ol>
              {position ? (
                <>
                  <li>{position.groupe.libelle}</li>
                  <li>
                    <Icone nom="chevron" taille={14} />
                    {position.detail ? (
                      <a
                        href={position.entree.vers}
                        onClick={(evenement) => suivre(evenement, position.entree.vers)}
                      >
                        {position.entree.libelle}
                      </a>
                    ) : (
                      <span aria-current="page">{position.entree.libelle}</span>
                    )}
                  </li>
                  {position.detail && (
                    <li>
                      <Icone nom="chevron" taille={14} />
                      <span aria-current="page">{position.detail}</span>
                    </li>
                  )}
                </>
              ) : (
                <li>
                  <span aria-current="page">{ENTETE_PAR_DEFAUT.titre}</span>
                </li>
              )}
            </ol>
          </nav>
        </div>

        <header className="console-entete">
          <div className="console-entete-texte">
            <h1 className="console-titre-page">{titre}</h1>
            <p className="console-aide">{aide}</p>
          </div>
          {/* Vide tant qu'aucun écran n'y dépose rien : la feuille le retire
              alors de la mise en page (`:empty`). */}
          <div ref={setEmplacement} className="console-entete-actions" />
        </header>

        <main ref={contenu} id={ID_DU_CONTENU} className="console-contenu" tabIndex={-1}>
          <EmplacementDesActions.Provider value={emplacement}>
            <Outlet />
          </EmplacementDesActions.Provider>
        </main>
      </div>
    </div>
  );
}
