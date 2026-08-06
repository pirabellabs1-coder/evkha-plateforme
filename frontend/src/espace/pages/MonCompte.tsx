/** Mon compte : qui je suis, et comment je reprends la main sur mon accès.
 *
 * L'espace client n'avait aucune page personnelle. La route de changement de
 * mot de passe existait pourtant côté serveur, documentée et couverte par des
 * tests — mais aucun écran ne la proposait et aucun appel du client d'API ne
 * l'atteignait. Quelqu'un dont le jeton fuitait n'avait donc aucun recours :
 * l'intrus restait connecté quatorze jours, le temps que le jeton expire.
 *
 * Le geste est annoncé pour ce qu'il est. Fermer toutes les autres sessions
 * n'est pas un effet de bord qu'on tairait par crainte d'inquiéter : c'est
 * précisément ce qu'on vient chercher ici.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErreurApi, espaceApi } from "../api";
import { useMoi } from "../useMoi";
import * as f from "../format";
import { Bandeau, Carte, Champ, Squelette } from "../composants/Interface";

const VIDE = { actuel: "", nouveau: "", confirmation: "" };

/** Quel champ porte le refus, selon le code rendu par le serveur.
 *
 * Poser le message sous le champ fautif plutôt que dans un bandeau évite de
 * faire chercher : « le mot de passe actuel est incorrect » n'a de sens qu'à
 * côté de la case où on l'a saisi. Les codes viennent du serveur ; seul
 * `confirmation` est local, la concordance des deux saisies n'ayant de sens
 * que devant l'écran. Un code inconnu retombe sur le bandeau, jamais dans le
 * vide.
 */
const CHAMP_FAUTIF: Record<string, "actuel" | "nouveau" | "confirmation"> = {
  mot_de_passe_actuel: "actuel",
  mot_de_passe_faible: "nouveau",
  confirmation: "confirmation",
};

/** Combien d'autres sessions sont tombées, en toutes lettres.
 *
 * Le serveur compte TOUTES les sessions révoquées, y compris celle qui a
 * demandé le changement — elle repart pourtant avec un jeton neuf. L'annoncer
 * telle quelle ferait lire « 1 session fermée » à quelqu'un qui était seul, et
 * douter de l'écran qu'il a sous les yeux.
 */
function autresSessions(fermees: number): string {
  const autres = Math.max(fermees - 1, 0);
  if (autres === 0) return "Aucune autre session n'était ouverte.";
  if (autres === 1) return "Une autre session a été fermée.";
  return `${f.nombre(autres)} autres sessions ont été fermées.`;
}

export function MonCompte() {
  const { data: moi } = useMoi();
  const [saisie, setSaisie] = useState(VIDE);
  const [erreur, setErreur] = useState("");
  const [code, setCode] = useState("");
  const [fermees, setFermees] = useState<number | null>(null);

  const changement = useMutation({
    mutationFn: () =>
      espaceApi.changerMotDePasse({
        mot_de_passe_actuel: saisie.actuel,
        nouveau_mot_de_passe: saisie.nouveau,
      }),
    onSuccess: (retour) => {
      setErreur("");
      setCode("");
      // Les trois cases sont vidées : un mot de passe qui traîne dans un
      // formulaire après coup ne sert plus à rien et reste lisible à l'écran.
      setSaisie(VIDE);
      setFermees(retour.sessions_fermees);
    },
    onError: (cause) => {
      // La confirmation précédente disparaît : laisser « mot de passe changé »
      // au-dessus d'un refus dirait deux choses contraires en même temps.
      setFermees(null);
      setErreur(
        cause instanceof ErreurApi
          ? cause.message
          : "Changement impossible. Vérifiez votre réseau.",
      );
      setCode(cause instanceof ErreurApi ? cause.code : "");
    },
  });

  const fautif = CHAMP_FAUTIF[code];

  function modifier(champ: keyof typeof VIDE) {
    return (evenement: React.ChangeEvent<HTMLInputElement>) => {
      const valeur = evenement.target.value;
      setSaisie((precedent) => ({ ...precedent, [champ]: valeur }));
    };
  }

  function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setFermees(null);
    if (saisie.nouveau !== saisie.confirmation) {
      // Contrôlé ici seulement : le serveur n'a jamais reçu la confirmation, et
      // n'a aucune raison de la recevoir. La solidité du mot de passe, elle,
      // reste son affaire — la rejouer ici ferait deux avis sur une seule
      // question.
      setErreur("Les deux saisies ne sont pas identiques.");
      setCode("confirmation");
      return;
    }
    setErreur("");
    setCode("");
    changement.mutate();
  }

  return (
    <>
      <Carte
        titre="Vos informations"
        note="Elles viennent de votre compte et de votre organisation."
      >
        {/* Le squelette ne couvre QUE cette carte. Le changement de mot de
            passe reste atteignable même si l'identité n'arrive pas : c'est le
            recours de quelqu'un dont l'accès est compromis, il ne doit dépendre
            d'aucune autre requête. */}
        {moi ? (
          <dl className="compte-identite">
            <div>
              <dt>Adresse e-mail</dt>
              <dd>{moi.utilisateur.email}</dd>
            </div>
            <div>
              <dt>Prénom</dt>
              <dd>{moi.utilisateur.prenom || "—"}</dd>
            </div>
            <div>
              <dt>Nom</dt>
              <dd>{moi.utilisateur.nom || "—"}</dd>
            </div>
            <div>
              <dt>Rôle</dt>
              <dd>{f.role(moi.utilisateur.role)}</dd>
            </div>
            <div>
              <dt>Organisation</dt>
              <dd>{moi.organisation.raison_sociale}</dd>
            </div>
          </dl>
        ) : (
          <Squelette lignes={4} />
        )}
        <p className="carte-note compte-pied">
          Votre adresse et votre nom sont ceux de votre compte de connexion.
          Pour les corriger, écrivez à EVKHA — nous ne changeons pas une adresse
          de connexion sans en avoir la confirmation.
        </p>
      </Carte>

      <Carte
        titre="Changer de mot de passe"
        note="Choisissez-en un nouveau, sans passer par votre boîte mail."
      >
        <div className="compte-avis">
          <strong className="compte-avis-titre">
            Ce changement ferme toutes vos autres sessions
          </strong>
          <p>
            Tous les appareils déjà connectés à votre espace en sont sortis
            sur-le-champ. C'est le recours si vous pensez que quelqu'un d'autre
            a la main sur votre compte&nbsp;: l'intrus perd l'accès à l'instant
            où vous validez, sans attendre l'expiration de son jeton. Seul cet
            écran-ci reste connecté.
          </p>
        </div>

        {/* Refus et confirmation vivent DANS le formulaire, dont l'espacement
            les sépare des champs. Posés à côté, ils se colleraient à la
            première ligne de saisie : aucune des deux briques ne porte de marge
            propre, et c'est voulu — l'espacement appartient au conteneur. */}
        <form className="compte-formulaire" onSubmit={soumettre} noValidate>
          {/* Un code que la table ne connaît pas — réseau coupé, session
              expirée — n'a pas de champ où se poser : il lui faut le bandeau,
              sinon le refus resterait muet. */}
          {erreur && !fautif && <Bandeau ton="echec">{erreur}</Bandeau>}

          {fermees !== null && (
            <p className="compte-confirmation" role="status">
              Mot de passe changé. {autresSessions(fermees)} Votre session sur
              cet appareil reste ouverte.
            </p>
          )}

          <div className="grille-champs">
            <Champ
              libelle="Mot de passe actuel"
              name="mot_de_passe_actuel"
              type="password"
              autoComplete="current-password"
              required
              value={saisie.actuel}
              onChange={modifier("actuel")}
              erreur={fautif === "actuel" ? erreur : undefined}
              aide="Exigé pour prouver que c'est bien vous — un jeton volé ne doit pas suffire à vous verrouiller dehors."
            />
            {/* Aucun seuil recopié dans l'aide : les règles de solidité sont
                celles du serveur, et une longueur écrite en dur ici finirait
                par ne plus être la sienne. S'il refuse, il dit pourquoi, et son
                message prend la place de l'aide. */}
            <Champ
              libelle="Nouveau mot de passe"
              name="nouveau_mot_de_passe"
              type="password"
              autoComplete="new-password"
              required
              value={saisie.nouveau}
              onChange={modifier("nouveau")}
              erreur={fautif === "nouveau" ? erreur : undefined}
              aide="Long, et sans rapport avec votre nom ou votre adresse. S'il est refusé, la raison s'affiche ici."
            />
            <Champ
              libelle="Confirmer le nouveau mot de passe"
              name="confirmation_mot_de_passe"
              type="password"
              autoComplete="new-password"
              required
              value={saisie.confirmation}
              onChange={modifier("confirmation")}
              erreur={fautif === "confirmation" ? erreur : undefined}
              aide="Recopiez-le, pour écarter une faute de frappe."
            />
          </div>

          <div className="compte-actions">
            <button
              type="submit"
              className="bouton bouton-principal"
              disabled={changement.isPending}
            >
              {changement.isPending
                ? "Changement…"
                : "Changer mon mot de passe"}
            </button>
            <span className="carte-note">
              Les autres sessions tombent dès validation.
            </span>
          </div>
        </form>
      </Carte>
    </>
  );
}
