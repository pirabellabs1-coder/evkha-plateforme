/** « Combien de temps mes crédits tiennent-ils ? »
 *
 *  La question que se pose une agence abonnée, et à laquelle ni le solde seul
 *  ni le journal ligne à ligne ne répondent : il faut faire la moyenne de tête,
 *  puis la diviser dans le solde.
 *
 *  Le calcul vit **côté serveur** (`/api/espace/consommation/`). Le refaire ici
 *  produirait un second résultat, et deux endroits finiraient par annoncer deux
 *  dates différentes pour le même compte.
 *
 *  Ce composant ne fabrique jamais de date de repli. Quand le serveur dit qu'il
 *  ne peut pas conclure, on affiche la raison : une date inventée se croit, et
 *  elle décide d'un renouvellement.
 */
import type { Rythme } from "../api";
import * as f from "../format";
import { Bandeau, Carte } from "./Interface";

/** Sous ce seuil, l'information devient une alerte.
 *
 *  Trente jours parce qu'il faut le temps de commander des crédits
 *  supplémentaires ou de changer de formule sans interrompre la production. */
const SEUIL_ALERTE_JOURS = 30;

const RAISONS: Record<Exclude<Rythme["motif"], "">, string> = {
  aucun_mouvement:
    "Votre autonomie s'affichera dès le premier mouvement enregistré sur votre portefeuille.",
  pas_assez_d_historique:
    "Votre compte a été ouvert ce mois-ci : il faut un mois complet pour mesurer un rythme qui veuille dire quelque chose.",
  aucune_consommation:
    "Aucune consommation mesurée pour l'instant. Vos crédits restent disponibles sans limite de durée pendant l'abonnement.",
};

export function Autonomie({ rythme }: { rythme: Rythme }) {
  if (rythme.motif !== "") {
    return (
      <Carte titre="Autonomie" note="Estimée sur votre consommation passée.">
        <p className="carte-note">{RAISONS[rythme.motif]}</p>
      </Carte>
    );
  }

  const jours = rythme.jours_restants ?? 0;
  const alerte = jours <= SEUIL_ALERTE_JOURS;
  const mois = Math.floor(jours / 30.44);

  return (
    <Carte
      titre="Autonomie"
      note={`Mesurée sur ${rythme.mois_observes} mois révolu${
        rythme.mois_observes > 1 ? "s" : ""
      }, mois en cours exclu.`}
    >
      {alerte && (
        <Bandeau titre="Vos crédits arrivent à leur terme">
          À ce rythme, votre solde sera épuisé dans {jours} jour
          {jours > 1 ? "s" : ""}. Vous pouvez commander des crédits
          supplémentaires ou passer à une formule supérieure sans attendre
          l'échéance.
        </Bandeau>
      )}

      <div className="autonomie">
        <div>
          <div className="chiffre-libelle">Rythme constaté</div>
          <div className="autonomie-valeur">
            {f.nombre(rythme.mensuel)}
            <span className="autonomie-unite"> crédits / mois</span>
          </div>
        </div>
        <div>
          <div className="chiffre-libelle">Solde actuel</div>
          <div className="autonomie-valeur">
            {f.nombre(rythme.solde)}
            <span className="autonomie-unite">
              {" "}
              crédit{rythme.solde > 1 ? "s" : ""}
            </span>
          </div>
        </div>
        <div>
          <div className="chiffre-libelle">Épuisement estimé</div>
          <div className={`autonomie-valeur ${alerte ? "autonomie-tendue" : ""}`}>
            {f.date(rythme.epuisement_le)}
          </div>
          <div className="carte-note">
            {/* Les jours bruts en dessous : « dans 3 mois » se compare mal à
                une échéance d'abonnement, « dans 94 jours » se compare bien. */}
            {mois >= 1
              ? `Environ ${mois} mois — ${jours} jours`
              : `Dans ${jours} jour${jours > 1 ? "s" : ""}`}
          </div>
        </div>
      </div>
    </Carte>
  );
}
