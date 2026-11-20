"""Les formations : une fiche, des modules, des leçons — tenus par la cliente.

Ce que ces tests verrouillent, et qu'on ne verrait pas autrement :

- **rien ne se supprime** : un retrait pose une date, le nombre de lignes ne
  bouge pas, et aucune route n'accepte `DELETE` ;
- **le contenu payant ne sort pas** : ni l'adresse d'une vidéo, ni le texte
  d'une leçon, ni son document ne figurent dans une réponse publique ;
- **un champ illisible ne remet rien à zéro**, et la réponse le nomme.

Chaque refus a sa contre-épreuve : le cas voisin légitime passe.
"""
from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, RequestFactory

from catalog import formations as regles
from catalog.models import (
    PREFIXE_VITRINE_FORMATIONS,
    Formation,
    LeconDeFormation,
    ModuleDeFormation,
)

pytestmark = pytest.mark.django_db

ADMIN = "/api/dashboard/formations/"
PUBLIC = "/api/public/formations/"
VIDEO = "https://vimeo.com/123456789"


@pytest.fixture(autouse=True)
def _medias_a_part(settings: Any, tmp_path: Any) -> None:
    """Les fichiers déposés par ces tests ne vont pas dans le vrai `media/`."""
    settings.MEDIA_ROOT = tmp_path
    settings.EVKHA_BASE_URL = "https://api2.evkha.fr"


def une_formation(**surcharges: Any) -> Formation:
    defauts: dict[str, Any] = {
        "titre": "Créer son entreprise de A à Z",
        "slug": f"formation-{uuid.uuid4().hex[:8]}",
        "prix_cents": 149_000,
    }
    defauts.update(surcharges)
    return Formation.objects.create(**defauts)


def un_module(formation: Formation, **surcharges: Any) -> ModuleDeFormation:
    defauts: dict[str, Any] = {"titre": "Module", "rang": 0}
    defauts.update(surcharges)
    return ModuleDeFormation.objects.create(formation=formation, **defauts)


def une_lecon(module: ModuleDeFormation, **surcharges: Any) -> LeconDeFormation:
    defauts: dict[str, Any] = {"titre": "Leçon", "rang": 0}
    defauts.update(surcharges)
    return LeconDeFormation.objects.create(module=module, **defauts)


def avec_une_lecon(formation: Formation) -> Formation:
    """Lui donne un programme : sans leçon, une formation ne se met pas en ligne."""
    une_lecon(un_module(formation, titre="Module du programme"), titre="Leçon du programme")
    return formation


def envoyer(client: Any, adresse: str, charge: dict[str, Any]) -> Any:
    return client.post(adresse, data=charge, content_type="application/json")


def _png() -> bytes:
    """Un vrai PNG : la couverture est lue par Pillow, pas crue sur son nom."""
    from PIL import Image  # noqa: PLC0415

    tampon = io.BytesIO()
    Image.new("RGB", (4, 4), "#FF5500").save(tampon, "PNG")
    return tampon.getvalue()


def _lignes() -> tuple[int, int, int]:
    return (
        Formation.objects.count(),
        ModuleDeFormation.objects.count(),
        LeconDeFormation.objects.count(),
    )


# ── 1. Créer et modifier une formation ───────────────────────────────────────


def test_une_formation_se_cree_HORS_LIGNE(client_admin: Any) -> None:
    """La cliente relit avant de publier : rien n'arrive en ligne tout seul."""
    une_formation(rang=4)

    reponse = envoyer(
        client_admin,
        ADMIN,
        {"titre": "  Méthode P.O.P  ", "prix_cents": 85_000, "duree_heures": 7},
    )

    assert reponse.status_code == 201, reponse.content
    fiche = reponse.json()["formation"]
    assert fiche["titre"] == "Méthode P.O.P"
    assert fiche["slug"] == "methode-pop"
    assert fiche["en_ligne"] is False
    assert fiche["prix_cents"] == 85_000
    assert fiche["duree_heures"] == 7
    assert fiche["devise"] == "EUR"
    assert fiche["rang"] == 5, "une nouvelle formation se range en fin de liste"
    assert fiche["modules"] == []
    assert reponse.json()["refuses"] == []


def test_demander_la_mise_en_ligne_A_LA_CREATION_est_ecarte(client_admin: Any) -> None:
    """La fiche est créée, hors ligne, et la réponse dit pourquoi."""
    reponse = envoyer(
        client_admin, ADMIN, {"titre": "Pressée", "prix_cents": 100, "en_ligne": True}
    )

    assert reponse.status_code == 201
    assert reponse.json()["formation"]["en_ligne"] is False
    assert [r["champ"] for r in reponse.json()["refuses"]] == ["en_ligne"]


def test_une_formation_sans_titre_est_refusee(client_admin: Any) -> None:
    reponse = envoyer(client_admin, ADMIN, {"titre": "   ", "prix_cents": 100})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "titre_manquant"
    assert reponse.json()["champ"] == "titre"
    assert "titre" in reponse.json()["erreur"]
    assert Formation.objects.count() == 0


def test_une_modification_partielle_ne_touche_que_ce_qui_est_envoye(
    client_admin: Any,
) -> None:
    formation = une_formation(sous_titre="Avant", accroche="Gardée")

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"sous_titre": "Après"})

    assert reponse.status_code == 200, reponse.content
    formation.refresh_from_db()
    assert formation.sous_titre == "Après"
    assert formation.accroche == "Gardée"
    assert formation.prix_cents == 149_000
    assert formation.titre == "Créer son entreprise de A à Z"


def test_vider_le_titre_d_une_formation_est_refuse(client_admin: Any) -> None:
    formation = une_formation()

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"titre": ""})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "titre_manquant"
    formation.refresh_from_db()
    assert formation.titre == "Créer son entreprise de A à Z"


def test_un_champ_ILLISIBLE_laisse_la_valeur_et_la_reponse_le_nomme(
    client_admin: Any,
) -> None:
    """Remettre le prix à zéro sur une faute de frappe afficherait « 0 € ».

    Le reste de l'envoi, lui, est enregistré : un champ fautif ne fait pas
    perdre les autres.
    """
    formation = une_formation(prix_cents=149_000, duree_heures=18)

    reponse = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/",
        {"prix_cents": "mille", "duree_heures": 12.5, "accroche": "Nouvelle"},
    )

    assert reponse.status_code == 200, reponse.content
    assert sorted(r["champ"] for r in reponse.json()["refuses"]) == [
        "duree_heures", "prix_cents",
    ]
    formation.refresh_from_db()
    assert formation.prix_cents == 149_000
    assert formation.duree_heures == 18
    assert formation.accroche == "Nouvelle"


def test_un_nombre_ecrit_en_texte_est_lu(client_admin: Any) -> None:
    """Contre-épreuve : un formulaire envoie « 1500 », pas 1500."""
    formation = une_formation()

    reponse = client_admin.post(f"{ADMIN}{formation.id}/", {"prix_cents": "1500"})

    assert reponse.json()["refuses"] == []
    formation.refresh_from_db()
    assert formation.prix_cents == 1500


def test_un_champ_INCONNU_n_est_pas_ignore_en_silence(client_admin: Any) -> None:
    """Une clé mal orthographiée par l'écran serait sinon « enregistrée »."""
    formation = une_formation()

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"soustitre": "Raté"})

    assert reponse.status_code == 200
    assert reponse.json()["refuses"] == [
        {"champ": "soustitre", "raison": "Ce champ n'existe pas."}
    ]


def test_un_prix_negatif_est_refuse(client_admin: Any) -> None:
    formation = une_formation(prix_cents=149_000)

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"prix_cents": -1})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "prix_negatif"
    formation.refresh_from_db()
    assert formation.prix_cents == 149_000


def test_un_prix_a_zero_est_admis_HORS_LIGNE(client_admin: Any) -> None:
    """Contre-épreuve : zéro n'est pas négatif, et une fiche se prépare."""
    formation = avec_une_lecon(une_formation(prix_cents=149_000))

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"prix_cents": 0})

    assert reponse.status_code == 200
    assert reponse.json()["formation"]["publiable"] is False
    assert reponse.json()["formation"]["manque"] == ["un prix"]


def test_le_prix_se_saisit_aussi_en_euros(client_admin: Any) -> None:
    formation = une_formation(prix_cents=0)

    envoyer(client_admin, f"{ADMIN}{formation.id}/", {"prix_euros": "1 490,50"})

    formation.refresh_from_db()
    assert formation.prix_cents == 149_050


def test_mettre_en_ligne_SANS_PRIX_est_refuse(client_admin: Any) -> None:
    """Le refus nomme ce qui manque, et rien n'est enregistré."""
    formation = une_formation(prix_cents=0)

    reponse = envoyer(
        client_admin, f"{ADMIN}{formation.id}/", {"en_ligne": True, "accroche": "x"}
    )

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "formation_incomplete"
    assert "un prix" in reponse.json()["erreur"]
    formation.refresh_from_db()
    assert formation.en_ligne is False
    assert formation.accroche == "", "un envoi refusé n'enregistre rien"


def test_mettre_en_ligne_AVEC_un_prix_passe(client_admin: Any) -> None:
    """Contre-épreuve — et le prix peut arriver dans le même envoi."""
    formation = avec_une_lecon(une_formation(prix_cents=0))

    reponse = envoyer(
        client_admin, f"{ADMIN}{formation.id}/", {"en_ligne": "true", "prix_cents": 85_000}
    )

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["formation"]["en_ligne"] is True
    assert [f["slug"] for f in Client().get(PUBLIC).json()["formations"]] == [
        formation.slug
    ]


def test_retirer_le_prix_d_une_formation_EN_LIGNE_est_refuse(client_admin: Any) -> None:
    """La règle tient dans les deux sens, pas seulement au clic « en ligne »."""
    formation = avec_une_lecon(une_formation(en_ligne=True))

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"prix_cents": 0})

    assert reponse.status_code == 409
    # Le refus vient bien du PRIX : la formation a son programme.
    assert reponse.json()["erreur"].endswith("il lui manque un prix.")
    formation.refresh_from_db()
    assert formation.prix_cents == 149_000


def test_une_formation_se_met_hors_ligne_sans_disparaitre(client_admin: Any) -> None:
    formation = une_formation(en_ligne=True)
    un_module(formation)

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"en_ligne": False})

    assert reponse.status_code == 200
    assert Client().get(PUBLIC).json()["formations"] == []
    assert _lignes() == (1, 1, 0)


def test_la_base_refuse_une_formation_en_ligne_a_zero_euro() -> None:
    """Le dernier rempart : ce qui écrirait sans passer par les règles."""
    with pytest.raises(IntegrityError), transaction.atomic():
        Formation.objects.create(titre="Gratuite", slug="gratuite", en_ligne=True)

    # Contre-épreuve : la même, hors ligne, s'enregistre.
    Formation.objects.create(titre="Gratuite", slug="gratuite", en_ligne=False)


def test_mettre_en_ligne_SANS_LECON_est_refuse(client_admin: Any) -> None:
    """Une formation sans leçon encaisserait pour un espace vide.

    Un module ne suffit pas, ni une leçon retirée, ni une leçon rangée dans un
    module retiré : aucune ne serait lue par l'acheteur.
    """
    formation = une_formation()
    un_module(formation, titre="Module vide")
    une_lecon(
        un_module(formation, titre="Module garni", rang=1),
        retire_le="2026-11-01T10:00:00Z",
    )
    une_lecon(
        un_module(
            formation, titre="Module retiré", rang=2, retire_le="2026-11-01T10:00:00Z"
        )
    )

    reponse = envoyer(
        client_admin, f"{ADMIN}{formation.id}/", {"en_ligne": True, "accroche": "x"}
    )

    assert reponse.status_code == 409, reponse.content
    assert reponse.json()["code"] == "formation_incomplete"
    assert reponse.json()["erreur"].endswith("il lui manque au moins une leçon.")
    formation.refresh_from_db()
    assert formation.en_ligne is False
    assert formation.accroche == "", "un envoi refusé n'enregistre rien"
    fiche = client_admin.get(ADMIN).json()["formations"][0]
    assert (fiche["publiable"], fiche["manque"]) == (False, ["au moins une leçon"])


def test_mettre_en_ligne_AVEC_une_lecon_passe(client_admin: Any) -> None:
    """Contre-épreuve : une seule leçon présente suffit."""
    formation = une_formation()
    une_lecon(un_module(formation))

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"en_ligne": True})

    assert reponse.status_code == 200, reponse.content
    fiche = reponse.json()["formation"]
    assert (fiche["en_ligne"], fiche["publiable"], fiche["manque"]) == (True, True, [])


def test_retirer_la_DERNIERE_lecon_laisse_la_formation_affichee(
    client_admin: Any,
) -> None:
    """Un retrait de leçon n'est pas une mise hors ligne.

    La formation reste sur la page publique — la cliente est souvent en train
    de remplacer la leçon — mais sa fiche dit ce qui lui manque, et son achat
    est refusé (`test_achat_de_formation.py`).
    """
    formation = une_formation(en_ligne=True)
    lecon = une_lecon(un_module(formation))

    reponse = envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"retire": True})

    assert reponse.status_code == 200, reponse.content
    fiche = reponse.json()["formation"]
    assert fiche["en_ligne"] is True
    assert (fiche["publiable"], fiche["manque"]) == (False, ["au moins une leçon"])
    assert [f["slug"] for f in Client().get(PUBLIC).json()["formations"]] == [
        formation.slug
    ]
    assert regles.a_un_programme(Formation.objects.get(pk=formation.pk)) is False


def test_un_titre_trop_long_est_refuse_AVANT_la_base(client_admin: Any) -> None:
    """SQLite accepte 300 signes dans un champ de 200 ; PostgreSQL lève.

    Sans ce contrôle la suite est verte et la production rend 500.
    """
    formation = une_formation()

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"titre": "x" * 201})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "texte_trop_long"
    # Contre-épreuve : la longueur maximale exacte passe.
    assert (
        envoyer(client_admin, f"{ADMIN}{formation.id}/", {"titre": "x" * 200}).status_code
        == 200
    )


# ── 2. Le slug ───────────────────────────────────────────────────────────────


def test_le_slug_ne_suit_PAS_le_titre(client_admin: Any) -> None:
    """Un lien déjà diffusé ne doit pas casser parce qu'un titre est retouché."""
    formation = avec_une_lecon(une_formation(slug="creer-son-entreprise", en_ligne=True))

    reponse = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/",
        {"titre": "Un tout autre titre", "slug": "autre-adresse"},
    )

    assert reponse.status_code == 200
    formation.refresh_from_db()
    assert formation.titre == "Un tout autre titre"
    assert formation.slug == "creer-son-entreprise"
    assert [r["champ"] for r in reponse.json()["refuses"]] == ["slug"]


def test_deux_formations_du_meme_titre_ont_deux_slugs(client_admin: Any) -> None:
    premiere = envoyer(client_admin, ADMIN, {"titre": "Méthode P.O.P"}).json()
    seconde = envoyer(client_admin, ADMIN, {"titre": "Méthode P.O.P"}).json()

    assert premiere["formation"]["slug"] == "methode-pop"
    assert seconde["formation"]["slug"] == "methode-pop-2"


def test_l_adresse_peut_etre_proposee_a_la_creation(client_admin: Any) -> None:
    reponse = envoyer(
        client_admin, ADMIN, {"titre": "Méthode P.O.P", "slug": "La Méthode POP !"}
    )

    assert reponse.json()["formation"]["slug"] == "la-methode-pop"
    assert reponse.json()["refuses"] == []


# ── 3. Les adresses externes ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "adresse",
    [
        "http://vimeo.com/123456789",
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "https://vimeo.com/123 456",
        "https://vimeo.com/123\n456",
        "https://",
        "https:///chemin",
        "https://localhost/video",
        "https://evkha.fr@ailleurs.example/video",
        "https://vimeo.com/\"><script>",
        "//vimeo.com/123456789",
        "vimeo.com/123456789",
        "ftp://vimeo.com/123456789",
        "https://vimeo.com:port/1",
    ],
)
def test_une_adresse_qui_n_est_pas_du_https_bien_forme_est_refusee(adresse: str) -> None:
    with pytest.raises(regles.Refus) as refus:
        regles.adresse_https(adresse, code="adresse_video_invalide", champ="adresse_video")

    assert refus.value.code == "adresse_video_invalide"
    assert "https://" in refus.value.message


@pytest.mark.parametrize(
    ("adresse", "rendue"),
    [
        ("", ""),
        ("   ", ""),
        (VIDEO, VIDEO),
        (f"  {VIDEO}\n", VIDEO),
        ("HTTPS://Vimeo.com/1", "https://Vimeo.com/1"),
        (
            "https://www.youtube.com/watch?v=abc_DEF-123&t=42s#debut",
            "https://www.youtube.com/watch?v=abc_DEF-123&t=42s#debut",
        ),
        ("https://vidéos.exemple.fr:8443/a%20b", "https://vidéos.exemple.fr:8443/a%20b"),
    ],
)
def test_une_adresse_https_ou_vide_est_admise(adresse: str, rendue: str) -> None:
    """Contre-épreuve : la règle ne bloque ni le vide, ni les adresses réelles."""
    assert (
        regles.adresse_https(adresse, code="x", champ="adresse_video") == rendue
    )


def test_le_lien_d_achat_suit_la_MEME_regle_que_la_video(client_admin: Any) -> None:
    """Il part dans un `href` public : `javascript:` s'y exécuterait."""
    formation = une_formation(lien_d_achat="https://www.evkha.fr/paiement")

    reponse = envoyer(
        client_admin, f"{ADMIN}{formation.id}/", {"lien_d_achat": "javascript:alert(1)"}
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "lien_d_achat_invalide"
    assert reponse.json()["champ"] == "lien_d_achat"
    formation.refresh_from_db()
    assert formation.lien_d_achat == "https://www.evkha.fr/paiement"
    # Contre-épreuve : le vider reste possible.
    assert (
        envoyer(client_admin, f"{ADMIN}{formation.id}/", {"lien_d_achat": ""}).status_code
        == 200
    )


# ── 4. Les modules ───────────────────────────────────────────────────────────


def test_un_module_s_ajoute_en_FIN_de_liste(client_admin: Any) -> None:
    formation = une_formation()
    un_module(formation, titre="Premier", rang=0)
    un_module(formation, titre="Deuxième", rang=1)

    reponse = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/modules/",
        {"titre": "Troisième", "description": "Le financement"},
    )

    assert reponse.status_code == 201, reponse.content
    modules = reponse.json()["formation"]["modules"]
    assert [m["titre"] for m in modules] == ["Premier", "Deuxième", "Troisième"]
    assert modules[-1]["rang"] == 2
    assert modules[-1]["description"] == "Le financement"
    assert modules[-1]["id"] == reponse.json()["module_id"]
    assert reponse.json()["formation"]["nombre_de_modules"] == 3


def test_un_module_sans_titre_est_refuse(client_admin: Any) -> None:
    formation = une_formation()

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/modules/", {"description": "x"})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "titre_manquant"
    assert ModuleDeFormation.objects.count() == 0


def test_un_module_se_modifie(client_admin: Any) -> None:
    module = un_module(une_formation(), titre="Avant", description="Gardée")

    reponse = envoyer(client_admin, f"{ADMIN}modules/{module.id}/", {"titre": "Après"})

    assert reponse.status_code == 200
    module.refresh_from_db()
    assert (module.titre, module.description) == ("Après", "Gardée")


def test_le_rang_d_un_module_ne_se_change_pas_a_la_main(client_admin: Any) -> None:
    """Un rang écrit seul ferait deux modules à la même place."""
    module = un_module(une_formation(), rang=3)

    reponse = envoyer(client_admin, f"{ADMIN}modules/{module.id}/", {"rang": 0})

    assert [r["champ"] for r in reponse.json()["refuses"]] == ["rang"]
    module.refresh_from_db()
    assert module.rang == 3


# ── 5. Les leçons ────────────────────────────────────────────────────────────


def test_une_lecon_video_s_ajoute_avec_son_adresse(client_admin: Any) -> None:
    module = un_module(une_formation())
    une_lecon(module, titre="Première", rang=0)

    reponse = envoyer(
        client_admin,
        f"{ADMIN}modules/{module.id}/lecons/",
        {
            "titre": "Choisir son statut",
            "nature": "video",
            "adresse_video": VIDEO,
            "duree_minutes": 12,
            "en_apercu_libre": True,
        },
    )

    assert reponse.status_code == 201, reponse.content
    lecons = reponse.json()["formation"]["modules"][0]["lecons"]
    assert [ligne["titre"] for ligne in lecons] == ["Première", "Choisir son statut"]
    assert lecons[1] == {
        "id": reponse.json()["lecon_id"],
        "rang": 1,
        "titre": "Choisir son statut",
        "nature": "video",
        "adresse_video": VIDEO,
        "duree_minutes": 12,
        "texte": "",
        "fichier": "",
        "fichier_nom": "",
        "en_apercu_libre": True,
        "retire": False,
        "retire_le": "",
    }


def test_une_lecon_VIDEO_sans_adresse_est_refusee(client_admin: Any) -> None:
    module = un_module(une_formation())

    reponse = envoyer(
        client_admin,
        f"{ADMIN}modules/{module.id}/lecons/",
        {"titre": "Sans vidéo", "nature": "video"},
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "adresse_video_manquante"
    assert LeconDeFormation.objects.count() == 0


def test_une_lecon_TEXTE_sans_adresse_passe(client_admin: Any) -> None:
    """Contre-épreuve : l'adresse n'est exigée que d'une vidéo."""
    module = un_module(une_formation())

    reponse = envoyer(
        client_admin,
        f"{ADMIN}modules/{module.id}/lecons/",
        {"titre": "À lire", "texte": "Le contenu rédigé."},
    )

    assert reponse.status_code == 201, reponse.content
    lecon = LeconDeFormation.objects.get()
    assert (lecon.nature, lecon.texte, lecon.adresse_video) == (
        "texte", "Le contenu rédigé.", "",
    )


@pytest.mark.parametrize(
    "adresse", ["http://vimeo.com/123456789", "javascript:alert(1)", "https://vimeo.com/1 2"]
)
def test_une_adresse_video_refusee_laisse_la_precedente(
    client_admin: Any, adresse: str
) -> None:
    lecon = une_lecon(un_module(une_formation()), nature="video", adresse_video=VIDEO)

    reponse = envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"adresse_video": adresse})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "adresse_video_invalide"
    assert reponse.json()["champ"] == "adresse_video"
    lecon.refresh_from_db()
    assert lecon.adresse_video == VIDEO


def test_passer_une_lecon_en_video_exige_l_adresse(client_admin: Any) -> None:
    lecon = une_lecon(un_module(une_formation()), nature="texte")

    sans = envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"nature": "video"})
    avec = envoyer(
        client_admin,
        f"{ADMIN}lecons/{lecon.id}/",
        {"nature": "video", "adresse_video": VIDEO},
    )

    assert sans.status_code == 400
    assert sans.json()["code"] == "adresse_video_manquante"
    assert avec.status_code == 200
    lecon.refresh_from_db()
    assert lecon.nature == "video"


def test_une_nature_inconnue_est_refusee(client_admin: Any) -> None:
    lecon = une_lecon(un_module(une_formation()))

    reponse = envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"nature": "podcast"})

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "nature_inconnue"
    # Contre-épreuve : les quatre natures annoncées passent.
    for nature in ("texte", "document", "quiz"):
        assert (
            envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"nature": nature}).status_code
            == 200
        )


def test_la_base_refuse_une_lecon_video_sans_adresse() -> None:
    module = un_module(une_formation())

    with pytest.raises(IntegrityError), transaction.atomic():
        une_lecon(module, nature="video", adresse_video="")
    with pytest.raises(IntegrityError), transaction.atomic():
        une_lecon(module, nature="texte", adresse_video="javascript:alert(1)")

    une_lecon(module, nature="video", adresse_video=VIDEO)


# ── 6. Retirer et rétablir — jamais supprimer ────────────────────────────────


def test_un_module_se_RETIRE_sans_etre_supprime(client_admin: Any) -> None:
    formation = une_formation(en_ligne=True)
    garde = un_module(formation, titre="Gardé", rang=0)
    retire = un_module(formation, titre="Retiré", rang=1)
    une_lecon(retire)
    avant = _lignes()

    reponse = envoyer(client_admin, f"{ADMIN}modules/{retire.id}/", {"retire": True})

    assert reponse.status_code == 200, reponse.content
    assert _lignes() == avant, "un retrait ne supprime aucune ligne"
    retire.refresh_from_db()
    assert retire.retire_le is not None
    # L'administration le montre encore, marqué, après les présents.
    fiche = reponse.json()["formation"]
    assert [(m["titre"], m["retire"]) for m in fiche["modules"]] == [
        ("Gardé", False), ("Retiré", True),
    ]
    assert fiche["modules"][1]["retire_le"] != ""
    assert fiche["nombre_de_modules"] == 1
    # Le public ne le voit plus.
    publique = Client().get(PUBLIC).json()["formations"][0]
    assert [m["titre"] for m in publique["modules"]] == [garde.titre]
    assert publique["nombre_de_modules"] == 1


def test_un_module_retire_se_RETABLIT_en_fin_de_liste(client_admin: Any) -> None:
    formation = une_formation(en_ligne=True)
    revenant = un_module(formation, titre="Revenant", rang=0)
    un_module(formation, titre="Resté", rang=1)
    envoyer(client_admin, f"{ADMIN}modules/{revenant.id}/", {"retire": True})
    avant = _lignes()

    reponse = envoyer(client_admin, f"{ADMIN}modules/{revenant.id}/", {"retire": False})

    assert reponse.status_code == 200
    assert _lignes() == avant
    fiche = reponse.json()["formation"]
    assert [(m["titre"], m["retire"], m["rang"]) for m in fiche["modules"]] == [
        ("Resté", False, 1), ("Revenant", False, 2),
    ]
    publique = Client().get(PUBLIC).json()["formations"][0]
    assert [m["titre"] for m in publique["modules"]] == ["Resté", "Revenant"]


def test_retablir_un_module_PRESENT_ne_le_deplace_pas(client_admin: Any) -> None:
    """Contre-épreuve : `retire: false` sur un présent ne réordonne rien."""
    formation = une_formation()
    premier = un_module(formation, titre="Premier", rang=0)
    un_module(formation, titre="Second", rang=1)

    envoyer(client_admin, f"{ADMIN}modules/{premier.id}/", {"retire": False})

    premier.refresh_from_db()
    assert premier.rang == 0


def test_une_lecon_se_retire_et_se_retablit(client_admin: Any) -> None:
    formation = une_formation(en_ligne=True)
    module = un_module(formation)
    lecon = une_lecon(module, titre="Passagère", rang=0)
    une_lecon(module, titre="Durable", rang=1)
    avant = _lignes()

    retrait = envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"retire": "true"})

    assert retrait.status_code == 200
    assert _lignes() == avant
    lecons = retrait.json()["formation"]["modules"][0]["lecons"]
    assert [(ligne["titre"], ligne["retire"]) for ligne in lecons] == [
        ("Durable", False), ("Passagère", True),
    ]
    publiques = Client().get(PUBLIC).json()["formations"][0]["modules"][0]["lecons"]
    assert [ligne["titre"] for ligne in publiques] == ["Durable"]

    retour = envoyer(client_admin, f"{ADMIN}lecons/{lecon.id}/", {"retire": "false"})

    assert _lignes() == avant
    lecons = retour.json()["formation"]["modules"][0]["lecons"]
    assert [(ligne["titre"], ligne["retire"]) for ligne in lecons] == [
        ("Durable", False), ("Passagère", False),
    ]


def test_un_retrait_illisible_ne_retire_rien(client_admin: Any) -> None:
    module = un_module(une_formation())

    reponse = envoyer(client_admin, f"{ADMIN}modules/{module.id}/", {"retire": "peut-être"})

    assert [r["champ"] for r in reponse.json()["refuses"]] == ["retire"]
    module.refresh_from_db()
    assert module.retire_le is None


def test_AUCUNE_route_n_accepte_de_supprimer(client_admin: Any) -> None:
    """La règle du client : on ne supprime jamais définitivement une donnée."""
    formation = une_formation()
    module = un_module(formation)
    lecon = une_lecon(module)
    avant = _lignes()

    for adresse in (
        ADMIN,
        f"{ADMIN}{formation.id}/",
        f"{ADMIN}{formation.id}/modules/",
        f"{ADMIN}{formation.id}/ordre/",
        f"{ADMIN}modules/{module.id}/",
        f"{ADMIN}modules/{module.id}/lecons/",
        f"{ADMIN}modules/{module.id}/ordre/",
        f"{ADMIN}lecons/{lecon.id}/",
    ):
        assert client_admin.delete(adresse).status_code == 405, adresse

    assert _lignes() == avant


# ── 7. Réordonner ────────────────────────────────────────────────────────────


def _trois_modules() -> tuple[Formation, list[ModuleDeFormation]]:
    formation = une_formation()
    return formation, [
        un_module(formation, titre=titre, rang=rang)
        for rang, titre in enumerate(["A", "B", "C"])
    ]


def _ordre(formation: Formation) -> list[str]:
    return list(
        ModuleDeFormation.objects.filter(formation=formation, retire_le__isnull=True)
        .order_by("rang", "created_at")
        .values_list("titre", flat=True)
    )


def test_les_modules_se_reordonnent(client_admin: Any) -> None:
    formation, (a, b, c) = _trois_modules()

    reponse = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/ordre/",
        {"modules": [str(c.id), str(a.id), str(b.id)]},
    )

    assert reponse.status_code == 200, reponse.content
    assert _ordre(formation) == ["C", "A", "B"]
    assert [
        (m["titre"], m["rang"]) for m in reponse.json()["formation"]["modules"]
    ] == [("C", 0), ("A", 1), ("B", 2)]


def test_un_ordre_INCOMPLET_est_refuse(client_admin: Any) -> None:
    formation, (a, b, _c) = _trois_modules()

    reponse = envoyer(
        client_admin, f"{ADMIN}{formation.id}/ordre/", {"modules": [str(b.id), str(a.id)]}
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "ordre_incomplet"
    assert _ordre(formation) == ["A", "B", "C"]


def test_un_ordre_avec_un_DOUBLON_est_refuse(client_admin: Any) -> None:
    formation, (a, b, _c) = _trois_modules()

    reponse = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/ordre/",
        {"modules": [str(b.id), str(a.id), str(b.id)]},
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "ordre_doublon"
    assert _ordre(formation) == ["A", "B", "C"]


def test_un_ordre_avec_un_identifiant_ETRANGER_est_refuse(client_admin: Any) -> None:
    formation, (a, b, c) = _trois_modules()

    for intrus in (str(uuid.uuid4()), "pas-un-identifiant"):
        reponse = envoyer(
            client_admin,
            f"{ADMIN}{formation.id}/ordre/",
            {"modules": [str(c.id), str(b.id), str(a.id), intrus]},
        )

        assert reponse.status_code == 400, intrus
        assert reponse.json()["code"] == "ordre_etranger"
    assert _ordre(formation) == ["A", "B", "C"]


def test_le_module_d_une_AUTRE_formation_est_refuse_dans_l_ordre(
    client_admin: Any,
) -> None:
    """L'isolation : réordonner une formation ne touche jamais sa voisine."""
    formation, (a, b, c) = _trois_modules()
    voisine = une_formation()
    d_ailleurs = un_module(voisine, titre="Voisin", rang=7)

    # À la place d'un module de la formation : même nombre, mais un étranger.
    reponse = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/ordre/",
        {"modules": [str(d_ailleurs.id), str(b.id), str(a.id)]},
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "ordre_etranger"
    assert _ordre(formation) == ["A", "B", "C"]
    d_ailleurs.refresh_from_db()
    assert d_ailleurs.rang == 7
    c.refresh_from_db()
    assert c.rang == 2, "le module écarté de la liste n'a pas bougé non plus"


def test_un_module_RETIRE_ne_fait_pas_partie_de_l_ordre(client_admin: Any) -> None:
    formation, (a, b, c) = _trois_modules()
    envoyer(client_admin, f"{ADMIN}modules/{b.id}/", {"retire": True})

    avec = envoyer(
        client_admin,
        f"{ADMIN}{formation.id}/ordre/",
        {"modules": [str(c.id), str(b.id), str(a.id)]},
    )
    sans = envoyer(
        client_admin, f"{ADMIN}{formation.id}/ordre/", {"modules": [str(c.id), str(a.id)]}
    )

    assert avec.status_code == 400
    assert avec.json()["code"] == "ordre_etranger"
    # Contre-épreuve : la liste des seuls présents est l'ordre complet.
    assert sans.status_code == 200
    assert _ordre(formation) == ["C", "A"]


def test_un_ordre_qui_n_est_pas_une_liste_est_refuse(client_admin: Any) -> None:
    formation, _ = _trois_modules()

    charges: list[dict[str, Any]] = [{}, {"modules": "abc"}, {"lecons": []}]
    for charge in charges:
        reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/ordre/", charge)
        assert reponse.status_code == 400
        assert reponse.json()["code"] == "ordre_illisible"
    assert _ordre(formation) == ["A", "B", "C"]


def test_les_lecons_se_reordonnent_et_restent_dans_leur_module(
    client_admin: Any,
) -> None:
    formation = une_formation()
    module = un_module(formation, rang=0)
    voisin = un_module(formation, titre="Voisin", rang=1)
    x = une_lecon(module, titre="X", rang=0)
    y = une_lecon(module, titre="Y", rang=1)
    z = une_lecon(voisin, titre="Z", rang=5)

    etrangere = envoyer(
        client_admin, f"{ADMIN}modules/{module.id}/ordre/", {"lecons": [str(z.id), str(x.id)]}
    )
    juste = envoyer(
        client_admin, f"{ADMIN}modules/{module.id}/ordre/", {"lecons": [str(y.id), str(x.id)]}
    )

    assert etrangere.status_code == 400
    assert etrangere.json()["code"] == "ordre_etranger"
    assert juste.status_code == 200, juste.content
    assert [
        ligne["titre"] for ligne in juste.json()["formation"]["modules"][0]["lecons"]
    ] == ["Y", "X"]
    z.refresh_from_db()
    assert z.rang == 5


# ── 8. La garde, les identifiants, les corps ─────────────────────────────────

_UN_ID = "5f0c1f0e-7d0a-4c56-9d6e-2a4b8a1f3c11"
ROUTES = [
    ("get", ADMIN),
    ("post", ADMIN),
    ("post", f"{ADMIN}{_UN_ID}/"),
    ("post", f"{ADMIN}{_UN_ID}/modules/"),
    ("post", f"{ADMIN}{_UN_ID}/ordre/"),
    ("post", f"{ADMIN}modules/{_UN_ID}/"),
    ("post", f"{ADMIN}modules/{_UN_ID}/lecons/"),
    ("post", f"{ADMIN}modules/{_UN_ID}/ordre/"),
    ("post", f"{ADMIN}lecons/{_UN_ID}/"),
]


@pytest.mark.parametrize(("methode", "adresse"), ROUTES)
def test_sans_jeton_l_administration_des_formations_est_fermee(
    methode: str, adresse: str
) -> None:
    reponse = getattr(Client(), methode)(adresse)

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "unauthorized"


@pytest.mark.parametrize(("methode", "adresse"), ROUTES)
def test_avec_le_jeton_la_route_repond(
    client_admin: Any, methode: str, adresse: str
) -> None:
    """Contre-épreuve : le 401 vient bien du jeton absent, pas de la route."""
    assert getattr(client_admin, methode)(adresse).status_code != 401


def test_un_mauvais_jeton_ne_cree_rien() -> None:
    client = Client(HTTP_AUTHORIZATION="Bearer un-jeton-qui-n-est-pas-le-bon")

    reponse = envoyer(client, ADMIN, {"titre": "Intruse"})

    assert reponse.status_code == 401
    assert Formation.objects.count() == 0


@pytest.mark.parametrize("identifiant", ["pas-un-uuid", "123", _UN_ID])
@pytest.mark.parametrize(
    ("gabarit", "code"),
    [
        ("{}/", "formation_inconnue"),
        ("{}/modules/", "formation_inconnue"),
        ("{}/ordre/", "formation_inconnue"),
        ("modules/{}/", "module_inconnu"),
        ("modules/{}/lecons/", "module_inconnu"),
        ("modules/{}/ordre/", "module_inconnu"),
        ("lecons/{}/", "lecon_inconnue"),
    ],
)
def test_un_identifiant_inconnu_OU_mal_forme_rend_404(
    client_admin: Any, gabarit: str, code: str, identifiant: str
) -> None:
    """Filtrer un `UUIDField` sur « pas-un-uuid » lève : c'était un 500."""
    reponse = envoyer(client_admin, ADMIN + gabarit.format(identifiant), {"titre": "x"})

    assert reponse.status_code == 404
    assert reponse.json()["code"] == code
    assert reponse.json()["erreur"]


def test_un_corps_JSON_illisible_est_refuse(client_admin: Any) -> None:
    """Le lire comme un envoi vide répondrait « 200 » à un écran qui croit
    avoir enregistré."""
    formation = une_formation()

    for corps in ('{"titre": ', "[1, 2]", '"texte"'):
        reponse = client_admin.post(
            f"{ADMIN}{formation.id}/", data=corps, content_type="application/json"
        )
        assert reponse.status_code == 400, corps
        assert reponse.json()["code"] == "corps_invalide"

    # Contre-épreuve : un envoi vide est un envoi qui ne change rien.
    vide = client_admin.post(
        f"{ADMIN}{formation.id}/", data="", content_type="application/json"
    )
    assert vide.status_code == 200


def test_un_envoi_trop_lourd_n_atteint_pas_les_formations(
    client_admin: Any, settings: Any
) -> None:
    """La borne de `evkha/corps.py` couvre ces routes sans qu'on y pense."""
    reponse = client_admin.post(
        ADMIN,
        data='{"titre": "Lourde"}',
        content_type="application/json",
        CONTENT_LENGTH=str(settings.EVKHA_TAILLE_MAX_REQUETE + 1),
    )

    assert reponse.status_code == 413
    assert Formation.objects.count() == 0


# ── 9. Les fichiers ──────────────────────────────────────────────────────────


def test_la_couverture_se_depose_et_se_sert_EN_LIGNE(
    client_admin: Any, tmp_path: Any
) -> None:
    """Elle doit s'afficher dans une balise `<img>` : ni signature, ni pièce
    jointe — et son extension est celle du format LU, pas celle du nom."""
    from evkha.media import servir_media  # noqa: PLC0415

    formation = avec_une_lecon(une_formation(slug="methode-pop", en_ligne=True))

    reponse = client_admin.post(
        f"{ADMIN}{formation.id}/",
        {"image": SimpleUploadedFile("couverture.html", _png(), "text/html")},
    )

    assert reponse.status_code == 200, reponse.content
    adresse = reponse.json()["formation"]["image"]
    assert adresse.startswith(
        f"https://api2.evkha.fr/media/{PREFIXE_VITRINE_FORMATIONS}/methode-pop/"
    )
    assert adresse.endswith(".png")
    assert Client().get(PUBLIC).json()["formations"][0]["image"] == adresse

    chemin = adresse.replace("https://api2.evkha.fr/media/", "")
    servie = servir_media(RequestFactory().get("/"), chemin, document_root=tmp_path)
    assert servie.status_code == 200
    assert servie.headers["Content-Disposition"] == "inline"


def test_une_couverture_qui_n_est_pas_une_image_est_refusee(client_admin: Any) -> None:
    formation = une_formation()

    reponse = client_admin.post(
        f"{ADMIN}{formation.id}/",
        {
            "image": SimpleUploadedFile("c.png", b"<script>alert(1)</script>", "image/png"),
            "accroche": "Ne doit pas être enregistrée",
        },
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "image_refusee"
    formation.refresh_from_db()
    assert not formation.image
    assert formation.accroche == ""


def test_chaque_format_de_couverture_est_servi_en_ligne() -> None:
    """Sinon la couverture est acceptée au dépôt, puis introuvable à l'écran."""
    from evkha.media import EXTENSIONS_EN_LIGNE  # noqa: PLC0415

    assert set(regles.FORMATS_D_IMAGE.values()) <= EXTENSIONS_EN_LIGNE


def test_le_document_d_une_lecon_se_depose_et_reste_SIGNE(
    client_admin: Any, tmp_path: Any
) -> None:
    """C'est du contenu payant : il vit hors de la vitrine."""
    from evkha.media import servir_media  # noqa: PLC0415

    formation = une_formation(slug="methode-pop")
    lecon = une_lecon(un_module(formation), nature="document")

    reponse = client_admin.post(
        f"{ADMIN}lecons/{lecon.id}/",
        {"fichier": SimpleUploadedFile("support.html", b"%PDF-1.4 cours", "text/html")},
    )

    assert reponse.status_code == 200, reponse.content
    vue = reponse.json()["formation"]["modules"][0]["lecons"][0]
    # L'extension du client (`.html`) est remplacée par celle du format lu.
    assert vue["fichier_nom"] == "support.pdf"
    lecon.refresh_from_db()
    assert lecon.fichier.name == "formations/methode-pop/support.pdf"
    assert not lecon.fichier.name.startswith(PREFIXE_VITRINE_FORMATIONS)

    with pytest.raises(Http404):
        servir_media(RequestFactory().get("/"), lecon.fichier.name, document_root=tmp_path)
    # Contre-épreuve : le lien rendu à l'administration, lui, ouvre le fichier.
    assert vue["fichier"].startswith("https://api2.evkha.fr/media/formations/methode-pop/")
    signature = vue["fichier"].split("?s=", 1)[1]
    servi = servir_media(
        RequestFactory().get("/", {"s": signature}),
        lecon.fichier.name,
        document_root=tmp_path,
    )
    assert servi.status_code == 200
    assert servi.headers["Content-Disposition"] == "attachment"


def test_une_VIDEO_ne_se_depose_pas_sur_le_serveur(client_admin: Any) -> None:
    """Contrainte du client : la place disque. Une vidéo se donne par son
    adresse, jamais par son fichier."""
    lecon = une_lecon(un_module(une_formation()))
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64

    reponse = client_admin.post(
        f"{ADMIN}lecons/{lecon.id}/",
        {"fichier": SimpleUploadedFile("cours.mp4", mp4, "video/mp4")},
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "document_refuse"
    lecon.refresh_from_db()
    assert not lecon.fichier


# ── 10. Ce que le public reçoit ──────────────────────────────────────────────


def _programme_complet() -> Formation:
    """Une formation en ligne dont chaque leçon porte du contenu payant."""
    formation = une_formation(
        slug="creer-son-entreprise",
        sous_titre="De l'idée au premier client",
        accroche="Dix-huit heures pour se lancer.",
        description="Présentation longue.",
        duree_heures=18,
        heures_de_coaching=2,
        lien_d_achat="https://www.evkha.fr/paiement-formationsociete",
        en_ligne=True,
    )
    module = un_module(formation, titre="Le statut", description="SARL ou SAS ?", rang=3)
    video = une_lecon(
        module,
        titre="Choisir son statut",
        nature="video",
        adresse_video="https://vimeo.com/secret-987654",
        duree_minutes=12,
        texte="TEXTE-RESERVE-AUX-ACHETEURS",
        en_apercu_libre=True,
        rang=4,
    )
    video.fichier.save(
        "support-reserve.pdf", SimpleUploadedFile("s.pdf", b"%PDF-1.4"), save=True
    )
    une_lecon(module, titre="Leçon retirée", rang=0, retire_le="2026-11-01T10:00:00Z")
    un_module(formation, titre="Module retiré", rang=0, retire_le="2026-11-01T10:00:00Z")
    return formation


def test_la_reponse_publique_a_EXACTEMENT_la_forme_annoncee() -> None:
    _programme_complet()

    charge = Client().get(PUBLIC).json()

    assert charge == {
        "formations": [
            {
                "slug": "creer-son-entreprise",
                "titre": "Créer son entreprise de A à Z",
                "sous_titre": "De l'idée au premier client",
                "accroche": "Dix-huit heures pour se lancer.",
                "prix_cents": 149_000,
                "devise": "EUR",
                "duree_heures": 18,
                "heures_de_coaching": 2,
                "lien_d_achat": "https://www.evkha.fr/paiement-formationsociete",
                "image": "",
                "nombre_de_modules": 1,
                "modules": [
                    {
                        "rang": 1,
                        "titre": "Le statut",
                        "description": "SARL ou SAS ?",
                        "lecons": [
                            {
                                "rang": 1,
                                "titre": "Choisir son statut",
                                "nature": "video",
                                "duree_minutes": 12,
                                "en_apercu_libre": True,
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _cles(valeur: Any) -> set[str]:
    if isinstance(valeur, dict):
        return set(valeur) | {c for v in valeur.values() for c in _cles(v)}
    if isinstance(valeur, list):
        return {c for v in valeur for c in _cles(v)}
    return set()


def test_le_contenu_PAYANT_n_apparait_dans_aucune_reponse_publique() -> None:
    """Ni par sa clé, ni par sa valeur — même pour une leçon en aperçu libre.

    Le contrôle porte sur le TEXTE de la réponse autant que sur ses clés : un
    contenu glissé sous un autre nom ne passerait pas un test de clés.
    """
    _programme_complet()

    reponse = Client().get(PUBLIC)

    texte = reponse.content.decode()
    assert not (_cles(reponse.json()) & set(regles.CONTENU_PAYANT))
    for secret in ("secret-987654", "TEXTE-RESERVE", "support-reserve", "/media/formations/"):
        assert secret not in texte, secret
    # Contre-épreuve : la leçon est bien là, et l'administration, elle, voit
    # son contenu — le test ne passe pas parce que la réponse serait vide.
    assert "Choisir son statut" in texte


def test_l_administration_voit_le_contenu_que_le_public_ne_voit_pas(
    client_admin: Any,
) -> None:
    _programme_complet()

    lecons = client_admin.get(ADMIN).json()["formations"][0]["modules"]
    video = next(ligne for m in lecons for ligne in m["lecons"] if ligne["nature"] == "video")

    assert video["adresse_video"] == "https://vimeo.com/secret-987654"
    assert video["texte"] == "TEXTE-RESERVE-AUX-ACHETEURS"
    assert "support-reserve" in video["fichier"]


def test_le_public_ne_voit_que_les_formations_EN_LIGNE() -> None:
    en_ligne = une_formation(titre="Publiée", en_ligne=True, rang=1)
    une_formation(titre="Brouillon", en_ligne=False, rang=0)

    slugs = [f["slug"] for f in Client().get(PUBLIC).json()["formations"]]

    assert slugs == [en_ligne.slug]


def test_les_formations_sortent_dans_l_ordre_des_rangs() -> None:
    une_formation(titre="Seconde", slug="b", en_ligne=True, rang=2)
    une_formation(titre="Première", slug="a", en_ligne=True, rang=1)

    titres = [f["titre"] for f in Client().get(PUBLIC).json()["formations"]]

    assert titres == ["Première", "Seconde"]


def test_la_route_publique_ne_s_ecrit_pas() -> None:
    assert Client().post(PUBLIC, {"titre": "x"}).status_code == 405


def _garnir(nombre: int) -> None:
    for numero in range(nombre):
        formation = une_formation(en_ligne=True, rang=numero)
        for rang_module in range(3):
            module = un_module(formation, rang=rang_module)
            for rang_lecon in range(3):
                une_lecon(module, rang=rang_lecon)


def test_la_liste_publique_coute_TROIS_requetes_quel_que_soit_le_volume(
    django_assert_num_queries: Any,
) -> None:
    """Formations, modules, leçons : pas une requête de plus par formation."""
    _garnir(1)
    with django_assert_num_queries(3):
        assert len(Client().get(PUBLIC).json()["formations"]) == 1

    _garnir(5)
    with django_assert_num_queries(3):
        charge = Client().get(PUBLIC).json()["formations"]
    assert len(charge) == 6
    assert sum(len(m["lecons"]) for f in charge for m in f["modules"]) == 54


def test_la_liste_d_administration_coute_trois_requetes_aussi(
    client_admin: Any, django_assert_num_queries: Any
) -> None:
    _garnir(4)

    with django_assert_num_queries(3):
        charge = client_admin.get(ADMIN).json()["formations"]

    assert len(charge) == 4


# ── 11. L'amorçage ───────────────────────────────────────────────────────────


def _amorcer() -> str:
    sortie = io.StringIO()
    call_command("seed_formations", stdout=sortie)
    return sortie.getvalue()


def test_l_amorcage_cree_les_trois_formations_HORS_LIGNE_et_sans_module() -> None:
    sortie = _amorcer()

    fiches = {
        f.slug: (f.titre, f.prix_cents, f.duree_heures, f.heures_de_coaching, f.lien_d_achat)
        for f in Formation.objects.all()
    }
    assert fiches == {
        # Le lien d'achat est VIDE : les pages de paiement de l'ancien site
        # n'existent plus, une formation se paie par Stripe sur la plateforme.
        "creer-son-entreprise": ("Créer son entreprise de A à Z", 149_000, 18, 2, ""),
        "creer-sa-micro-entreprise": (
            "Créer sa micro-entreprise de A à Z", 149_000, 18, 2, "",
        ),
        "methode-pop": ("Méthode P.O.P", 85_000, 7, 0, ""),
    }
    assert not Formation.objects.filter(en_ligne=True).exists()
    assert ModuleDeFormation.objects.count() == 0
    assert Client().get(PUBLIC).json()["formations"] == []
    assert sortie.count("[CRÉÉE]") == 3
    assert "3 formation(s) créée(s), 0 déjà" in sortie


def test_l_amorcage_rejoue_ne_cree_ni_ne_modifie_rien() -> None:
    """La cliente a changé un prix, un titre, et publié : la commande, relancée
    à un déploiement, ne doit rien lui reprendre."""
    _amorcer()
    modifiee = Formation.objects.get(slug="methode-pop")
    modifiee.titre = "La méthode P.O.P, édition 2027"
    modifiee.prix_cents = 99_000
    modifiee.lien_d_achat = "https://exemple.fr/saisi-a-la-main"
    modifiee.en_ligne = True
    modifiee.save()
    un_module(modifiee, titre="Saisi à la main")

    sortie = _amorcer()

    assert Formation.objects.count() == 3
    modifiee.refresh_from_db()
    assert (modifiee.titre, modifiee.prix_cents, modifiee.lien_d_achat, modifiee.en_ligne) == (
        "La méthode P.O.P, édition 2027", 99_000, "https://exemple.fr/saisi-a-la-main", True,
    )
    assert modifiee.modules.count() == 1
    assert sortie.count("[LAISSÉE]") == 3
    assert "0 formation(s) créée(s), 3 déjà" in sortie


def test_l_amorcage_complete_une_fiche_ABSENTE_sans_toucher_les_autres() -> None:
    """Contre-épreuve : « ne rien modifier » ne veut pas dire « ne rien faire »."""
    une_formation(slug="methode-pop", titre="Déjà là", prix_cents=1)

    sortie = _amorcer()

    assert Formation.objects.count() == 3
    assert Formation.objects.get(slug="methode-pop").titre == "Déjà là"
    assert sortie.count("[CRÉÉE]") == 2
    assert sortie.count("[LAISSÉE]") == 1


# ── 13. Une saisie démesurée est un refus, pas une erreur 500 ────────────────


def test_un_prix_demesure_est_ecarte_et_ne_fait_pas_tomber_la_route(
    client_admin: Any,
) -> None:
    """`Decimal("1e30")` est fini, mais ne se quantifie pas : la route rendait 500."""
    formation = une_formation(prix_cents=149_000)

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"prix_euros": "1e30"})

    assert reponse.status_code < 500, reponse.content
    formation.refresh_from_db()
    assert formation.prix_cents == 149_000


def test_un_corps_imbrique_a_l_exces_est_refuse_proprement(client_admin: Any) -> None:
    formation = une_formation()
    corps = "[" * 100_000 + "]" * 100_000

    reponse = client_admin.post(
        f"{ADMIN}{formation.id}/", data=corps, content_type="application/json"
    )

    assert reponse.status_code == 400, reponse.status_code
    assert reponse.json()["code"] == "corps_invalide"


def test_le_lien_du_document_rendu_a_l_administration_expire_vite() -> None:
    """Cinq minutes : l'écran le relit au moment d'ouvrir (audit du 20/11/2026)."""
    from dashboard import formations as vues  # noqa: PLC0415

    assert 0 < vues._VIE_DU_LIEN_S <= 600


def test_une_devise_qui_n_est_pas_en_lettres_simples_est_refusee(
    client_admin: Any,
) -> None:
    """« ééé » est alphabétique : le navigateur, lui, refuse une devise pareille."""
    formation = une_formation()

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"devise": "ééé"})

    formation.refresh_from_db()
    assert formation.devise == "EUR", reponse.content


def test_une_ecriture_part_de_ce_qui_est_en_base_et_non_de_ce_qui_fut_lu(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Une mise hors ligne survenue PENDANT l'envoi d'une fiche n'est pas écrasée.

    On la simule au seul instant où elle peut se glisser : entre la lecture
    de la cible et la transaction, c'est-à-dire pendant la lecture du corps.
    """
    from dashboard import formations as vues  # noqa: PLC0415

    formation = une_formation(en_ligne=True, prix_cents=149_000)
    lire = vues._donnees

    def lire_pendant_qu_on_met_hors_ligne(request: Any) -> Any:
        Formation.objects.filter(pk=formation.pk).update(en_ligne=False)
        return lire(request)

    monkeypatch.setattr(vues, "_donnees", lire_pendant_qu_on_met_hors_ligne)

    reponse = envoyer(client_admin, f"{ADMIN}{formation.id}/", {"accroche": "Neuve"})

    assert reponse.status_code == 200, reponse.content
    formation.refresh_from_db()
    assert formation.accroche == "Neuve"
    assert formation.en_ligne is False
