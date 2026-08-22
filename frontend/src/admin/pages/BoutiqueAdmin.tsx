/** La boutique vue de l'administration : ajouter, modifier, retirer.
 *
 * « Le catalogue s'élargit chaque mois » : c'est le seul chemin, et il ne
 * repasse ni par un développeur ni par une mise en ligne.
 *
 * ## Pourquoi un parcours en étapes, et non un formulaire
 *
 * La première version posait les seize champs d'une étude sur un seul écran.
 * Tout y était, et rien ne s'y voyait : on ne savait ni par quoi commencer, ni
 * ce qui restait à faire, ni pourquoi le bouton « Mettre en ligne » refusait.
 * Les quatre étapes suivent l'ordre dans lequel on prépare réellement une
 * étude — on la nomme et on la tarife, on écrit ce que l'acheteuse lira, on
 * dépose les fichiers, puis on relit avant de publier.
 *
 * Les valeurs vivent dans l'état de React, jamais dans le DOM du formulaire :
 * les champs d'une étape masquée sont DÉMONTÉS, et un `FormData` construit à
 * partir du formulaire perdrait tout ce qui n'est pas à l'écran. Les fichiers
 * choisis sont retenus de la même façon, dans l'état.
 *
 * Le NOMBRE DE PAGES n'est plus ni demandé ni affiché. Il se lisait comme une
 * mesure de la valeur, et il la mesure mal : trente-cinq pages utiles valent
 * mieux que soixante délayées, et deux acheteuses qui comparent deux nombres
 * comparent exactement ce qui ne compte pas. Le sommaire et l'extrait disent
 * ce que le document contient. La colonne reste en base — la retirer
 * demanderait une migration pour une donnée que plus personne ne lit.
 *
 * Un produit ne se supprime plus dès qu'il a été vendu. Le retirer se fait par
 * « hors ligne », qui préserve l'historique des ventes et l'accès de ceux qui
 * l'ont payé — ce qu'ils ont acheté reste à eux.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi, type AvisBoutique, type ProduitBoutique } from "../api";
// Les deux mêmes formateurs servent la boutique publique. Les recopier ici en
// ferait une seconde source : la copie admin de `initiale` avait déjà perdu
// « des » dans sa liste d'articles, et « Le marché des X » n'y donnait pas la
// même lettre que sur la fiche (règle 5).
import { etoiles, initiale } from "../../public/catalogue";
import "./BoutiqueAdmin.css";

function montant(cents: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

// ── Le parcours d'ajout ──────────────────────────────────────────────────────

const ETAPES = [
  {
    titre: "L'étude",
    aide: "Son nom, son thème et son prix.",
  },
  {
    titre: "Le contenu",
    aide: "Ce que l'acheteuse lira avant de payer.",
  },
  {
    titre: "Les fichiers",
    aide: "La couverture, le document remis et l'extrait.",
  },
  {
    titre: "Vérification",
    aide: "Un dernier regard, puis la mise en ligne.",
  },
] as const;

type ChampsFichiers = {
  fichier: File | null;
  fichier_editable: File | null;
  extrait: File | null;
  image: File | null;
};

function Pipeline({
  etape,
  atteinte,
  aller,
}: {
  etape: number;
  atteinte: number;
  aller: (n: number) => void;
}) {
  return (
    <ol className="bqa-pipeline" aria-label="Étapes de l'ajout">
      {ETAPES.map((e, index) => {
        const etat =
          index < etape ? "faite" : index === etape ? "courante" : "a-venir";
        return (
          <li key={e.titre} className={`bqa-etape bqa-etape-${etat}`}>
            <button
              type="button"
              // Revenir en arrière est toujours permis ; sauter en avant sur
              // une étape jamais atteinte ne l'est pas — on n'a pas encore
              // vérifié ce qui la précède.
              disabled={index > atteinte}
              onClick={() => aller(index)}
              aria-current={index === etape ? "step" : undefined}
            >
              <span className="bqa-etape-puce" aria-hidden="true">
                {index < etape ? "✓" : index + 1}
              </span>
              <span className="bqa-etape-texte">
                <span className="bqa-etape-titre">{e.titre}</span>
                <span className="bqa-etape-aide">{e.aide}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function ChampFichier({
  libelle,
  aide,
  accept,
  fichier,
  deja,
  onChange,
}: {
  libelle: string;
  aide: string;
  accept: string;
  fichier: File | null;
  deja?: string;
  onChange: (f: File | null) => void;
}) {
  return (
    <label className="bqa-depot">
      <span className="bqa-depot-titre">{libelle}</span>
      <span className="bqa-depot-aide">{aide}</span>
      <input
        type="file"
        accept={accept}
        onChange={(evenement) => onChange(evenement.currentTarget.files?.[0] ?? null)}
      />
      {fichier ? (
        <span className="bqa-depot-etat bqa-depot-neuf">{fichier.name}</span>
      ) : deja ? (
        <span className="bqa-depot-etat">déjà déposé — le remplacer ?</span>
      ) : (
        <span className="bqa-depot-etat bqa-depot-vide">aucun fichier</span>
      )}
    </label>
  );
}

function Assistant({
  produit,
  onFini,
  onAnnuler,
}: {
  produit?: ProduitBoutique;
  onFini: () => void;
  onAnnuler: () => void;
}) {
  const [etape, setEtape] = useState(0);
  // La plus haute étape déjà franchie : elle seule autorise un saut en avant
  // dans le fil. En modification, tout est déjà rempli — on ouvre le fil
  // entier plutôt que de faire recliquer quatre fois pour changer un prix.
  const [atteinte, setAtteinte] = useState(produit ? ETAPES.length - 1 : 0);
  const [erreur, setErreur] = useState("");

  const [titre, setTitre] = useState(produit?.titre ?? "");
  const [prix, setPrix] = useState(produit ? String(produit.prix_cents / 100) : "");
  const [theme, setTheme] = useState(produit?.theme ?? "");
  const [miseAJour, setMiseAJour] = useState(produit?.mise_a_jour ?? "");
  const [description, setDescription] = useState(produit?.description ?? "");
  const [sommaire, setSommaire] = useState(produit?.sommaire ?? "");
  const [fichiers, setFichiers] = useState<ChampsFichiers>({
    fichier: null,
    fichier_editable: null,
    extrait: null,
    image: null,
  });

  // L'aperçu de la couverture. DÉRIVÉ du fichier choisi, et non posé dans un
  // état depuis un effet : l'adresse est une pure fonction du fichier, et la
  // recopier dans l'état ferait un rendu en cascade à chaque choix.
  // L'effet ne sert plus qu'à relâcher l'adresse — chaque `createObjectURL`
  // retient son fichier en mémoire jusqu'à ce qu'on la révoque.
  const apercu = useMemo(
    () => (fichiers.image ? URL.createObjectURL(fichiers.image) : ""),
    [fichiers.image],
  );
  useEffect(() => {
    if (!apercu) return;
    return () => URL.revokeObjectURL(apercu);
  }, [apercu]);

  const prixCents = Math.max(0, Math.round(Number(prix.replace(",", ".")) * 100) || 0);
  const aUnFichier = Boolean(fichiers.fichier || produit?.fichier);
  const manque = [
    ...(prixCents > 0 ? [] : ["un prix"]),
    ...(aUnFichier ? [] : ["le document à remettre"]),
  ];

  const envoi = useMutation({
    mutationFn: async (enLigne: boolean | null) => {
      const donnees = new FormData();
      donnees.set("titre", titre.trim());
      donnees.set("prix_euros", prix.replace(",", "."));
      donnees.set("theme", theme.trim());
      donnees.set("mise_a_jour", miseAJour);
      donnees.set("description", description);
      donnees.set("sommaire", sommaire);
      for (const [champ, valeur] of Object.entries(fichiers)) {
        if (valeur) donnees.set(champ, valeur);
      }
      if (enLigne !== null) donnees.set("en_ligne", enLigne ? "true" : "false");

      return produit
        ? adminApi.modifierLeProduit(produit.id, donnees)
        : adminApi.creerUnProduit(donnees);
    },
    onSuccess: () => {
      setErreur("");
      onFini();
    },
    onError: (cause: unknown) =>
      setErreur(cause instanceof Error ? cause.message : "Enregistrement impossible."),
  });

  function suivant() {
    if (etape === 0) {
      if (!titre.trim()) {
        setErreur("Donnez un titre à l'étude : c'est lui qui la nomme partout.");
        return;
      }
      if (prixCents <= 0) {
        setErreur(
          "Indiquez le prix. Une étude à zéro euro ouvrirait un paiement de " +
            "zéro, accepté par Stripe, et le document partirait sans contrepartie.",
        );
        return;
      }
    }
    setErreur("");
    const prochaine = Math.min(ETAPES.length - 1, etape + 1);
    setEtape(prochaine);
    setAtteinte((haute) => Math.max(haute, prochaine));
  }

  return (
    <section className="bqa-assistant">
      <header className="bqa-assistant-entete">
        <div>
          <h3>{produit ? "Modifier l'étude" : "Ajouter une étude"}</h3>
          <p className="bqa-assistant-sous">
            Étape {etape + 1} sur {ETAPES.length} — {ETAPES[etape].aide}
          </p>
        </div>
        <button type="button" className="bqa-fermer" onClick={onAnnuler} aria-label="Fermer">
          ✕
        </button>
      </header>

      <Pipeline
        etape={etape}
        atteinte={atteinte}
        aller={(n) => {
          setErreur("");
          setEtape(n);
        }}
      />

      {erreur && (
        <p className="bqa-erreur" role="alert">
          {erreur}
        </p>
      )}

      <div className="bqa-panneau">
        {etape === 0 && (
          <div className="bqa-champs">
            <label className="bqa-champ bqa-large">
              <span>Titre de l'étude</span>
              <input
                value={titre}
                onChange={(e) => setTitre(e.currentTarget.value)}
                placeholder="Le marché des foodtrucks en 2026"
                autoFocus
              />
            </label>
            <label className="bqa-champ">
              <span>Prix en euros</span>
              <input
                type="number"
                min={0}
                step="1"
                value={prix}
                onChange={(e) => setPrix(e.currentTarget.value)}
                placeholder="89"
              />
            </label>
            <label className="bqa-champ">
              <span>Thème</span>
              <input
                value={theme}
                onChange={(e) => setTheme(e.currentTarget.value)}
                placeholder="Restauration, Services…"
              />
              <small>Il regroupe les études proches sur la fiche.</small>
            </label>
            <label className="bqa-champ">
              <span>Dernière mise à jour</span>
              <input
                type="date"
                value={miseAJour}
                onChange={(e) => setMiseAJour(e.currentTarget.value)}
              />
              <small>Affichée sur la fiche : « Mise à jour en mars 2026 ».</small>
            </label>
          </div>
        )}

        {etape === 1 && (
          <div className="bqa-champs">
            <label className="bqa-champ bqa-large">
              <span>Description</span>
              <textarea
                rows={6}
                value={description}
                onChange={(e) => setDescription(e.currentTarget.value)}
                placeholder="Ce que contient l'étude, à qui elle s'adresse, ce qu'elle permet de décider."
                autoFocus
              />
              <small>{description.trim().length} caractères.</small>
            </label>
            <label className="bqa-champ bqa-large">
              <span>Sommaire — une entrée par ligne</span>
              <textarea
                rows={7}
                value={sommaire}
                onChange={(e) => setSommaire(e.currentTarget.value)}
                placeholder={"Taille du marché et croissance\nProfil des clients\nRéglementation"}
              />
              <small>
                {sommaire.split("\n").filter((l) => l.trim()).length} entrée(s).
              </small>
            </label>
          </div>
        )}

        {etape === 2 && (
          <div className="bqa-fichiers">
            <div className="bqa-couverture">
              {apercu || produit?.image ? (
                <img src={apercu || produit?.image} alt="Aperçu de la couverture" />
              ) : (
                <span className="bqa-couverture-vide">{initiale(titre) || "?"}</span>
              )}
            </div>
            <div className="bqa-depots">
              <ChampFichier
                libelle="Image de couverture"
                aide="Elle porte la carte en boutique. Format paysage, 1200 × 800 environ."
                accept="image/*"
                fichier={fichiers.image}
                deja={produit?.image}
                onChange={(f) => setFichiers((v) => ({ ...v, image: f }))}
              />
              <ChampFichier
                libelle="Le document remis (PDF)"
                aide="Ce que l'acheteuse télécharge. Sans lui, l'étude ne peut pas être mise en ligne."
                accept=".pdf"
                fichier={fichiers.fichier}
                deja={produit?.fichier}
                onChange={(f) => setFichiers((v) => ({ ...v, fichier: f }))}
              />
              <ChampFichier
                libelle="Version Word (facultatif)"
                aide="Remise en plus du PDF, pour qui veut reprendre le document."
                accept=".doc,.docx"
                fichier={fichiers.fichier_editable}
                deja={produit?.fichier_editable}
                onChange={(f) => setFichiers((v) => ({ ...v, fichier_editable: f }))}
              />
              <ChampFichier
                libelle="Extrait consultable (facultatif)"
                aide="Quelques pages ouvertes avant l'achat. C'est ce qui rassure le plus."
                accept=".pdf"
                fichier={fichiers.extrait}
                deja={produit?.extrait}
                onChange={(f) => setFichiers((v) => ({ ...v, extrait: f }))}
              />
            </div>
          </div>
        )}

        {etape === 3 && (
          <div className="bqa-recap">
            <div className="bqa-recap-carte">
              <div className="bqa-recap-image">
                {apercu || produit?.image ? (
                  <img src={apercu || produit?.image} alt="" />
                ) : (
                  <span>{initiale(titre) || "?"}</span>
                )}
              </div>
              <div className="bqa-recap-corps">
                <p className="bqa-recap-titre">{titre || "Sans titre"}</p>
                <p className="bqa-recap-note">
                  {montant(prixCents)}
                  {theme ? ` · ${theme}` : ""}
                </p>
              </div>
            </div>

            <dl className="bqa-recap-liste">
              <div>
                <dt>Description</dt>
                <dd>
                  {description.trim()
                    ? `${description.trim().length} caractères`
                    : "aucune — la fiche paraîtra vide"}
                </dd>
              </div>
              <div>
                <dt>Sommaire</dt>
                <dd>
                  {sommaire.split("\n").filter((l) => l.trim()).length || "aucune"} entrée(s)
                </dd>
              </div>
              <div>
                <dt>Document remis</dt>
                <dd>{aUnFichier ? "déposé" : "manquant"}</dd>
              </div>
              <div>
                <dt>Extrait</dt>
                <dd>{fichiers.extrait || produit?.extrait ? "déposé" : "aucun"}</dd>
              </div>
              <div>
                <dt>Version Word</dt>
                <dd>
                  {fichiers.fichier_editable || produit?.fichier_editable
                    ? "déposée"
                    : "aucune"}
                </dd>
              </div>
              <div>
                <dt>Couverture</dt>
                <dd>{fichiers.image || produit?.image ? "déposée" : "aucune"}</dd>
              </div>
            </dl>

            {manque.length > 0 && (
              <p className="bqa-manque">
                Il manque {manque.join(" et ")} : l'étude sera enregistrée{" "}
                <b>hors ligne</b>, et pourra être publiée dès que ce sera complété.
              </p>
            )}
          </div>
        )}
      </div>

      <footer className="bqa-assistant-pied">
        <button
          type="button"
          className="bouton bouton-discret"
          onClick={() => (etape === 0 ? onAnnuler() : setEtape(etape - 1))}
        >
          {etape === 0 ? "Annuler" : "Précédent"}
        </button>

        {etape < ETAPES.length - 1 ? (
          <button type="button" className="bouton" onClick={suivant}>
            Suivant
          </button>
        ) : (
          <div className="bqa-final">
            <button
              type="button"
              className="bouton bouton-contour"
              disabled={envoi.isPending}
              onClick={() => envoi.mutate(produit ? null : false)}
            >
              {envoi.isPending ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button
              type="button"
              className="bouton"
              disabled={envoi.isPending || manque.length > 0}
              onClick={() => envoi.mutate(true)}
            >
              Enregistrer et mettre en ligne
            </button>
          </div>
        )}
      </footer>
    </section>
  );
}

// ── Les avis d'une étude ─────────────────────────────────────────────────────

function Avis({
  produit,
  onChange,
  onErreur,
}: {
  produit: ProduitBoutique;
  onChange: () => void;
  onErreur: (message: string) => void;
}) {
  const [auteur, setAuteur] = useState("");
  const [qualite, setQualite] = useState("");
  const [note, setNote] = useState(5);
  const [texte, setTexte] = useState("");

  const echoue = (cause: unknown) =>
    onErreur(cause instanceof Error ? cause.message : "Action impossible.");

  const ajout = useMutation({
    mutationFn: () => {
      const donnees = new FormData();
      donnees.set("auteur", auteur.trim());
      donnees.set("qualite", qualite.trim());
      donnees.set("note", String(note));
      donnees.set("texte", texte.trim());
      return adminApi.ajouterUnAvis(produit.id, donnees);
    },
    onSuccess: () => {
      setAuteur("");
      setQualite("");
      setTexte("");
      setNote(5);
      onChange();
    },
    onError: echoue,
  });

  const bascule = useMutation({
    mutationFn: ({ id, publie }: { id: string; publie: boolean }) =>
      adminApi.publierUnAvis(id, publie),
    onSuccess: onChange,
    onError: echoue,
  });

  const retrait = useMutation({
    mutationFn: (id: string) => adminApi.supprimerUnAvis(id),
    onSuccess: onChange,
    onError: echoue,
  });

  return (
    <div className="bqa-avis">
      <ul className="bqa-avis-liste">
        {produit.avis.length === 0 && (
          <li className="bqa-avis-vide">
            Aucun avis. Un témoignage vaut plus qu'un argument : ajoutez celui
            d'une lectrice.
          </li>
        )}
        {produit.avis.map((a: AvisBoutique) => (
          <li key={a.id} className={a.publie ? "" : "bqa-avis-cache"}>
            <div>
              <p className="bqa-avis-tete">
                <span className="bqa-avis-etoiles" aria-label={`${a.note} sur 5`}>
                  {etoiles(a.note)}
                </span>
                <b>{a.auteur}</b>
                {a.qualite && <span className="bqa-avis-qualite">{a.qualite}</span>}
                {!a.publie && <span className="bqa-avis-etat">non publié</span>}
              </p>
              {a.texte && <p className="bqa-avis-texte">{a.texte}</p>}
            </div>
            <div className="bqa-avis-actions">
              <button
                type="button"
                className="bouton bouton-discret bouton-sm"
                onClick={() => bascule.mutate({ id: a.id, publie: !a.publie })}
              >
                {a.publie ? "Retirer" : "Publier"}
              </button>
              <button
                type="button"
                className="bouton bouton-discret bouton-sm"
                onClick={() => retrait.mutate(a.id)}
              >
                Supprimer
              </button>
            </div>
          </li>
        ))}
      </ul>

      <form
        className="bqa-avis-formulaire"
        onSubmit={(evenement) => {
          evenement.preventDefault();
          if (!auteur.trim()) {
            onErreur("Donnez le nom de la personne qui témoigne.");
            return;
          }
          ajout.mutate();
        }}
      >
        <input
          value={auteur}
          onChange={(e) => setAuteur(e.currentTarget.value)}
          placeholder="Prénom et nom"
          aria-label="Auteur de l'avis"
        />
        <input
          value={qualite}
          onChange={(e) => setQualite(e.currentTarget.value)}
          placeholder="Restauratrice, Lyon"
          aria-label="Qualité de l'auteur"
        />
        <select
          value={note}
          onChange={(e) => setNote(Number(e.currentTarget.value))}
          aria-label="Note"
        >
          {[5, 4, 3, 2, 1].map((n) => (
            <option key={n} value={n}>
              {etoiles(n)}
            </option>
          ))}
        </select>
        <input
          className="bqa-avis-texte-champ"
          value={texte}
          onChange={(e) => setTexte(e.currentTarget.value)}
          placeholder="Ce qu'elle en a retiré, en une phrase."
          aria-label="Texte de l'avis"
        />
        <button type="submit" className="bouton bouton-sm" disabled={ajout.isPending}>
          Ajouter
        </button>
      </form>
    </div>
  );
}

// ── La carte d'une étude ─────────────────────────────────────────────────────

function Carte({
  produit,
  onModifier,
  onBasculer,
  onSupprimer,
  onChange,
  onErreur,
  occupe,
}: {
  produit: ProduitBoutique;
  onModifier: () => void;
  onBasculer: () => void;
  onSupprimer: () => void;
  onChange: () => void;
  onErreur: (message: string) => void;
  occupe: boolean;
}) {
  const [avisOuverts, setAvisOuverts] = useState(false);
  const publies = produit.avis.filter((a) => a.publie).length;

  return (
    <li className={`bqa-carte ${produit.en_ligne ? "" : "bqa-carte-hors-ligne"}`}>
      <div className="bqa-carte-image">
        {produit.image ? (
          <img src={produit.image} alt="" loading="lazy" />
        ) : (
          <span className="bqa-carte-initiale">{initiale(produit.titre)}</span>
        )}
        <span className={`bqa-fanion ${produit.en_ligne ? "bqa-fanion-vif" : ""}`}>
          {produit.en_ligne ? "en ligne" : "hors ligne"}
        </span>
      </div>

      <div className="bqa-carte-corps">
        <h3>{produit.titre}</h3>
        <p className="bqa-carte-meta">
          <b>{montant(produit.prix_cents)}</b>
          {produit.theme && <span>{produit.theme}</span>}
        </p>

        <dl className="bqa-mesures">
          <div>
            <dt>Ventes</dt>
            <dd>{produit.ventes}</dd>
          </div>
          <div>
            <dt>Recette</dt>
            <dd>{montant(produit.recette_cents)}</dd>
          </div>
          <div>
            <dt>Avis</dt>
            {/* Les avis PUBLIÉS, parce que la note n'est calculée que sur
                ceux-là : compter tous les avis en face d'elle affichait
                « 0,0 · 1 » dès qu'on retirait le seul avis publié. Le total,
                brouillons compris, reste sur le bouton « Avis (n) ». */}
            <dd>
              {publies === 0 ? "—" : `${produit.note.toFixed(1)} · ${publies}`}
            </dd>
          </div>
        </dl>

        {produit.manque.length > 0 && (
          <p className="bqa-carte-manque">
            Il manque {produit.manque.join(" et ")} pour pouvoir la mettre en ligne.
          </p>
        )}

        <div className="bqa-carte-boutons">
          <button type="button" className="bouton bouton-contour bouton-sm" onClick={onModifier}>
            Modifier
          </button>
          <button
            type="button"
            className="bouton bouton-discret bouton-sm"
            disabled={occupe || (!produit.en_ligne && !produit.publiable)}
            onClick={onBasculer}
          >
            {produit.en_ligne ? "Retirer" : "Mettre en ligne"}
          </button>
          <button
            type="button"
            className="bouton bouton-discret bouton-sm"
            onClick={() => setAvisOuverts((ouvert) => !ouvert)}
            aria-expanded={avisOuverts}
          >
            Avis ({produit.avis.length})
          </button>
          {produit.ventes === 0 && (
            <button
              type="button"
              className="bouton bouton-discret bouton-sm"
              disabled={occupe}
              onClick={onSupprimer}
            >
              Supprimer
            </button>
          )}
        </div>

        {avisOuverts && (
          <Avis produit={produit} onChange={onChange} onErreur={onErreur} />
        )}
      </div>
    </li>
  );
}

// ── La page ──────────────────────────────────────────────────────────────────

export function BoutiqueAdmin() {
  const cache = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["admin", "boutique"],
    queryFn: adminApi.produitsBoutique,
  });
  const [edite, setEdite] = useState<ProduitBoutique | null>(null);
  const [ajoute, setAjoute] = useState(false);
  const [erreur, setErreur] = useState("");
  const [filtre, setFiltre] = useState<"toutes" | "en-ligne" | "hors-ligne">("toutes");

  const rafraichir = () => {
    void cache.invalidateQueries({ queryKey: ["admin", "boutique"] });
    setEdite(null);
    setAjoute(false);
  };

  const bascule = useMutation({
    mutationFn: ({ id, enLigne }: { id: string; enLigne: boolean }) => {
      const donnees = new FormData();
      donnees.set("en_ligne", enLigne ? "true" : "false");
      return adminApi.modifierLeProduit(id, donnees);
    },
    onSuccess: rafraichir,
    onError: (cause: unknown) =>
      setErreur(cause instanceof Error ? cause.message : "Modification impossible."),
  });

  const supprime = useMutation({
    mutationFn: (id: string) => adminApi.supprimerLeProduit(id),
    onSuccess: rafraichir,
    onError: (cause: unknown) =>
      setErreur(cause instanceof Error ? cause.message : "Suppression impossible."),
  });

  const produits = useMemo(() => data?.produits ?? [], [data]);
  const visibles = produits.filter((p) =>
    filtre === "toutes" ? true : filtre === "en-ligne" ? p.en_ligne : !p.en_ligne,
  );
  const enLigne = produits.filter((p) => p.en_ligne).length;
  const recette = produits.reduce((somme, p) => somme + p.recette_cents, 0);
  const ventes = produits.reduce((somme, p) => somme + p.ventes, 0);
  const vendues = produits.filter((p) => p.ventes > 0).length;

  if (isPending) return <p>Chargement…</p>;

  return (
    <section className="bqa">
      <header className="bqa-entete">
        <dl className="bqa-chiffres">
          <div>
            <dt>Au catalogue</dt>
            <dd>{produits.length}</dd>
            <span className="bqa-chiffres-detail">
              {produits.length - enLigne} en préparation
            </span>
          </div>
          <div>
            <dt>En ligne</dt>
            <dd>{enLigne}</dd>
            <span className="bqa-chiffres-detail">visibles en boutique</span>
          </div>
          <div>
            <dt>Ventes</dt>
            <dd>{ventes}</dd>
            <span className="bqa-chiffres-detail">
              {ventes === 0
                ? "aucune pour l'instant"
                : `sur ${vendues} étude${vendues > 1 ? "s" : ""}`}
            </span>
          </div>
          <div>
            <dt>Recette</dt>
            <dd>{montant(recette)}</dd>
            <span className="bqa-chiffres-detail">
              {ventes === 0 ? "—" : `${montant(Math.round(recette / ventes))} en moyenne`}
            </span>
          </div>
        </dl>
        {!ajoute && !edite && (
          <button
            type="button"
            className="bouton"
            onClick={() => {
              setErreur("");
              setAjoute(true);
            }}
          >
            Ajouter une étude
          </button>
        )}
      </header>

      {erreur && (
        <p className="bqa-erreur" role="alert">
          {erreur}
        </p>
      )}

      {(ajoute || edite) && (
        <Assistant
          key={edite?.id ?? "nouvelle"}
          produit={edite ?? undefined}
          onFini={rafraichir}
          onAnnuler={() => {
            setEdite(null);
            setAjoute(false);
          }}
        />
      )}

      {!ajoute && !edite && (
        <div className="bqa-filtres" role="group" aria-label="Filtrer le catalogue">
          {(
            [
              ["toutes", `Toutes (${produits.length})`],
              ["en-ligne", `En ligne (${enLigne})`],
              ["hors-ligne", `Hors ligne (${produits.length - enLigne})`],
            ] as const
          ).map(([cle, libelle]) => (
            <button
              key={cle}
              type="button"
              className={`bqa-filtre ${filtre === cle ? "bqa-filtre-actif" : ""}`}
              onClick={() => setFiltre(cle)}
            >
              {libelle}
            </button>
          ))}
        </div>
      )}

      {produits.length === 0 && !ajoute && (
        <p className="carte-note">Aucune étude. Ajoutez-en une pour ouvrir la boutique.</p>
      )}

      <ul className="bqa-grille">
        {visibles.map((p) => (
          <Carte
            key={p.id}
            produit={p}
            occupe={bascule.isPending || supprime.isPending}
            onModifier={() => {
              setErreur("");
              setAjoute(false);
              setEdite(p);
            }}
            onBasculer={() => {
              setErreur("");
              bascule.mutate({ id: p.id, enLigne: !p.en_ligne });
            }}
            onSupprimer={() => {
              setErreur("");
              supprime.mutate(p.id);
            }}
            onChange={() => void cache.invalidateQueries({ queryKey: ["admin", "boutique"] })}
            onErreur={setErreur}
          />
        ))}
      </ul>
    </section>
  );
}
