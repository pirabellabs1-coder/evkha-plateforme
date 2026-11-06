"""Une adresse plausible inventée passait le gate : personne ne vérifiait qu'elle mène quelque part.

Audit du 26/09/2026. `_URL_BIDON_RE` ne connaît que les gabarits (example.com,
source.fr) ; « https://www.observatoire-des-services-premium.fr/etude-2025 »
passait. Comparer chaque domaine au brief de recherche aurait été FAUX par
construction : la charte ordonne de remonter au PRODUCTEUR de la donnée, dont
le domaine n'est jamais dans le brief quand la recherche n'a rapporté que la
presse. On ne juge donc que ce qui se prouve : un domaine que rien ne nous a
donné ET qui n'existe pas (aucune résolution DNS) est un lien mort. Une panne
DNS n'accuse personne (règle 2).
"""
from __future__ import annotations

import socket
from typing import Any

import pytest

from generation.checks_post_rendu import (
    _hote,
    detecter_domaines_inexistants,
    hotes_cites,
    resoudre_dns,
)
from generation.correction import _CHECK_LABELS, _is_regenerable
from generation.rendering import RenderedSection


def _section(numero: int, corps: str) -> RenderedSection:
    return RenderedSection(number=numero, title=f"Chapitre {numero}", kind="chapitre", body=corps)


# ── Lire un domaine ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("adresse", "hote"),
    [
        pytest.param(
            "https://www.Insee.fr/fr/statistiques/8727786?x=1", "insee.fr", id="url-complete",
        ),
        pytest.param("http://data.gouv.fr:8080/", "data.gouv.fr", id="port-et-sous-domaine"),
        pytest.param("gold.fr/vente-or", "gold.fr", id="domaine-nu"),
        pytest.param("WWW.XERFI.COM", "xerfi.com", id="majuscules"),
    ],
)
def test_l_hote_est_normalise(adresse: str, hote: str) -> None:
    assert _hote(adresse) == hote


def test_les_deux_formes_d_adresse_sont_lues() -> None:
    cites = hotes_cites(
        "Voir https://www.insee.fr/fr/statistiques/1 et gold.fr/vente-or (Insee, 2025)."
    )
    assert set(cites) == {"insee.fr", "gold.fr"}


# ── Un domaine se lit ENTIER, ou pas du tout ─────────────────────────────────
#
# Mesuré le 06/11/2026 sur la reprise `ecb28fa8` de l'étude de la concurrence
# SUN TZU. Trois adresses du document ne résolvaient pas ; UNE SEULE a été
# signalée :
#
#     culinaconcepts.com        -> motif          (.com simple)
#     citysuper.com.tw          -> AUCUN motif    (lu « citysuper.com »)
#     thefrenchgrocer.com.sg    -> AUCUN motif    (lu « thefrenchgrocer.com »)
#
# `_DOMAINE_RE` énumérait quinze terminaisons, toutes européennes ou
# génériques, et son `\b` laissait la correspondance s'arrêter au premier
# morceau connu. Les deux adresses asiatiques étaient donc TRONQUÉES vers un
# domaine qui, lui, existe : le contrôle jugeait un hôte que le lecteur ne
# clique pas et déclarait l'adresse saine (règle 2).
#
# Les trois étaient des domaines NUS dans des tableaux, sans « https:// ».


@pytest.mark.parametrize(
    ("texte", "hotes"),
    [
        pytest.param("citysuper.com.tw", {"citysuper.com.tw"}, id="com-tw-nu"),
        pytest.param(
            "thefrenchgrocer.com.sg", {"thefrenchgrocer.com.sg"}, id="com-sg-nu",
        ),
        pytest.param("ole.com.cn", {"ole.com.cn"}, id="com-cn-nu"),
        pytest.param("seijoishii.co.jp", {"seijoishii.co.jp"}, id="co-jp-nu"),
        pytest.param("www.citysuper.com.tw", {"citysuper.com.tw"}, id="www-com-tw"),
        pytest.param("shinsegae.com", {"shinsegae.com"}, id="com-simple-inchange"),
    ],
)
def test_un_domaine_a_deux_niveaux_est_lu_entier(texte: str, hotes: set[str]) -> None:
    """Le défaut mesuré : « .com.tw » ne doit jamais devenir « .com »."""
    assert set(hotes_cites(texte)) == hotes


def test_une_terminaison_inconnue_fait_taire_la_lecture_au_lieu_de_tronquer() -> None:
    """LA classe du défaut, pas son exemple (règle 4).

    Allonger la liste des terminaisons n'aurait réglé que les pays prévus : le
    premier « .com.xx » absent de la liste aurait été tronqué comme avant. Un
    contrôle muet est acceptable ; un contrôle qui juge le MAUVAIS hôte ne
    l'est pas (règles 1 et 2).
    """
    assert hotes_cites("exemple.com.zz") == {}
    assert hotes_cites("maison.fr.qq") == {}


@pytest.mark.parametrize(
    "prose",
    [
        # Ces huit mots français SONT des terminaisons de pays réelles :
        # il (Israël), sa (Arabie saoudite), de (Allemagne), ne (Niger),
        # ma (Maroc), se (Suède), es (Espagne), it (Italie). Une majuscule
        # après un point sans espace les transforme en domaine.
        pytest.param("le chiffre d'affaires.Il progresse", id="il-israel"),
        pytest.param("des produits.Sa qualité est reconnue", id="sa-arabie"),
        pytest.param("la marge.De plus, le panier", id="de-allemagne"),
        pytest.param("le marché.Ne pas confondre", id="ne-niger"),
        pytest.param("la zone.Ma lecture du panel", id="ma-maroc"),
        pytest.param("le panel.Se distingue par", id="se-suede"),
        pytest.param("le prix.Es-tu sûr", id="es-espagne"),
        pytest.param("le coût.It depends", id="it-italie"),
        # Et les mots qui ne sont pas des terminaisons : la liste les refuse
        # déjà parce qu'elle est fermée.
        pytest.param("des produits.Les clients hésitent", id="les-inconnu"),
        pytest.param("fin de phrase.Le paragraphe suivant", id="le-inconnu"),
    ],
)
def test_contre_epreuve_une_coquille_de_prose_n_est_pas_une_adresse(prose: str) -> None:
    """Deux garde-fous, et il faut les DEUX.

    1. La liste des terminaisons est fermée : « produits.Les » ne passe pas,
       parce que `les` n'est le code d'aucun pays. Avec une règle ouverte
       (« le dernier morceau est une suite de lettres »), il passerait.
    2. La terminaison doit être tout en minuscules ou tout en MAJUSCULES, pas
       capitalisée : « affaires.Il » ne passe pas, bien que `il` soit Israël.

    Sans le second, l'extension du 06/11/2026 aurait introduit un motif faux
    sur le pronom le plus courant de la langue — et le défaut existait déjà
    pour « .De », l'Allemagne étant dans la liste depuis le début.
    """
    assert hotes_cites(prose) == {}


def test_une_adresse_tout_en_majuscules_reste_lue() -> None:
    """CONTRE-ÉPREUVE de la règle de casse : une cellule de tableau en capitales.

    Contraindre la casse ne doit pas rendre le contrôle aveugle à une adresse
    écrite « XERFI.COM ». Seule la forme capitalisée est refusée.
    """
    assert set(hotes_cites("Source : WWW.XERFI.COM")) == {"xerfi.com"}


# ── Juger ────────────────────────────────────────────────────────────────────

RESOLUTIONS = {
    "insee.fr": True,
    "observatoire-bidon.fr": False,
    "portail-inconnu-mais-reel.fr": True,
    "dns-en-panne.fr": None,
}


def _faux_dns(hote: str) -> bool | None:
    return RESOLUTIONS.get(hote, False)


def test_un_domaine_inconnu_et_inexistant_est_signale() -> None:
    (trouve,) = detecter_domaines_inexistants(
        [_section(9, "Source : https://observatoire-bidon.fr/etude-2025")],
        hotes_admis=frozenset({"insee.fr"}),
        resoudre=_faux_dns,
    )
    assert trouve.hote == "observatoire-bidon.fr"
    assert trouve.chapitre == 9
    assert "ne répond pas" in str(trouve)


# ── L'hôte interrogé est celui que le LECTEUR saisit ─────────────────────────
#
# Mesuré le 06/11/2026 sur `03c9291b` avec un second résolveur : trois enseignes
# RÉELLES du document — `citysuper.com.tw`, `isetan.co.jp`, `samsclub.cn` — ont
# une zone DNS qui existe (NS trouvé) et AUCUNE adresse à l'apex ; leur site
# est sur `www`. `getaddrinfo` rend `EAI_NONAME` pour ce cas comme pour un
# NXDOMAIN, et `_hote` retirait `www` avant d'interroger. Un document qui écrit
# correctement `www.citysuper.com.tw` se faisait donc accuser sur
# `citysuper.com.tw`, qui ne répond pas — un motif faux, qui fait payer une
# réécriture pour retirer un concurrent qui existe (règle 2).


def test_une_adresse_en_www_est_interrogee_telle_quelle() -> None:
    """LE défaut : `www` était retiré, et c'est l'apex muet qu'on jugeait.

    Échoue sur le code d'avant : l'hôte y valait « citysuper.com.tw », que
    `_dns_reel_du_06_11` déclare sans réponse → un motif sur une adresse qui
    marche.
    """
    def _dns_reel_du_06_11(hote: str) -> bool | None:
        return hote.startswith("www.")        # apex muet, site sur www

    assert detecter_domaines_inexistants(
        [_section(1, "City'super Taïwan — www.citysuper.com.tw")],
        hotes_admis=frozenset(),
        resoudre=_dns_reel_du_06_11,
    ) == []


def test_l_adresse_nue_vers_un_apex_muet_reste_signalee_sans_nier_le_domaine() -> None:
    """CONTRE-ÉPREUVE : on ne se taît pas, et on n'affirme pas le faux.

    Écrite nue, l'adresse ne mène nulle part : le motif reste dû. Mais il ne
    doit plus dire « le domaine n'existe pas » — c'est faux de l'enseigne
    réelle — et il doit nommer la piste qui répare les deux cas.
    """
    (trouve,) = detecter_domaines_inexistants(
        [_section(1, "City'super Taïwan — citysuper.com.tw")],
        hotes_admis=frozenset(),
        resoudre=lambda hote: hote.startswith("www."),
    )
    assert trouve.hote == "citysuper.com.tw"
    assert "ne répond pas" in str(trouve)
    assert "n'existe pas" not in str(trouve)
    assert "www." in str(trouve)


def test_un_domaine_admis_couvre_son_www() -> None:
    """CONTRE-ÉPREUVE : la liste blanche est sans `www`, la citation peut en avoir.

    `_admis` compare par suffixe : un `insee.fr` donné par la cliente doit
    continuer de couvrir `www.insee.fr` cité, même avec un DNS qui refuse tout.
    """
    assert detecter_domaines_inexistants(
        [_section(2, "Source : https://www.insee.fr/fr/statistiques/1")],
        hotes_admis=frozenset({"insee.fr"}),
        resoudre=lambda _: False,
    ) == []


def test_la_liste_blanche_reste_sans_www() -> None:
    """La forme par défaut ne change pas : la liste blanche se construit dessus."""
    assert set(hotes_cites("Source : www.insee.fr/x")) == {"insee.fr"}
    assert set(hotes_cites("Source : www.insee.fr/x", garder_www=True)) == {"www.insee.fr"}


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("Source : https://www.insee.fr/fr/statistiques/1", id="admis"),
        pytest.param("Source : https://data.insee.fr/serie/2", id="sous-domaine-admis"),
        pytest.param(
            "Source : https://portail-inconnu-mais-reel.fr/rapport", id="inconnu-mais-existant",
        ),
        pytest.param(
            "Source : https://dns-en-panne.fr/rapport", id="dns-indisponible-n-accuse-pas",
        ),
        pytest.param(
            "Article L221-18 du code de la consommation.", id="reference-juridique-sans-adresse",
        ),
    ],
)
def test_ce_qui_ne_se_prouve_pas_n_est_pas_signale(texte: str) -> None:
    assert detecter_domaines_inexistants(
        [_section(9, texte)], hotes_admis=frozenset({"insee.fr"}), resoudre=_faux_dns,
    ) == []


def test_chaque_domaine_n_est_interroge_qu_une_fois() -> None:
    appels: list[str] = []

    def _compteur(hote: str) -> bool | None:
        appels.append(hote)
        return False

    detecter_domaines_inexistants(
        [_section(3, "https://a-bidon.fr/x et https://a-bidon.fr/y"), _section(4, "a-bidon.fr/z")],
        hotes_admis=frozenset(), resoudre=_compteur,
    )
    assert appels == ["a-bidon.fr"]


# ── Le DNS réel, classé ──────────────────────────────────────────────────────


def test_seul_un_nom_inconnu_vaut_inexistant(monkeypatch: pytest.MonkeyPatch) -> None:
    def _inconnu(*_: Any, **__: Any) -> Any:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    def _resolveur_en_panne(*_: Any, **__: Any) -> Any:
        raise socket.gaierror(getattr(socket, "EAI_AGAIN", 11002), "Temporary failure")

    monkeypatch.setattr(socket, "getaddrinfo", _inconnu)
    assert resoudre_dns("n-importe-quoi.fr") is False
    monkeypatch.setattr(socket, "getaddrinfo", _resolveur_en_panne)
    assert resoudre_dns("n-importe-quoi.fr") is None
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_, **__: [("ok",)])
    assert resoudre_dns("insee.fr") is True


def test_la_boucle_de_correction_sait_le_reparer() -> None:
    assert _is_regenerable("domaine_inexistant")
    assert "domaine_inexistant" in _CHECK_LABELS
