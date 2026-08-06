/** Équipe de l'organisation (§9.1) et rappel des droits (§12). */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErreurApi, espaceApi, type Role } from "../api";
import * as f from "../format";
import { peut, useMoi } from "../useMoi";
import {
  Bandeau,
  Carte,
  Champ,
  Pastille,
  Squelette,
} from "../composants/Interface";

/** Les droits affichés viennent du serveur (`moi.utilisateur.droits`) ; seuls
 *  les LIBELLÉS sont ici. Recopier la matrice du §12 dans l'interface la ferait
 *  diverger du serveur au premier ajout d'action.
 *
 *  `gerer_clients_finaux` est le nom de l'action côté serveur, hérité du modèle
 *  où un abonné gérait un portefeuille de clients. Cet espace est celui d'UN
 *  abonné qui gère SA marque, pas une agence : le libellé le dit, la clé garde
 *  son nom tant que le serveur ne change pas le sien. Renommer l'un sans
 *  l'autre romprait la correspondance en silence. */
const LIBELLE_DROIT: Record<string, string> = {
  commander: "Commander un document",
  consulter_livrables: "Consulter les livrables",
  gerer_clients_finaux: "Modifier ma marque et ma charte",
  gerer_membres: "Inviter ou révoquer un collaborateur",
  gerer_abonnement: "Changer de formule, acheter des crédits",
  consulter_factures: "Consulter les factures",
};

export function Equipe() {
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("membre");
  const [erreur, setErreur] = useState("");
  // Ce que le SERVEUR a réellement fait, pas ce qu'on suppose : l'adresse
  // invitée, si le courriel est parti, et le lien de secours dans le cas
  // contraire. L'écran affirmait « EVKHA lui transmettra ses identifiants »
  // alors que le message part tout seul — et se taisait quand il ne partait pas.
  const [invitation_faite, setInvitationFaite] = useState<{
    email: string;
    envoyee: boolean;
    lien: string;
  } | null>(null);

  const peutGerer = peut(moi, "gerer_membres");

  const { data, isPending } = useQuery({
    queryKey: ["espace", "equipe"],
    queryFn: espaceApi.equipe,
  });

  const invitation = useMutation({
    mutationFn: () => espaceApi.inviter({ email: email.trim(), role }),
    onSuccess: (retour) => {
      setErreur("");
      setInvitationFaite({
        email: retour.email,
        envoyee: retour.invitation_envoyee,
        lien: retour.lien_activation,
      });
      setEmail("");
      void cache.invalidateQueries({ queryKey: ["espace", "equipe"] });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Invitation impossible.",
      ),
  });

  const revocation = useMutation({
    mutationFn: (id: string) => espaceApi.revoquer(id),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["espace", "equipe"] });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Révocation impossible.",
      ),
  });

  const membres = data?.membres ?? [];

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {/* Une phrase, un fait. La version précédente expliquait en outre que le
          mot de passe resterait secret et qu'EVKHA n'interviendrait pas :
          personne ne se pose ces questions au moment d'inviter quelqu'un, et
          les devancer donne à une réussite le ton d'une justification. */}
      {invitation_faite?.envoyee && (
        <Bandeau ton="succes" titre="Invitation envoyée">
          {invitation_faite.email} a reçu un courriel pour rejoindre votre
          espace.
        </Bandeau>
      )}
      {/* L'envoi a échoué : on donne le lien plutôt que de laisser quelqu'un
          attendre un courriel qui n'arrivera pas. C'est le serveur qui le
          fournit, et seulement dans ce cas. */}
      {invitation_faite && !invitation_faite.envoyee && (
        <Bandeau ton="echec" titre="Courriel non parti">
          {invitation_faite.email} fait bien partie de votre équipe, mais le
          message n'a pas pu être envoyé. Transmettez-lui ce lien vous-même — il
          est valable trois jours et ne sert qu'une fois :
          <br />
          <code className="equipe-lien-secours">{invitation_faite.lien}</code>
        </Bandeau>
      )}

      {peutGerer && (
        <Carte
          titre="Inviter un collaborateur"
          note="Il partagera votre portefeuille de crédits."
        >
          <form
            onSubmit={(evenement) => {
              evenement.preventDefault();
              invitation.mutate();
            }}
            style={{
              display: "flex",
              gap: "var(--e-4)",
              alignItems: "flex-end",
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: "1 1 260px" }}>
              <Champ
                libelle="Adresse e-mail"
                name="email"
                type="email"
                required
                value={email}
                onChange={(evenement) => setEmail(evenement.target.value)}
              />
            </div>
            <label className="champ" style={{ minWidth: 190 }}>
              <span className="champ-libelle">Rôle</span>
              <select
                className="champ-saisie"
                value={role}
                onChange={(evenement) => setRole(evenement.target.value as Role)}
              >
                {(data?.roles_disponibles ?? []).map((entree) => (
                  <option key={entree.code} value={entree.code}>
                    {entree.libelle}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              className="bouton bouton-principal"
              disabled={invitation.isPending}
            >
              {invitation.isPending ? "Envoi…" : "Inviter"}
            </button>
          </form>
        </Carte>
      )}

      <Carte
        titre={`${membres.length} collaborateur${membres.length > 1 ? "s" : ""}`}
        note="Tous partagent le même portefeuille de crédits."
      >
        {isPending ? (
          <Squelette lignes={3} />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Collaborateur</th>
                  <th scope="col">Rôle</th>
                  <th scope="col">Accès</th>
                  <th scope="col">Invité le</th>
                  {peutGerer && (
                    <th scope="col">
                      <span className="visuellement-cache">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {membres.map((membre) => (
                  <tr key={membre.id}>
                    <td>
                      <strong>
                        {[membre.prenom, membre.nom].filter(Boolean).join(" ") ||
                          membre.email}
                      </strong>
                      <div className="carte-note">{membre.email}</div>
                    </td>
                    <td>{f.role(membre.role)}</td>
                    <td>
                      <Pastille
                        statut={membre.actif ? "active" : "expired"}
                        texte={membre.actif ? "Actif" : "Révoqué"}
                      />
                    </td>
                    <td>{f.date(membre.invite_le)}</td>
                    {peutGerer && (
                      <td>
                        {membre.actif && (
                          <button
                            type="button"
                            className="bouton bouton-discret bouton-sm"
                            onClick={() => revocation.mutate(membre.id)}
                            disabled={revocation.isPending}
                          >
                            Révoquer
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>

      <Carte
        titre="Vos droits"
        note={`Rôle : ${f.role(moi?.utilisateur.role ?? "")}`}
      >
        <ul
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "var(--e-3)",
            listStyle: "none",
            margin: 0,
            padding: 0,
          }}
        >
          {Object.entries(LIBELLE_DROIT).map(([code, libelle]) => {
            const accorde = moi?.utilisateur.droits.includes(code) ?? false;
            return (
              <li
                key={code}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--e-3)",
                  color: accorde ? "var(--texte)" : "var(--texte-tenu)",
                }}
              >
                {/* Un symbole, pas seulement une couleur : la distinction reste
                    lisible en noir et blanc comme pour un daltonien. */}
                <span
                  aria-hidden="true"
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    display: "grid",
                    placeItems: "center",
                    flex: "0 0 20px",
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    background: accorde ? "var(--evkha-or)" : "var(--evkha-nuage)",
                    color: accorde ? "var(--texte-sur-or)" : "var(--texte-tenu)",
                  }}
                >
                  {accorde ? "✓" : "—"}
                </span>
                {libelle}
                <span className="visuellement-cache">
                  {accorde ? " : autorisé" : " : non autorisé"}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="carte-note" style={{ marginTop: "var(--e-5)" }}>
          Corriger un socle, relancer une génération ou modifier une trame reste
          réservé à EVKHA, quel que soit votre rôle.
        </p>
      </Carte>
    </>
  );
}
