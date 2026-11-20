/** Chaque cellule d'un tableau de l'administration connaît le nom de sa colonne.
 *
 * Sous 760 px, un tableau de données ne tient pas : huit colonnes dans 360 px
 * obligent à faire défiler latéralement, et l'on perd l'en-tête de vue. La
 * feuille (`console.css`, « Tableaux ») le replie donc en cartes empilées, une
 * par ligne, chaque valeur sous le nom de sa colonne. Ce nom, le CSS ne peut
 * le lire que dans la cellule elle-même : `content: attr(data-libelle)`.
 *
 * Plutôt que de recopier l'intitulé de la colonne sur chaque `<td>` de chaque
 * écran — vingt tableaux, cent colonnes, et la certitude qu'un intitulé
 * corrigé dans l'en-tête ne le sera pas dans les cellules (règle 5) —, cette
 * fonction le lit UNE fois dans le `<thead>` et le pose sur les cellules.
 * Branchée par la coquille sur son `<main>`, elle couvre tous les écrans,
 * présents et à venir, et rejoue quand des lignes arrivent.
 *
 * Trois précisions :
 *
 * - une cellule qui porte DÉJÀ `data-libelle` est laissée telle quelle : un
 *   écran peut nommer lui-même une cellule que l'en-tête ne décrit pas ;
 * - une colonne dont l'en-tête n'est lu que par les lecteurs d'écran
 *   (« Actions », dans un `.visuellement-cache`) reçoit un libellé VIDE : la
 *   carte n'écrit pas « ACTIONS » au-dessus de ses boutons ;
 * - une cellule étendue (`colspan`) n'appartient à aucune colonne : libellé
 *   vide aussi.
 *
 * Les rôles sont réécrits explicitement (`table`, `row`, `cell`…). Dès qu'une
 * feuille passe un `<tr>` en `display: grid`, plusieurs navigateurs cessent
 * d'annoncer un tableau ; le rôle explicite le leur rend. Sur grand écran ce
 * sont les rôles que ces éléments ont déjà : rien ne change.
 *
 * Enfin, un cadre qui défile (`.tableau-defile`) doit pouvoir défiler au
 * clavier : s'il déborde, il devient focalisable et se nomme.
 */

const ROLES: [selecteur: string, role: string][] = [
  ["thead, tbody, tfoot", "rowgroup"],
  ["tr", "row"],
  ["thead th", "columnheader"],
  ["tbody th", "rowheader"],
  ["td", "cell"],
];

/** L'intitulé visible d'un en-tête de colonne ; vide s'il n'est destiné
 *  qu'aux lecteurs d'écran. */
function intituleVisible(enTete: Element): string {
  const copie = enTete.cloneNode(true) as Element;
  copie.querySelectorAll(".visuellement-cache").forEach((cache) => cache.remove());
  return (copie.textContent ?? "").replace(/\s+/g, " ").trim();
}

function etiqueter(tableau: HTMLTableElement): void {
  if (tableau.getAttribute("role") !== "table") tableau.setAttribute("role", "table");
  for (const [selecteur, role] of ROLES) {
    tableau.querySelectorAll(selecteur).forEach((element) => {
      // Un tableau imbriqué dans une cellule a ses propres lignes : il sera
      // traité à son tour, avec SES en-têtes.
      if (element.closest("table") !== tableau) return;
      if (element.getAttribute("role") !== role) element.setAttribute("role", role);
    });
  }

  // `Array.from` et non un étalement : il accepte une liste de nœuds sans
  // exiger qu'elle soit itérable, quelle que soit la bibliothèque DOM visée.
  const enTetes = Array.from(tableau.querySelectorAll("thead tr:last-child > th")).filter(
    (enTete) => enTete.closest("table") === tableau,
  );
  const intitules = enTetes.map(intituleVisible);

  tableau.querySelectorAll("tbody > tr").forEach((ligne) => {
    if (ligne.closest("table") !== tableau) return;
    let colonne = 0;
    for (const cellule of Array.from(ligne.children)) {
      const etendue = Number(cellule.getAttribute("colspan") ?? "1") || 1;
      if (cellule instanceof HTMLTableCellElement && cellule.tagName === "TD") {
        const voulu = etendue > 1 ? "" : (intitules[colonne] ?? "");
        // `data-libelle-auto` marque ce que CETTE fonction a écrit : un
        // libellé sans cette marque vient de l'écran, et on n'y touche pas.
        const ecritParLEcran =
          cellule.hasAttribute("data-libelle") && !cellule.hasAttribute("data-libelle-auto");
        if (!ecritParLEcran && cellule.getAttribute("data-libelle") !== voulu) {
          cellule.setAttribute("data-libelle", voulu);
          cellule.setAttribute("data-libelle-auto", "");
        }
      }
      colonne += etendue;
    }
  });
}

/** Un cadre qui déborde se parcourt au clavier, et se nomme. */
function rendreDefilable(cadre: HTMLElement): void {
  const deborde =
    cadre.scrollWidth > cadre.clientWidth + 1 || cadre.scrollHeight > cadre.clientHeight + 1;
  if (deborde) {
    // Un `tabindex` déjà posé par l'écran est respecté.
    if (cadre.hasAttribute("tabindex") && cadre.dataset.defilable !== "auto") return;
    cadre.dataset.defilable = "auto";
    cadre.setAttribute("tabindex", "0");
    if (!cadre.hasAttribute("role")) cadre.setAttribute("role", "region");
    if (!cadre.hasAttribute("aria-label") && !cadre.hasAttribute("aria-labelledby")) {
      const titre = cadre.closest(".carte")?.querySelector(".carte-titre")?.textContent?.trim();
      cadre.setAttribute("aria-label", titre ? `Tableau : ${titre}` : "Tableau de données");
    }
  } else if (cadre.dataset.defilable === "auto") {
    // Il ne déborde plus (fenêtre élargie, filtre) : un arrêt de tabulation
    // sur une zone qui ne défile pas ne sert à rien.
    cadre.removeAttribute("tabindex");
    delete cadre.dataset.defilable;
  }
}

/** Étiquette tous les tableaux `.tableau` sous `racine`, maintenant. */
export function etiqueterLesTableaux(racine: ParentNode): void {
  racine.querySelectorAll<HTMLTableElement>("table.tableau").forEach(etiqueter);
  racine.querySelectorAll<HTMLElement>(".tableau-defile").forEach(rendreDefilable);
}

/** Étiquette les tableaux de `racine`, et recommence chaque fois que son
 *  contenu change (une liste qui arrive, un filtre, une ligne dépliée). Rend
 *  la fonction qui arrête la surveillance.
 *
 *  Seuls les AJOUTS et RETRAITS de nœuds sont observés, pas les attributs :
 *  les attributs que cette fonction écrit ne la réveillent donc pas, et elle
 *  ne peut pas tourner en boucle. Les rafales (une liste de cinquante lignes
 *  montée d'un coup) sont regroupées en un seul passage par image. */
export function surveillerLesTableaux(racine: HTMLElement): () => void {
  etiqueterLesTableaux(racine);
  if (typeof MutationObserver !== "function") return () => undefined;

  let prevu: number | null = null;
  const planifier =
    typeof window.requestAnimationFrame === "function"
      ? (rappel: () => void) => window.requestAnimationFrame(rappel)
      : (rappel: () => void) => window.setTimeout(rappel, 16);
  const annuler =
    typeof window.cancelAnimationFrame === "function"
      ? (numero: number) => window.cancelAnimationFrame(numero)
      : (numero: number) => window.clearTimeout(numero);

  const passer = () => {
    if (prevu !== null) return;
    prevu = planifier(() => {
      prevu = null;
      etiqueterLesTableaux(racine);
    });
  };

  const observateur = new MutationObserver(passer);
  observateur.observe(racine, { childList: true, subtree: true });
  window.addEventListener("resize", passer);

  return () => {
    observateur.disconnect();
    window.removeEventListener("resize", passer);
    if (prevu !== null) annuler(prevu);
  };
}
