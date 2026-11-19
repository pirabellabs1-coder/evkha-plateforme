"""Adresses vérifiées et dédoublonnage solide (audit du 19/11/2026).

Quatre défauts d'une même famille — ce que la recherche enregistre sans le
regarder :

- l'adresse rendue par le modèle était stockée telle quelle (« non communiqué »
  devenait une adresse, et la fiche n'était plus enrichie) ;
- faute d'adresse au domaine du site, `_email_par_site` prenait n'importe
  quelle adresse vue sur la page (agence web, hébergeur) ;
- le dédoublonnage comparait les raisons sociales à la casse près seulement
  (« BGE Hauts-de-France » et « BGE Hauts de France » : deux fiches) et ignorait
  le site ;
- l'enrichissement — payant — tournait AVANT le dédoublonnage, y compris pour
  les fiches qu'on écartait ensuite.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from prospection import agents
from prospection.models import Campagne, Prospect

from integrations.claude import StructuredResult
from integrations.search import SearchResponse, SearchResult

pytestmark = pytest.mark.django_db


def _campagne() -> Campagne:
    return Campagne.objects.create(nom="Réseaux Lille", secteur="Accompagnement", zone="Lille")


class _ClientFaux:
    def __init__(self, charges: dict[str, dict[str, Any]]) -> None:
        self._charges = charges
        self.appels: list[str] = []

    def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
        self.appels.append(outil_nom)
        return StructuredResult(payload=dict(self._charges.get(outil_nom, {})),
                                input_tokens=1, output_tokens=1, model="claude-opus")


class _RechercheEspionne:
    """Rend des extraits figés ; note chaque requête (une par enrichissement)."""

    def __init__(self, contenu: str = "…", url: str = "https://annuaire.fr/x") -> None:
        self._contenu, self._url = contenu, url
        self.requetes: list[str] = []

    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        self.requetes.append(query)
        return SearchResponse(
            query=query, results=(SearchResult(title="T", url=self._url, content=self._contenu),)
        )

    @property
    def enrichissements(self) -> list[str]:
        return [r for r in self.requetes if r.endswith("email contact")]


# ── L'adresse doit avoir la forme d'une adresse ──────────────────────────────


@pytest.mark.parametrize(
    "rendu",
    ["non communiqué", "N/A", "contact", "contact@", "@alpha.fr", "voir le site",
     "contact [at] alpha.fr", "contact@alpha"],
)
def test_ce_qui_n_a_pas_la_forme_d_une_adresse_n_est_jamais_enregistre(rendu: str) -> None:
    """Sur le code d'avant : la chaîne du modèle était stockée telle quelle."""
    crees = agents._creer_les_prospects(
        _campagne(), [{"raison_sociale": "Alpha", "email": rendu}], 10
    )

    assert len(crees) == 1  # la fiche est créée — SANS adresse
    assert Prospect.objects.get().email == ""


@pytest.mark.parametrize(
    ("rendu", "attendu"),
    [
        ("contact@alpha.fr", "contact@alpha.fr"),
        (" Contact@Alpha.FR ", "contact@alpha.fr"),
        ("Email : contact@alpha.fr", "contact@alpha.fr"),
        ("prenom.nom+pro@sous.alpha-conseil.fr", "prenom.nom+pro@sous.alpha-conseil.fr"),
    ],
)
def test_une_vraie_adresse_est_gardee_et_normalisee(rendu: str, attendu: str) -> None:
    """Contre-épreuve : le filtre ne jette pas ce qui est correct."""
    agents._creer_les_prospects(_campagne(), [{"raison_sociale": "Alpha", "email": rendu}], 10)

    assert Prospect.objects.get().email == attendu


def test_une_adresse_factice_du_modele_n_empeche_plus_l_enrichissement() -> None:
    """« non communiqué » valait « adresse connue » : la fiche n'était pas enrichie."""
    recherche = _RechercheEspionne(contenu="Écrire à contact@alpha.fr", url="https://alpha.fr")
    client = _ClientFaux({"extraire_prospects": {"prospects": [
        {"raison_sociale": "Alpha", "email": "non communiqué", "site_web": "https://alpha.fr"},
    ]}})

    agents.rechercher_des_prospects(_campagne(), recherche=recherche, client=client)

    assert Prospect.objects.get().email == "contact@alpha.fr"


# ── L'adresse lue sur un site doit être celle du site ────────────────────────


def _faux_httpx(monkeypatch: pytest.MonkeyPatch, pages: dict[str, str], hote: str) -> list[str]:
    """Remplace `httpx` par un module factice : aucun réseau. Rend les URL demandées."""
    demandes: list[str] = []

    def get(url: str, **_: Any) -> Any:
        demandes.append(url)
        chemin = url.split(hote, 1)[-1].strip("/")
        return types.SimpleNamespace(
            text=pages.get(chemin, ""), url=types.SimpleNamespace(host=hote)
        )

    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(get=get))
    return demandes


def test_le_site_ne_rend_pas_l_adresse_de_son_agence_web(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sur le code d'avant : `candidats[0]` — la première adresse vue, quelle qu'elle soit."""
    demandes = _faux_httpx(
        monkeypatch,
        {"": "Site réalisé par contact@agence-web.fr — hébergé par abuse@ovh.net",
         "mentions-legales": "Hébergeur : abuse@ovh.net"},
        "cabinet-dupont.fr",
    )

    assert agents._email_par_site("https://www.cabinet-dupont.fr") == ""
    assert demandes, "le site a bien été parcouru : le vide est un résultat, pas un oubli"


def test_un_domaine_contenu_dans_un_autre_n_est_pas_le_meme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """« lille.fr » est une sous-chaîne d'« agence-lille.fr » : le test d'inclusion
    du code d'avant prenait l'adresse de l'agence pour celle de la mairie."""
    _faux_httpx(monkeypatch, {"": "Création : contact@agence-lille.fr"}, "lille.fr")

    assert agents._email_par_site("https://lille.fr") == ""


def test_le_site_rend_son_adresse_meme_citee_apres_les_autres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve : l'adresse AU DOMAINE du site est trouvée, où qu'elle soit."""
    _faux_httpx(
        monkeypatch,
        {"": "Réalisé par contact@agence-web.fr",
         "contact": "Nous écrire : Accueil@Cabinet-Dupont.fr ou abuse@ovh.net"},
        "cabinet-dupont.fr",
    )

    assert agents._email_par_site("https://www.cabinet-dupont.fr") == "accueil@cabinet-dupont.fr"


def test_un_sous_domaine_du_site_est_bien_au_domaine(monkeypatch: pytest.MonkeyPatch) -> None:
    _faux_httpx(monkeypatch, {"": "contact@mail.cabinet-dupont.fr"}, "cabinet-dupont.fr")

    assert agents._email_par_site("cabinet-dupont.fr") == "contact@mail.cabinet-dupont.fr"


# ── L'adresse lue dans des extraits de recherche ─────────────────────────────


def test_la_recherche_ne_prend_pas_d_office_l_adresse_d_un_annuaire() -> None:
    """Une adresse hors du domaine du site ne se prend pas à l'aveugle : le modèle
    désigne, et sa réponse doit FIGURER dans les extraits."""
    recherche = _RechercheEspionne(contenu="Annuaire : webmaster@annuaire.fr")

    invente = agents._email_par_recherche(
        "Alpha", "Lille", recherche, _ClientFaux({"extraire_email": {"email": "contact@alpha.fr"}}),
        site="https://alpha.fr",
    )
    ecarte = agents._email_par_recherche(
        "Alpha", "Lille", recherche, _ClientFaux({"extraire_email": {"email": ""}}),
        site="https://alpha.fr",
    )
    designe = agents._email_par_recherche(
        "Alpha", "Lille", _RechercheEspionne(contenu="Alpha : alpha.conseil@gmail.com"),
        _ClientFaux({"extraire_email": {"email": "alpha.conseil@gmail.com"}}),
        site="https://alpha.fr",
    )

    assert invente == "", "une adresse absente des extraits est une invention"
    assert ecarte == "", "le modèle a jugé que l'adresse de l'annuaire n'est pas la bonne"
    assert designe == "alpha.conseil@gmail.com"


def test_sans_adresse_dans_les_extraits_le_modele_n_est_pas_paye() -> None:
    client = _ClientFaux({"extraire_email": {"email": "contact@alpha.fr"}})

    adresse = agents._email_par_recherche(
        "Alpha", "Lille", _RechercheEspionne(contenu="Aucune coordonnée ici."), client
    )

    assert adresse == "" and client.appels == []


# ── Dédoublonnage : nom normalisé, site ──────────────────────────────────────


@pytest.mark.parametrize(
    "variante",
    ["BGE Hauts de France", "bge hauts-de-france", "BGE  Hauts‑de‑France",
     "B.G.E. Hauts-de-France", "BGÉ Hauts de France"],
)
def test_la_meme_organisation_ecrite_autrement_n_est_pas_recreee(variante: str) -> None:
    """Sur le code d'avant : comparaison à la casse près — une seconde fiche."""
    campagne = _campagne()
    Prospect.objects.create(campagne=campagne, raison_sociale="BGE Hauts-de-France")

    crees = agents._creer_les_prospects(campagne, [{"raison_sociale": variante}], 10)

    assert crees == []
    assert Prospect.objects.filter(campagne=campagne).count() == 1


def test_le_meme_site_designe_la_meme_organisation() -> None:
    """Sur le code d'avant : le site n'entrait pas dans le dédoublonnage."""
    campagne = _campagne()
    Prospect.objects.create(
        campagne=campagne, raison_sociale="Cabinet Dupont",
        site_web="https://www.cabinet-dupont.fr/",
    )

    crees = agents._creer_les_prospects(
        campagne, [{"raison_sociale": "Dupont & Associés", "site_web": "cabinet-dupont.fr"}], 10
    )

    assert crees == []


def test_deux_antennes_d_un_reseau_restent_deux_organisations() -> None:
    """Contre-épreuve : même hôte, PAGES différentes — et noms différents.

    Les cibles n°1 d'EVKHA sont des réseaux ; fondre leurs antennes sur le seul
    hôte écarterait de vraies cibles.
    """
    campagne = _campagne()

    crees = agents._creer_les_prospects(
        campagne,
        [
            {"raison_sociale": "Initiative Lille", "site_web":
                "https://www.initiative-france.fr/reseau/lille"},
            {"raison_sociale": "Initiative Lens", "site_web":
                "https://www.initiative-france.fr/reseau/lens"},
            {"raison_sociale": "BGE Flandre Création"},
        ],
        10,
    )

    assert {p.raison_sociale for p in crees} == {
        "Initiative Lille", "Initiative Lens", "BGE Flandre Création",
    }


def test_le_dedoublonnage_precede_l_enrichissement() -> None:
    """Sur le code d'avant : une recherche d'adresse par fiche RENDUE (trois ici),
    doublons compris — payée pour des fiches écartées juste après."""
    campagne = _campagne()
    Prospect.objects.create(campagne=campagne, raison_sociale="BGE Hauts-de-France")
    Prospect.objects.create(campagne=campagne, raison_sociale="Initiative Lille")
    recherche = _RechercheEspionne()
    client = _ClientFaux({"extraire_prospects": {"prospects": [
        {"raison_sociale": "BGE Hauts de France"},   # doublon
        {"raison_sociale": "INITIATIVE LILLE"},      # doublon
        {"raison_sociale": "Réseau Entreprendre Nord"},
    ]}})

    bilan = agents.rechercher_avec_bilan(campagne, recherche=recherche, client=client)

    assert [p.raison_sociale for p in bilan.crees] == ["Réseau Entreprendre Nord"]
    assert (bilan.proposees, bilan.deja_connues) == (3, 2)
    assert len(recherche.enrichissements) == 1, recherche.enrichissements


def test_on_n_enrichit_pas_au_dela_de_la_limite() -> None:
    """Sur le code d'avant : toutes les fiches rendues étaient enrichies, puis bornées."""
    recherche = _RechercheEspionne()
    client = _ClientFaux({"extraire_prospects": {"prospects": [
        {"raison_sociale": f"Structure {i}"} for i in range(4)
    ]}})

    crees = agents.rechercher_des_prospects(
        _campagne(), limite=2, recherche=recherche, client=client
    )

    assert len(crees) == 2
    assert len(recherche.enrichissements) == 2
