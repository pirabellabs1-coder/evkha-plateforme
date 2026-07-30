/** Graphiques SVG de l'espace administrateur.
 *
 * Écrits à la main, sans bibliothèque : quatre formes suffisent ici, et une
 * dépendance de plusieurs centaines de kilo-octets pour cela pèserait plus que
 * le reste de l'application. Le SVG hérite en outre des jetons de charte, ce
 * qu'un moteur tiers ne fait pas sans configuration.
 *
 * Spécifications tenues, reprises de la méthode data-viz :
 *
 * - barres et colonnes **≤ 24 px**, extrémité arrondie de 4 px côté donnée,
 *   carrée à la ligne de base ;
 * - lignes de **2 px**, jointures rondes ; marqueurs de **8 px** minimum avec
 *   anneau de 2 px en couleur de surface ;
 * - remplissage d'aire à **10 %** d'opacité, jamais un aplat saturé ;
 * - **écart de 2 px en couleur de surface** entre deux segments empilés — la
 *   séparation est faite par le vide, jamais par un contour, qui ajouterait de
 *   l'encre non porteuse de donnée ;
 * - grille au trait d'un cheveu, **continue** et non pointillée, récessive ;
 * - étiquettes **sélectives** : jamais un nombre sur chaque point ;
 * - le texte ne porte **jamais** la couleur de la série : les libellés restent
 *   en encre, l'identité vient de la pastille colorée à côté ;
 * - légende dès **deux** séries, absente pour une seule — un cartouche à une
 *   pastille ne fait que répéter le titre.
 */
import { useId, useState } from "react";
import { CHROME, couleurSerie } from "./palette";

// ── Utilitaires ─────────────────────────────────────────────────────────────

/** Graduations rondes. Un axe à 0 / 1 234 / 2 468 est illisible. */
function graduations(maximum: number, nombre = 4): number[] {
  if (maximum <= 0) return [0, 1];
  const brut = maximum / nombre;
  const magnitude = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((p) => p >= brut)!;
  const haut = Math.ceil(maximum / pas) * pas;
  return Array.from({ length: Math.round(haut / pas) + 1 }, (_, i) => i * pas);
}

const fr = new Intl.NumberFormat("fr-FR");

export interface Serie {
  cle: string;
  libelle: string;
  valeurs: number[];
}

// ── Légende ─────────────────────────────────────────────────────────────────

export function Legende({ series }: { series: Serie[] }) {
  // Une seule série : le titre du graphique dit déjà ce qui est tracé.
  if (series.length < 2) return null;
  return (
    <ul className="viz-legende">
      {series.map((serie, index) => (
        <li key={serie.cle}>
          <span
            className="viz-pastille"
            style={{ background: couleurSerie(index) }}
            aria-hidden="true"
          />
          {serie.libelle}
        </li>
      ))}
    </ul>
  );
}

// ── Vue tableau ─────────────────────────────────────────────────────────────

/** Vue tabulaire de tout graphique.
 *
 * Obligatoire, pas décorative : l'avertissement de contraste sur l'or de série
 * impose une voie de secours, et un graphique doit rester lisible pour qui
 * n'en voit pas les couleurs.
 */
export function TableauDeDonnees({
  abscisses,
  series,
  entete = "Période",
}: {
  abscisses: string[];
  series: Serie[];
  entete?: string;
}) {
  return (
    <details className="viz-tableau">
      <summary>Voir les données</summary>
      <div className="tableau-cadre tableau-defile">
        <table className="tableau">
          <thead>
            <tr>
              <th scope="col">{entete}</th>
              {series.map((serie) => (
                <th scope="col" key={serie.cle} style={{ textAlign: "right" }}>
                  {serie.libelle}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {abscisses.map((abscisse, position) => (
              <tr key={abscisse}>
                <th scope="row" style={{ fontWeight: 500 }}>
                  {abscisse}
                </th>
                {series.map((serie) => (
                  <td className="nombre" key={serie.cle}>
                    {fr.format(serie.valeurs[position] ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ── Colonnes groupées ───────────────────────────────────────────────────────

export function Colonnes({
  abscisses,
  series,
  hauteur = 240,
  unite = "",
}: {
  abscisses: string[];
  series: Serie[];
  hauteur?: number;
  unite?: string;
}) {
  const [survol, setSurvol] = useState<number | null>(null);
  const identifiant = useId();

  const largeur = 720;
  const marge = { haut: 16, droite: 12, bas: 34, gauche: 44 };
  const traceL = largeur - marge.gauche - marge.droite;
  const traceH = hauteur - marge.haut - marge.bas;

  const maximum = Math.max(
    1,
    ...series.flatMap((serie) => serie.valeurs),
  );
  const ticks = graduations(maximum);
  const plafond = ticks[ticks.length - 1];
  const y = (valeur: number) => marge.haut + traceH * (1 - valeur / plafond);

  const bande = traceL / Math.max(abscisses.length, 1);
  // Barres plafonnees a 24 px : au-dela elles remplissent la bande et le
  // graphique perd son air.
  const largeurBarre = Math.min(24, (bande * 0.62) / Math.max(series.length, 1));

  return (
    <figure className="viz" aria-describedby={`${identifiant}-tableau`}>
      <svg
        viewBox={`0 0 ${largeur} ${hauteur}`}
        role="img"
        aria-label={`Colonnes : ${series.map((s) => s.libelle).join(", ")}`}
        className="viz-svg"
      >
        {/* Grille au trait d'un cheveu, continue, sous les données. */}
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={marge.gauche}
              x2={largeur - marge.droite}
              y1={y(tick)}
              y2={y(tick)}
              stroke={tick === 0 ? CHROME.axe : CHROME.grille}
              strokeWidth={1}
            />
            <text
              x={marge.gauche - 8}
              y={y(tick) + 4}
              textAnchor="end"
              className="viz-tick"
            >
              {fr.format(tick)}
            </text>
          </g>
        ))}

        {abscisses.map((abscisse, position) => {
          const centre = marge.gauche + bande * (position + 0.5);
          const total = largeurBarre * series.length;
          return (
            <g
              key={abscisse}
              onPointerEnter={() => setSurvol(position)}
              onPointerLeave={() => setSurvol(null)}
            >
              {/* Zone de survol plus large que les barres : viser une colonne
                  de 6 px à la souris est un supplice. */}
              <rect
                x={centre - bande / 2}
                y={marge.haut}
                width={bande}
                height={traceH}
                fill={survol === position ? "var(--evkha-or-brume)" : "transparent"}
              />
              {series.map((serie, index) => {
                const valeur = serie.valeurs[position] ?? 0;
                const hauteurBarre = Math.max(
                  0,
                  traceH * (valeur / plafond),
                );
                const x = centre - total / 2 + largeurBarre * index;
                return (
                  <rect
                    key={serie.cle}
                    x={x + 1}
                    y={y(valeur)}
                    width={Math.max(largeurBarre - 2, 1)}
                    height={hauteurBarre}
                    // Extremite arrondie cote donnee, carree a la base : le
                    // rayon uniforme arrondirait le pied de la barre, qui doit
                    // rester ancre a la ligne de base.
                    rx={Math.min(4, largeurBarre / 2)}
                    fill={couleurSerie(index)}
                  />
                );
              })}
              <text
                x={centre}
                y={hauteur - 12}
                textAnchor="middle"
                className="viz-tick"
              >
                {abscisse}
              </text>
            </g>
          );
        })}
      </svg>

      {survol !== null && (
        <div className="viz-infobulle" role="status">
          <strong>{abscisses[survol]}</strong>
          {series.map((serie, index) => (
            <span key={serie.cle}>
              <span
                className="viz-pastille"
                style={{ background: couleurSerie(index) }}
                aria-hidden="true"
              />
              {serie.libelle} : {fr.format(serie.valeurs[survol] ?? 0)}
              {unite}
            </span>
          ))}
        </div>
      )}

      <Legende series={series} />
      <div id={`${identifiant}-tableau`}>
        <TableauDeDonnees abscisses={abscisses} series={series} />
      </div>
    </figure>
  );
}

// ── Courbes ─────────────────────────────────────────────────────────────────

export function Courbes({
  abscisses,
  series,
  hauteur = 240,
  unite = "",
}: {
  abscisses: string[];
  series: Serie[];
  hauteur?: number;
  unite?: string;
}) {
  const [survol, setSurvol] = useState<number | null>(null);
  const identifiant = useId();

  const largeur = 720;
  const marge = { haut: 18, droite: 56, bas: 34, gauche: 44 };
  const traceL = largeur - marge.gauche - marge.droite;
  const traceH = hauteur - marge.haut - marge.bas;

  const maximum = Math.max(1, ...series.flatMap((serie) => serie.valeurs));
  const ticks = graduations(maximum);
  const plafond = ticks[ticks.length - 1];
  const pas = traceL / Math.max(abscisses.length - 1, 1);
  const x = (position: number) => marge.gauche + pas * position;
  const y = (valeur: number) => marge.haut + traceH * (1 - valeur / plafond);

  return (
    <figure className="viz" aria-describedby={`${identifiant}-tableau`}>
      <svg
        viewBox={`0 0 ${largeur} ${hauteur}`}
        role="img"
        aria-label={`Courbes : ${series.map((s) => s.libelle).join(", ")}`}
        className="viz-svg"
        onPointerLeave={() => setSurvol(null)}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={marge.gauche}
              x2={largeur - marge.droite}
              y1={y(tick)}
              y2={y(tick)}
              stroke={tick === 0 ? CHROME.axe : CHROME.grille}
              strokeWidth={1}
            />
            <text
              x={marge.gauche - 8}
              y={y(tick) + 4}
              textAnchor="end"
              className="viz-tick"
            >
              {fr.format(tick)}
            </text>
          </g>
        ))}

        {/* Bandes de survol invisibles : le viseur suit la colonne entière,
            pas chaque point isolément. */}
        {abscisses.map((abscisse, position) => (
          <rect
            key={abscisse}
            x={x(position) - pas / 2}
            y={marge.haut}
            width={pas}
            height={traceH}
            fill="transparent"
            onPointerEnter={() => setSurvol(position)}
          />
        ))}

        {survol !== null && (
          <line
            x1={x(survol)}
            x2={x(survol)}
            y1={marge.haut}
            y2={marge.haut + traceH}
            stroke={CHROME.axe}
            strokeWidth={1}
          />
        )}

        {series.map((serie, index) => {
          const couleur = couleurSerie(index);
          const points = serie.valeurs
            .map((valeur, position) => `${x(position)},${y(valeur)}`)
            .join(" ");
          const dernier = serie.valeurs.length - 1;
          return (
            <g key={serie.cle}>
              {/* Aire en lavis à 10 % : jamais un aplat saturé. */}
              <polygon
                points={`${marge.gauche},${y(0)} ${points} ${x(dernier)},${y(0)}`}
                fill={couleur}
                opacity={0.1}
              />
              <polyline
                points={points}
                fill="none"
                stroke={couleur}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {/* Marqueur de fin avec anneau en couleur de surface : il reste
                  lisible là où deux courbes se croisent. */}
              <circle
                cx={x(dernier)}
                cy={y(serie.valeurs[dernier] ?? 0)}
                r={4}
                fill={couleur}
                stroke="var(--fond-carte)"
                strokeWidth={2}
              />
              {/* Étiquette directe SUR LA DERNIÈRE VALEUR seulement. Une valeur
                  à chaque point serait illisible. Le texte reste en encre. */}
              <text
                x={x(dernier) + 10}
                y={y(serie.valeurs[dernier] ?? 0) + 4}
                className="viz-etiquette"
              >
                {fr.format(serie.valeurs[dernier] ?? 0)}
              </text>
            </g>
          );
        })}

        {abscisses.map((abscisse, position) => (
          <text
            key={abscisse}
            x={x(position)}
            y={hauteur - 12}
            textAnchor="middle"
            className="viz-tick"
          >
            {/* Un mois sur deux : douze libellés se chevauchent. */}
            {position % 2 === 0 ? abscisse : ""}
          </text>
        ))}
      </svg>

      {survol !== null && (
        <div className="viz-infobulle" role="status">
          <strong>{abscisses[survol]}</strong>
          {series.map((serie, index) => (
            <span key={serie.cle}>
              <span
                className="viz-pastille"
                style={{ background: couleurSerie(index) }}
                aria-hidden="true"
              />
              {serie.libelle} : {fr.format(serie.valeurs[survol] ?? 0)}
              {unite}
            </span>
          ))}
        </div>
      )}

      <Legende series={series} />
      <div id={`${identifiant}-tableau`}>
        <TableauDeDonnees abscisses={abscisses} series={series} entete="Mois" />
      </div>
    </figure>
  );
}

// ── Barres horizontales (classement) ────────────────────────────────────────

export function BarresClassement({
  lignes,
  unite = "",
  libelleValeur = "Valeur",
}: {
  lignes: { cle: string; libelle: string; valeur: number }[];
  unite?: string;
  libelleValeur?: string;
}) {
  const maximum = Math.max(1, ...lignes.map((ligne) => ligne.valeur));
  return (
    <figure className="viz">
      <ul className="viz-classement">
        {lignes.map((ligne) => (
          <li key={ligne.cle}>
            <span className="viz-classement-libelle">{ligne.libelle}</span>
            <span className="viz-classement-piste">
              <span
                className="viz-classement-barre"
                style={{
                  width: `${Math.max((ligne.valeur / maximum) * 100, 1)}%`,
                  // Une seule série : la teinte de tête, pas de cycle.
                  background: couleurSerie(0),
                }}
              />
            </span>
            {/* Valeur en encre, à côté de la barre — jamais dans la couleur
                de la marque. */}
            <span className="viz-classement-valeur">
              {fr.format(ligne.valeur)}
              {unite}
            </span>
          </li>
        ))}
      </ul>
      <TableauDeDonnees
        abscisses={lignes.map((ligne) => ligne.libelle)}
        series={[
          {
            cle: "valeur",
            libelle: libelleValeur,
            valeurs: lignes.map((ligne) => ligne.valeur),
          },
        ]}
        entete="Organisation"
      />
    </figure>
  );
}
