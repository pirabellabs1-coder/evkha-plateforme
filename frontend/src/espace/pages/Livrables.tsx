/** Bibliothèque des livrables (§9.5). */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { espaceApi } from "../api";
import * as f from "../format";
import { Carte, Pastille, Squelette, Vide } from "../composants/Interface";

export function Livrables() {
  const [filtre, setFiltre] = useState("");
  const { data, isPending } = useQuery({
    queryKey: ["espace", "livrables"],
    queryFn: espaceApi.livrables,
  });

  // `data?.livrables ?? []` cree un nouveau tableau a chaque rendu : la
  // dependance de useMemo changerait sans arret. On memorise la liste elle-meme.
  const livrables = useMemo(() => data?.livrables ?? [], [data]);
  const types = useMemo(
    () => [...new Set(livrables.map((l) => l.type))],
    [livrables],
  );
  const affiches = filtre
    ? livrables.filter((l) => l.type === filtre)
    : livrables;

  return (
    <Carte
      titre={`${livrables.length} document${livrables.length > 1 ? "s" : ""}`}
      note="Téléchargeables sans limite de nombre, en Word et en PDF."
      action={
        types.length > 1 ? (
          <label className="champ" style={{ minWidth: 220 }}>
            <span className="visuellement-cache">Filtrer par type</span>
            <select
              className="champ-saisie"
              value={filtre}
              onChange={(evenement) => setFiltre(evenement.target.value)}
            >
              <option value="">Tous les types</option>
              {types.map((type) => (
                <option key={type} value={type}>
                  {f.typeLivrable(type)}
                </option>
              ))}
            </select>
          </label>
        ) : undefined
      }
    >
      {isPending ? (
        <Squelette lignes={5} />
      ) : affiches.length === 0 ? (
        <Vide
          icone="▤"
          titre={filtre ? "Aucun document de ce type" : "Aucun document"}
          texte={
            filtre
              ? "Essayez un autre filtre."
              : "Vos études apparaîtront ici dès la première commande lancée."
          }
        />
      ) : (
        <div className="tableau-cadre tableau-defile">
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">Statut</th>
                <th scope="col">Chapitres</th>
                <th scope="col">Créé le</th>
                <th scope="col">Terminé le</th>
                <th scope="col">Fichiers</th>
              </tr>
            </thead>
            <tbody>
              {affiches.map((livrable) => (
                <tr key={livrable.id}>
                  <td>
                    <Link
                      to="/espace/livrables/$jobId"
                      params={{ jobId: livrable.id }}
                      style={{ fontWeight: 600, color: "var(--texte-fort)" }}
                    >
                      {f.typeLivrable(livrable.type)}
                    </Link>
                    <div className="carte-note">{livrable.offre}</div>
                  </td>
                  <td>
                    <Pastille statut={livrable.statut} />
                  </td>
                  <td className="nombre">{f.nombre(livrable.chapitres_faits)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {f.date(livrable.cree_le)}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {f.date(livrable.termine_le)}
                  </td>
                  <td>
                    {livrable.fichiers.length === 0 ? (
                      <span className="carte-note">En préparation</span>
                    ) : (
                      <span style={{ display: "flex", gap: "var(--e-2)" }}>
                        {livrable.fichiers.map((fichier) => (
                          <a
                            key={fichier.kind}
                            className="bouton bouton-contour bouton-sm"
                            href={fichier.url}
                          >
                            {fichier.kind.toUpperCase()}
                          </a>
                        ))}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Carte>
  );
}
