"""L'audience du site : ressources gratuites contre une adresse, et lettre.

Demande de la cliente du 24/11/2026 : téléchargement IMMÉDIAT des PDF (elle
ne veut plus les envoyer elle-même), qui récolte les adresses ; inscription à
la lettre sur le blog.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from audience.models import Contact, Demande
from audience.vues_publiques import (
    FICHIERS,
    INSCRIPTIONS_GLOBALES_PAR_HEURE,
    INSCRIPTIONS_PAR_HEURE,
    cle_de_l_appelant,
)

pytestmark = pytest.mark.django_db

RESSOURCES = "/api/public/ressources/"
LETTRE = "/api/public/lettre/"


def _poster(adresse: str, charge: Any) -> Any:
    return Client().post(adresse, data=json.dumps(charge), content_type="application/json")


def _confirmer(email: str) -> None:
    """Le clic dans le courriel de confirmation (double consentement)."""
    from lettre.gabarit import jeton_de_confirmation

    contact = Contact.objects.get(email=email)
    reponse = Client().post(f"/l/confirmation/{jeton_de_confirmation(contact)}/")
    assert reponse.status_code == 200


# ── Les ressources ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("nom", ["checklist", "lexique"])
def test_une_ressource_rend_son_pdf_et_note_l_adresse(nom: str) -> None:
    reponse = _poster(RESSOURCES, {"email": "marie@exemple.fr", "ressource": nom})

    assert reponse.status_code == 200
    assert reponse.json() == {"lien": FICHIERS[nom]}
    contact = Contact.objects.get(email="marie@exemple.fr")
    assert [d.origine for d in contact.demandes.all()] == [nom]
    # Prendre une ressource ne vaut PAS inscription à la lettre.
    assert contact.inscrit_a_la_lettre is False


def test_les_fichiers_annonces_existent_dans_le_site() -> None:
    from pathlib import Path

    racine = Path(__file__).resolve().parents[2] / "frontend" / "public"
    for lien in FICHIERS.values():
        fichier = racine / lien.lstrip("/")
        assert fichier.is_file(), lien
        assert fichier.read_bytes()[:5] == b"%PDF-", lien


def test_la_case_de_la_lettre_cochee_inscrit_et_seulement_elle() -> None:
    _poster(RESSOURCES, {"email": "a@exemple.fr", "ressource": "lexique", "lettre": True})
    # Une valeur « vraie » qui n'est pas `true` n'est pas un consentement.
    _poster(RESSOURCES, {"email": "b@exemple.fr", "ressource": "lexique", "lettre": "oui"})

    a = Contact.objects.get(email="a@exemple.fr")
    b = Contact.objects.get(email="b@exemple.fr")
    # Cocher DEMANDE l'inscription ; elle n'est faite qu'à la confirmation.
    assert a.inscrit_a_la_lettre is False
    assert a.confirmation_demandee_le is not None
    assert b.confirmation_demandee_le is None
    _confirmer("a@exemple.fr")
    assert Contact.objects.get(email="a@exemple.fr").inscrit_a_la_lettre is True
    assert Contact.objects.get(email="b@exemple.fr").inscrit_a_la_lettre is False


def test_une_meme_personne_est_un_seul_contact_quelle_que_soit_la_casse() -> None:
    _poster(RESSOURCES, {"email": "Marie@Exemple.FR", "ressource": "checklist"})
    _poster(RESSOURCES, {"email": " marie@exemple.fr ", "ressource": "lexique"})

    assert Contact.objects.count() == 1
    contact = Contact.objects.get()
    assert contact.email == "marie@exemple.fr"
    assert sorted(d.origine for d in contact.demandes.all()) == ["checklist", "lexique"]


@pytest.mark.parametrize(
    ("charge", "code"),
    [
        ({"email": "pas-une-adresse", "ressource": "checklist"}, "adresse_invalide"),
        ({"email": "", "ressource": "checklist"}, "adresse_invalide"),
        ({"email": 42, "ressource": "checklist"}, "adresse_invalide"),
        ({"email": "a@exemple.fr", "ressource": "../../etc/passwd"}, "ressource_inconnue"),
        ({"email": "a@exemple.fr"}, "ressource_inconnue"),
        ({"email": "a@exemple.fr", "ressource": []}, "ressource_inconnue"),
        ({"email": "a@exemple.fr", "ressource": {"x": 1}}, "ressource_inconnue"),
    ],
)
def test_contre_epreuve_une_saisie_fausse_est_refusee_sans_rien_ecrire(
    charge: dict[str, Any], code: str
) -> None:
    reponse = _poster(RESSOURCES, charge)
    assert reponse.status_code == 400
    assert reponse.json()["code"] == code
    assert Contact.objects.count() == 0


def test_un_corps_illisible_est_refuse() -> None:
    reponse = Client().post(RESSOURCES, data="pas du json", content_type="application/json")
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "corps_invalide"


def test_le_champ_piege_rempli_repond_comme_un_succes_sans_rien_ecrire() -> None:
    reponse = _poster(
        RESSOURCES, {"email": "robot@exemple.fr", "ressource": "checklist", "site": "http://spam"}
    )
    assert reponse.status_code == 200
    assert reponse.json() == {"lien": FICHIERS["checklist"]}
    assert Contact.objects.count() == 0


def test_le_plafond_par_adresse_ip_arrete_une_salve() -> None:
    for k in range(INSCRIPTIONS_PAR_HEURE.maximum):
        reponse = _poster(RESSOURCES, {"email": f"p{k}@exemple.fr", "ressource": "checklist"})
        assert reponse.status_code == 200
    reponse = _poster(RESSOURCES, {"email": "de-trop@exemple.fr", "ressource": "checklist"})
    assert reponse.status_code == 429
    assert not Contact.objects.filter(email="de-trop@exemple.fr").exists()


def test_seul_post_est_accepte() -> None:
    assert Client().get(RESSOURCES).status_code == 405
    assert Client().get(LETTRE).status_code == 405


# ── La lettre ────────────────────────────────────────────────────────────────


def test_l_inscription_a_la_lettre_est_un_consentement_date_et_confirme() -> None:
    reponse = _poster(LETTRE, {"email": "lea@exemple.fr"})

    assert reponse.status_code == 200
    assert reponse.json() == {"inscrit": True}
    contact = Contact.objects.get(email="lea@exemple.fr")
    # Double consentement (26/11/2026) : la requête anonyme ne fait que
    # demander ; seul le lien reçu dans la boîte inscrit.
    assert contact.inscrit_a_la_lettre is False
    assert contact.lettre_le is None
    assert contact.confirmation_demandee_le is not None
    assert [d.origine for d in contact.demandes.all()] == ["lettre"]

    _confirmer("lea@exemple.fr")
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is True
    assert contact.lettre_le is not None


def test_une_seconde_inscription_garde_la_date_de_la_premiere() -> None:
    _poster(LETTRE, {"email": "lea@exemple.fr"})
    _confirmer("lea@exemple.fr")
    premiere = Contact.objects.get().lettre_le
    demandee = Contact.objects.get().confirmation_demandee_le
    _poster(LETTRE, {"email": "lea@exemple.fr"})
    contact = Contact.objects.get()
    assert contact.lettre_le == premiere
    # Déjà inscrite : aucune nouvelle confirmation n'est demandée — la date de
    # la demande d'origine reste, trace du double consentement.
    assert contact.confirmation_demandee_le == demandee
    assert demandee is not None


def test_une_requete_anonyme_n_annule_jamais_une_desinscription() -> None:
    """Audit du 25/11/2026 : sinon n'importe qui réinscrit l'adresse d'un
    tiers qui a demandé à partir — par la lettre comme par la case."""
    _poster(LETTRE, {"email": "lea@exemple.fr"})
    _confirmer("lea@exemple.fr")
    contact = Contact.objects.get()
    contact.desinscrit_le = timezone.now()
    contact.save()
    assert Contact.objects.get().inscrit_a_la_lettre is False

    assert _poster(LETTRE, {"email": "lea@exemple.fr"}).status_code == 200
    _poster(RESSOURCES, {"email": "lea@exemple.fr", "ressource": "lexique", "lettre": True})
    assert Contact.objects.get().inscrit_a_la_lettre is False
    # Seule la boîte aux lettres peut ramener la personne : le clic confirme.
    _confirmer("lea@exemple.fr")
    assert Contact.objects.get().inscrit_a_la_lettre is True


def test_une_demande_repetee_ne_fait_pas_grossir_la_base() -> None:
    for _ in range(3):
        _poster(RESSOURCES, {"email": "a@exemple.fr", "ressource": "checklist"})
    assert Demande.objects.count() == 1


def test_seul_le_json_est_accepte() -> None:
    """Un `text/plain` est une requête « simple » qu'une page tierce peut
    faire poster par ses visiteurs, sans contrôle CORS."""
    corps = json.dumps({"email": "a@exemple.fr", "ressource": "checklist"})
    for adresse in (RESSOURCES, LETTRE):
        reponse = Client().post(adresse, data=corps, content_type="text/plain")
        assert reponse.status_code == 415
    assert Contact.objects.count() == 0


def test_le_plafond_compte_le_prefixe_ipv6_pas_l_adresse() -> None:
    from django.test import RequestFactory

    def cle(ip: str) -> str:
        return cle_de_l_appelant(RequestFactory().post("/", REMOTE_ADDR=ip))

    assert cle("2001:db8:1:2::1") == cle("2001:db8:1:2:ffff::9")
    assert cle("2001:db8:1:2::1") != cle("2001:db8:1:3::1")
    # Contre-épreuve : en IPv4, deux adresses voisines restent distinctes.
    assert cle("203.0.113.1") != cle("203.0.113.2")


def test_le_plafond_global_arrete_des_adresses_qui_tournent() -> None:
    for k in range(INSCRIPTIONS_GLOBALES_PAR_HEURE.maximum):
        Client(REMOTE_ADDR=f"10.{k // 250}.{k % 250}.1").post(
            RESSOURCES,
            data=json.dumps({"email": f"g{k}@exemple.fr", "ressource": "checklist"}),
            content_type="application/json",
        )
    reponse = Client(REMOTE_ADDR="10.99.99.99").post(
        RESSOURCES,
        data=json.dumps({"email": "de-trop@exemple.fr", "ressource": "checklist"}),
        content_type="application/json",
    )
    assert reponse.status_code == 429


def test_contre_epreuve_une_adresse_fausse_n_inscrit_personne() -> None:
    reponse = _poster(LETTRE, {"email": "lea@"})
    assert reponse.status_code == 400
    assert Contact.objects.count() == 0


# ── Le tableau de bord ───────────────────────────────────────────────────────


def test_le_tableau_de_bord_exige_le_jeton() -> None:
    _poster(LETTRE, {"email": "lea@exemple.fr"})
    _confirmer("lea@exemple.fr")
    contact = Contact.objects.get()
    assert Client().get("/api/dashboard/audience/").status_code in (401, 403)
    assert Client().get("/api/dashboard/audience.csv").status_code in (401, 403)
    for geste in ("desinscrire", "supprimer"):
        reponse = Client().post(f"/api/dashboard/audience/{contact.id}/{geste}/")
        assert reponse.status_code in (401, 403), geste
    assert Contact.objects.get().inscrit_a_la_lettre is True


def test_le_tableau_de_bord_liste_les_contacts(client_admin: Any) -> None:
    _poster(RESSOURCES, {"email": "a@exemple.fr", "ressource": "checklist", "lettre": True})
    _confirmer("a@exemple.fr")
    _poster(RESSOURCES, {"email": "a@exemple.fr", "ressource": "lexique"})
    _poster(RESSOURCES, {"email": "b@exemple.fr", "ressource": "lexique"})

    reponse = client_admin.get("/api/dashboard/audience/")
    assert reponse.status_code == 200
    assert reponse["Cache-Control"] == "no-store"
    corps = reponse.json()
    assert corps["total"] == 2
    assert corps["inscrits_a_la_lettre"] == 1
    a = next(c for c in corps["contacts"] if c["email"] == "a@exemple.fr")
    assert a["demandes"] == ["Checklist", "Lexique"]
    assert a["inscrit_a_la_lettre"] is True


def test_l_export_csv_neutralise_les_formules(client_admin: Any) -> None:
    contact = Contact.objects.create(email="=cmd@exemple.fr")
    Demande.objects.create(contact=contact, origine="checklist")

    reponse = client_admin.get("/api/dashboard/audience.csv")
    assert reponse.status_code == 200
    assert reponse["Content-Disposition"] == 'attachment; filename="audience-evkha.csv"'
    texte = reponse.content.decode("utf-8-sig")
    lignes = list(csv.reader(io.StringIO(texte), delimiter=";"))
    assert lignes[0][0] == "Adresse e-mail"
    assert not lignes[1][0].startswith("=")


def test_la_desinscription_garde_l_historique(client_admin: Any) -> None:
    _poster(LETTRE, {"email": "lea@exemple.fr"})
    _confirmer("lea@exemple.fr")
    contact = Contact.objects.get()
    assert contact.inscrit_a_la_lettre is True

    reponse = client_admin.post(f"/api/dashboard/audience/{contact.id}/desinscrire/")
    assert reponse.status_code == 200
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is False
    assert contact.demandes.count() == 1
    assert client_admin.post("/api/dashboard/audience/inconnu/desinscrire/").status_code == 404


def test_l_export_de_la_lettre_ne_porte_que_les_inscrits(client_admin: Any) -> None:
    _poster(RESSOURCES, {"email": "inscrite@exemple.fr", "ressource": "checklist", "lettre": True})
    _confirmer("inscrite@exemple.fr")
    _poster(RESSOURCES, {"email": "telechargeur@exemple.fr", "ressource": "checklist"})

    reponse = client_admin.get("/api/dashboard/audience.csv?lettre=1")
    assert reponse["Content-Disposition"] == 'attachment; filename="newsletter-evkha-inscrits.csv"'
    texte = reponse.content.decode("utf-8-sig")
    assert "inscrite@exemple.fr" in texte
    assert "telechargeur@exemple.fr" not in texte
    # Contre-épreuve : l'export complet porte les deux.
    complet = client_admin.get("/api/dashboard/audience.csv").content.decode("utf-8-sig")
    assert "telechargeur@exemple.fr" in complet


def test_l_effacement_supprime_le_contact_et_ses_demandes(client_admin: Any) -> None:
    _poster(RESSOURCES, {"email": "a@exemple.fr", "ressource": "checklist"})
    _poster(RESSOURCES, {"email": "b@exemple.fr", "ressource": "lexique"})
    contact = Contact.objects.get(email="a@exemple.fr")

    reponse = client_admin.post(f"/api/dashboard/audience/{contact.id}/supprimer/")
    assert reponse.status_code == 200
    assert not Contact.objects.filter(email="a@exemple.fr").exists()
    assert Demande.objects.filter(contact_id=contact.id).count() == 0
    # Contre-épreuve : l'autre contact est intact.
    assert Contact.objects.filter(email="b@exemple.fr").exists()
    assert client_admin.post("/api/dashboard/audience/inconnu/supprimer/").status_code == 404
