"""Remplit les colonnes de formule restées à leur valeur par défaut.

Constaté en production le 07/08/2026, page tarifs publique : les quatre
formules affichaient « Crédit supplémentaire : 0 € », aucune puce d'avantage,
et aucune mise en avant — là où le local affichait 59 €, cinq puces et la
formule Pro encadrée.

Ce n'était pas une régression du rendu. `prix_credit_supplementaire_cents`,
`avantages`, `rang` et `mise_en_avant` ont été ajoutés APRÈS la création des
lignes de production, et `seed_formules` laisse par conception une formule
existante intacte — sans ce refus, un tarif ajusté en administration serait
écrasé au prochain déploiement. La protection est juste ; il manquait le
rattrapage ponctuel des lignes créées avant les colonnes.

Ce rattrapage ne touche QUE ce qui est encore à la valeur par défaut, champ
par champ. Une formule dont le prix de crédit supplémentaire a déjà été réglé
en administration n'est pas retouchée : c'est la même règle que la commande,
appliquée au grain du champ plutôt qu'à celui de la ligne.

Les valeurs viennent de `seed_formules`, pas d'une copie : deux tables de
tarifs finiraient par diverger (règle 5). `test_rattrapage_des_formules.py`
vérifie que cette migration et la commande disent bien la même chose.
"""
from __future__ import annotations

from typing import Any

from django.db import migrations


def remplir_les_colonnes_vides(apps: Any, schema_editor: Any) -> None:
    from organisations.management.commands.seed_formules import (
        AVANTAGES_COMMUNS,
        CODE_MIS_EN_AVANT,
        FORMULES,
    )

    Formule = apps.get_model("organisations", "Formule")

    # Une seule formule est mise en avant. Si l'administration en a déjà
    # désigné une, on ne la déplace pas : ce serait décider à sa place.
    mise_en_avant_deja_choisie = Formule.objects.filter(mise_en_avant=True).exists()

    for rang, (code, _libelle, _cible, _credits, _prix, prix_credit,
               propres) in enumerate(FORMULES, start=1):
        formule = Formule.objects.filter(code=code).first()
        if formule is None:
            continue

        modifies: list[str] = []
        if not formule.prix_credit_supplementaire_cents:
            formule.prix_credit_supplementaire_cents = prix_credit
            modifies.append("prix_credit_supplementaire_cents")
        if not formule.avantages:
            formule.avantages = [*AVANTAGES_COMMUNS, *propres]
            modifies.append("avantages")
        if not formule.rang:
            formule.rang = rang
            modifies.append("rang")
        if not mise_en_avant_deja_choisie and code == CODE_MIS_EN_AVANT:
            formule.mise_en_avant = True
            modifies.append("mise_en_avant")

        if modifies:
            formule.save(update_fields=modifies)


def ne_rien_defaire(apps: Any, schema_editor: Any) -> None:
    """Irréversible à dessein.

    Revenir en arrière voudrait dire remettre ces colonnes à zéro, sans pouvoir
    distinguer ce que cette migration a écrit de ce que l'administration a
    réglé depuis. Un retour arrière destructeur vaut moins qu'un non-retour.
    """


class Migration(migrations.Migration):
    dependencies = [("organisations", "0007_arret_du_renouvellement")]

    operations = [
        migrations.RunPython(remplir_les_colonnes_vides, ne_rien_defaire),
    ]
