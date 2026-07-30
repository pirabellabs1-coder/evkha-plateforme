/** Connexion à l'espace client. */
import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ErreurApi, espaceApi, jeton } from "../api";
import { Champ } from "../composants/Interface";

export function Connexion() {
  const naviguer = useNavigate();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur("");
    setEnvoi(true);
    try {
      const reponse = await espaceApi.connexion(email, motDePasse);
      jeton.ecrire(reponse.jeton);
      await naviguer({ to: "/espace" });
    } catch (cause) {
      // Le serveur ne distingue pas « e-mail inconnu » de « mot de passe
      // faux » ; l'interface ne doit pas non plus le faire.
      setErreur(
        cause instanceof ErreurApi
          ? cause.message
          : "Connexion impossible. Vérifiez votre réseau.",
      );
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "var(--evkha-noir)",
        padding: "var(--e-6)",
      }}
    >
      <div
        className="carte"
        style={{ width: "100%", maxWidth: 420, borderRadius: "var(--rayon-xl)" }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--e-3)",
            marginBottom: "var(--e-6)",
          }}
        >
          <span className="espace-sceau" aria-hidden="true">
            E
          </span>
          <div>
            <div className="carte-titre">EVKHA</div>
            <div className="carte-note">Espace client</div>
          </div>
        </div>

        <form
          onSubmit={soumettre}
          style={{ display: "flex", flexDirection: "column", gap: "var(--e-4)" }}
        >
          <Champ
            libelle="Adresse e-mail"
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Champ
            libelle="Mot de passe"
            name="mot_de_passe"
            type="password"
            autoComplete="current-password"
            required
            value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)}
            erreur={erreur || undefined}
          />
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={envoi}
            style={{ marginTop: "var(--e-2)" }}
          >
            {envoi ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <p className="carte-note" style={{ marginTop: "var(--e-5)" }}>
          Votre accès est créé par EVKHA. Si vous ne parvenez pas à vous
          connecter, contactez votre interlocutrice.
        </p>
      </div>
    </div>
  );
}
