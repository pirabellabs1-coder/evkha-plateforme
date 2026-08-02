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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  const client = useQueryClient();

  const { data, isPending } = useQuery({
    queryKey: ["espace", "suivi", jobId],
    queryFn: () => espaceApi.suivi(jobId),
    // Rafraîchissement uniquement tant que l'étude est en production.
    refetchInterval: (requete) =>
      requete.state.data?.en_production ? 10_000 : false,
  });

  const abandon = useMutation({
    mutationFn: () => espaceApi.abandonnerLivrable(jobId),
    onSuccess: () => {
      // Le solde et la liste changent tous les deux : les rafraîchir ensemble
      // évite d'afficher un crédit rendu à côté d'un solde périmé.
      void client.invalidateQueries({ queryKey: ["espace"] });
    },
  });

  if (isPending) return <Squelette lignes={5} />;
  if (!data) return <Bandeau ton="echec">Étude introuvable.</Bandeau>;

  const echec = data.statut === "failed" || data.statut === "intervention_requise";

  return (
    <>
      {/* Hors de la carte d'échec, et c'est délibéré : dès la restitution
          obtenue, le serveur renvoie le statut « annulée » et le bandeau
          d'échec disparaît. Placée à l'intérieur, la confirmation partait avec
          lui — le client voyait « Cette étude a été annulée » et n'apprenait
          nulle part que son crédit était revenu. Constaté en cliquant, pas en
          relisant le code (règle 7). */}
      {abandon.isSuccess && (
        <Bandeau titre="Votre crédit vous a été restitué">
          Le crédit de cette étude est de nouveau disponible
          {typeof abandon.data?.solde === "number"
            ? ` — vous en avez ${abandon.data.solde} au total.`
            : "."}{" "}
          Vous pouvez commander une nouvelle étude quand vous le souhaitez.
        </Bandeau>
      )}

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
            {/* Le crédit a été débité au lancement. Sans ce bouton, la seule
                issue était d'écrire à EVKHA et d'attendre un geste manuel —
                pour un document qui ne sera jamais livré. */}
            <p style={{ marginTop: "var(--e-3)" }}>
              Vous pouvez renoncer à cette étude : son crédit vous est rendu
              immédiatement.
            </p>
            <button
              type="button"
              className="bouton bouton-contour bouton-sm"
              style={{ marginTop: "var(--e-2)" }}
              disabled={abandon.isPending}
              onClick={() => abandon.mutate()}
            >
              {abandon.isPending
                ? "Restitution en cours…"
                : "Renoncer et récupérer mon crédit"}
            </button>
            {abandon.isError && (
              <p className="carte-note" style={{ marginTop: "var(--e-2)" }}>
                La restitution n'a pas abouti : {String(abandon.error)}
              </p>
            )}
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
