/** Suivi d'une génération (§9.4).
 *
 * Le client lance une étude qui dure trente à quarante minutes. Sans cet écran,
 * il ne voit rien pendant tout ce temps — et c'est le manque le plus visible de
 * l'espace.
 *
 * Trois partis pris :
 *
 * - la progression est **comptée** sur les chapitres terminés, jamais simulée.
 *   Une barre qui avance toute seule se trahit au moment où elle atteint 99 %
 *   et s'arrête ;
 * - le rafraîchissement ne tourne **que pendant la production**. Interroger le
 *   serveur toutes les dix secondes sur une étude terminée est du bruit ;
 * - **le mouvement non plus**. Une frise qui pulse sur une étude livrée, en
 *   échec ou annulée raconte une production qui n'a plus lieu ; l'animation est
 *   donc conditionnée à `en_production`, et jamais au fait qu'un jalon porte
 *   l'état « en cours » — un échec fige justement l'étape courante.
 *
 * ## Pourquoi une frise et non plus une liste
 *
 * Les quatre étapes s'affichaient l'une sous l'autre, quatre pastilles reliées
 * par un filet gris. On y lisait où en était l'étude, mais rien de ce qu'un
 * client attend d'un écran d'attente : le chemin déjà parcouru, celui qui
 * reste, et le fait que quelque chose est en train de se produire à l'instant
 * même. La frise porte les trois — le segment rempli derrière le jalon courant,
 * les segments vides devant, et un flux qui circule uniquement là où la
 * production travaille.
 *
 * Le mouvement n'apporte **rien** que le texte ne dise déjà : chaque jalon
 * porte son état en toutes lettres (« En cours », « À venir »…). C'est ce qui
 * rend `prefers-reduced-motion` tenable — on retire les animations sans retirer
 * une information.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { espaceApi, type EtapeSuivi, type Suivi } from "../api";
import * as f from "../format";
import { LIBELLE_ETAT, delaiAnnonce, liaison } from "../suivi";
import { Bandeau, Carte, Squelette } from "../composants/Interface";

/** Le médaillon d'un jalon.
 *
 * Dessiné à la main : quatre formes, aucune bibliothèque à charger pour cela.
 * Il ne porte AUCUNE couleur — tout vient des classes, donc des jetons de
 * charte (`theme/espace.css`). Un `fill` écrit ici échapperait au thème et
 * serait le premier endroit oublié le jour d'un changement de palette.
 *
 * Chaque état a sa forme propre, lisible sans la couleur : disque plein et
 * coche pour ce qui est fait, croix pour l'échec, anneau pointillé numéroté
 * pour ce qui attend, arc en rotation pour ce qui travaille.
 */
function Medaille({ etat, rang }: { etat: EtapeSuivi["etat"]; rang: number }) {
  return (
    <svg
      className="frise-medaille"
      viewBox="0 0 44 44"
      aria-hidden="true"
      focusable="false"
    >
      {etat === "attente" && (
        <circle className="frise-anneau" cx="22" cy="22" r="20" />
      )}
      {etat === "en_cours" && (
        <>
          <circle className="frise-piste" cx="22" cy="22" r="20" />
          <circle className="frise-noyau" cx="22" cy="22" r="14" />
          <circle className="frise-arc" cx="22" cy="22" r="20" />
        </>
      )}
      {(etat === "fait" || etat === "echec") && (
        <circle className="frise-disque" cx="22" cy="22" r="21" />
      )}
      {etat === "fait" && (
        <path className="frise-glyphe" d="M14.5 22.6l5.2 5.2 9.8-11.4" />
      )}
      {etat === "echec" && (
        <path className="frise-glyphe" d="M16.5 16.5l11 11m0-11l-11 11" />
      )}
      {(etat === "attente" || etat === "en_cours") && (
        <text className="frise-numero" x="22" y="22">
          {rang}
        </text>
      )}
    </svg>
  );
}

/** Un jalon et le segment qui en part.
 *
 * `liaison` regarde l'étape AMONT : le trait dit ce qu'il est advenu du travail
 * de cette étape-là, pas ce que la suivante promet.
 */
function Jalon({ etape, rang }: { etape: EtapeSuivi; rang: number }) {
  return (
    <li
      className={`frise-etape frise-etape-${etape.etat} frise-liaison-${liaison(
        etape.etat,
      )}`}
    >
      <span className="frise-jalon">
        <Medaille etat={etape.etat} rang={rang} />
      </span>
      <div className="frise-texte">
        <p className="frise-libelle">{etape.libelle}</p>
        <p className="frise-etat">{LIBELLE_ETAT[etape.etat]}</p>
        {/* « 22 chapitres sur 22 » : le seul endroit où le client voit que
            l'étude avance vraiment, pas juste qu'elle est « en cours ». */}
        {etape.detail && <p className="frise-detail">{etape.detail}</p>}
      </div>
    </li>
  );
}

/** La frise complète : avancement chiffré, délai s'il est connu, quatre jalons. */
function Frise({ suivi }: { suivi: Suivi }) {
  const delai = delaiAnnonce(suivi);

  // Le pourcentage n'a de sens ni sur une étude livrée — il vaut 100 et les
  // quatre jalons verts le disent mieux —, ni sur une étude annulée, où le
  // serveur le force à zéro pour signifier « sans objet » et non « rien de
  // fait ». Après un échec, en revanche, il dit jusqu'où on était allé.
  const montrerAvancement =
    suivi.statut !== "done" && suivi.statut !== "cancelled";

  return (
    <div className={suivi.en_production ? "frise frise-active" : "frise"}>
      {(montrerAvancement || delai) && (
        // `aria-live` : ces deux valeurs changent toutes les dix secondes sous
        // les yeux de quelqu'un qui ne les regarde pas. Le reste de la frise
        // n'est pas annoncé — relire quatre étapes à chaque sondage rendrait
        // l'écran inutilisable au lecteur d'écran.
        <div className="frise-tete" aria-live="polite">
          {montrerAvancement && (
            <p className="frise-chiffre">
              {suivi.progression}
              <span className="frise-unite">%</span>
            </p>
          )}
          {delai && (
            <div className="frise-delai">
              <p className="frise-delai-titre">{delai.texte}</p>
              {delai.reserve && (
                <p className="frise-delai-reserve">{delai.reserve}</p>
              )}
            </div>
          )}
        </div>
      )}

      {montrerAvancement && (
        <div
          className="jauge"
          role="progressbar"
          aria-valuenow={suivi.progression}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Avancement de la production"
        >
          <span
            className="jauge-remplissage"
            style={{ width: `${suivi.progression}%` }}
          />
        </div>
      )}

      <ol className="frise-etapes">
        {suivi.etapes.map((etape, index) => (
          <Jalon key={etape.cle} etape={etape} rang={index + 1} />
        ))}
      </ol>
    </div>
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
          <p style={{ margin: 0 }}>{data.message}</p>
        )}
      </Carte>

      {/* Avancement, délai et étapes dans UNE carte, et non plus une jauge ici
          et des pastilles là. Les deux moitiés décrivaient le même fait à deux
          endroits, avec deux vocabulaires du temps qui pouvaient se
          contredire : la jauge annonçait « durée habituelle : 20 à 45 minutes »
          pendant que rien ne disait où en était réellement l'étude (règle 5). */}
      <Carte titre="Où en est votre étude">
        <Frise suivi={data} />
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
