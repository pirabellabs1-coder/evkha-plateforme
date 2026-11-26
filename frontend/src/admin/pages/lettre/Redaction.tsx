/** Ce que partagent une lettre, un modèle et un message d'automatisation :
 * les trois champs du contenu, et les deux gestes de relecture — voir le
 * courriel tel qu'il partira, et s'en envoyer un exemplaire. */
import { lazy, Suspense, useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { adminApi, type ContenuDeLettre } from "../../api";
import { Squelette } from "../../../espace/composants/Interface";
import { message } from "./outils";

const EditeurEnrichi = lazy(() => import("./EditeurEnrichi"));

export function ChampsDuContenu({
  contenu,
  changer,
  lectureSeule = false,
  objetObligatoire = true,
}: {
  contenu: ContenuDeLettre;
  changer: (contenu: ContenuDeLettre) => void;
  lectureSeule?: boolean;
  objetObligatoire?: boolean;
}) {
  const id = useId();
  return (
    <div className="lt-champs">
      <label className="champ" htmlFor={`${id}-objet`}>
        <span className="champ-libelle">Objet{objetObligatoire ? "" : " (facultatif)"}</span>
        <input
          id={`${id}-objet`}
          className="champ-saisie"
          value={contenu.objet}
          maxLength={200}
          required={objetObligatoire}
          readOnly={lectureSeule}
          onChange={(e) => changer({ ...contenu, objet: e.target.value })}
        />
      </label>
      <label className="champ" htmlFor={`${id}-apercu`}>
        <span className="champ-libelle">Texte d'aperçu (facultatif)</span>
        <input
          id={`${id}-apercu`}
          className="champ-saisie"
          value={contenu.apercu}
          maxLength={200}
          readOnly={lectureSeule}
          aria-describedby={`${id}-apercu-aide`}
          onChange={(e) => changer({ ...contenu, apercu: e.target.value })}
        />
        <span className="champ-aide" id={`${id}-apercu-aide`}>
          La ligne grise que les messageries affichent à côté de l'objet.
        </span>
      </label>
      {lectureSeule ? (
        <div className="lt-lu">
          <span className="champ-libelle">Texte</span>
          {/* Contenu déjà nettoyé par le serveur ; affiché dans un cadre isolé. */}
          <ApercuIsole html={contenu.corps_html} titre="Texte de la lettre" />
        </div>
      ) : (
        <div className="lt-editeur">
          <span className="champ-libelle" id={`${id}-texte`}>
            Texte
          </span>
          <Suspense fallback={<Squelette lignes={6} />}>
            <EditeurEnrichi
              valeur={contenu.corps_html}
              changer={(corps_html) => changer({ ...contenu, corps_html })}
              libelle="Texte de la lettre"
            />
          </Suspense>
        </div>
      )}
    </div>
  );
}

/** Un HTML montré sans qu'il puisse rien exécuter : `sandbox` vide interdit
 *  scripts, formulaires et navigation de la page. */
function ApercuIsole({ html, titre }: { html: string; titre: string }) {
  return <iframe className="lt-cadre" title={titre} sandbox="" srcDoc={html} />;
}

export function Relecture({ contenu }: { contenu: ContenuDeLettre }) {
  const id = useId();
  const [adresse, setAdresse] = useState("");
  const [html, setHtml] = useState("");
  const [retour, setRetour] = useState<{ ton: "succes" | "echec"; texte: string } | null>(null);

  const apercu = useMutation({
    mutationFn: () => adminApi.apercuDeLettre(contenu),
    onSuccess: (r) => setHtml(r.html),
    onError: (cause) =>
      setRetour({ ton: "echec", texte: message(cause, "L'aperçu n'a pas pu être préparé.") }),
  });

  const essai = useMutation({
    mutationFn: () => adminApi.essaiDeLettre(contenu, adresse),
    onSuccess: (r) =>
      setRetour({
        ton: "succes",
        texte: `Exemplaire d'essai envoyé à ${r.adresse}. Il arrive en général en moins d'une minute.`,
      }),
    onError: (cause) =>
      setRetour({ ton: "echec", texte: message(cause, "L'essai n'est pas parti. Réessayez.") }),
  });

  return (
    <div className="lt-relecture">
      <div className="lt-relecture-gestes">
        <button
          type="button"
          className="bouton bouton-contour bouton-sm"
          onClick={() => apercu.mutate()}
          disabled={apercu.isPending}
        >
          {html ? "Mettre l'aperçu à jour" : "Voir le courriel"}
        </button>
        <form
          className="lt-essai"
          onSubmit={(e) => {
            e.preventDefault();
            setRetour(null);
            essai.mutate();
          }}
        >
          <label className="champ" htmlFor={`${id}-essai`}>
            <span className="champ-libelle">S'envoyer un essai</span>
            <input
              id={`${id}-essai`}
              className="champ-saisie"
              type="email"
              autoComplete="email"
              placeholder="votre@adresse.fr"
              value={adresse}
              onChange={(e) => setAdresse(e.target.value)}
              required
            />
          </label>
          <button
            type="submit"
            className="bouton bouton-contour bouton-sm"
            disabled={essai.isPending || !contenu.objet.trim()}
          >
            {essai.isPending ? "Envoi…" : "Envoyer l'essai"}
          </button>
        </form>
      </div>
      <p className="lt-statut" aria-live="polite">
        {retour && <span className={`lt-statut-${retour.ton}`}>{retour.texte}</span>}
      </p>
      {html && <ApercuIsole html={html} titre="Aperçu du courriel" />}
    </div>
  );
}
