"""La boutique : un fichier deja ecrit, paye une fois, remis tout de suite.

Ce qui distingue ces tests de ceux de l'achat a l'unite : ici, AUCUNE
production n'est declenchee. Le paiement ouvre un acces, il ne verse pas de
credit. Un test qui verrait un credit apparaitre signalerait que les deux
chemins se sont melanges.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from paiement import boutique

from catalog.models import AchatProduit, AvisProduit, ProduitBoutique
from organisations import credits
from organisations.models import Encaissement, Organisation, TypeDeCompte

pytestmark = pytest.mark.django_db


#: Les huit octets qui ouvrent un PNG. `ImageField` refuse un fichier que
#: Pillow ne sait pas ouvrir : un contenu arbitraire ne passerait pas.
ENTETE_PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def produit_en_ligne(**surcharges: Any) -> ProduitBoutique:
    """Un produit reellement vendable : un prix ET un fichier."""
    defauts: dict[str, Any] = {
        "titre": "Le marché des foodtrucks en 2026",
        "slug": f"foodtrucks-{uuid.uuid4().hex[:6]}",
        "description": "Une étude complète du marché.",
        "sommaire": "Taille du marché\nConcurrence\nRentabilité",
        "theme": "Restauration",
        "prix_cents": 8900,
        "nombre_de_pages": 42,
        "en_ligne": True,
    }
    defauts.update(surcharges)
    produit = ProduitBoutique(**defauts)
    produit.fichier.save(
        "etude.pdf", SimpleUploadedFile("etude.pdf", b"%PDF-1.4 contenu"), save=False
    )
    produit.save()
    return produit


def session_stripe(produit: ProduitBoutique, **surcharges: Any) -> dict[str, Any]:
    """Une session de paiement telle que le prestataire la rend."""
    session: dict[str, Any] = {
        "id": f"cs_test_{uuid.uuid4().hex[:16]}",
        "payment_status": "paid",
        "amount_total": produit.prix_cents,
        "currency": "eur",
        "customer_details": {
            "email": f"{uuid.uuid4().hex[:8]}@example.com",
            "name": "Camille Durand",
        },
        "metadata": {"achat": "produit", "produit_slug": produit.slug},
    }
    session.update(surcharges)
    return session


# ── 1. Le catalogue public ───────────────────────────────────────────────────


def test_le_catalogue_ne_montre_que_les_produits_vendables() -> None:
    """Un produit sans fichier encaisserait sans rien remettre.

    Un produit a zero euro ouvrirait un paiement de zero euro, accepte par le
    prestataire, qui livrerait l'etude sans contrepartie. Les deux sont des
    defauts silencieux : ils ne se voient qu'au premier acheteur.
    """
    vendable = produit_en_ligne()
    ProduitBoutique.objects.create(
        titre="Sans fichier", slug="sans-fichier", prix_cents=8900, en_ligne=True
    )
    sans_prix = produit_en_ligne(titre="Gratuite", prix_cents=0)
    hors_ligne = produit_en_ligne(titre="Brouillon", en_ligne=False)

    charge = Client().get("/api/public/boutique/").json()

    slugs = [p["slug"] for p in charge["produits"]]
    assert slugs == [vendable.slug]
    assert sans_prix.slug not in slugs
    assert hors_ligne.slug not in slugs


def test_la_fiche_rend_le_sommaire_en_lignes() -> None:
    """Le decoupage se fait au SERVEUR, pas dans la page.

    Laisser le navigateur decouper un texte donnerait deux avis sur ce qu'est
    une ligne, et le jour ou l'un change, l'autre ne suivrait pas.
    """
    produit = produit_en_ligne()

    charge = Client().get(f"/api/public/boutique/{produit.slug}/").json()

    assert charge["produit"]["sommaire"] == [
        "Taille du marché", "Concurrence", "Rentabilité",
    ]


def test_la_fiche_d_un_produit_hors_ligne_est_introuvable() -> None:
    produit = produit_en_ligne(en_ligne=False)

    reponse = Client().get(f"/api/public/boutique/{produit.slug}/")

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "produit_inconnu"


def test_les_etudes_proches_completent_au_dela_du_theme() -> None:
    """Un theme etroit ne doit pas laisser la fiche sans suggestion."""
    cible = produit_en_ligne(theme="Restauration")
    produit_en_ligne(titre="Micro-crèches", theme="Petite enfance")
    produit_en_ligne(titre="Conciergeries", theme="Services")

    charge = Client().get(f"/api/public/boutique/{cible.slug}/").json()

    assert len(charge["proches"]) == 2
    assert cible.slug not in [p["slug"] for p in charge["proches"]]


# ── 2. La remise apres paiement ──────────────────────────────────────────────


def test_le_paiement_ouvre_l_acces_et_le_compte() -> None:
    produit = produit_en_ligne()

    resultat = boutique.livrer_le_produit(session_stripe(produit))

    assert resultat.nouveau is True
    assert resultat.produit == produit
    assert resultat.organisation.type_de_compte == TypeDeCompte.A_L_UNITE
    assert AchatProduit.objects.filter(organisation=resultat.organisation).count() == 1


def test_la_remise_ne_verse_AUCUN_credit() -> None:
    """Une etude de boutique est deja ecrite : rien n'est a produire.

    Sans cette verification, un melange des deux chemins passerait inapercu —
    le client recevrait son fichier ET un credit, donc une seconde etude
    gratuite.
    """
    produit = produit_en_ligne()

    resultat = boutique.livrer_le_produit(session_stripe(produit))

    assert credits.solde(resultat.organisation) == 0


def test_la_remise_est_rejouable_sans_compter_deux_fois() -> None:
    """Le webhook et la page de retour se croisent : c'est le cas NORMAL."""
    produit = produit_en_ligne()
    session = session_stripe(produit)

    premier = boutique.livrer_le_produit(session)
    second = boutique.livrer_le_produit(session)

    assert premier.nouveau is True
    assert second.nouveau is False
    assert AchatProduit.objects.count() == 1
    assert Organisation.objects.count() == 1


def test_une_session_non_payee_est_refusee() -> None:
    """`status: complete` dit que le formulaire est alle au bout, pas que la
    carte a ete debitee.
    """
    produit = produit_en_ligne()
    session = session_stripe(produit, payment_status="unpaid", status="complete")

    with pytest.raises(boutique.AchatInexploitable, match="non payée"):
        boutique.livrer_le_produit(session)

    assert AchatProduit.objects.count() == 0


def test_un_produit_inconnu_est_refuse_bruyamment() -> None:
    """L'argent a ete pris : se taire serait le pire (règle 1)."""
    produit = produit_en_ligne()
    session = session_stripe(produit)
    session["metadata"]["produit_slug"] = "produit-qui-n-existe-pas"

    with pytest.raises(boutique.AchatInexploitable, match="inconnu"):
        boutique.livrer_le_produit(session)


def test_la_vente_apparait_dans_les_encaissements() -> None:
    """Sans cette ligne, la vente serait invisible du chiffre d'affaires."""
    produit = produit_en_ligne()

    resultat = boutique.livrer_le_produit(session_stripe(produit))

    encaissement = Encaissement.objects.get(
        reference_facture=resultat.achat.reference_paiement
    )
    assert encaissement.montant_cents == produit.prix_cents


def test_un_second_achat_credite_l_espace_EXISTANT() -> None:
    """Deux espaces laisseraient l'acheteur avec deux historiques."""
    premier = produit_en_ligne()
    second = produit_en_ligne(titre="Micro-crèches")
    adresse = "camille@example.com"

    premiere = session_stripe(premier)
    premiere["customer_details"]["email"] = adresse
    a = boutique.livrer_le_produit(premiere)

    seconde = session_stripe(second)
    seconde["customer_details"]["email"] = adresse
    b = boutique.livrer_le_produit(seconde)

    assert a.organisation.id == b.organisation.id
    assert Organisation.objects.count() == 1
    assert AchatProduit.objects.filter(organisation=a.organisation).count() == 2


def test_l_organisation_designee_l_emporte_sur_l_adresse() -> None:
    """Le prestataire laisse MODIFIER l'adresse sur sa page de paiement.

    Un acheteur connecte qui la corrige verrait sinon s'ouvrir un second
    espace : il aurait paye, et son fichier l'attendrait la ou il ne se
    connectera jamais.
    """
    produit = produit_en_ligne()
    premier = boutique.livrer_le_produit(session_stripe(produit))
    avant = Organisation.objects.count()

    autre = produit_en_ligne(titre="Conciergeries")
    session = session_stripe(autre)
    session["customer_details"]["email"] = "adresse.differente@example.com"
    session["metadata"]["organisation_id"] = str(premier.organisation.id)

    resultat = boutique.livrer_le_produit(session)

    assert resultat.organisation.id == premier.organisation.id
    assert Organisation.objects.count() == avant


# ── 3. Le lien de telechargement ─────────────────────────────────────────────


def test_le_lien_de_telechargement_est_signe() -> None:
    """Un lien nu servirait le fichier a qui devine son chemin."""
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))

    lien = boutique.lien_de_telechargement(resultat.achat)

    assert "/media/" in lien
    assert "?s=" in lien


def test_le_lien_de_telechargement_porte_le_domaine_de_l_API(
    settings: Any,
) -> None:
    """Un lien RELATIF ne remet pas le fichier : il remet la page d'accueil.

    L'acheteur le lit sur `app2.evkha.fr` (page de retour, « Mes achats »)
    tandis que `/media/` est servi par `api2.evkha.fr`. Or `frontend/nginx.conf`
    ne proxifie que `/api/` : un chemin relatif y tombe sur `try_files $uri
    /index.html` et rend **200 text/html**. Mesure du 21/08/2026 avant
    correctif : 1 585 octets de HTML au lieu du PDF, sans une ligne dans les
    journaux.
    """
    settings.EVKHA_BASE_URL = "https://api2.evkha.fr"
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))

    lien = boutique.lien_de_telechargement(resultat.achat)

    assert lien.startswith("https://api2.evkha.fr/media/")


def test_la_couverture_s_affiche_sans_signature_et_EN_LIGNE(settings: Any) -> None:
    """Une couverture est un support de vente : elle doit s'AFFICHER.

    Deux protections la rendaient inutilisable. `/media/` sert tout en
    `Content-Disposition: attachment` — une image en pièce jointe ne s'affiche
    pas dans une balise `<img>` — et exige une signature qui expire, ce qui
    ferait disparaître les couvertures d'un catalogue public au bout de
    quelques jours.

    Les fichiers de vitrine vivent donc sous un préfixe distinct du document
    payé, et c'est le préfixe qui porte l'intention.
    """
    settings.EVKHA_BASE_URL = "https://api2.evkha.fr"
    produit = produit_en_ligne()
    produit.image.save(
        "couverture.png",
        SimpleUploadedFile("couverture.png", ENTETE_PNG, "image/png"),
        save=True,
    )

    fiche = Client().get(f"/api/public/boutique/{produit.slug}/").json()["produit"]
    assert fiche["image"].startswith("https://api2.evkha.fr/media/boutique-vitrine/")

    reponse = Client().get(fiche["image"].replace("https://api2.evkha.fr", ""))
    assert reponse.status_code == 200
    assert reponse.headers["Content-Disposition"] == "inline"
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"


def test_le_document_PAYE_reste_signe_meme_sous_la_boutique() -> None:
    """Contre-épreuve de la précédente : ouvrir la vitrine ne doit rien ouvrir
    d'autre.

    Le document vendu est rangé sous `boutique/`, la vitrine sous
    `boutique-vitrine/`. Rendre public « tout ce qui commence par boutique »
    aurait mis l'étude elle-même en libre accès — c'est précisément pourquoi
    les deux préfixes sont distincts et non imbriqués.
    """
    produit = produit_en_ligne()

    reponse = Client().get(f"/media/{produit.fichier.name}")

    assert reponse.status_code == 404


def test_un_html_depose_en_vitrine_reste_une_piece_jointe() -> None:
    """La faille d'origine : un `.html` servi EN LIGNE sur l'origine qui porte
    `/admin/` s'exécute avec ses cookies.

    L'ouverture de la vitrine ne la rouvre pas — la liste des extensions
    rendues en ligne est FERMÉE, et ce qui n'y figure pas retombe en pièce
    jointe quel que soit son emplacement (règle 4 : viser la classe).
    """
    produit = produit_en_ligne()
    produit.extrait.save(
        "piege.html",
        SimpleUploadedFile("piege.html", b"<script>alert(1)</script>", "text/html"),
        save=True,
    )

    reponse = Client().get(f"/media/{produit.extrait.name}")

    # Pas de signature, et l'extension n'ouvre pas la voie en ligne : refuse.
    assert reponse.status_code == 404


def test_sans_version_editable_le_lien_est_vide() -> None:
    """Une chaine vide, pas un lien mort : la page sait alors ne rien afficher."""
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))

    assert boutique.lien_de_telechargement(resultat.achat, editable=True) == ""


# ── 3 ter. Le suivi commercial ───────────────────────────────────────────────


def _stripe_en_doublure(monkeypatch: Any, reference: str) -> None:
    """Remplace l'ouverture de paiement, et RIEN d'autre.

    La cle Stripe n'existe pas dans les tests : sans cette doublure, la vue
    refuse en 503 et le panier qu'on veut observer n'est jamais ouvert.
    """
    from paiement import stripe_api

    monkeypatch.setattr(
        stripe_api,
        "creer_paiement_de_produit",
        lambda **_: stripe_api.SessionOuverte(
            identifiant=reference, adresse="https://checkout.test/x"
        ),
    )


def test_un_panier_de_boutique_ABANDONNE_est_visible(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Sans cette trace, la vente perdue la plus frequente est invisible.

    On achète en boutique SANS COMPTE : le visiteur qui clique « Acheter » puis
    referme la page de paiement n'a ni organisation ni session. Une tentative
    liée obligatoirement à une organisation ne pouvait donc pas l'enregistrer,
    et l'abandon le plus courant de la boutique était le seul qu'on ne voyait
    jamais.
    """
    produit = produit_en_ligne()
    _stripe_en_doublure(monkeypatch, "cs_test_panier_abandonne")

    reponse = Client().post(
        "/api/public/boutique/acheter/",
        json.dumps({"produit": produit.slug, "email": "hesitante@example.fr"}),
        content_type="application/json",
    )
    assert reponse.status_code == 200

    lignes = client_admin.get("/api/dashboard/supervision/transactions/").json()
    panier = next(t for t in lignes["transactions"] if t["produit"] == produit.titre)

    assert panier["etat"] == "ouverte"
    assert panier["organisation"] == "Visiteur"
    # L'adresse EST le point de contact : sans elle, il n'y a personne à
    # relancer.
    assert panier["contact"] == "hesitante@example.fr"
    assert panier["montant_cents"] == produit.prix_cents


def test_un_panier_de_boutique_paye_ne_se_relance_pas(client_admin: Any) -> None:
    """La page de retour livre SANS le webhook.

    Si elle ne soldait pas la tentative, un achat bel et bien encaissé
    resterait « ouvert », passerait « abandonné » au bout de vingt-quatre
    heures, et la cliente relancerait quelqu'un qui a déjà payé — l'exact
    contraire de ce que cet écran doit permettre.
    """
    produit = produit_en_ligne()
    session = session_stripe(produit)
    boutique.noter_la_tentative(
        session={"id": session["id"]}, produit=produit, email="acheteuse@example.fr"
    )

    boutique.livrer_le_produit(session)

    lignes = client_admin.get("/api/dashboard/supervision/transactions/").json()
    panier = next(t for t in lignes["transactions"] if t["produit"] == produit.titre)
    assert panier["etat"] == "payee"
    # Et l'organisation née du paiement lui est rattachée : la ligne cesse
    # d'être celle d'un « Visiteur » dès qu'on sait qui c'est.
    assert panier["organisation"] != "Visiteur"


def test_relancer_un_panier_sans_organisation_ecrit_a_l_adresse(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Le refus portait sur l'organisation, pas sur l'adresse.

    « Cette organisation n'a aucune adresse de contact » bloquait toute relance
    d'un achat de boutique — qui n'a pas d'organisation par construction, et
    dont on connaît pourtant l'adresse.
    """
    produit = produit_en_ligne()
    _stripe_en_doublure(monkeypatch, "cs_test_a_relancer")
    Client().post(
        "/api/public/boutique/acheter/",
        json.dumps({"produit": produit.slug, "email": "hesitante@example.fr"}),
        content_type="application/json",
    )
    lignes = client_admin.get("/api/dashboard/supervision/transactions/").json()
    panier = next(t for t in lignes["transactions"] if t["produit"] == produit.titre)

    reponse = client_admin.post(
        f"/api/dashboard/supervision/transactions/{panier['id']}/relancer/",
        content_type="application/json",
    )

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["relances"] == 1


# ── 3 bis. Les avis ──────────────────────────────────────────────────────────


def test_un_avis_non_publie_n_apparait_pas() -> None:
    """`publie` EST la modération. Un avis saisi mais non coché ne sort pas."""
    produit = produit_en_ligne()
    AvisProduit.objects.create(produit=produit, auteur="Claire", note=5, publie=True)
    AvisProduit.objects.create(produit=produit, auteur="Brouillon", note=1, publie=False)

    reponse = Client().get(f"/api/public/boutique/{produit.slug}/")
    fiche = reponse.json()["produit"]

    assert [a["auteur"] for a in fiche["avis"]] == ["Claire"]


def test_la_note_moyenne_ignore_les_avis_non_publies() -> None:
    """Sinon la note affichée ne correspondrait à aucun avis lisible.

    Le lecteur verrait « 3,0 sur 5 » sous une liste de deux avis à 5 : le
    chiffre contredirait ce qu'il a sous les yeux, sans que rien l'explique.
    """
    produit = produit_en_ligne()
    AvisProduit.objects.create(produit=produit, auteur="Claire", note=5, publie=True)
    AvisProduit.objects.create(produit=produit, auteur="Nadia", note=4, publie=True)
    AvisProduit.objects.create(produit=produit, auteur="Caché", note=1, publie=False)

    produit.refresh_from_db()
    assert produit.note_moyenne == 4.5
    assert produit.nombre_d_avis == 2


def test_sans_avis_la_note_vaut_zero() -> None:
    """Zéro et non `None` : la page teste le NOMBRE d'avis pour décider
    d'afficher des étoiles, et une moyenne absente obligerait chaque appelant
    à décider quoi en faire."""
    assert produit_en_ligne().note_moyenne == 0.0


def test_un_avis_sans_auteur_est_refuse(client_admin: Any) -> None:
    """Un témoignage anonyme n'engage personne, donc ne rassure personne."""
    produit = produit_en_ligne()

    reponse = client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/avis/", {"note": "5", "texte": "Super"}
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "auteur_manquant"
    assert produit.avis.count() == 0


def test_une_note_hors_bornes_est_ramenee_dans_l_echelle(client_admin: Any) -> None:
    """Les validateurs du modèle ne s'exécutent qu'à `full_clean()`, que
    `create()` n'appelle pas : la borne doit être appliquée par la vue, sinon
    un 9 sur 5 entrerait en base et fausserait toutes les moyennes."""
    produit = produit_en_ligne()

    client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/avis/", {"auteur": "Claire", "note": "9"}
    )

    assert produit.avis.get().note == 5


def test_un_avis_se_retire_sans_se_supprimer(client_admin: Any) -> None:
    """Le retrait est réversible ; la suppression ne l'est pas."""
    produit = produit_en_ligne()
    ligne = AvisProduit.objects.create(produit=produit, auteur="Claire", note=5)

    reponse = client_admin.post(
        f"/api/dashboard/boutique/avis/{ligne.id}/", {"publie": "false"}
    )

    assert reponse.status_code == 200
    ligne.refresh_from_db()
    assert ligne.publie is False
    assert AvisProduit.objects.filter(id=ligne.id).exists()


# ── 3 quater. L'avis depose par l'acheteuse ─────────────────────────────────


def _espace_de(resultat: Any) -> tuple[Client, Any]:
    """Un client HTTP authentifie sur l'espace ouvert par un achat."""
    from organisations import authentification  # noqa: PLC0415

    jeton = authentification.ouvrir_session_sans_mot_de_passe(resultat.compte)
    return Client(HTTP_AUTHORIZATION=f"Bearer {jeton}"), resultat.achat


def test_l_acheteuse_depose_son_avis_NON_PUBLIE() -> None:
    """Un texte ecrit par un tiers ne s'affiche pas avant d'avoir ete relu.

    Il est enregistre, et la reponse le dit franchement — sinon son auteure
    cherche son texte sur la fiche et croit qu'il s'est perdu.
    """
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))
    client, achat = _espace_de(resultat)

    reponse = client.post(
        f"/api/espace/achats/{achat.id}/avis/",
        data={"note": 5, "texte": "Le montage financier vaut a lui seul le prix."},
        content_type="application/json",
    )

    assert reponse.status_code == 201, reponse.content
    avis = produit.avis.get()
    assert avis.publie is False
    assert avis.achat_id == achat.id
    # Rien de la fiche publique ne le montre tant qu'il n'est pas relu.
    fiche = Client().get(f"/api/public/boutique/{produit.slug}/").json()["produit"]
    assert fiche["avis"] == []


def test_on_ne_donne_PAS_son_avis_sur_l_achat_d_un_autre() -> None:
    """L'achat porte le droit d'ecrire, et on le cherche DANS l'organisation.

    La reponse est un 404, identique a celle d'un achat inexistant : dire
    « cet achat ne vous appartient pas » confirmerait au passage qu'il existe.
    """
    mien = boutique.livrer_le_produit(session_stripe(produit_en_ligne()))
    autre = boutique.livrer_le_produit(
        session_stripe(
            produit_en_ligne(slug="autre-etude"),
            id="cs_test_autre_acheteuse",
            customer_details={"email": "autre@example.com", "name": "Autre"},
        )
    )
    client, _ = _espace_de(mien)

    reponse = client.post(
        f"/api/espace/achats/{autre.achat.id}/avis/",
        data={"note": 1, "texte": "Je n'ai pas achete cette etude."},
        content_type="application/json",
    )

    assert reponse.status_code == 404
    assert AvisProduit.objects.count() == 0


def test_un_second_avis_sur_le_meme_achat_est_refuse() -> None:
    """`OneToOneField` porte la garantie, pas un comptage en Python : deux
    envois simultanes passeraient tous deux un `if deja_donne`."""
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))
    client, achat = _espace_de(resultat)

    premier = client.post(
        f"/api/espace/achats/{achat.id}/avis/",
        data={"note": 4, "texte": "Un premier avis."},
        content_type="application/json",
    )
    second = client.post(
        f"/api/espace/achats/{achat.id}/avis/",
        data={"note": 1, "texte": "Un second avis."},
        content_type="application/json",
    )

    assert premier.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "avis_deja_donne"
    assert produit.avis.count() == 1


def test_un_avis_sans_texte_est_refuse() -> None:
    """Une note seule n'apprend rien a celle qui hesite."""
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))
    client, achat = _espace_de(resultat)

    reponse = client.post(
        f"/api/espace/achats/{achat.id}/avis/",
        data={"note": 5, "texte": "   "},
        content_type="application/json",
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "texte_manquant"


def test_l_adresse_electronique_ne_signe_JAMAIS_un_avis() -> None:
    """Le repli du nom d'auteur ne doit pas etre l'adresse : elle finirait
    affichee sur la fiche publique de l'etude."""
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(
        session_stripe(
            produit, customer_details={"email": "discrete@example.com", "name": ""}
        )
    )
    client, achat = _espace_de(resultat)

    client.post(
        f"/api/espace/achats/{achat.id}/avis/",
        data={"note": 5, "texte": "Tres bonne etude."},
        content_type="application/json",
    )

    assert "@" not in produit.avis.get().auteur


# ── 3 quater. La demande d'avis, deux jours apres ────────────────────────────


def test_la_demande_d_avis_attend_le_delai() -> None:
    """Ecrire le jour meme demanderait un avis sur un document a peine ouvert."""
    from organisations.tasks import demander_les_avis  # noqa: PLC0415

    boutique.livrer_le_produit(session_stripe(produit_en_ligne()))

    assert demander_les_avis() == 0


def test_la_demande_part_une_seule_fois(settings: Any) -> None:
    """La tache tourne toutes les heures. Sans le marqueur, la meme personne
    recevrait la meme demande toutes les heures, indefiniment."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    from organisations.tasks import demander_les_avis  # noqa: PLC0415

    settings.EVKHA_DELAI_DEMANDE_AVIS_H = 48
    resultat = boutique.livrer_le_produit(session_stripe(produit_en_ligne()))
    AchatProduit.objects.filter(pk=resultat.achat.pk).update(
        created_at=timezone.now() - timedelta(hours=49)
    )

    premier = demander_les_avis()
    second = demander_les_avis()

    assert premier == 1
    assert second == 0
    resultat.achat.refresh_from_db()
    assert resultat.achat.avis_demande_le is not None


def test_on_ne_redemande_pas_son_avis_a_qui_l_a_donne(settings: Any) -> None:
    """Contre-epreuve : le delai atteint ne suffit pas a solliciter."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    from organisations.tasks import demander_les_avis  # noqa: PLC0415

    settings.EVKHA_DELAI_DEMANDE_AVIS_H = 48
    produit = produit_en_ligne()
    resultat = boutique.livrer_le_produit(session_stripe(produit))
    AchatProduit.objects.filter(pk=resultat.achat.pk).update(
        created_at=timezone.now() - timedelta(hours=72)
    )
    AvisProduit.objects.create(
        produit=produit, achat=resultat.achat, auteur="Deja dit", note=5, texte="Bien."
    )

    assert demander_les_avis() == 0


# ── 3 quinquies. Les avis a la une de la boutique ────────────────────────────


def test_la_boutique_ne_met_qu_UN_avis_par_etude_a_la_une() -> None:
    """Trois cartes qui parlent deux fois de la meme etude font croire qu'il
    n'y en a qu'une — l'inverse de l'effet cherche."""
    bavarde = produit_en_ligne(slug="bavarde", titre="L'etude bavarde")
    for numero in range(4):
        AvisProduit.objects.create(
            produit=bavarde, auteur=f"Lectrice {numero}", note=5, texte="Excellente."
        )
    discrete = produit_en_ligne(slug="discrete", titre="L'etude discrete")
    AvisProduit.objects.create(
        produit=discrete, auteur="Unique", note=4, texte="Tres bien."
    )

    avis = Client().get("/api/public/boutique/").json()["avis"]

    assert sorted(a["slug"] for a in avis) == ["bavarde", "discrete"]


def test_un_avis_sans_texte_ne_monte_pas_a_la_une() -> None:
    """Il ne porte qu'une note, deja comptee dans la moyenne de sa carte."""
    produit = produit_en_ligne()
    AvisProduit.objects.create(produit=produit, auteur="Muette", note=5, texte="")

    assert Client().get("/api/public/boutique/").json()["avis"] == []


# ── 3 sexies. Le jeu de demonstration ────────────────────────────────────────


def test_le_jeu_de_demonstration_n_ECRASE_PAS_un_vrai_document() -> None:
    """La commande tourne a CHAQUE demarrage du conteneur.

    Sans garde-fou, chaque deploiement remplacerait le document depose par la
    cliente par un PDF generique, et effacerait les avis qu'elle a saisis a la
    main. C'est le meme raisonnement que `seed_boutique`, qui ne remplit que
    les fiches absentes.
    """
    from django.core.management import call_command  # noqa: PLC0415

    call_command("seed_boutique", verbosity=0)
    vraie = ProduitBoutique.objects.get(slug="marche-foodtrucks-2026")
    vraie.fichier.save(
        "la-vraie-etude.pdf",
        SimpleUploadedFile("la-vraie-etude.pdf", b"%PDF-1.4 le vrai travail", "application/pdf"),
        save=True,
    )
    AvisProduit.objects.create(
        produit=vraie, auteur="Retour recu par courriel", note=5, texte="Parfait."
    )

    call_command("seed_boutique_demo", verbosity=0)

    vraie.refresh_from_db()
    assert "la-vraie-etude" in vraie.fichier.name
    assert vraie.fichier.read() == b"%PDF-1.4 le vrai travail"
    assert [a.auteur for a in vraie.avis.all()] == ["Retour recu par courriel"]


def test_le_jeu_de_demonstration_remplit_une_fiche_VIDE() -> None:
    """Contre-epreuve : le garde-fou ne doit pas bloquer ce qu'il doit faire."""
    from django.core.management import call_command  # noqa: PLC0415

    call_command("seed_boutique", verbosity=0)
    vide = ProduitBoutique.objects.get(slug="marche-micro-creches-2026")
    assert not vide.fichier

    call_command("seed_boutique_demo", verbosity=0)

    vide.refresh_from_db()
    assert vide.fichier
    assert vide.extrait
    assert vide.image
    assert vide.description
    assert vide.sommaire.count("\n") >= 5
    assert vide.nombre_d_avis >= 1
    assert vide.en_ligne is True


def test_un_document_de_demonstration_se_DIT_de_demonstration() -> None:
    """Il est achetable tant qu'il est en ligne : sa page de garde doit le dire.

    Le controle porte sur le PDF REELLEMENT produit, pas sur la constante :
    c'est ce que le lecteur ouvrira (regle 3).
    """
    from django.core.management import call_command  # noqa: PLC0415

    from catalog.management.commands.seed_boutique_demo import MENTION_DEMO

    call_command("seed_boutique", verbosity=0)
    call_command("seed_boutique_demo", verbosity=0)

    produit = ProduitBoutique.objects.get(slug="marche-foodtrucks-2026")
    import pypdfium2  # noqa: PLC0415

    document = pypdfium2.PdfDocument(produit.fichier.path)
    garde = document[0].get_textpage().get_text_range()
    document.close()

    # Les premiers mots de la mention suffisent : le repli de ligne du PDF
    # coupe la phrase, et exiger la chaine entiere verrouillerait la largeur de
    # colonne plutot que la mention.
    assert MENTION_DEMO.split(".")[0] in garde.replace("\r\n", " ").replace("\n", " ")


# ── 4. L'administration ──────────────────────────────────────────────────────


def test_un_produit_vendu_ne_peut_plus_etre_supprime(client_admin: Any) -> None:
    """Le supprimer detruirait l'historique ET l'acces de l'acheteur.

    Ce qu'il a paye doit rester a lui. Le retrait passe par « hors ligne »,
    qui preserve les deux.
    """
    produit = produit_en_ligne()
    boutique.livrer_le_produit(session_stripe(produit))

    reponse = client_admin.delete(f"/api/dashboard/boutique/{produit.id}/")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "produit_vendu"
    assert ProduitBoutique.objects.filter(pk=produit.pk).exists()


def test_un_produit_jamais_vendu_se_supprime(client_admin: Any) -> None:
    produit = produit_en_ligne()

    reponse = client_admin.delete(f"/api/dashboard/boutique/{produit.id}/")

    assert reponse.status_code == 200
    assert not ProduitBoutique.objects.filter(pk=produit.pk).exists()


def test_mettre_en_ligne_un_produit_incomplet_est_refuse(client_admin: Any) -> None:
    """Le refus NOMME ce qui manque : un bouton qui refuse sans expliquer se
    lit comme une panne.
    """
    produit = ProduitBoutique.objects.create(
        titre="Sans fichier", slug="sans-fichier-2", prix_cents=8900
    )

    reponse = client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/",
        data={"en_ligne": "true"},
        content_type="application/json",
    )

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "produit_incomplet"
    produit.refresh_from_db()
    assert produit.en_ligne is False


def test_deposer_le_SEUL_fichier_ne_casse_pas(client_admin: Any) -> None:
    """Le geste le plus courant : deposer le PDF, sans rien changer d'autre.

    Il rendait 500. La vue choisissait entre `request.POST` et le corps JSON
    sur le CONTENU (`request.POST if request.POST else …`) : un multipart ne
    portant qu'un fichier a un `request.POST` vide, on lisait donc
    `request.body` apres que l'analyseur multipart a consomme le flux, et
    Django leve `RawPostDataException`.

    L'administration n'affichait qu'« Enregistrement impossible », sans dire
    que le fichier etait pourtant arrive jusqu'au serveur.
    """
    produit = ProduitBoutique.objects.create(
        titre="Le marche du coaching sportif en 2026",
        slug="coaching-sportif-2026",
        prix_cents=12900,
    )

    reponse = client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/",
        {"fichier": SimpleUploadedFile("etude.pdf", b"%PDF-1.4 x", "application/pdf")},
    )

    assert reponse.status_code == 200, reponse.content
    produit.refresh_from_db()
    assert produit.fichier
    assert produit.est_publiable


def test_le_prix_se_saisit_en_euros(client_admin: Any) -> None:
    """La conversion vit au serveur : la faire dans le navigateur donnerait
    deux endroits ou l'arrondi peut differer.
    """
    produit = produit_en_ligne(prix_cents=0)

    client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/",
        data={"prix_euros": "89"},
        content_type="application/json",
    )

    produit.refresh_from_db()
    assert produit.prix_cents == 8900


def test_un_prix_illisible_laisse_le_precedent(client_admin: Any) -> None:
    """Contre-epreuve : remettre le prix a zero vendrait l'etude gratuitement."""
    produit = produit_en_ligne(prix_cents=8900)

    client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/",
        data={"prix_euros": "quatre-vingt-neuf"},
        content_type="application/json",
    )

    produit.refresh_from_db()
    assert produit.prix_cents == 8900


def test_le_slug_ne_change_pas_quand_le_titre_change(client_admin: Any) -> None:
    """Le slug est dans l'adresse de la fiche : le changer casserait les liens
    partages et le referencement.
    """
    produit = produit_en_ligne()
    slug = produit.slug

    client_admin.post(
        f"/api/dashboard/boutique/{produit.id}/",
        data={"titre": "Un tout autre titre"},
        content_type="application/json",
    )

    produit.refresh_from_db()
    assert produit.titre == "Un tout autre titre"
    assert produit.slug == slug
