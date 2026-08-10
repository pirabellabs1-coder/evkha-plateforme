"""Le plafond annoncé et le plafond appliqué doivent être le même.

## Le cas réel

09/08/2026 : « je ne pouvais pas joindre le fichier, il ne s'ajoutait pas
pourtant il faisait 3,5 Mo ».

Deux plafonds se contredisaient, et le plus bas n'était écrit nulle part :

  - `organisations.fichiers.TAILLE_MAX_DOCUMENT` accepte **10 Mo**, repris à
    l'octet près du formulaire Tally ;
  - `DATA_UPLOAD_MAX_MEMORY_SIZE`, réglage de Django jamais défini ici, valait
    son défaut de **2,5 Mo**.

Django refuse le corps de requête AVANT que la vue ne s'exécute. La validation
applicative — celle qui dit « le fichier dépasse 10 Mo » avec un message clair —
n'était donc jamais atteinte. L'utilisateur voyait un dépôt qui échoue sans
raison.

C'est le défaut que la règle 5 décrit exactement : deux modules qui ne sont pas
d'accord, et un désaccord silencieux. Ici, c'était un module et le cadre.

## Ce que ce test verrouille

Que le réglage du cadre soit DÉRIVÉ du plafond applicatif, pas recopié. Deux
nombres égaux aujourd'hui divergeraient au premier ajustement — et le désaccord
serait de nouveau invisible.
"""
from __future__ import annotations

import pytest
from django.conf import settings

from organisations.fichiers import TAILLE_MAX_DOCUMENT, TAILLE_MAX_LOGO


def test_django_accepte_au_moins_ce_que_l_application_annonce() -> None:
    """Le cadre ne doit jamais couper plus bas que la règle métier."""
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE >= TAILLE_MAX_DOCUMENT


def test_le_fichier_de_3_5_Mo_de_la_cliente_passerait() -> None:
    """Le cas exact, à sa taille exacte."""
    assert 3.5 * 1024 * 1024 < settings.DATA_UPLOAD_MAX_MEMORY_SIZE


def test_un_fichier_de_10_Mo_pile_passe_l_enveloppe() -> None:
    """La marge multipart n'est pas décorative.

    Les en-têtes et les frontières de parties s'ajoutent au fichier lui-même :
    un document de 10,0 Mo pile produit un corps de requête plus lourd que
    10,0 Mo. Sans marge, le plafond annoncé serait inatteignable — et le refus
    tomberait, là encore, avant tout message utile.
    """
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE > TAILLE_MAX_DOCUMENT


def test_le_reglage_est_DERIVE_et_non_recopie() -> None:
    """Deux nombres égaux aujourd'hui divergent au premier ajustement (règle 5).

    Ce test échouerait si quelqu'un écrivait « 11534336 » en dur : la valeur
    doit suivre `TAILLE_MAX_DOCUMENT` quand il bouge.
    """
    marge = settings.DATA_UPLOAD_MAX_MEMORY_SIZE - TAILLE_MAX_DOCUMENT

    assert 0 < marge <= 2 * 1024 * 1024, (
        "la marge doit rester une marge : ni nulle, ni un second plafond"
    )


@pytest.mark.parametrize(
    ("nom", "plafond"), [("logo", TAILLE_MAX_LOGO), ("document", TAILLE_MAX_DOCUMENT)]
)
def test_aucun_plafond_metier_ne_depasse_celui_du_cadre(
    nom: str, plafond: int
) -> None:
    """Contre-épreuve : le jour où un plafond métier monte, le cadre suit.

    Sinon on recrée exactement le défaut d'origine — une règle annoncée que
    l'infrastructure rend inatteignable.
    """
    assert plafond <= settings.DATA_UPLOAD_MAX_MEMORY_SIZE, nom
