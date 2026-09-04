/** Signaler un problème, et suivre ce qu'EVKHA en fait (§9.10).
 *
 * ## Pourquoi cet écran existe
 *
 * Jusqu'ici, un client dont l'étude échouait n'avait qu'une adresse e-mail.
 * Le message partait dans une boîte, sans numéro, sans statut, sans lien avec
 * le dossier concerné — et sans que la personne sache jamais si quelqu'un
 * l'avait lu. Un formulaire qui rattache le problème AU dossier et qui montre
 * son avancement remplace trois allers-retours.
 *
 * ## Deux décisions
 *
 * **Le formulaire et la liste sur le même écran.** Séparer les deux ferait
 * déposer deux fois le même problème par qui ne voit pas que le premier est
 * déjà en cours de traitement.
 *
 * **La réponse d'EVKHA est affichée en entier**, sous le message. Un statut
 * « traité » sans un mot n'apprend rien à qui attend : il dit que c'est fini,
 * pas ce qui a été fait.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErreurApi, espaceApi } from "../api";
import * as f from "../format";
import {
  Bandeau,
  Carte,
  Pastille,
  Squelette,
  Vide,
} from "../composants/Interface";

export function Signalements() {
  const cache = useQueryClient();
  const [sujet, setSujet] = useState("");
  const [message, setMessage] = useState("");
  const [livrableId, setLivrableId] = useState("");
  const [erreur, setErreur] = useState("");
  const [depose, setDepose] = useState(false);

  const { data, isPending } = useQuery({
    queryKey: ["espace", "signalements"],
    queryFn: espaceApi.signalements,
  });

  // Les livrables servent à rattacher le signalement à un dossier précis. La
  // liste est celle de l'espace : proposer une saisie libre d'identifiant
  // reviendrait à demander au client de recopier un UUID.
  const { data: livrables } = useQuery({
    queryKey: ["espace", "livrables"],
    queryFn: espaceApi.livrables,
  });

  const sujets = data?.sujets ?? [];
  const liste = data?.signalements ?? [];

  // Le sujet EFFECTIF, celui qui part au serveur — et le même que le menu
  // affiche. L'état démarre vide, et un `<select>` dont la valeur ne
  // correspond à aucune option affiche la première : l'écran montrait « Un
  // document produit ne va pas » pendant qu'« Autre chose » était enregistré.
  // Constaté en déposant un signalement pour de bon, pas en relisant le code.
  const sujetChoisi = sujet || sujets[0]?.code || "autre";

  const envoi = useMutation({
    mutationFn: () =>
      espaceApi.signaler({
        sujet: sujetChoisi,
        message: message.trim(),
        ...(livrableId ? { livrable_id: livrableId } : {}),
      }),
    onSuccess: () => {
      setErreur("");
      setDepose(true);
      setMessage("");
      setLivrableId("");
      void cache.invalidateQueries({ queryKey: ["espace", "signalements"] });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi
          ? cause.message
          : "Le signalement n'a pas pu être envoyé. Réessayez, ou écrivez-nous à contact@evkha.fr.",
      ),
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--e-5)" }}>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {depose && !erreur && (
        <Bandeau ton="succes" titre="Signalement enregistré">
          Nous l'avons reçu et nous revenons vers vous. Vous suivez son
          avancement ci-dessous.
        </Bandeau>
      )}

      <Carte
        titre="Signaler un problème"
        note="Un document qui ne va pas, une génération bloquée, une question de facturation — décrivez, nous prenons la main."
      >
        <form
          onSubmit={(evenement) => {
            evenement.preventDefault();
            setDepose(false);
            if (!message.trim()) {
              setErreur("Décrivez le problème en quelques lignes.");
              return;
            }
            envoi.mutate();
          }}
          style={{ display: "flex", flexDirection: "column", gap: "var(--e-3)" }}
        >
          <label className="champ" htmlFor="signalement-sujet">
            <span className="champ-libelle">De quoi s'agit-il ?</span>
            <select
              id="signalement-sujet"
              className="champ-saisie"
              value={sujetChoisi}
              onChange={(evenement) => setSujet(evenement.target.value)}
            >
              {sujets.map((entree) => (
                <option key={entree.code} value={entree.code}>
                  {entree.libelle}
                </option>
              ))}
            </select>
          </label>

          <label className="champ" htmlFor="signalement-livrable">
            <span className="champ-libelle">Document concerné (facultatif)</span>
            <select
              id="signalement-livrable"
              className="champ-saisie"
              value={livrableId}
              onChange={(evenement) => setLivrableId(evenement.target.value)}
            >
              <option value="">Aucun document en particulier</option>
              {(livrables?.livrables ?? []).map((livrable) => (
                <option key={livrable.id} value={livrable.id}>
                  {f.typeLivrable(livrable.type)} — {f.date(livrable.cree_le)}
                </option>
              ))}
            </select>
            <span className="champ-aide">
              Le choisir nous évite de le chercher : nous ouvrons directement le
              bon dossier.
            </span>
          </label>

          <label className="champ" htmlFor="signalement-message">
            <span className="champ-libelle">Que s'est-il passé ?</span>
            <textarea
              id="signalement-message"
              className="champ-saisie"
              rows={5}
              maxLength={4000}
              value={message}
              placeholder="Le graphique du chapitre 4 affiche des chiffres qui ne correspondent pas à mon secteur…"
              onChange={(evenement) => setMessage(evenement.target.value)}
            />
          </label>

          <div>
            <button type="submit" className="bouton" disabled={envoi.isPending}>
              {envoi.isPending ? "Envoi…" : "Envoyer le signalement"}
            </button>
          </div>
        </form>
      </Carte>

      <Carte titre="Vos signalements">
        {isPending && <Squelette lignes={3} />}
        {!isPending && liste.length === 0 && (
          <Vide
            titre="Aucun signalement"
            texte="Tout va bien de notre côté comme du vôtre. Le formulaire ci-dessus est là si ça change."
          />
        )}
        {!isPending && liste.length > 0 && (
          <ul className="signalements">
            {liste.map((signalement) => (
              <li key={signalement.id} className="signalement">
                <div className="signalement-tete">
                  <span className="signalement-sujet">
                    {signalement.sujet_libelle}
                  </span>
                  <Pastille
                    statut={signalement.statut}
                    texte={signalement.statut_libelle}
                  />
                  <span className="signalement-date">
                    {f.date(signalement.cree_le)}
                  </span>
                </div>
                <p className="signalement-message">{signalement.message}</p>
                {/* La réponse d'EVKHA, quand elle existe. Le bloc n'apparaît
                    pas vide : un cadre « Notre réponse » sans texte se lit
                    comme une réponse perdue. */}
                {signalement.reponse && (
                  <div className="signalement-reponse">
                    <div className="signalement-reponse-titre">Notre réponse</div>
                    <p className="signalement-message">{signalement.reponse}</p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Carte>
    </div>
  );
}
