"""Un montant que la LOI fixe n'est pas un chiffre hors socle.

Mesuré le 26/10/2026 sur le business plan `68fc68b4`, en production. Le
contrôle des chiffres hors socle signalait :

    « 83 600 € » n'a pas d'équivalent dans le socle, ni dans le brief, ni dans
    les documents du client.
    « 37 500 € » n'a pas d'équivalent dans le socle, ni dans le brief, ni dans
    les documents du client.

Exact, et hors sujet : ce sont le plafond de la micro-entreprise et la
franchise en base de TVA. Ils ne viennent ni du socle ni du client, ils
viennent du CGI — et `memoire.regles` les impose par ailleurs au même
document. Le contrôle accusait le livrable d'avoir inventé un chiffre que le
dépôt lui ordonne d'écrire (règle 2 : un motif faux envoie corriger ce qui est
juste, et noie les vrais).
"""
from __future__ import annotations

from generation.memoire.regles import (
    FRANCHISE_TVA,
    PLAFOND_MICRO,
    Nature,
    valeurs_des_seuils_legaux,
)


def test_les_seuils_des_deux_tables_sont_exposes() -> None:
    """Le test qui échoue sur le code d'avant : la fonction n'existait pas."""
    valeurs = valeurs_des_seuils_legaux()
    assert FRANCHISE_TVA[Nature.SERVICES].valeur in valeurs
    assert PLAFOND_MICRO[Nature.SERVICES].valeur in valeurs
    assert FRANCHISE_TVA[Nature.VENTES].valeur in valeurs
    assert PLAFOND_MICRO[Nature.VENTES].valeur in valeurs


def test_les_seuils_majores_comptent_aussi() -> None:
    """Un document qui cite la tolérance cite encore la loi."""
    majore = FRANCHISE_TVA[Nature.SERVICES].majore
    assert majore is not None
    assert majore in valeurs_des_seuils_legaux()


def test_les_deux_montants_du_defaut_mesure_y_figurent() -> None:
    """Les deux chiffres exacts que la production signalait à tort."""
    valeurs = valeurs_des_seuils_legaux()
    assert 83_600.0 in valeurs, "plafond de la micro-entreprise (services)"
    assert 37_500.0 in valeurs, "franchise en base de TVA (services)"


def test_les_montants_ne_sont_pas_recopies_dans_le_controle() -> None:
    """Contre-épreuve de la règle 5 : une seule source pour ces montants.

    Les recopier dans `verification/controles.py` en ferait une seconde
    vérité, qui divergerait au prochain budget — exactement le défaut que ce
    dépôt a payé trois fois sur ses listes de devises et de labels.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "generation" / "verification" / "controles.py"
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    litteraux = {
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, int | float)
    }
    for montant in valeurs_des_seuils_legaux():
        assert montant not in litteraux, f"{montant} recopié dans le contrôle"


def test_un_seuil_legal_ne_nourrit_jamais_les_derivations() -> None:
    """Contre-épreuve : la première version de ce correctif a AFFAIBLI le contrôle.

    Les seuils légaux étaient verses dans `references`, qui alimente
    `_derivations` — les combinaisons deux à deux du socle. Six valeurs de
    plus, et `test_un_en_tete_qui_ne_decide_rien_ne_blanchit_rien` est tombé
    aussitôt : « 47,1 % » cessait d'être signalé, justifié par hasard par un
    quotient de deux seuils.

    C'est exactement ce que la docstring de `_derivations` annonce : « la
    probabilité qu'un chiffre INVENTÉ tombe par hasard sur l'une d'elles
    devient réelle. Un contrôle qui justifie tout ne justifie plus rien. »

    Un seuil légal justifie le montant QU'IL EST, pas ce qu'on peut calculer
    avec : rien n'en dérive. Ce test interdit de les remettre dans le même sac.
    """
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "generation" / "verification" / "controles.py"
    )
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    appels = [
        ast.unparse(noeud)
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call) and ast.unparse(noeud.func).endswith("_derivations")
    ]
    assert appels, "le contrôle doit toujours calculer ses dérivations"
    for appel in appels:
        assert "seuils_legaux" not in appel, appel
