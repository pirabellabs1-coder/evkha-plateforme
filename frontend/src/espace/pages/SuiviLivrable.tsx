/** Suivi d'une génération (§9.4).
 *
 * Le client lance une étude qui dure trente à quarante minutes. Sans cet écran,
 * il ne voit rien pendant tout ce temps — et c'est le manque le plus visible de
 * l'espace.
 *
 * Deux partis pris :
 *
 * - la progression est **comptée** sur les chapitres terminés, jamais simulée.
 *   Une barre qui avance toute seule se trahit au moment où elle atteint 99 %
 *   et s'arrête ;
 * - le rafraîchissement ne tourne **que pendant la production**. Interroger le
 *   serveur toutes les dix secondes sur une étude terminée est du bruit.
 */
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { espaceApi, type EtapeSuivi } from "../api";
import * as f from "../format";
import { Bandeau, Carte, Squelette } from "../composants/Interface";

const SYMBOLE: Record<EtapeSuivi["etat"], string> = {
  fait: "✓",
  en_cours: "•",
  attente: "",
  echec: "!",
};

function Etape({ etape }: { etape: EtapeSuivi }) {
  return (
    <li className={`etape etape-${etape.etat}`}>
      {/* Un symbole en plus de la couleur : la distinction reste lisible en
          noir et blanc comme pour un daltonien. */}
      <span className="etape-puce" aria-hidden="true">
        {SYMBOLE[etape.etat]}
      </span>
      <div>
        <p className="etape-libelle">{etape.libelle}</p>
        {etape.detail && <p className="etape-detail">{etape.detail}</p>}
      </div>
      <span className="visuellement-cache">
        {etape.etat === "fait"
          ? " : terminé"
          : etape.etat === "en_cours"
            ? " : en cours"
            : etape.etat === "echec"
              ? " : interrompu"
              : " : à venir"}
      </span>
    </li>
  );
}

export function SuiviLivrable() {
  const { jobId } = useParams({ from: "/espace/livrables/$jobId" });

  const { data, isPending } = useQuery({
    queryKey: ["espace", "suivi", jobId],
    queryFn: () => espaceApi.suivi(jobId),
    // Rafraîchissement uniquement tant que l'étude est en production.
    refetchInterval: (requete) =>
      requete.state.data?.en_production ? 10_000 : false,
  });

  if (isPending) return <Squelette lignes={5} />;
  if (!data) return <Bandeau ton="echec">Étude introuvable.</Bandeau>;

  const echec = data.statut === "failed" || data.statut === "intervention_requise";

  return (
    <>
      <Carte
        titre={f.typeLivrable(data.type)}
        note={`Commandée le ${f.dateHeure(data.cree_le)}`}
        action={
          <Link to="/espace/livrables" className="bouton bouton-contour bouton-sm">
            Tous mes livrables
          </Link>
        }
      >
        {/* Le message vient du serveur : il est écrit pour le client, sans
            terme technique. Le détail d'erreur reste côté administration. */}
        {echec ? (
          <Bandeau ton="echec" titre="Production interrompue">
            {data.message}
          </Bandeau>
        ) : (
          <p style={{ margin: "0 0 var(--e-5)" }}>{data.message}</p>
        )}

        {data.statut !== "done" && (
          <>
            <div
              className="jauge"
              role="progressbar"
              aria-valuenow={data.progression}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Avancement de la production"
            >
              <span
                className="jauge-remplissage"
                style={{ width: `${data.progression}%` }}
              />
            </div>
            <p className="carte-note" style={{ marginTop: "var(--e-2)" }}>
              {data.progression} % ·{" "}
              {data.duree_estimee_minutes
                ? `durée habituelle : ${data.duree_estimee_minutes[0]} à ${data.duree_estimee_minutes[1]} minutes`
                : "durée inconnue"}
            </p>
          </>
        )}
      </Carte>

      <Carte titre="Où en est votre étude">
        <ol className="etapes">
          {data.etapes.map((etape) => (
            <Etape key={etape.cle} etape={etape} />
          ))}
        </ol>
      </Carte>

      {data.fichiers.length > 0 && (
        <Carte titre="Votre document" note="Word et PDF, sans limite de téléchargement.">
          <div style={{ display: "flex", gap: "var(--e-3)", flexWrap: "wrap" }}>
            {data.fichiers.map((fichier) => (
              <a
                key={fichier.kind}
                className="bouton bouton-principal"
                href={fichier.url}
              >
                Télécharger le {fichier.kind.toUpperCase()}
              </a>
            ))}
          </div>
        </Carte>
      )}

      {data.statut === "done" && data.fichiers.length === 0 && (
        <Bandeau titre="Mise en forme en cours">
          Votre étude est rédigée. Les fichiers Word et PDF apparaîtront ici
          d'ici quelques minutes.
        </Bandeau>
      )}
    </>
  );
}
