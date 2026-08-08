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
 *
 * ## Trois cartes, et non deux, parce que le nom et l'adresse ne se valent pas
 *
 * Le nom se corrige seul : il n'appartient qu'à la personne et n'engage rien.
 * L'adresse est l'IDENTIFIANT de connexion et la destination des liens de
 * réinitialisation — qui la change prend le compte. Elle exige donc deux
 * preuves, le mot de passe puis un clic dans la boîte visée, et ce n'est pas
 * la même carte ni le même geste. Les mêler dans un seul formulaire ferait
 * réclamer un mot de passe à qui vient corriger une faute sur son prénom.
 *
 * L'écran disait auparavant d'écrire à EVKHA pour l'un comme pour l'autre.
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ErreurApi, espaceApi } from "../api";
import { CLE_MOI, useMoi } from "../useMoi";
import * as f from "../format";
import { Bandeau, Carte, Champ, Squelette } from "../composants/Interface";

const VIDE = { actuel: "", nouveau: "", confirmation: "" };
const ADRESSE_VIDE = { motDePasse: "", nouvelle: "" };

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
  const cache = useQueryClient();
  const [saisie, setSaisie] = useState(VIDE);
  const [erreur, setErreur] = useState("");
  const [code, setCode] = useState("");
  const [fermees, setFermees] = useState<number | null>(null);

  // `null` tant que rien n'a été saisi : le formulaire AFFICHE alors ce que
  // rend le serveur. Recopier ces valeurs dans l'état depuis un effet
  // écraserait la frappe en cours dès que `moi` se rejoue en arrière-plan —
  // ce qu'il fait au retour sur la fenêtre.
  const [profil, setProfil] = useState<{ prenom: string; nom: string } | null>(
    null,
  );
  const [erreurProfil, setErreurProfil] = useState("");
  const [profilEnregistre, setProfilEnregistre] = useState(false);

  const [adresse, setAdresse] = useState(ADRESSE_VIDE);
  const [erreurAdresse, setErreurAdresse] = useState("");
  const [demande, setDemande] = useState<{
    adresse_visee: string;
    courriel_envoye: boolean;
    lien_confirmation: string;
  } | null>(null);

  const brouillon = profil ?? {
    prenom: moi?.utilisateur.prenom ?? "",
    nom: moi?.utilisateur.nom ?? "",
  };

  const enregistrementProfil = useMutation({
    mutationFn: () => espaceApi.modifierProfil(brouillon),
    onSuccess: (retour) => {
      setErreurProfil("");
      setProfilEnregistre(true);
      // On adopte ce que le serveur a RETENU, pas ce qui a été tapé : il coupe
      // à 150 caractères et retire les espaces de bordure. Garder la saisie
      // laisserait le champ afficher autre chose que le nom réellement porté
      // par le compte — deux vérités pour un même état civil.
      setProfil(retour);
      // La coquille, l'en-tête et les courriels lisent tous `moi` : sans cette
      // invalidation, le nom corrigé n'apparaîtrait qu'au rechargement complet.
      void cache.invalidateQueries({ queryKey: CLE_MOI });
    },
    onError: (cause) => {
      setProfilEnregistre(false);
      setErreurProfil(
        cause instanceof ErreurApi
          ? cause.message
          : "Enregistrement impossible. Vérifiez votre réseau.",
      );
    },
  });

  const demandeAdresse = useMutation({
    mutationFn: () =>
      espaceApi.demanderNouvelleAdresse({
        mot_de_passe: adresse.motDePasse,
        nouvelle_adresse: adresse.nouvelle,
      }),
    onSuccess: (retour) => {
      setErreurAdresse("");
      setDemande(retour);
      // Le mot de passe ne traîne pas à l'écran une fois la demande partie ; la
      // nouvelle adresse non plus, le bandeau la répète déjà.
      setAdresse(ADRESSE_VIDE);
      // Aucune invalidation de `CLE_MOI` ici, et c'est le point de tout
      // l'écran : la demande ne change RIEN. Rafraîchir l'identité afficherait
      // encore l'ancienne adresse et donnerait à croire que l'envoi a échoué.
    },
    onError: (cause) => {
      setDemande(null);
      setErreurAdresse(
        cause instanceof ErreurApi
          ? cause.message
          : "Demande impossible. Vérifiez votre réseau.",
      );
    },
  });

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

  function modifierProfil(champ: "prenom" | "nom") {
    return (evenement: React.ChangeEvent<HTMLInputElement>) => {
      const valeur = evenement.target.value;
      // La confirmation disparaît dès la frappe suivante : un « Enregistré »
      // laissé au-dessus d'un champ modifié depuis affirmerait le faux.
      setProfilEnregistre(false);
      setProfil((precedent) => ({ ...(precedent ?? brouillon), [champ]: valeur }));
    };
  }

  function modifierAdresse(champ: keyof typeof ADRESSE_VIDE) {
    return (evenement: React.ChangeEvent<HTMLInputElement>) => {
      const valeur = evenement.target.value;
      setAdresse((precedent) => ({ ...precedent, [champ]: valeur }));
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
        note="Votre prénom et votre nom se corrigent ici, sans passer par personne."
      >
        {/* Le squelette ne couvre QUE cette carte. Le changement de mot de
            passe reste atteignable même si l'identité n'arrive pas : c'est le
            recours de quelqu'un dont l'accès est compromis, il ne doit dépendre
            d'aucune autre requête. */}
        {moi ? (
          <>
            {/* Refus et confirmation vivent DANS le formulaire, dont
                l'espacement les sépare des champs : ni `.bandeau` ni `.carte`
                ne portent de marge propre, et c'est le conteneur qui espace. */}
            <form
              className="compte-formulaire"
              onSubmit={(evenement) => {
                evenement.preventDefault();
                enregistrementProfil.mutate();
              }}
              noValidate
            >
              {erreurProfil && <Bandeau ton="echec">{erreurProfil}</Bandeau>}
              {profilEnregistre && (
                <Bandeau ton="succes">Votre nom est enregistré.</Bandeau>
              )}

              <div className="grille-champs">
                <Champ
                  libelle="Prénom"
                  name="prenom"
                  autoComplete="given-name"
                  value={brouillon.prenom}
                  onChange={modifierProfil("prenom")}
                />
                <Champ
                  libelle="Nom"
                  name="nom"
                  autoComplete="family-name"
                  value={brouillon.nom}
                  onChange={modifierProfil("nom")}
                />
              </div>
              <div className="compte-actions">
                <button
                  type="submit"
                  className="bouton bouton-principal"
                  disabled={enregistrementProfil.isPending}
                >
                  {enregistrementProfil.isPending
                    ? "Enregistrement…"
                    : "Enregistrer"}
                </button>
              </div>
            </form>

            {/* Ce qui ne se corrige pas d'un champ de saisie : l'adresse a sa
                carte, le rôle et l'organisation viennent de l'équipe. */}
            <div className="compte-lecture">
              <dl className="compte-identite">
                <div>
                  <dt>Adresse de connexion</dt>
                  <dd>{moi.utilisateur.email}</dd>
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
            </div>
          </>
        ) : (
          <Squelette lignes={4} />
        )}
      </Carte>

      <Carte
        titre="Changer d'adresse de connexion"
        note="Votre mot de passe ici, puis un clic dans la nouvelle boîte."
      >
        <form
          className="compte-formulaire"
          onSubmit={(evenement) => {
            evenement.preventDefault();
            // La demande précédente disparaît : un « courriel parti » laissé
            // au-dessus d'un refus dirait deux choses contraires à la fois.
            setDemande(null);
            setErreurAdresse("");
            demandeAdresse.mutate();
          }}
          noValidate
        >
          {/* Le refus du serveur est affiché TEL QUEL : « C'est déjà votre
              adresse » et « Cette adresse est déjà utilisée par un compte »
              n'appellent pas la même correction, et un message générique les
              confondrait. */}
          {erreurAdresse && <Bandeau ton="echec">{erreurAdresse}</Bandeau>}

          {/* Un envoi, jamais un changement : le serveur répond 202, l'adresse
              n'a pas bougé. Une phrase — la cliente a reproché aux bandeaux de
              se justifier. */}
          {demande?.courriel_envoye && (
            <Bandeau ton="succes">
              Un courriel est parti vers {demande.adresse_visee}&nbsp;: votre
              adresse de connexion ne changera qu'au clic sur le lien qu'il
              contient.
            </Bandeau>
          )}

          {/* L'envoi a échoué : on donne le lien plutôt que de laisser quelqu'un
              attendre un message qui n'arrivera pas. C'est le serveur qui le
              fournit, et seulement dans ce cas. */}
          {demande && !demande.courriel_envoye && (
            <Bandeau ton="echec" titre="Courriel non parti">
              Le message destiné à {demande.adresse_visee} n'a pas pu être
              envoyé. Ouvrez ce lien vous-même&nbsp;— rien ne change
              avant&nbsp;:
              <code className="equipe-lien-secours">
                {demande.lien_confirmation}
              </code>
            </Bandeau>
          )}

          <div className="grille-champs">
            {/* `name` distinct de celui du formulaire de mot de passe : `Champ`
                en dérive l'identifiant, et deux `id` identiques feraient
                pointer le libellé d'ici sur la case de l'autre carte. */}
            <Champ
              libelle="Mot de passe actuel"
              name="mot_de_passe_adresse"
              type="password"
              autoComplete="current-password"
              required
              value={adresse.motDePasse}
              onChange={modifierAdresse("motDePasse")}
              aide="Exigé en plus de votre session — un écran resté ouvert ne doit pas suffire à déplacer votre identifiant de connexion."
            />
            <Champ
              libelle="Nouvelle adresse"
              name="nouvelle_adresse"
              type="email"
              autoComplete="email"
              required
              value={adresse.nouvelle}
              onChange={modifierAdresse("nouvelle")}
              aide="Le lien de confirmation y sera envoyé. Rien ne change avant le clic."
            />
          </div>

          <div className="compte-actions">
            <button
              type="submit"
              className="bouton bouton-principal"
              disabled={demandeAdresse.isPending}
            >
              {demandeAdresse.isPending ? "Envoi…" : "Envoyer la confirmation"}
            </button>
            <span className="carte-note">
              Votre adresse actuelle est prévenue au même moment.
            </span>
          </div>
        </form>
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
