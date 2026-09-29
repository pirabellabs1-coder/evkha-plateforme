/** Rapport interne de qualité : ce que la production a trouvé et corrigé.
 *
 * 29/09/2026 : le client ne voit qu'une progression fluide et un document
 * propre. Ce qui a été repris en route se lit ICI, pour corriger les causes à
 * la source : quels chapitres et quels prompts de rédacteur produisent le plus
 * de reprises, combien de replis de dernier recours, quels constats sur le
 * PDF final. Lecture seule.
 */
import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api";
import * as f from "../../espace/format";
import { Carte, Chiffre, Squelette, Vide } from "../../espace/composants/Interface";

const TYPES: Record<string, string> = {
  market_study: "Étude de marché",
  competitor_study: "Étude de la concurrence",
  business_plan: "Business plan",
  business_strategy: "Stratégie",
};

export function QualiteAdmin() {
  const { data, isPending } = useQuery({
    queryKey: ["admin", "qualite"],
    queryFn: adminApi.qualite,
  });

  if (isPending) return <Squelette lignes={6} />;
  const dossiers = data?.dossiers ?? [];
  if (dossiers.length === 0) {
    return (
      <Vide
        icone="◇"
        titre="Aucune étude contrôlée pour l'instant"
        texte="Le rapport se remplit avec les études produites avec la mémoire de l'étude, ou relues après rendu."
      />
    );
  }

  const motifs = dossiers.reduce((total, d) => total + d.motifs, 0);
  const replis = dossiers.reduce((total, d) => total + d.replis, 0);
  const constats = dossiers.reduce((total, d) => total + d.constats_pdf, 0);

  return (
    <>
      <div className="grille-chiffres">
        <Chiffre libelle="Études contrôlées" valeur={f.nombre(dossiers.length)} accent />
        <Chiffre libelle="Reprises demandées" valeur={f.nombre(motifs)} detail="Motifs de la mémoire" />
        <Chiffre libelle="Replis de dernier recours" valeur={f.nombre(replis)} detail="Chapitres validés au dernier essai" />
        <Chiffre libelle="Constats sur le PDF" valeur={f.nombre(constats)} detail="Relecture après rendu" />
      </div>

      <Carte titre="Chapitres qui demandent le plus de reprises" note="Le prompt du rédacteur est la première piste.">
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Étude</th>
                <th scope="col">Chapitre</th>
                <th scope="col">Passages</th>
                <th scope="col">Reprises</th>
                <th scope="col">Replis</th>
              </tr>
            </thead>
            <tbody>
              {(data?.chapitres ?? []).map((c) => (
                <tr key={`${c.type}-${c.chapitre}`}>
                  <td>{TYPES[c.type] ?? c.type}</td>
                  <td>
                    {c.chapitre} — {c.titre}
                  </td>
                  <td className="nombre">{f.nombre(c.passages)}</td>
                  <td className="nombre">{f.nombre(c.motifs)}</td>
                  <td className="nombre">{f.nombre(c.replis)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Carte>

      <Carte titre="Genres de reprises" note="Ce que le contrôle de chaque chapitre a trouvé.">
        <div className="tableau-cadre">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Motif</th>
                <th scope="col">Occurrences</th>
              </tr>
            </thead>
            <tbody>
              {(data?.familles_de_motifs ?? []).map((m) => (
                <tr key={m.famille}>
                  <td>{m.famille}</td>
                  <td className="nombre">{f.nombre(m.occurrences)}</td>
                </tr>
              ))}
              {(data?.constats_pdf ?? []).map((c) => (
                <tr key={`pdf-${c.controle}`}>
                  <td>PDF — {c.controle}</td>
                  <td className="nombre">{f.nombre(c.occurrences)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Carte>

      <Carte titre="Études" note="Les plus récentes d'abord.">
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Étude</th>
                <th scope="col">Créée le</th>
                <th scope="col">Chapitres contrôlés</th>
                <th scope="col">Reprises</th>
                <th scope="col">Replis</th>
                <th scope="col">Constats PDF</th>
                <th scope="col">Coût</th>
              </tr>
            </thead>
            <tbody>
              {dossiers.map((d) => (
                <tr key={d.id}>
                  <td>
                    {TYPES[d.type] ?? d.type}
                    <div className="carte-note">{d.id.slice(0, 8)}</div>
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>{f.date(d.cree_le)}</td>
                  <td className="nombre">{f.nombre(d.chapitres_controles)}</td>
                  <td className="nombre">{f.nombre(d.motifs)}</td>
                  <td className="nombre">{f.nombre(d.replis)}</td>
                  <td className="nombre">{f.nombre(d.constats_pdf)}</td>
                  <td className="nombre">{d.cout_eur} €</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Carte>
    </>
  );
}
