"""La lettre d'information : double consentement, envois, automatisations,
désinscription, et l'administration qui les pilote (26/11/2026).

Aucun courriel réel : le client de messagerie est remplacé par un témoin qui
note ce qu'on lui confie.
"""

from __future__ import annotations

import io
import json
import re
import time
import urllib.error
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.test import Client
from django.utils import timezone
from lettre import envoi as pompe
from lettre.gabarit import contact_a_confirmer, jeton_de_confirmation
from lettre.models import (
    Automatisation,
    Envoi,
    Etape,
    Lettre,
    StatutEnvoi,
    StatutLettre,
)
from lettre.nettoyage import nettoyer

from audience.models import Contact, Demande
from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db


class Temoin:
    def __init__(self) -> None:
        self.envoyes: list[dict[str, Any]] = []
        self.erreur: Exception | None = None

    def send_delivery_email(self, **kwargs: Any) -> EmailSendResult:
        if self.erreur is not None:
            raise self.erreur
        self.envoyes.append(kwargs)
        return EmailSendResult(provider_message_id=f"id-{len(self.envoyes)}")

    def a(self, adresse: str) -> list[dict[str, Any]]:
        return [e for e in self.envoyes if e["recipient_email"] == adresse]


@pytest.fixture
def temoin(monkeypatch: pytest.MonkeyPatch) -> Temoin:
    t = Temoin()
    monkeypatch.setattr(pompe, "get_transactional_email_client", lambda: t)
    return t


def _pomper() -> dict[str, int]:
    return pompe.pomper(pause_s=0)


def _inscrit(email: str, depuis: timedelta = timedelta(0)) -> Contact:
    return Contact.objects.create(email=email, lettre_le=timezone.now() - depuis)


def _poster(adresse: str, charge: Any) -> Any:
    return Client().post(adresse, data=json.dumps(charge), content_type="application/json")


# ── Double consentement ──────────────────────────────────────────────────────


def test_s_inscrire_envoie_une_confirmation_une_seule_fois(temoin: Temoin) -> None:
    _poster("/api/public/lettre/", {"email": "lea@exemple.fr"})
    _pomper()
    _pomper()

    courriels = temoin.a("lea@exemple.fr")
    assert len(courriels) == 1
    contact = Contact.objects.get()
    # Le jeton signé porte l'heure à la seconde : on ne le recalcule pas, on
    # relit celui du courriel et on vérifie qu'il désigne bien ce contact.
    trouve = re.search(r"/l/confirmation/([^/\"]+)/", courriels[0]["html_body"])
    assert trouve is not None
    assert contact_a_confirmer(trouve.group(1)) == contact
    # Le jeton de DÉSINSCRIPTION ne figure pas dans ce courriel.
    assert str(contact.jeton) not in courriels[0]["html_body"]
    assert contact.inscrit_a_la_lettre is False


def test_une_salve_de_demandes_n_inonde_pas_la_boite_d_un_tiers(temoin: Temoin) -> None:
    for _ in range(5):
        _poster("/api/public/lettre/", {"email": "tiers@exemple.fr"})
        _pomper()
    assert len(temoin.a("tiers@exemple.fr")) == 1


def test_la_visite_du_lien_de_confirmation_n_inscrit_pas() -> None:
    contact = Contact.objects.create(
        email="lea@exemple.fr", confirmation_demandee_le=timezone.now()
    )
    lien = f"/l/confirmation/{jeton_de_confirmation(contact)}/"
    page = Client().get(lien)
    assert page.status_code == 200
    assert "method='post'" in page.content.decode()
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is False

    Client().post(lien)
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is True


def test_un_lien_sans_demande_en_attente_ne_confirme_rien() -> None:
    """Le jeton seul ne vaut pas consentement : il faut une demande."""
    contact = Contact.objects.create(email="a@exemple.fr")
    lien = f"/l/confirmation/{jeton_de_confirmation(contact)}/"
    assert Client().post(lien).status_code == 404
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is False


def test_le_lien_de_desinscription_ne_confirme_pas() -> None:
    """Audit du 26/11/2026 : le jeton de désinscription circule dans chaque
    lettre (transferts, boîtes partagées). Il ne doit pas réinscrire."""
    contact = Contact.objects.create(
        email="v@exemple.fr",
        lettre_le=timezone.now() - timedelta(days=9),
        desinscrit_le=timezone.now() - timedelta(days=2),
        confirmation_demandee_le=timezone.now(),
    )
    assert Client().post(f"/l/confirmation/{contact.jeton}/").status_code == 404
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is False


def test_un_lien_de_confirmation_perime_ou_remplace_ne_sert_plus() -> None:
    contact = Contact.objects.create(
        email="a@exemple.fr", confirmation_demandee_le=timezone.now() - timedelta(days=2)
    )
    ancien = jeton_de_confirmation(contact)
    contact.confirmation_demandee_le = timezone.now()
    contact.save()
    assert Client().post(f"/l/confirmation/{ancien}/").status_code == 404

    with mock.patch("django.core.signing.time.time", return_value=time.time() - 8 * 86400):
        vieux = jeton_de_confirmation(contact)
    assert Client().post(f"/l/confirmation/{vieux}/").status_code == 404
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is False
    # Contre-épreuve : le lien de la demande en cours, lui, confirme.
    actuel = f"/l/confirmation/{jeton_de_confirmation(contact)}/"
    assert Client().post(actuel).status_code == 200


def test_les_relances_sans_reponse_sont_bornees(temoin: Temoin) -> None:
    """Le formulaire public ne doit pas servir à écrire sans fin à un tiers."""
    from audience.vues_publiques import RELANCES_MAX

    for _ in range(RELANCES_MAX + 2):
        Contact.objects.filter(email="tiers@exemple.fr").update(
            confirmation_demandee_le=timezone.now() - timedelta(days=2)
        )
        _poster("/api/public/lettre/", {"email": "tiers@exemple.fr"})
        _pomper()
    assert len(temoin.a("tiers@exemple.fr")) == RELANCES_MAX


def test_une_confirmation_ralentie_repart_au_passage_suivant(temoin: Temoin) -> None:
    _poster("/api/public/lettre/", {"email": "lea@exemple.fr"})
    temoin.erreur = urllib.error.HTTPError("https://x", 429, "trop", {}, None)  # type: ignore[arg-type]
    _pomper()
    assert temoin.envoyes == []
    temoin.erreur = None
    _pomper()
    assert len(temoin.a("lea@exemple.fr")) == 1


def test_les_demandes_jamais_confirmees_sont_purgees() -> None:
    il_y_a_31_jours = timezone.now() - timedelta(days=31)
    vieille = Contact.objects.create(
        email="vieille@exemple.fr", confirmation_demandee_le=il_y_a_31_jours
    )
    Demande.objects.create(contact=vieille, origine="lettre")
    lectrice = Contact.objects.create(
        email="lectrice@exemple.fr", confirmation_demandee_le=il_y_a_31_jours
    )
    Demande.objects.create(contact=lectrice, origine="checklist")
    recente = Contact.objects.create(
        email="recente@exemple.fr", confirmation_demandee_le=timezone.now() - timedelta(days=3)
    )
    _pomper()
    restants = set(Contact.objects.values_list("email", flat=True))
    assert restants == {lectrice.email, recente.email}


# ── Désinscription ───────────────────────────────────────────────────────────


def test_la_desinscription_demande_puis_execute() -> None:
    contact = _inscrit("lea@exemple.fr")
    Client().get(f"/l/desinscription/{contact.jeton}/")
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is True

    # Le « one-click » des messageries (RFC 8058) poste ce corps-là.
    reponse = Client().post(
        f"/l/desinscription/{contact.jeton}/",
        data="List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )
    assert reponse.status_code == 200
    contact.refresh_from_db()
    assert contact.inscrit_a_la_lettre is False


def test_la_desinscription_par_l_administration_annule_la_confirmation_en_attente(
    client_admin: Any, temoin: Temoin
) -> None:
    contact = _inscrit("lea@exemple.fr", depuis=timedelta(days=5))
    contact.desinscrit_le = timezone.now() - timedelta(days=1)
    contact.confirmation_demandee_le = timezone.now()
    contact.save()
    client_admin.post(f"/api/dashboard/audience/{contact.id}/desinscrire/")
    _pomper()
    assert temoin.envoyes == []
    contact.refresh_from_db()
    assert contact.confirmation_demandee_le is None


def test_un_jeton_inconnu_rend_une_page_polie() -> None:
    reponse = Client().get("/l/desinscription/00000000-0000-0000-0000-000000000000/")
    assert reponse.status_code == 404


# ── Lettres ──────────────────────────────────────────────────────────────────


def _lettre(**champs: Any) -> Lettre:
    valeurs = {"objet": "Nouveautés", "corps_html": "<p>Bonjour</p>"}
    valeurs.update(champs)
    return Lettre.objects.create(**valeurs)


def test_une_lettre_part_aux_seuls_inscrits_avec_sa_sortie(temoin: Temoin) -> None:
    lea = _inscrit("lea@exemple.fr")
    Contact.objects.create(email="telechargeur@exemple.fr")
    partie = Contact.objects.create(
        email="partie@exemple.fr",
        lettre_le=timezone.now() - timedelta(days=3),
        desinscrit_le=timezone.now(),
    )
    lettre = _lettre(statut=StatutLettre.PROGRAMMEE, programmee_pour=timezone.now())

    bilan = _pomper()

    assert bilan["envoyes"] == 1
    assert [e["recipient_email"] for e in temoin.envoyes] == ["lea@exemple.fr"]
    message = temoin.envoyes[0]
    lien = f"/l/desinscription/{lea.jeton}/"
    assert lien in message["html_body"]
    assert lien in message["headers"]["List-Unsubscribe"]
    assert message["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message["copie_cachee"] is False
    assert not temoin.a(partie.email)
    lettre.refresh_from_db()
    assert lettre.statut == StatutLettre.ENVOYEE


def test_une_lettre_ne_part_jamais_deux_fois(temoin: Temoin) -> None:
    _inscrit("lea@exemple.fr")
    lettre = _lettre()
    assert pompe.lancer(lettre) == 1
    assert pompe.lancer(lettre) == 0
    _pomper()
    _pomper()
    assert len(temoin.envoyes) == 1


def test_une_lettre_programmee_plus_tard_attend(temoin: Temoin) -> None:
    _inscrit("lea@exemple.fr")
    lettre = _lettre(
        statut=StatutLettre.PROGRAMMEE, programmee_pour=timezone.now() + timedelta(hours=2)
    )
    _pomper()
    assert temoin.envoyes == []
    lettre.refresh_from_db()
    assert lettre.statut == StatutLettre.PROGRAMMEE


def test_une_desinscription_entre_file_et_depart_arrete_le_message(temoin: Temoin) -> None:
    lea = _inscrit("lea@exemple.fr", depuis=timedelta(days=1))
    pompe.lancer(_lettre())
    lea.desinscrit_le = timezone.now()
    lea.save()

    _pomper()
    assert temoin.envoyes == []
    assert Envoi.objects.get().statut == StatutEnvoi.IGNORE


def test_un_envoi_interrompu_n_est_pas_renvoye(temoin: Temoin) -> None:
    _inscrit("lea@exemple.fr")
    pompe.lancer(_lettre())
    Envoi.objects.update(statut=StatutEnvoi.EN_COURS, pris_le=timezone.now() - timedelta(hours=1))
    _pomper()
    assert temoin.envoyes == []
    assert Envoi.objects.get().statut == StatutEnvoi.ECHEC


def test_un_prestataire_sature_fait_reprendre_plus_tard(temoin: Temoin) -> None:
    _inscrit("lea@exemple.fr")
    pompe.lancer(_lettre())
    temoin.erreur = urllib.error.HTTPError("https://x", 429, "trop", {}, None)  # type: ignore[arg-type]
    _pomper()
    assert Envoi.objects.get().statut == StatutEnvoi.A_ENVOYER
    temoin.erreur = None
    _pomper()
    assert Envoi.objects.get().statut == StatutEnvoi.ENVOYE


def test_une_erreur_est_notee_et_la_file_continue(temoin: Temoin) -> None:
    _inscrit("a@exemple.fr")
    pompe.lancer(_lettre())
    temoin.erreur = RuntimeError("adresse refusée")
    bilan = _pomper()
    envoi = Envoi.objects.get()
    assert envoi.statut == StatutEnvoi.ECHEC
    assert "adresse refusée" in envoi.erreur
    assert bilan["echecs"] == 1


# ── Automatisations ─────────────────────────────────────────────────────────


def _automatisation(declencheur: str = "inscription", **etape: Any) -> Automatisation:
    auto = Automatisation.objects.create(
        nom="Bienvenue", declencheur=declencheur, active=True, active_depuis=timezone.now()
    )
    Etape.objects.create(
        automatisation=auto,
        ordre=1,
        delai_jours=etape.get("delai_jours", 0),
        objet="Bienvenue",
        corps_html="<p>Merci</p>",
    )
    return auto


def test_l_automatisation_n_ecrit_pas_aux_inscrits_d_avant(temoin: Temoin) -> None:
    _inscrit("ancienne@exemple.fr", depuis=timedelta(days=30))
    _automatisation()
    _inscrit("nouvelle@exemple.fr")
    _pomper()
    assert [e["recipient_email"] for e in temoin.envoyes] == ["nouvelle@exemple.fr"]
    _pomper()
    assert len(temoin.envoyes) == 1


def test_l_automatisation_attend_son_delai(temoin: Temoin) -> None:
    auto = _automatisation(delai_jours=3)
    auto.active_depuis = timezone.now() - timedelta(days=10)
    auto.save()
    Etape.objects.filter(automatisation=auto).update(created_at=auto.active_depuis)
    _inscrit("hier@exemple.fr", depuis=timedelta(days=1))
    _inscrit("semaine@exemple.fr", depuis=timedelta(days=5))
    _pomper()
    assert [e["recipient_email"] for e in temoin.envoyes] == ["semaine@exemple.fr"]


def test_une_ressource_sans_consentement_ne_declenche_rien(temoin: Temoin) -> None:
    _automatisation(declencheur="checklist")
    simple = Contact.objects.create(email="simple@exemple.fr")
    Demande.objects.create(contact=simple, origine="checklist")
    abonnee = _inscrit("abonnee@exemple.fr", depuis=timedelta(minutes=5))
    Demande.objects.create(contact=abonnee, origine="checklist")
    _pomper()
    assert [e["recipient_email"] for e in temoin.envoyes] == ["abonnee@exemple.fr"]


def test_une_demande_anterieure_a_la_confirmation_ne_declenche_rien(temoin: Temoin) -> None:
    """N'importe qui peut saisir l'adresse d'un abonné dans le formulaire :
    seule une demande faite APRÈS sa confirmation déclenche la suite."""
    _automatisation(declencheur="checklist")
    abonnee = Contact.objects.create(email="abonnee@exemple.fr")
    Demande.objects.create(contact=abonnee, origine="checklist")
    abonnee.lettre_le = timezone.now()
    abonnee.save()
    _pomper()
    assert temoin.envoyes == []


def test_un_message_ajoute_a_une_suite_active_n_ecrit_pas_au_passe(temoin: Temoin) -> None:
    auto = _automatisation(delai_jours=0)
    il_y_a_10_jours = timezone.now() - timedelta(days=10)
    auto.active_depuis = il_y_a_10_jours
    auto.save()
    Etape.objects.filter(automatisation=auto).update(created_at=il_y_a_10_jours)
    ancienne = _inscrit("ancienne@exemple.fr", depuis=timedelta(days=5))
    Envoi.objects.create(etape=Etape.objects.get(), contact=ancienne, statut=StatutEnvoi.ENVOYE)
    # La gérante ajoute un deuxième message, à 3 jours, aujourd'hui.
    Etape.objects.create(
        automatisation=auto, ordre=2, delai_jours=3, objet="Suite", corps_html="<p>b</p>"
    )
    _pomper()
    assert temoin.envoyes == []


def test_une_suite_mise_en_pause_retient_ce_qui_attendait(
    client_admin: Any, temoin: Temoin
) -> None:
    auto = _automatisation()
    _inscrit("lea@exemple.fr")
    pompe.mettre_en_file_les_automatisations(timezone.now())
    assert Envoi.objects.filter(statut=StatutEnvoi.A_ENVOYER).count() == 1
    etape = Etape.objects.get()
    reponse = _json(
        client_admin,
        "put",
        f"automatisations/{auto.id}/",
        {
            "nom": auto.nom,
            "declencheur": "inscription",
            "active": False,
            "etapes": [{"id": str(etape.id), "objet": "Bienvenue", "delai_jours": 0}],
        },
    )
    assert reponse.status_code == 200
    _pomper()
    assert temoin.envoyes == []


def test_une_automatisation_inactive_n_envoie_rien(temoin: Temoin) -> None:
    auto = _automatisation()
    auto.active = False
    auto.save()
    _inscrit("lea@exemple.fr")
    _pomper()
    assert temoin.envoyes == []


# ── Nettoyage ───────────────────────────────────────────────────────────────


def test_le_nettoyage_garde_la_mise_en_forme_et_retire_le_dangereux() -> None:
    sale = (
        '<p style="text-align:center;position:fixed">Bonjour '
        '<a href="javascript:alert(1)" onclick="x">piège</a> '
        '<a href="https://evkha.fr">site</a>'
        '<span style="color:#c00">rouge</span>'
        '<mark style="background-color:#ff0">surligné</mark>'
        '<img src="https://evkha.fr/a.png" onerror="x" alt="a"></p>'
        "<script>alert(1)</script><iframe src='https://x'></iframe>"
    )
    sale += (
        '<a href="//ailleurs.example">relatif</a><img src="/media/x.png">'
        '<span style="font-size:99999px;color:var(--x);background-color:url(x)">t</span>'
    )
    propre = nettoyer(sale)
    for interdit in (
        "javascript:",
        "onclick",
        "onerror",
        "<script",
        "<iframe",
        "position",
        "//ailleurs",
        "/media/x.png",
        "99999",
        "var(",
        "url(",
    ):
        assert interdit not in propre, interdit
    for garde in (
        "text-align:center",
        'href="https://evkha.fr"',
        "color:#c00",
        "background-color:#ff0",
        'src="https://evkha.fr/a.png"',
        'target="_blank"',
        "max-width:100%",
    ):
        assert garde in propre, garde


# ── Administration ───────────────────────────────────────────────────────────


def _json(client: Any, methode: str, chemin: str, charge: Any = None) -> Any:
    return getattr(client, methode)(
        f"/api/dashboard/lettre/{chemin}",
        data=json.dumps(charge or {}),
        content_type="application/json",
    )


def test_l_administration_de_la_lettre_exige_le_jeton() -> None:
    lettre = _lettre()
    for chemin in ("", "lettres/", "modeles/", "automatisations/"):
        assert Client().get(f"/api/dashboard/lettre/{chemin}").status_code in (401, 403)
    for chemin in (f"lettres/{lettre.id}/programmer/", "essai/", "images/", "apercu/"):
        assert Client().post(f"/api/dashboard/lettre/{chemin}").status_code in (401, 403)
    lettre.refresh_from_db()
    assert lettre.statut == StatutLettre.BROUILLON


def test_rediger_nettoie_et_programmer_fait_partir(client_admin: Any, temoin: Temoin) -> None:
    _inscrit("lea@exemple.fr")
    cree = _json(
        client_admin,
        "post",
        "lettres/",
        {"objet": "Novembre", "corps_html": "<p>Salut<script>x</script></p>"},
    )
    assert cree.status_code == 201
    corps = cree.json()
    assert "<script" not in corps["corps_html"]

    reponse = _json(client_admin, "post", f"lettres/{corps['id']}/programmer/", {"quand": None})
    assert reponse.status_code == 200
    assert reponse.json()["destinataires_prevus"] == 1
    # Une lettre engagée ne se modifie plus.
    assert _json(client_admin, "put", f"lettres/{corps['id']}/", {"objet": "x"}).status_code == 409

    _pomper()
    assert len(temoin.a("lea@exemple.fr")) == 1
    assert Lettre.objects.get().statut == StatutLettre.ENVOYEE


def test_programmer_refuse_sans_inscrit_ou_dans_le_passe(client_admin: Any) -> None:
    lettre = _lettre()
    assert _json(client_admin, "post", f"lettres/{lettre.id}/programmer/").status_code == 409
    _inscrit("lea@exemple.fr")
    hier = (timezone.now() - timedelta(days=1)).isoformat()
    reponse = _json(client_admin, "post", f"lettres/{lettre.id}/programmer/", {"quand": hier})
    assert reponse.status_code == 400
    lettre.refresh_from_db()
    assert lettre.statut == StatutLettre.BROUILLON


def test_annuler_un_envoi_en_cours_retient_ce_qui_n_est_pas_parti(client_admin: Any) -> None:
    _inscrit("a@exemple.fr")
    _inscrit("b@exemple.fr")
    lettre = _lettre()
    pompe.lancer(lettre)
    premier = Envoi.objects.first()
    assert premier is not None
    Envoi.objects.filter(pk=premier.pk).update(statut=StatutEnvoi.ENVOYE)

    reponse = _json(client_admin, "post", f"lettres/{lettre.id}/annuler/")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == StatutLettre.ANNULEE
    assert list(Envoi.objects.values_list("statut", flat=True)) == [StatutEnvoi.ENVOYE]


def test_l_essai_part_a_une_seule_adresse(client_admin: Any, temoin: Temoin) -> None:
    _inscrit("abonnee@exemple.fr")
    charge = {"objet": "Essai", "corps_html": "<p>x</p>", "email": "moi@exemple.fr"}
    assert _json(client_admin, "post", "essai/", charge).status_code == 200
    assert [e["recipient_email"] for e in temoin.envoyes] == ["moi@exemple.fr"]
    assert temoin.envoyes[0]["subject"] == "[Essai] Essai"
    assert _json(client_admin, "post", "essai/", {**charge, "email": "moi@"}).status_code == 400


def test_l_apercu_rend_le_courriel_nettoye(client_admin: Any) -> None:
    reponse = _json(
        client_admin, "post", "apercu/", {"objet": "A", "corps_html": "<p onclick='x'>Hé</p>"}
    )
    html = reponse.json()["html"]
    assert "<p>Hé</p>" in html
    assert "onclick" not in html


def test_une_image_televersee_est_publique_et_redessinee(
    client_admin: Any, settings: Any, tmp_path: Any
) -> None:
    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    source = io.BytesIO()
    Image.new("RGB", (2400, 1200), "red").save(source, format="JPEG")
    source.seek(0)
    source.name = "photo.jpg"
    reponse = client_admin.post("/api/dashboard/lettre/images/", {"image": source})
    assert reponse.status_code == 201
    url = reponse.json()["url"]
    assert url.startswith(("http://", "https://"))
    assert "/lettre-vitrine/" in url
    fichier = next((tmp_path / "lettre-vitrine").iterdir())
    with Image.open(fichier) as image:
        assert image.width == 1200
    # Servie sans signature et EN LIGNE : une messagerie doit l'afficher.
    # (`servir_media` appelé directement : la route lit MEDIA_ROOT au
    # chargement des URL, avant que le test ne le déplace.)
    from django.test import RequestFactory

    from evkha.media import servir_media

    chemin = url.split("/media/", 1)[1]
    servie = servir_media(
        RequestFactory().get(f"/media/{chemin}"), chemin, document_root=str(tmp_path)
    )
    assert servie.status_code == 200
    assert servie["Content-Disposition"] == "inline"


def test_une_image_demesuree_est_refusee_avant_decodage(client_admin: Any) -> None:
    from PIL import Image

    source = io.BytesIO()
    Image.new("1", (8000, 8000)).save(source, format="PNG")
    source.seek(0)
    source.name = "enorme.png"
    reponse = client_admin.post("/api/dashboard/lettre/images/", {"image": source})
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "image_trop_grande"


def test_les_essais_sont_plafonnes(client_admin: Any, temoin: Temoin) -> None:
    from dashboard.lettre import ESSAIS_PAR_HEURE

    charge = {"objet": "Essai", "corps_html": "<p>x</p>", "email": "moi@exemple.fr"}
    codes = [
        _json(client_admin, "post", "essai/", charge).status_code
        for _ in range(ESSAIS_PAR_HEURE.maximum + 1)
    ]
    assert codes[-1] == 429
    assert len(temoin.envoyes) == ESSAIS_PAR_HEURE.maximum


def test_un_fichier_qui_n_est_pas_une_image_est_refuse(client_admin: Any) -> None:
    faux = io.BytesIO(b"<svg onload='x'></svg>")
    faux.name = "image.png"
    reponse = client_admin.post("/api/dashboard/lettre/images/", {"image": faux})
    assert reponse.status_code == 400


def test_les_modeles_se_creent_et_se_nettoient(client_admin: Any) -> None:
    cree = _json(
        client_admin,
        "post",
        "modeles/",
        {"nom": "Mensuelle", "corps_html": "<p>a<script>b</script></p>"},
    )
    assert cree.status_code == 201
    assert "<script" not in cree.json()["corps_html"]
    assert _json(client_admin, "post", "modeles/", {"nom": ""}).status_code == 400
    liste = client_admin.get("/api/dashboard/lettre/modeles/").json()["modeles"]
    assert [m["nom"] for m in liste] == ["Mensuelle"]


def test_reordonner_les_etapes_garde_leur_historique(client_admin: Any) -> None:
    cree = _json(
        client_admin,
        "post",
        "automatisations/",
        {
            "nom": "Bienvenue",
            "declencheur": "inscription",
            "etapes": [
                {"objet": "Un", "delai_jours": 0, "corps_html": "<p>1</p>"},
                {"objet": "Deux", "delai_jours": 3, "corps_html": "<p>2</p>"},
            ],
        },
    ).json()
    un, deux = cree["etapes"]
    assert cree["active"] is False and cree["active_depuis"] is None
    # L'étape « Un » a déjà un historique : il doit survivre à l'échange.
    contact = _inscrit("lea@exemple.fr")
    Envoi.objects.create(etape_id=un["id"], contact=contact, statut=StatutEnvoi.ENVOYE)

    modifie = _json(
        client_admin,
        "put",
        f"automatisations/{cree['id']}/",
        {
            "nom": "Bienvenue",
            "declencheur": "inscription",
            "active": True,
            "etapes": [deux, un],
        },
    ).json()
    assert [e["id"] for e in modifie["etapes"]] == [deux["id"], un["id"]]
    assert modifie["active"] is True and modifie["active_depuis"] is not None
    assert Envoi.objects.filter(etape_id=un["id"], contact=contact).count() == 1


def test_une_automatisation_sans_message_ne_s_active_pas(client_admin: Any) -> None:
    reponse = _json(
        client_admin,
        "post",
        "automatisations/",
        {"nom": "Vide", "declencheur": "inscription", "active": True, "etapes": []},
    )
    assert reponse.status_code == 400
    assert not Automatisation.objects.exists()
