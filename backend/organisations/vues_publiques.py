"""Ce que le public voit avant d'avoir un compte.

La page partenaires est ouverte : quelqu'un qui découvre l'offre n'a ni jeton,
ni organisation. Ces vues sont donc les seules de l'application à répondre
sans authentification — et c'est précisément pour ça qu'elles vivent dans un
fichier séparé de `vues_espace`, où **tout** est nominatif. Mélanger les deux
ferait qu'un jour une vue privée hériterait du décorateur public par
inadvertance.

Elles n'exposent que le catalogue commercial. Aucune donnée d'organisation,
aucun compteur, aucun identifiant : rien qui n'est pas déjà sur la plaquette.
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .models import Formule


@require_GET
def formules_publiques(request: HttpRequest) -> HttpResponse:
    """Catalogue des formules, pour la page partenaires.

    Même source que `vues_espace.formules` : la table. La page publique et
    l'espace client ne peuvent donc pas afficher deux tarifs différents
    (règle 5) — c'était le risque en recopiant les prix dans le React.

    Le coût par livrable inclus est **calculé ici**, jamais stocké : c'est un
    rapport entre deux champs de la formule. Le mémoriser en ferait une
    troisième valeur susceptible de contredire les deux autres.
    """
    formules = Formule.objects.filter(active=True).order_by("rang", "prix_mensuel_cents")
    return JsonResponse({
        "formules": [
            {
                "code": f.code,
                "libelle": f.libelle,
                "credits_par_echeance": f.credits_par_echeance,
                "prix_mensuel_cents": f.prix_mensuel_cents,
                "prix_credit_supplementaire_cents": f.prix_credit_supplementaire_cents,
                "cout_par_livrable_cents": (
                    round(f.prix_mensuel_cents / f.credits_par_echeance)
                    if f.credits_par_echeance
                    else 0
                ),
                "devise": f.devise,
                "avantages": list(f.avantages or []),
                "mise_en_avant": f.mise_en_avant,
            }
            for f in formules
        ],
    })
