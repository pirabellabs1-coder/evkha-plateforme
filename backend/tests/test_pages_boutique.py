"""Les fiches de la boutique telles qu'un robot les lit (`pages_boutique`).

Mesure le 20/11/2026 : `/boutique/<etude>` rendait a un robot sans JavaScript
la coquille vide de l'application, et une etude inventee repondait 200.

Ce fichier verrouille :

1. la page d'une etude en vente porte son titre, sa description, son adresse
   canonique, son bloc `Product` et son texte — et la coquille reste entiere ;
2. une etude absente ou hors ligne repond 404, sans rien annoncer ;
3. rien de ce que la gerante saisit ne peut sortir du texte (echappement) ;
4. les donnees structurees ne declarent que ce qui est etabli ;
5. si la coquille manque ou a change de forme : 503, jamais une demi-page ;
6. le plan des fiches ne liste que ce qui se vend ;
7. ce que ce module partage avec le front (marques, nom du service, forme de
   la coquille) est tenu d'accord avec lui.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from django.test import Client

from catalog.models import AvisProduit
from organisations import pages_boutique
from tests.test_boutique import produit_en_ligne

pytestmark = pytest.mark.django_db

RACINE = Path(__file__).resolve().parents[2]

#: La VRAIE coquille, celle du depot. Vite n'y change que la balise du script
#: et y ajoute sa feuille de style : le titre, les balises `meta` et la racine
#: partent tels quels. Tester sur une coquille ecrite ici prouverait seulement
#: que le module sait lire ce que le test a invente (regle 2).
COQUILLE = (RACINE / "frontend" / "index.html").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _coquille_du_depot(monkeypatch: Any, settings: Any) -> None:
    monkeypatch.setattr(pages_boutique, "_coquille", lambda: COQUILLE)
    settings.EVKHA_APP_URL = "https://site.exemple"


def _page(slug: str) -> Any:
    return Client().get(f"/api/public/boutique/{slug}/page/")


def _bloc(html: str) -> dict[str, Any]:
    trouve = re.search(
        r'<script type="application/ld\+json" data-prerendu="">(.*?)</script>', html, re.S
    )
    assert trouve, "bloc de donnees structurees absent"
    donnees: dict[str, Any] = json.loads(trouve.group(1))
    return donnees


# ── 1. Une etude en vente ───────────────────────────────────────────────────


def test_la_page_porte_l_en_tete_et_le_texte_de_l_etude() -> None:
    produit = produit_en_ligne(
        titre="Le marché des salons de coiffure",
        slug="salons-de-coiffure",
        description="Premier paragraphe.\n\nSecond paragraphe.",
        sommaire="Taille du marché\nConcurrence",
    )
    AvisProduit.objects.create(
        produit=produit, auteur="Claire", qualite="Coiffeuse", note=5, texte="Utile.", publie=True
    )

    reponse = _page("salons-de-coiffure")
    html = reponse.content.decode("utf-8")

    assert reponse.status_code == 200
    assert reponse["Content-Type"] == "text/html; charset=utf-8"
    assert reponse["Cache-Control"] == "no-cache"
    # L'en-tete : le titre de l'etude, marque de la valeur du gabarit.
    assert (
        '<title data-origine="EVKHA — Espace client">'
        "Le marché des salons de coiffure — EVKHA</title>" in html
    )
    assert html.count("<title") == 1
    assert re.search(
        r'<meta name="description" content="Premier paragraphe\." data-origine="[^"]+" />', html
    )
    assert (
        '<link rel="canonical" href="https://site.exemple/boutique/salons-de-coiffure" '
        'data-prerendu="" />' in html
    )
    assert 'name="robots"' not in html
    # Le texte, dans un `<noscript>` pose APRES une racine restee vide.
    corps = html.split('<div id="root"></div><noscript>')[1].split("</noscript>")[0]
    for attendu in (
        "<h1>Le marché des salons de coiffure</h1>",
        "89 € TTC",
        "<p>Premier paragraphe.</p><p>Second paragraphe.</p>",
        "<li>Taille du marché</li><li>Concurrence</li>",
        "Claire, Coiffeuse",
        '<a href="/etudes">',
    ):
        assert attendu in corps, attendu
    # La coquille est entiere : son script, sa preuve de propriete.
    assert '<script type="module"' in html
    assert "google-site-verification" in html


def test_les_etudes_proches_sont_celles_de_la_fiche_de_l_api() -> None:
    produit = produit_en_ligne(slug="etude-a", theme="Beauté")
    produit_en_ligne(slug="etude-b", titre="Étude B", theme="Beauté")
    produit_en_ligne(slug="etude-c", titre="Étude C", theme="Autre")

    html = _page(produit.slug).content.decode("utf-8")
    api = Client().get(f"/api/public/boutique/{produit.slug}/").json()

    liens = re.findall(r'<li><a href="/boutique/([^"]+)">', html)
    assert liens == [p["slug"] for p in api["proches"]]
    assert liens, "aucune etude proche : le test ne compare rien"


# ── 2. Une etude qui ne se vend pas ─────────────────────────────────────────


@pytest.mark.parametrize("cas", ["inconnue", "hors_ligne", "sans_prix"])
def test_une_etude_qui_ne_se_vend_pas_repond_404(cas: str, monkeypatch: Any) -> None:
    if cas == "hors_ligne":
        produit_en_ligne(slug="etude-cachee", en_ligne=False)
    elif cas == "sans_prix":
        produit_en_ligne(slug="etude-cachee", prix_cents=0)

    def interdit() -> str:
        raise AssertionError("la coquille ne se lit pas pour une etude absente")

    monkeypatch.setattr(pages_boutique, "_coquille", interdit)

    reponse = _page("etude-cachee")

    # 404 SANS corps : nginx sert la coquille avec ce code. Rien n'est
    # annonce, et la coquille n'est pas lue — une adresse inventee ne coute
    # qu'une requete en base.
    assert reponse.status_code == 404
    assert reponse.content == b""


@pytest.mark.parametrize(
    "adresse", ["/api/public/boutique/{}/page/", "/api/public/boutique/plan.xml"]
)
def test_une_sonde_HEAD_recoit_le_meme_code_qu_une_lecture(adresse: str) -> None:
    """Verificateurs de liens et sondes demandent en HEAD : 405 leur ferait
    croire la fiche en panne."""
    produit = produit_en_ligne(slug="etude-sondee")
    reponse = Client().head(adresse.format(produit.slug))
    assert reponse.status_code == 200
    assert Client().post(adresse.format(produit.slug)).status_code == 405


# ── 3. Ce que la gerante saisit ne sort pas du texte ────────────────────────


def test_un_texte_saisi_ne_peut_pas_ecrire_de_balise() -> None:
    attaque = '</noscript><script>alert(1)</script>"><img src=x onerror=alert(2)>'
    produit = produit_en_ligne(
        slug="etude-piegee",
        titre=f"Titre {attaque}",
        description=f"Texte {attaque}\n\n</script><script>alert(3)</script>",
        sommaire=f"Ligne {attaque}",
        theme=f"Thème {attaque}",
    )
    AvisProduit.objects.create(
        produit=produit, auteur=attaque, qualite=attaque, note=5, texte=attaque, publie=True
    )

    html = _page("etude-piegee").content.decode("utf-8")

    assert "<script>alert" not in html
    assert "<img src=x" not in html
    # Un seul `<noscript>`, referme une seule fois : le texte n'en sort pas.
    assert html.count("<noscript>") == 1
    assert html.count("</noscript>") == 1
    # Le bloc de donnees reste du JSON lisible, et ne referme pas sa balise.
    bloc = _bloc(html)
    assert bloc["name"] == f"Titre {attaque}"
    assert html.count("</script>") == COQUILLE.count("</script>") + 1


def test_un_texte_saisi_ne_sort_pas_d_un_attribut() -> None:
    """Sans chevron : un guillemet suffirait a ouvrir un attribut dans une
    balise `meta`. La valeur relue doit etre la saisie, entiere."""
    saisie = 'Titre" onmouseover="x' + "' data-y='z"
    produit_en_ligne(slug="etude-guillemets", titre=saisie, description=saisie)

    html = _page("etude-guillemets").content.decode("utf-8")

    import html as html_lib

    for motif in (
        r'<meta property="og:title" content="([^"]*)" data-origine=',
        r'<meta name="description" content="([^"]*)" data-origine=',
        r'<meta name="twitter:description" content="([^"]*)" data-prerendu=',
    ):
        trouve = re.search(motif, html)
        assert trouve, motif
        assert html_lib.unescape(trouve.group(1)).startswith(saisie), motif
    # Hors du bloc de donnees (du JSON, ou le guillemet est precede d'une
    # barre), la saisie n'apparait jamais avec son guillemet NU.
    hors_json = re.sub(r"<script type=\"application/ld\+json\".*?</script>", "", html, flags=re.S)
    assert '" onmouseover="x' not in hors_json


def test_un_titre_ne_se_lit_pas_comme_un_motif_de_remplacement() -> None:
    """`\\1` et `\\g<0>` dans un titre : ecrits tels quels, pas remplaces par
    ce que l'expression a capture dans la coquille."""
    saisie = r"Etude \1 et \g<0> fin"
    produit_en_ligne(slug="etude-motif", titre=saisie, description=saisie)

    html = _page("etude-motif").content.decode("utf-8")

    assert r"Etude \1 et \g&lt;0&gt; fin — EVKHA</title>" in html
    assert _bloc(html)["name"] == saisie


# ── 4. Les donnees structurees ne declarent que l'etabli ────────────────────


def test_le_bloc_ne_declare_pas_de_note_sans_avis_publie() -> None:
    produit = produit_en_ligne(slug="etude-sans-avis", theme="")
    AvisProduit.objects.create(produit=produit, auteur="Brouillon", note=1, publie=False)

    bloc = _bloc(_page("etude-sans-avis").content.decode("utf-8"))

    assert "aggregateRating" not in bloc
    assert "category" not in bloc
    assert "image" not in bloc
    assert bloc["offers"] == {
        "@type": "Offer",
        "price": "89.00",
        "priceCurrency": "EUR",
        "url": "https://site.exemple/boutique/etude-sans-avis",
    }
    for invente in ("availability", "brand", "review"):
        assert invente not in bloc


def test_le_bloc_declare_la_note_des_avis_publies() -> None:
    produit = produit_en_ligne(slug="etude-notee")
    AvisProduit.objects.create(produit=produit, auteur="A", note=5, publie=True)
    AvisProduit.objects.create(produit=produit, auteur="B", note=4, publie=True)
    AvisProduit.objects.create(produit=produit, auteur="C", note=1, publie=False)

    bloc = _bloc(_page("etude-notee").content.decode("utf-8"))

    assert bloc["aggregateRating"] == {
        "@type": "AggregateRating",
        "ratingValue": 4.5,
        "reviewCount": 2,
    }


@pytest.mark.parametrize(
    ("cents", "devise", "attendu"),
    [(8900, "EUR", "89 €"), (8950, "eur", "89,50 €"), (1205, "USD", "12,05 USD")],
)
def test_le_prix_s_ecrit_comme_sur_le_site(cents: int, devise: str, attendu: str) -> None:
    assert pages_boutique._prix(cents, devise) == attendu


def test_la_description_de_la_page_se_coupe_entre_deux_mots() -> None:
    longue = "mot " * 80
    resume = pages_boutique._resume(longue)
    assert len(resume) <= 160
    assert resume.endswith("mot…")
    assert pages_boutique._resume("Court.\n\nSuite.") == "Court."
    assert pages_boutique._resume("") == ""


# ── 5. Une coquille absente ou changee : 503, jamais une demi-page ──────────


def test_sans_coquille_la_page_repond_503(monkeypatch: Any) -> None:
    def en_panne() -> str:
        raise pages_boutique.CoquilleIllisible("ConnectError")

    monkeypatch.setattr(pages_boutique, "_coquille", en_panne)
    produit = produit_en_ligne(slug="etude-en-panne")

    reponse = _page(produit.slug)

    assert reponse.status_code == 503
    assert reponse.content == b""


@pytest.mark.parametrize(
    "abimee",
    [
        COQUILLE.replace("<title>", "<title lang='fr'>"),
        COQUILLE.replace('<div id="root"></div>', '<div id="app"></div>'),
        COQUILLE.replace('name="description"', 'name="resume"'),
        COQUILLE.replace("</head>", ""),
        COQUILLE + "<title>Un second titre</title>",
    ],
)
def test_une_coquille_qui_a_change_de_forme_repond_503(monkeypatch: Any, abimee: str) -> None:
    assert abimee != COQUILLE
    monkeypatch.setattr(pages_boutique, "_coquille", lambda: abimee)
    produit = produit_en_ligne(slug="etude-coquille-abimee")

    assert _page(produit.slug).status_code == 503


def test_la_lecture_de_la_coquille_dit_sa_panne(monkeypatch: Any, settings: Any) -> None:
    monkeypatch.undo()  # la vraie `_coquille`, pas la doublure du fichier
    demandes: list[str] = []

    def refuse(adresse: str, **_: Any) -> Any:
        demandes.append(adresse)
        raise httpx.ConnectError("refuse")

    monkeypatch.setattr(httpx, "get", refuse)
    settings.EVKHA_FRONT_INTERNE = "http://front.interne/"

    with pytest.raises(pages_boutique.CoquilleIllisible):
        pages_boutique._coquille()
    assert demandes == ["http://front.interne/index.html"]

    settings.EVKHA_FRONT_INTERNE = ""
    with pytest.raises(pages_boutique.CoquilleIllisible):
        pages_boutique._coquille()
    assert len(demandes) == 1, "sans adresse, rien n'est demande"


# ── 6. Le plan des fiches ───────────────────────────────────────────────────


def test_le_plan_ne_liste_que_ce_qui_se_vend() -> None:
    import datetime as dt

    produit_en_ligne(slug="etude-visible", mise_a_jour_le=dt.date(2026, 10, 3))
    produit_en_ligne(slug="etude-retiree", en_ligne=False)
    produit_en_ligne(slug="etude-gratuite", prix_cents=0)

    reponse = Client().get("/api/public/boutique/plan.xml")
    corps = reponse.content.decode("utf-8")

    assert reponse.status_code == 200
    assert reponse["Content-Type"] == "text/xml; charset=utf-8"
    assert re.findall(r"<loc>([^<]+)</loc>", corps) == [
        "https://site.exemple/boutique/etude-visible"
    ]
    assert "<lastmod>2026-10-03</lastmod>" in corps


def test_le_plan_ne_prend_pas_la_place_d_une_fiche() -> None:
    """`plan.xml` porte un point : aucun slug ne peut le masquer, ni lui."""
    produit_en_ligne(slug="plan")
    assert Client().get("/api/public/boutique/plan/").json()["produit"]["slug"] == "plan"
    assert Client().get("/api/public/boutique/plan.xml")["Content-Type"].startswith("text/xml")


# ── 7. Ce que ce module partage avec le front ───────────────────────────────


def test_les_marques_sont_celles_du_front() -> None:
    source = (RACINE / "frontend" / "src" / "enTetePrerendu.ts").read_text(encoding="utf-8")
    assert f'export const MARQUE_AJOUTEE = "{pages_boutique.MARQUE_AJOUTEE}";' in source
    assert f'export const MARQUE_CHANGEE = "{pages_boutique.MARQUE_CHANGEE}";' in source


def test_l_adresse_interne_nomme_le_service_du_front() -> None:
    composition = (RACINE / "docker-compose.prod.yml").read_text(encoding="utf-8")
    service = re.search(
        r"^  (\w+):\n(?:    .*\n|\n)*?    build:\n      context: \.\n"
        r"      dockerfile: frontend/Dockerfile",
        composition,
        re.M,
    )
    assert service, "le service du front est introuvable dans la composition"
    reglages = (RACINE / "backend" / "evkha" / "settings.py").read_text(encoding="utf-8")
    assert (
        f'EVKHA_FRONT_INTERNE = env("EVKHA_FRONT_INTERNE", default="http://{service.group(1)}")'
        in reglages
    )


def test_nginx_confie_les_fiches_et_le_plan_a_ces_routes() -> None:
    nginx = (RACINE / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "rewrite ^ /api/public/boutique/$etude/page/ break;" in nginx
    assert "proxy_pass http://api:8000/api/public/boutique/plan.xml;" in nginx
    # Une etude absente : Django rend 404 sans corps, nginx sert la coquille.
    fiches = nginx.split("location ~ ^/boutique/")[1].split("\n    }")[0]
    assert "error_page 404 /index.html;" in fiches
    assert "proxy_read_timeout" in fiches
    # La coquille reste lisible par son nom, de l'interieur.
    assert r"location ~ ^/(?!index\.html$).+\.html$ {" in nginx
