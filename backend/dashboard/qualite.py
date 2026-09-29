"""Le rapport interne de qualité : ce que la production a corrigé, étude par étude.

Administrateur seulement (route du tableau de bord, jeton de la console).

## Pourquoi

29/09/2026 : le client ne doit voir qu'une progression fluide et un document
propre — jamais « erreur », jamais « à revoir ». Ce qui a été trouvé et
corrigé en route doit donc se lire AILLEURS, pour que les causes se corrigent
à la source : quels chapitres, quels prompts de rédacteur produisent le plus de
reprises, combien de replis de dernier recours, quels constats sur le PDF.

Tout est LU, rien n'est écrit : la trace vient de `GenerationJob.memoire_etude`
(chapitres contrôlés contre la mémoire de l'étude) et de
`controle_final["rendu_pdf"]` (relecture du PDF final).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from generation.models import GenerationJob

#: Au-delà, la page devient un journal ; les agrégats restent calculés sur tout.
MAX_DOSSIERS_LISTES = 100


def famille_du_motif(motif: str) -> str:
    """Le genre d'un motif, pour les compter ensemble (« Chiffre écrit en clair »)."""
    sans_citation = re.sub(r"«[^»]*»|\{\{.*?\}\}", " ", motif)
    tete = re.split(r"[:(]", sans_citation, maxsplit=1)[0]
    tete = re.sub(r"\s+", " ", tete).strip()
    return tete[:60] or "autre"


def _resume_du_dossier(job: GenerationJob) -> dict[str, Any]:
    memoire = job.memoire_etude or {}
    chapitres = memoire.get("chapitres") or {}
    motifs = sum(len(c.get("motifs") or []) for c in chapitres.values())
    replis = sum(1 for c in chapitres.values() if c.get("replie"))
    reperes = sum(len(c.get("reperes") or []) for c in chapitres.values())
    rendu = (job.controle_final or {}).get("rendu_pdf") or []
    utilisees = {code for c in chapitres.values() for code in (c.get("questions") or [])}
    non_utilisees = [
        r.get("libelle") or r.get("code")
        for r in memoire.get("reponses") or []
        if r.get("renseignee") and r.get("code") not in utilisees
    ] if chapitres else []
    return {
        "id": str(job.id),
        "type": job.deliverable_type,
        "statut": job.status,
        "qa_status": job.qa_status,
        "cree_le": job.created_at.isoformat(),
        "memoire": job.memoire_active,
        "chapitres_controles": len(chapitres),
        "motifs": motifs,
        "replis": replis,
        "reperes": reperes,
        "constats_pdf": len(rendu),
        "questions_non_utilisees": non_utilisees,
        "cout_eur": str(job.total_cost_eur),
    }


@require_GET
@csrf_exempt
def rapport_qualite(request: HttpRequest) -> JsonResponse:
    """Le rapport interne : par dossier, puis agrégé par chapitre et par motif."""
    dossiers = (
        GenerationJob.objects.filter(Q(memoire_active=True) | ~Q(controle_final={}))
        .order_by("-created_at")
    )

    par_chapitre: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    par_famille: Counter[str] = Counter()
    par_constat: Counter[str] = Counter()
    liste: list[dict[str, Any]] = []
    for rang, job in enumerate(dossiers.iterator()):
        if rang < MAX_DOSSIERS_LISTES:
            liste.append(_resume_du_dossier(job))
        for numero, trace in ((job.memoire_etude or {}).get("chapitres") or {}).items():
            compte = par_chapitre[(str(job.deliverable_type), str(numero))]
            compte["passages"] += 1
            compte["motifs"] += len(trace.get("motifs") or [])
            compte["replis"] += 1 if trace.get("replie") else 0
            compte["titre_" + str(trace.get("titre") or "")] = 1
            for motif in trace.get("motifs") or []:
                par_famille[famille_du_motif(str(motif))] += 1
        for constat in (job.controle_final or {}).get("rendu_pdf") or []:
            par_constat[str(constat.get("controle") or "autre")] += 1

    chapitres = []
    for (livrable, numero), compte in par_chapitre.items():
        titre = next((k[6:] for k in compte if k.startswith("titre_")), "")
        chapitres.append({
            "type": livrable, "chapitre": int(numero), "titre": titre,
            "passages": compte["passages"], "motifs": compte["motifs"],
            "replis": compte["replis"],
        })
    chapitres.sort(key=lambda c: (-c["motifs"], -c["replis"], c["type"], c["chapitre"]))

    return JsonResponse({
        "dossiers": liste,
        "chapitres": chapitres[:30],
        "familles_de_motifs": [
            {"famille": famille, "occurrences": n} for famille, n in par_famille.most_common(15)
        ],
        "constats_pdf": [
            {"controle": controle, "occurrences": n} for controle, n in par_constat.most_common()
        ],
    })
