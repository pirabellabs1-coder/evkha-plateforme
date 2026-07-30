/** Ma marque : le profil de l'abonné et la charte de ses documents.
 *
 * L'espace client est celui d'**un** abonné qui gère **ses** études : un seul
 * profil, pas une liste de clients finaux. Ces valeurs habillent chaque
 * document produit — bandeaux de chapitre, en-têtes de tableau, palette des
 * graphiques, logo de couverture.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErreurApi, espaceApi, type Marque } from "../api";
import { peut, useMoi } from "../useMoi";
import { Bandeau, Carte, Champ, Squelette } from "../composants/Interface";
import { ZoneDepot } from "../composants/Televersement";
import { poids } from "../composants/poids";

const VIDE: Marque = {
  raison_sociale: "",
  secteur: "",
  pays: "",
  region: "",
  ville: "",
  logo_url: "",
  couleur_principale: "",
  couleur_secondaire: "",
  couleur_fond: "",
  mention_confidentialite: "",
};

/** Aperçu de la charte telle qu'elle sera appliquée au document.
 *
 * Un aplat de couleur ne dit pas grand-chose ; une maquette de bandeau de
 * chapitre, si. C'est exactement la forme que le livrable emploie.
 */
function Apercu({ marque }: { marque: Marque }) {
  const principale = marque.couleur_principale || "#3A132C";
  const fond = marque.couleur_fond || "#F1EEDB";
  const secondaire = marque.couleur_secondaire || "#B98B4E";
  return (
    <div className="apercu-charte">
      <div className="apercu-bandeau" style={{ background: principale }}>
        <span className="apercu-numero">01</span>
        <span className="apercu-titre-chapitre">Marché et périmètre</span>
      </div>
      <div className="apercu-corps" style={{ background: fond }}>
        <span className="apercu-ligne longue" />
        <span className="apercu-ligne" />
        <span
          className="apercu-accent"
          style={{ background: secondaire }}
          aria-hidden="true"
        />
      </div>
      <p className="carte-note">
        Aperçu d'un bandeau de chapitre et d'un encadré, aux couleurs saisies.
      </p>
    </div>
  );
}

export function MaMarque() {
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  // `null` tant que rien n'a été saisi : le formulaire AFFICHE alors les
  // données du serveur. Synchroniser un état local depuis un effet écraserait
  // la saisie en cours dès qu'une requête se rejoue en arrière-plan — et la
  // règle des crochets l'interdit à juste titre.
  const [saisie, setSaisie] = useState<Marque | null>(null);
  const [erreur, setErreur] = useState("");
  const [enregistre, setEnregistre] = useState(false);

  const peutModifier = peut(moi, "gerer_clients_finaux");

  const { data, isPending } = useQuery({
    queryKey: ["espace", "marque"],
    queryFn: espaceApi.marque,
  });

  const brouillon: Marque = saisie ?? data ?? VIDE;

  const depotLogo = useMutation({
    mutationFn: (fichier: File) => espaceApi.deposerFichier(fichier, "logo"),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["espace", "marque"] });
      void cache.invalidateQueries({ queryKey: ["espace", "fichiers"] });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Dépôt impossible.",
      ),
  });

  const { data: pieces } = useQuery({
    queryKey: ["espace", "fichiers", "logo"],
    queryFn: () => espaceApi.fichiers("logo"),
  });
  const logo = pieces?.pieces[0];

  const suppressionLogo = useMutation({
    mutationFn: (id: string) => espaceApi.supprimerFichier(id),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ["espace", "marque"] });
      void cache.invalidateQueries({ queryKey: ["espace", "fichiers"] });
    },
  });

  const envoi = useMutation({
    mutationFn: () => espaceApi.enregistrerMarque(brouillon),
    onSuccess: (retour) => {
      setErreur("");
      setEnregistre(true);
      setSaisie(retour);
      void cache.invalidateQueries({ queryKey: ["espace", "marque"] });
      void cache.invalidateQueries({ queryKey: ["espace", "moi"] });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Enregistrement impossible.",
      ),
  });

  function modifier(champ: keyof Marque) {
    return (evenement: React.ChangeEvent<HTMLInputElement>) => {
      setEnregistre(false);
      const valeur = evenement.target.value;
      setSaisie((precedent) => ({ ...(precedent ?? data ?? VIDE), [champ]: valeur }));
    };
  }

  if (isPending) return <Squelette lignes={6} />;

  return (
    <>
      <Carte
        titre="Votre entreprise"
        note="Ces informations identifient vos documents et orientent le choix des visuels."
      >
        {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
        <form
          onSubmit={(evenement) => {
            evenement.preventDefault();
            envoi.mutate();
          }}
          style={{ display: "flex", flexDirection: "column", gap: "var(--e-5)" }}
        >
          <div className="grille-champs">
            <Champ
              libelle="Raison sociale"
              name="raison_sociale"
              required
              disabled={!peutModifier}
              value={brouillon.raison_sociale}
              onChange={modifier("raison_sociale")}
              aide="Apparaît sur la couverture et dans l'en-tête."
            />
            <Champ
              libelle="Secteur d'activité"
              name="secteur"
              disabled={!peutModifier}
              value={brouillon.secteur}
              onChange={modifier("secteur")}
              aide="Détermine les graphiques retenus dans vos études."
            />
            <Champ
              libelle="Pays"
              name="pays"
              disabled={!peutModifier}
              value={brouillon.pays}
              onChange={modifier("pays")}
            />
            <Champ
              libelle="Région"
              name="region"
              disabled={!peutModifier}
              value={brouillon.region}
              onChange={modifier("region")}
            />
            <Champ
              libelle="Ville"
              name="ville"
              disabled={!peutModifier}
              value={brouillon.ville}
              onChange={modifier("ville")}
            />
            <Champ
              libelle="Mention de confidentialité"
              name="mention_confidentialite"
              disabled={!peutModifier}
              value={brouillon.mention_confidentialite}
              onChange={modifier("mention_confidentialite")}
              aide="Pied de page de chaque document."
            />
          </div>

          <div>
            <h3 className="carte-titre" style={{ marginBottom: "var(--e-4)" }}>
              Charte graphique
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(280px, 2fr) minmax(220px, 1fr)",
                gap: "var(--e-6)",
                alignItems: "start",
              }}
            >
              <div className="grille-champs">
                <Champ
                  libelle="Couleur principale"
                  name="couleur_principale"
                  placeholder="#3A132C"
                  disabled={!peutModifier}
                  value={brouillon.couleur_principale}
                  onChange={modifier("couleur_principale")}
                  aide="Bandeaux de chapitre et en-têtes de tableau."
                />
                <Champ
                  libelle="Couleur secondaire"
                  name="couleur_secondaire"
                  placeholder="#B98B4E"
                  disabled={!peutModifier}
                  value={brouillon.couleur_secondaire}
                  onChange={modifier("couleur_secondaire")}
                  aide="Accent des graphiques."
                />
                <Champ
                  libelle="Couleur de fond"
                  name="couleur_fond"
                  placeholder="#F1EEDB"
                  disabled={!peutModifier}
                  value={brouillon.couleur_fond}
                  onChange={modifier("couleur_fond")}
                  aide="Facultative — dérivée de la principale si vide."
                />
              </div>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "var(--e-4)" }}
              >
                {logo ? (
                  <div className="champ">
                    <span className="champ-libelle">Votre logo</span>
                    <img src={logo.url} alt="" className="apercu-logo" />
                    <span className="carte-note">
                      {logo.nom} · {poids(logo.taille_octets)}
                    </span>
                    {peutModifier && (
                      <button
                        type="button"
                        className="bouton bouton-discret bouton-sm"
                        style={{ alignSelf: "flex-start" }}
                        onClick={() => suppressionLogo.mutate(logo.id)}
                      >
                        Retirer le logo
                      </button>
                    )}
                  </div>
                ) : (
                  <ZoneDepot
                    libelle="Votre logo"
                    aide="PNG ou JPEG, 2 Mo maximum. Le SVG ne peut pas être intégré dans un Word."
                    accepte="image/png,image/jpeg"
                    tailleMax={2 * 1024 * 1024}
                    desactive={!peutModifier}
                    enCours={depotLogo.isPending}
                    onDeposer={(fichier) => depotLogo.mutate(fichier)}
                  />
                )}
                <Apercu marque={brouillon} />
              </div>
            </div>
          </div>

          {peutModifier ? (
            <div
              style={{ display: "flex", gap: "var(--e-4)", alignItems: "center" }}
            >
              <button
                type="submit"
                className="bouton bouton-principal"
                disabled={envoi.isPending}
              >
                {envoi.isPending ? "Enregistrement…" : "Enregistrer"}
              </button>
              {enregistre && (
                <span className="pastille pastille-succes">Enregistré</span>
              )}
            </div>
          ) : (
            <p className="carte-note">
              Votre rôle ne permet pas de modifier la charte. Demandez à un
              propriétaire de votre équipe.
            </p>
          )}
        </form>
      </Carte>

      <p className="carte-note">
        Si vous laissez une couleur vide, elle est dérivée de la couleur
        principale — le document reste cohérent, jamais bicolore par défaut. Le
        texte des bandeaux passe automatiquement en noir ou en blanc selon ce qui
        reste lisible sur votre couleur.
      </p>
    </>
  );
}
