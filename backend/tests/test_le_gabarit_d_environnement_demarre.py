"""`.env.example` doit décrire une configuration qui DÉMARRE.

C'est le fichier qu'on copie pour monter un environnement. Il portait
`DJANGO_DEBUG=false` avec `EVKHA_USE_STUB_AI=true` — combinaison que les
contrôles système refusent par une *erreur*, pas un avertissement. Or une
erreur de contrôle arrête `manage.py migrate`, deuxième maillon de la chaîne
`&&` de `docker-compose.prod.yml` : gunicorn n'est jamais lancé, et le
déploiement se termine en « finished » sans que rien ne réponde.

Le copier tel quel donnait donc un conteneur mort, sans cause lisible.

**Le second défaut est plus sournois : l'ABSENCE.** `EVKHA_USE_STUB_SEARCH`
n'était écrit nulle part, donc valait `True` par défaut sans que personne ne
l'ait choisi. Chaque « étude de marché » a été rédigée sur des résultats
portant « Contenu de démonstration (mode stub EVKHA) ». Un réglage absent n'est
pas un réglage neutre : c'est un réglage pris par défaut, en silence.

Ces tests ne recopient aucune règle : ils importent les listes qui font foi
(règle 5). Ajouter un bouchon à `BOUCHONS_INTERDITS_EN_PRODUCTION` fera tomber
le test tant que le gabarit ne l'aura pas suivi.
"""
from __future__ import annotations

from pathlib import Path

from organisations.checks import BOUCHONS_INTERDITS_EN_PRODUCTION

RACINE = Path(__file__).resolve().parents[2]
GABARIT = RACINE / ".env.example"


def _lire_gabarit() -> dict[str, str]:
    """Rend les affectations du gabarit, commentaires exclus."""
    valeurs: dict[str, str] = {}
    for ligne in GABARIT.read_text(encoding="utf-8").splitlines():
        nue = ligne.strip()
        if not nue or nue.startswith("#") or "=" not in nue:
            continue
        cle, _, valeur = nue.partition("=")
        valeurs[cle.strip()] = valeur.strip()
    return valeurs


def _est_vrai(valeur: str) -> bool:
    return valeur.lower() in {"1", "true", "yes", "on"}


def test_le_gabarit_est_lisible() -> None:
    """Sans cela, les deux tests suivants passeraient sur un dictionnaire vide.

    Un contrôle qui n'a rien à comparer n'est pas un succès (règle 1) : si le
    format du fichier change, ou si le chemin cesse d'être bon, il faut que ce
    soit CE test qui le dise, et non les autres qui se taisent.
    """
    valeurs = _lire_gabarit()

    assert GABARIT.is_file()
    assert "DJANGO_DEBUG" in valeurs
    assert len(valeurs) > 20


def test_aucun_bouchon_interdit_n_est_actif_hors_debug() -> None:
    """La combinaison qui produit un conteneur mort.

    Hors `DEBUG`, un bouchon de cette liste lève une erreur `evkha.C005`. Le
    gabarit ne doit jamais décrire les deux en même temps.
    """
    valeurs = _lire_gabarit()
    if _est_vrai(valeurs.get("DJANGO_DEBUG", "")):
        actifs: list[str] = []
    else:
        actifs = [
            nom
            for nom, _ in BOUCHONS_INTERDITS_EN_PRODUCTION
            if _est_vrai(valeurs.get(nom, "true"))
        ]

    assert not actifs, (
        "Le gabarit pose DJANGO_DEBUG=false ET laisse actifs des bouchons "
        f"interdits en production : {actifs}. Les controles levent alors une "
        "erreur evkha.C005, `migrate` s'arrete, et gunicorn n'est jamais lance."
    )


def test_chaque_bouchon_surveille_est_ecrit_explicitement() -> None:
    """Un réglage absent est un réglage pris par défaut, en silence.

    `EVKHA_USE_STUB_SEARCH` manquait : il valait donc `True` sans décision, et
    les études se sont écrites sur du contenu de démonstration pendant des
    semaines. Écrire le drapeau — même à sa valeur par défaut — force la
    décision à être visible.
    """
    valeurs = _lire_gabarit()

    manquants = [
        nom for nom, _ in BOUCHONS_INTERDITS_EN_PRODUCTION if nom not in valeurs
    ]

    assert not manquants, (
        f"Ces bouchons sont surveilles par un controle mais absents du "
        f"gabarit : {manquants}. Absent ne veut pas dire inactif — il veut "
        "dire « valeur par defaut, choisie par personne »."
    )


def test_l_adresse_de_l_espace_client_est_renseignee() -> None:
    """Sinon les liens d'invitation mènent à une page inexistante.

    Vide hors `DEBUG`, c'est une erreur `evkha.C004` — même conséquence :
    le conteneur ne démarre pas.
    """
    valeurs = _lire_gabarit()

    assert valeurs.get("EVKHA_APP_URL"), (
        "EVKHA_APP_URL est vide ou absent du gabarit. Les liens d'invitation "
        "et de reinitialisation de mot de passe sont batis dessus."
    )
