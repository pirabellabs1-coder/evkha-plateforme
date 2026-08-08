"""Un lien de téléchargement doit vivre exactement aussi longtemps que son fichier.

Le courriel de livraison annonce au client « Ce lien de téléchargement est
valable N jours », N venant de `Offer.retention_days` — un réglage **par
offre**. La signature du lien, elle, expirait sur une durée **globale**.

Les deux nombres valaient sept, donc rien ne se voyait. Le défaut était
**latent** : il attendait qu'on touche à un nombre en administration. Une offre
réglée à trente jours aurait donné un lien mort au huitième, et comme `/media/`
répond 404 sans distinguer une signature expirée d'un fichier absent, le client
aurait conclu que son document avait été supprimé — sans que rien, nulle part,
ne puisse le contredire.

« Sept jours » vivait à cinq endroits, dont trois copies de la même fonction et
un réglage (`EVKHA_DEFAULT_RETENTION_DAYS`) qui n'était lu par personne.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import override_settings

from evkha import retention, signatures


def _job(jours: int | None) -> SimpleNamespace:
    """Un dossier réduit à ce que la rétention lui demande."""
    offre = SimpleNamespace(retention_days=jours)
    return SimpleNamespace(order=SimpleNamespace(offer=offre))


# ── La source unique ────────────────────────────────────────────────────────


def test_la_retention_vient_de_l_offre() -> None:
    assert retention.jours(_job(30)) == 30


@override_settings(EVKHA_DEFAULT_RETENTION_DAYS=21)
def test_le_repli_est_le_reglage_et_non_un_sept_en_dur() -> None:
    """LE réglage mort : déclaré, documenté, et lu par personne.

    Les trois fonctions recopiées repliaient sur `7` écrit en dur. Changer
    `EVKHA_DEFAULT_RETENTION_DAYS` n'avait donc aucun effet — un bouton qui ne
    fait rien est pire qu'un bouton absent (règle 1).
    """
    assert retention.jours_par_defaut() == 21
    assert retention.jours(_job(None)) == 21
    assert retention.jours(SimpleNamespace()) == 21


def test_les_secondes_et_les_jours_disent_la_meme_chose() -> None:
    """Ce sont les deux moitiés qui divergeaient : jours promis, secondes signées."""
    job = _job(30)

    assert retention.duree_en_secondes(job) == retention.jours(job) * 24 * 3600


# ── L'échéance voyage dans le lien ──────────────────────────────────────────


def test_un_lien_long_survit_a_la_duree_globale() -> None:
    """LE défaut corrigé : trente jours promis, sept jours vécus.

    On vérifie la signature avec une durée globale volontairement courte. Avant,
    c'est elle qui décidait, et le lien mourait avec elle. Désormais la durée
    est inscrite dans le jeton.
    """
    jeton = signatures.signer("livrables/12.pdf", duree_s=30 * 24 * 3600)

    with override_settings(EVKHA_MEDIA_DUREE_LIEN_S=1):
        assert signatures.signature_valable("livrables/12.pdf", jeton)


def test_un_lien_court_ne_survit_pas_a_sa_propre_duree() -> None:
    """La contre-épreuve : porter sa durée ne doit pas vouloir dire vivre toujours.

    Sans ce test, une durée mal lue — ou ignorée — rendrait tous les liens
    éternels, et le test précédent passerait quand même.
    """
    jeton = signatures.signer("livrables/12.pdf", duree_s=0)

    assert not signatures.signature_valable("livrables/12.pdf", jeton)


def test_la_duree_ne_peut_pas_etre_rallongee_par_le_porteur() -> None:
    """Elle est SIGNÉE, sinon elle ne serait qu'une suggestion.

    Le porteur du lien voit la durée en clair dans l'URL. S'il pouvait la
    réécrire, l'échéance ne vaudrait rien — il suffirait de demander mille ans.
    """
    jeton = signatures.signer("livrables/12.pdf", duree_s=0)
    rallonge = jeton.replace(f"{signatures.MARQUEUR_DUREE}0", "d99999999", 1)

    assert rallonge != jeton
    assert not signatures.signature_valable("livrables/12.pdf", rallonge)


def test_une_signature_ne_vaut_toujours_que_pour_son_chemin() -> None:
    """Propriété d'origine, à ne pas perdre en changeant le format (règle 6)."""
    jeton = signatures.signer("livrables/12.pdf", duree_s=3600)

    assert not signatures.signature_valable("livrables/13.pdf", jeton)


def test_les_liens_de_l_ancien_format_restent_valables() -> None:
    """Les liens déjà envoyés aux clients ne portent pas de durée.

    Les refuser d'un bloc casserait des livraisons en cours pour une
    amélioration interne. Ils sont acceptés avec la durée de repli qui était la
    leur — c'est exactement ce que produisait l'ancien `signer`.
    """
    from django.core import signing

    chemin = "livrables/12.pdf"
    ancien = str(
        signing.TimestampSigner(salt=signatures.SEL).sign(chemin)[len(chemin) + 1 :]
    )

    assert ancien.count(":") == 1  # « horodatage:signature », sans duree
    assert signatures.signature_valable(chemin, ancien)


# ── Les deux bouts se rejoignent ────────────────────────────────────────────


@pytest.mark.parametrize("jours", [7, 30, 90])
def test_le_lien_produit_vit_aussi_longtemps_que_promis(jours: int) -> None:
    """La propriété qui compte, bout à bout.

    Ce que le courriel annonce (`retention.jours`) et ce que la signature tient
    (`duree_en_secondes`) sont désormais le même nombre, quelle que soit
    l'offre. C'est cette égalité qui manquait, et aucun test des deux moitiés
    prises séparément ne pouvait la voir.
    """
    job = _job(jours)
    jeton = signatures.signer("livrables/9.pdf", retention.duree_en_secondes(job))

    # L'echeance REELLEMENT inscrite dans le jeton, relue comme le fera le
    # verificateur. La comparer au nombre annonce au client est la seule facon
    # de constater l'egalite : attendre trente jours n'est pas une option, et
    # se contenter de « le lien est valable maintenant » passerait aussi bien
    # avec une duree globale — c'est-a-dire avec le defaut.
    portee = signatures._duree_portee(jeton)

    assert portee == jours * 24 * 3600
    assert portee == retention.duree_en_secondes(job)
    with override_settings(EVKHA_MEDIA_DUREE_LIEN_S=1):
        assert signatures.signature_valable("livrables/9.pdf", jeton)
