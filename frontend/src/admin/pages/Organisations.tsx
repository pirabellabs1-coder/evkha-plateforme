/** Organisations : formule, solde, consommation, volumes, et actions (§10.2).
 *
 * Doter un compte, le suspendre, le réactiver se faisaient jusqu'ici dans
 * l'administration Django. C'est le seul écran du produit que personne n'a
 * choisi : il n'a pas la charte, expose tous les modèles sans distinction, et
 * oblige à comprendre la structure de la base pour créditer un client.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi, type OrganisationSupervision } from "../api";
import * as f from "../../espace/format";
import {
  Bandeau,
  Carte,
  Champ,
  Chiffre,
  Pastille,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";

type Tri = "nom" | "consommation" | "documents" | "solde";

/** Dotation et suspension pour une organisation.
 *
 * Le motif est **obligatoire** dans les deux cas : le §11 exige que chaque
 * mouvement de crédit soit journalisé avec le sien, et une suspension sans
 * raison enregistrée devient ingérable trois mois plus tard.
 */
function ActionsOrganisation({
  organisation,
  onFait,
  onErreur,
}: {
  organisation: OrganisationSupervision;
  onFait: () => void;
  onErreur: (message: string) => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [quantite, setQuantite] = useState("1");
  const [motif, setMotif] = useState("");

  const echec = (cause: unknown) =>
    onErreur(cause instanceof Error ? cause.message : "Action impossible.");

  const reussite = () => {
    setMotif("");
    setOuvert(false);
    onFait();
  };

  const dotation = useMutation({
    mutationFn: () =>
      adminApi.doter(organisation.id, {
        quantite: Number(quantite),
        motif: motif.trim(),
      }),
    onSuccess: reussite,
    onError: echec,
  });

  const statut = useMutation({
    mutationFn: (action: "suspendre" | "reactiver") =>
      adminApi.basculerStatut(organisation.id, {
        action,
        motif: motif.trim() || "Sans motif précisé",
      }),
    onSuccess: reussite,
    onError: echec,
  });

  if (!ouvert) {
    return (
      <button
        type="button"
        className="bouton bouton-contour bouton-sm"
        onClick={() => setOuvert(true)}
      >
        Agir
      </button>
    );
  }

  const active = organisation.statut === "active";
  const motifSaisi = motif.trim().length > 0;

  return (
    <div className="actions-organisation">
      <Champ
        libelle="Motif"
        name={`motif-${organisation.id}`}
        value={motif}
        onChange={(evenement) => setMotif(evenement.target.value)}
        aide="Enregistré au journal de l'organisation."
      />
      <div style={{ display: "flex", gap: "var(--e-2)", alignItems: "center" }}>
        <input
          className="champ-saisie"
          type="number"
          min={1}
          max={100}
          aria-label="Nombre de crédits à ajouter"
          style={{ width: 84 }}
          value={quantite}
          onChange={(evenement) => setQuantite(evenement.target.value)}
        />
        <button
          type="button"
          className="bouton bouton-principal bouton-sm"
          disabled={dotation.isPending || !motifSaisi}
          title={motifSaisi ? undefined : "Le motif est obligatoire."}
          onClick={() => dotation.mutate()}
        >
          Créditer
        </button>
      </div>
      <button
        type="button"
        className="bouton bouton-contour bouton-sm"
        disabled={statut.isPending || (active && !motifSaisi)}
        title={
          active && !motifSaisi
            ? "Indiquez le motif de la suspension."
            : undefined
        }
        onClick={() => statut.mutate(active ? "suspendre" : "reactiver")}
      >
        {active ? "Suspendre" : "Réactiver"}
      </button>
      <button
        type="button"
        className="bouton bouton-discret bouton-sm"
        onClick={() => setOuvert(false)}
      >
        Annuler
      </button>
    </div>
  );
}

export function OrganisationsAdmin() {
  const cache = useQueryClient();
  const [recherche, setRecherche] = useState("");
  const [tri, setTri] = useState<Tri>("consommation");
  const [erreur, setErreur] = useState("");

  const { data, isPending } = useQuery({
    queryKey: ["admin", "organisations"],
    queryFn: adminApi.organisations,
  });

  const toutes = useMemo(() => data?.organisations ?? [], [data]);

  const affichees = useMemo(() => {
    const terme = recherche.trim().toLowerCase();
    const filtrees = terme
      ? toutes.filter(
          (o) =>
            o.raison_sociale.toLowerCase().includes(terme) ||
            o.contact.toLowerCase().includes(terme),
        )
      : [...toutes];
    const comparateurs: Record<
      Tri,
      (a: OrganisationSupervision, b: OrganisationSupervision) => number
    > = {
      nom: (a, b) => a.raison_sociale.localeCompare(b.raison_sociale, "fr"),
      consommation: (a, b) => b.credits_consommes - a.credits_consommes,
      documents: (a, b) => b.documents_produits - a.documents_produits,
      solde: (a, b) => b.solde - a.solde,
    };
    return filtrees.sort(comparateurs[tri]);
  }, [toutes, recherche, tri]);

  const totalRecurrent = toutes
    .filter((o) => o.statut === "active")
    .reduce((somme, o) => somme + o.prix_mensuel_cents, 0);
  const totalSolde = toutes.reduce((somme, o) => somme + o.solde, 0);
  const totalDocuments = toutes.reduce((somme, o) => somme + o.documents_produits, 0);

  return (
    <>
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}

      <div className="grille-chiffres">
        <Chiffre
          libelle="Organisations"
          valeur={f.nombre(toutes.length)}
          detail={`${f.nombre(
            toutes.filter((o) => o.statut === "active").length,
          )} actives`}
        />
        <Chiffre
          libelle="Revenu récurrent"
          valeur={f.montant(totalRecurrent)}
          detail="Somme des formules actives"
          accent
        />
        <Chiffre
          libelle="Crédits en circulation"
          valeur={f.nombre(totalSolde)}
          detail="Tous portefeuilles confondus"
        />
        <Chiffre
          libelle="Documents produits"
          valeur={f.nombre(totalDocuments)}
          detail="Depuis l'origine"
        />
      </div>

      <Carte
        titre={`${affichees.length} organisation${affichees.length > 1 ? "s" : ""}`}
        note="Créditer un compte ou le suspendre se fait directement ici."
        action={
          <div style={{ display: "flex", gap: "var(--e-3)", flexWrap: "wrap" }}>
            <label className="champ" style={{ minWidth: 200 }}>
              <span className="visuellement-cache">Rechercher une organisation</span>
              <input
                className="champ-saisie"
                type="search"
                placeholder="Rechercher…"
                value={recherche}
                onChange={(evenement) => setRecherche(evenement.target.value)}
              />
            </label>
            <label className="champ" style={{ minWidth: 170 }}>
              <span className="visuellement-cache">Trier</span>
              <select
                className="champ-saisie"
                value={tri}
                onChange={(evenement) => setTri(evenement.target.value as Tri)}
              >
                <option value="consommation">Consommation</option>
                <option value="documents">Documents produits</option>
                <option value="solde">Solde</option>
                <option value="nom">Nom</option>
              </select>
            </label>
          </div>
        }
      >
        {isPending ? (
          <Squelette lignes={5} />
        ) : affichees.length === 0 ? (
          <Vide
            icone="◍"
            titre={recherche ? "Aucun résultat" : "Aucune organisation"}
            texte={
              recherche
                ? "Essayez un autre terme."
                : "Les organisations apparaîtront ici dès la première création."
            }
          />
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Organisation</th>
                  <th scope="col">Formule</th>
                  <th scope="col">État</th>
                  <th scope="col" style={{ textAlign: "right" }}>
                    Solde
                  </th>
                  <th scope="col" style={{ textAlign: "right" }}>
                    Consommés
                  </th>
                  <th scope="col" style={{ textAlign: "right" }}>
                    Documents
                  </th>
                  <th scope="col" style={{ textAlign: "right" }}>
                    Équipe
                  </th>
                  <th scope="col">
                    <span className="visuellement-cache">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {affichees.map((organisation) => (
                  <tr key={organisation.id}>
                    <td>
                      <strong>{organisation.raison_sociale}</strong>
                      <div className="carte-note">{organisation.contact}</div>
                    </td>
                    <td>
                      {organisation.formule || "—"}
                      {organisation.prix_mensuel_cents > 0 && (
                        <div className="carte-note">
                          {f.montant(organisation.prix_mensuel_cents)} / mois ·{" "}
                          {f.nombre(organisation.credits_par_echeance)} crédits
                        </div>
                      )}
                    </td>
                    <td>
                      <Pastille statut={organisation.statut} />
                    </td>
                    <td className="nombre">{f.nombre(organisation.solde)}</td>
                    <td className="nombre">
                      {f.nombre(organisation.credits_consommes)}
                    </td>
                    <td className="nombre">
                      {f.nombre(organisation.documents_produits)}
                    </td>
                    <td className="nombre">
                      {f.nombre(organisation.membres)}
                      <div className="carte-note">
                        {f.nombre(organisation.clients_finaux)} client
                        {organisation.clients_finaux > 1 ? "s" : ""}
                      </div>
                    </td>
                    <td>
                      <ActionsOrganisation
                        organisation={organisation}
                        onErreur={setErreur}
                        onFait={() => {
                          setErreur("");
                          void cache.invalidateQueries({ queryKey: ["admin"] });
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>

      <p className="carte-note">
        Chaque dotation est enregistrée au journal de l'organisation avec son
        motif. Une suspension empêche toute nouvelle commande ; les documents
        déjà produits restent accessibles au client.
      </p>
    </>
  );
}
