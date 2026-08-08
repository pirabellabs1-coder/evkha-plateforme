/** Ce qui fabrique chaque livrable, en lecture seule.
 *
 * Cette configuration vivait dans le code, illisible pour qui ne l'écrit pas :
 * le plan de chapitres, le référentiel de données à collecter, la charte
 * envoyée au modèle. La plupart des questions portent sur ce que le système
 * fait vraiment — cet écran y répond sans qu'il faille ouvrir un fichier.
 *
 * **Aucun bouton pour modifier, et aucun pour ajouter.** Un livrable n'est pas
 * une donnée : c'est un assemblage de code — un plan, un référentiel, des axes
 * de recherche, des contrôles qui se répondent. La raison est DITE à l'écran
 * plutôt que laissée à deviner devant l'absence de bouton : quelqu'un qui
 * cherche « Modifier » sans le trouver conclut que l'écran est incomplet.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi } from "../api";
import * as f from "../../espace/format";
import { Bandeau, Carte, Chiffre, Squelette } from "../../espace/composants/Interface";

/** Les volets d'un livrable. Le plan d'abord : c'est ce qu'on vient voir. */
const VOLETS = [
  { cle: "chapitres", libelle: "Plan de chapitres" },
  { cle: "socle", libelle: "Données collectées" },
  { cle: "charte", libelle: "Charte du modèle" },
] as const;

export function LivrablesAdmin() {
  const [choisi, setChoisi] = useState<string>("");
  const [volet, setVolet] = useState<string>("chapitres");

  const { data, isPending } = useQuery({
    queryKey: ["admin", "livrables"],
    queryFn: adminApi.livrables,
  });

  if (isPending) return <Squelette lignes={5} />;

  const livrables = data?.livrables ?? [];
  const actif = livrables.find((l) => l.type === choisi) ?? livrables[0];

  return (
    <>
      <div className="grille-chiffres">
        <Chiffre
          libelle="Livrables au catalogue"
          valeur={f.nombre(livrables.length)}
          detail="Tous servis par le moteur structuré"
          accent
        />
        <Chiffre
          libelle="Figures par document"
          valeur={`${data?.figures.plancher ?? 0} à ${data?.figures.plafond ?? 0}`}
          detail={`${data?.figures.demandees_au_modele ?? 0} demandées au modèle, ${data?.figures.formes_minimum ?? 0} formes minimum`}
        />
        <Chiffre
          libelle="Données du socle"
          valeur={f.nombre(
            livrables.reduce((total, l) => total + l.socle.length, 0),
          )}
          detail="Vérifiées avant d'entrer dans un document"
        />
      </div>

      {data?.modifiable === false && (
        <Bandeau titre="Pourquoi rien n'est modifiable ici">
          {data.pourquoi} Un livrable change dans le dépôt, avec ses tests.
        </Bandeau>
      )}

      <div className="admin-periodes" role="group" aria-label="Livrable">
        {livrables.map((livrable) => (
          <button
            key={livrable.type}
            type="button"
            className={
              livrable.type === actif?.type
                ? "bouton bouton-sm"
                : "bouton bouton-contour bouton-sm"
            }
            aria-pressed={livrable.type === actif?.type}
            onClick={() => setChoisi(livrable.type)}
          >
            {livrable.libelle}
          </button>
        ))}
      </div>

      {actif && (
        <Carte titre={actif.libelle} note={actif.description}>
          <div className="admin-periodes" role="group" aria-label="Volet">
            {VOLETS.map((v) => (
              <button
                key={v.cle}
                type="button"
                className={
                  v.cle === volet
                    ? "bouton bouton-sm"
                    : "bouton bouton-contour bouton-sm"
                }
                aria-pressed={v.cle === volet}
                onClick={() => setVolet(v.cle)}
              >
                {v.libelle}
              </button>
            ))}
          </div>

          {volet === "chapitres" && (
            <div className="tableau-cadre tableau-defile">
              <table className="tableau">
                <thead>
                  <tr>
                    <th>N°</th>
                    <th>Chapitre</th>
                    <th>Mots au plus</th>
                  </tr>
                </thead>
                <tbody>
                  {actif.chapitres.map((chapitre) => (
                    <tr key={chapitre.numero}>
                      <td>{chapitre.numero}</td>
                      <td>{chapitre.titre}</td>
                      <td>{chapitre.mots_max || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {volet === "socle" && (
            <div className="tableau-cadre tableau-defile">
              <table className="tableau">
                <thead>
                  <tr>
                    <th>Identifiant</th>
                    <th>Ce que c'est</th>
                    <th>Périmètre</th>
                    <th>Unité</th>
                    <th>Obligatoire</th>
                    <th>Chapitres</th>
                  </tr>
                </thead>
                <tbody>
                  {actif.socle.map((donnee) => (
                    <tr key={donnee.identifiant}>
                      <td>
                        <code>{donnee.identifiant}</code>
                      </td>
                      <td>
                        {donnee.libelle}
                        {donnee.commentaire && (
                          <div className="carte-note">{donnee.commentaire}</div>
                        )}
                      </td>
                      <td>{donnee.perimetre}</td>
                      <td>{donnee.unite}</td>
                      <td>
                        {donnee.obligatoire ? (
                          <span className="pastille pastille-alerte">
                            Sans elle, refus
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        {donnee.chapitres.length
                          ? donnee.chapitres.join(", ")
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {volet === "charte" && (
            <>
              <p className="carte-note">
                Le texte exact reçu par le modèle avant chaque chapitre —{" "}
                {f.nombre(actif.charte.length)} signes. Il n'est pas résumé
                ici&nbsp;: c'est lui qui explique ce que le document devient, et
                le résumer trahirait.
              </p>
              <pre className="charte-modele">{actif.charte}</pre>
            </>
          )}
        </Carte>
      )}
    </>
  );
}
