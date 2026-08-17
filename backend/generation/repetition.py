"""Répétition à blanc : la chaîne entière, sans un appel d'API ni un centime.

## Pourquoi ce module existe

Le 10/08/2026, cinq défauts ont été découverts en PAYANT des générations
réelles — 5,22 € d'essais pour les voir. Trois des cinq étaient des
contradictions INTERNES, visibles sans aucun appel d'API :

  - la validation des chapitres ignorait les codes de la grille de notation
    que la consigne ordonnait de citer (`d326557e`, mort à 1 chapitre sur 10) ;
  - le contrôle de la grille refusait un socle réparable, trois fois, et
    l'étude mourait avant son premier chapitre (`6a44baff`, mort à 0 €) ;
  - le gate exigeait un tableau HTML que `_SYSTEME` interdit dans le même
    prompt (`6cb0fab3`, bloqué à la livraison).

Aucune n'avait besoin de l'API pour être vue : il fallait JOUER la chaîne,
pas la deviner. C'est ce que fait ce module — socle, chapitres, gate,
assemblage — sur la doublure (`StubClaudeClient`), pour les quatre livrables.

## Ce que la répétition prouve, et ce qu'elle ne prouve pas

Elle prouve qu'aucun contrôle n'exige ce qu'une consigne interdit, qu'aucun
chapitre n'est refusé pour une raison interne, que la chaîne va au bout.
Elle ne prouve RIEN sur le contenu qu'un vrai modèle produira (règle 7) :
les échecs de gate portant sur le CONTENU de la doublure (cardinaux,
verticales…) sont attendus et rapportés, pas comptés comme défauts.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.gate import run_delivery_gate
from generation.models import ChapterStatus
from generation.runner import GenerationRunError, run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order, OrderStatus

#: Brief minimal mais complet : les quatre variables requises, plus ce que
#: les livrables riches (EC, BP) exploitent quand c'est présent.
VARIABLES_DE_REPETITION: dict[str, str] = {
    "SECTEUR": "torréfaction artisanale de café",
    "PAYS": "France",
    "ZONE": "Lyon et sa métropole",
    "PROJET": "Atelier de torréfaction avec vente directe et abonnements",
    "CLIENTELE_CIBLE": "Particuliers amateurs et cafés-restaurants indépendants",
    "CONCURRENTS": "Torréfacteurs locaux, chaînes nationales, vente en ligne",
    # L'état chiffré client, sans lequel `_check_etat_chiffre_present` bloque
    # tout business plan — à raison : un gate sans référentiel de comparaison
    # rendrait `passed` sur n'importe quoi (règle 1). Un brief de répétition
    # sans ces montants ne répète pas le cas nominal, il répète le cas
    # dégradé « prévisionnel manquant, relecture admin ».
    "INVESTISSEMENT_TOTAL": "85 000 €",
    "APPORT": "25 000 €",
    "EMPRUNT": "60 000 €",
    "SUBVENTIONS": "0 €",
    "CA_PREVISIONNEL": "120 000 €",
    "EBE_PREVISIONNEL": "18 000 €",
    "RESULTAT_NET_PREVISIONNEL": "9 000 €",
    "SEUIL_RENTABILITE": "95 000 €",
    "TAUX_OCCUPATION": "70 %",
}


@dataclass
class RapportRepetition:
    """Le constat d'une répétition, séparé en défauts INTERNES et externes."""

    livrable: str
    job_id: str = ""
    chapitres_ok: int = 0
    chapitres_total: int = 0
    #: (numéro, motif) des chapitres FAILED — toujours un défaut interne :
    #: sur la doublure, un chapitre qui échoue ne peut s'en prendre qu'à nous.
    chapitres_rates: list[tuple[int, str]] = field(default_factory=list)
    #: Chapitres DONE sans payload structuré : le moteur HÉRITÉ a joué à la
    #: place du moteur de production. Mesuré le 10/08/2026 : la première
    #: version de cette répétition a rendu « SAIN ×4 » sur le mauvais moteur,
    #: parce que `EVKHA_SOCLE_ENABLED` est faux par défaut hors production.
    #: Une répétition de la mauvaise pièce est pire qu'aucune répétition.
    chapitres_sans_payload: list[int] = field(default_factory=list)
    gate_passe: bool = False
    #: Échecs de gate, rapportés pour information (contenu de doublure).
    gate_echecs: list[str] = field(default_factory=list)
    #: Une exception qui a arrêté la chaîne — toujours un défaut interne.
    erreur_chaine: str = ""

    @property
    def defauts_internes(self) -> list[str]:
        defauts = [f"chapitre {n} : {motif}" for n, motif in self.chapitres_rates]
        if self.chapitres_sans_payload:
            defauts.append(
                "moteur hérité employé — chapitres sans payload structuré : "
                + ", ".join(str(n) for n in self.chapitres_sans_payload)
                + ". La répétition doit jouer le moteur de PRODUCTION."
            )
        if self.erreur_chaine:
            defauts.append(f"chaîne interrompue : {self.erreur_chaine}")
        return defauts

    @property
    def saine(self) -> bool:
        return not self.defauts_internes


def jouer_a_blanc(deliverable_type: str) -> RapportRepetition:
    """Joue la chaîne complète d'UN livrable sur la doublure."""
    rapport = RapportRepetition(livrable=deliverable_type)

    suffixe = uuid.uuid4().hex[:10]
    offre, _ = Offer.objects.get_or_create(
        slug=f"repetition-{deliverable_type.replace('_', '-')}",
        defaults={
            "name": f"Répétition {deliverable_type}",
            "deliverable_type": deliverable_type,
        },
    )
    client_db, _ = Customer.objects.get_or_create(
        email="repetition@blanc.local",
    )
    commande = Order.objects.create(
        systeme_order_id=f"repetition-{suffixe}",
        customer=client_db,
        offer=offre,
        status=OrderStatus.WAITING_INTAKE,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        source=IntakeSource.MANUAL,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=dict(VARIABLES_DE_REPETITION),
    )

    job = bootstrap_generation_job(soumission)
    rapport.job_id = str(job.id)

    # Le client est INJECTÉ : la répétition ne dépend pas d'un réglage
    # d'environnement pour être gratuite. Quoi qu'il y ait dans le `.env`,
    # aucun appel réseau ne part d'ici.
    #
    # Et le moteur est FORCÉ sur celui de production. `EVKHA_SOCLE_ENABLED`
    # est faux par défaut hors production : sans ce forçage, la répétition
    # joue le moteur hérité et rend un « SAIN » qui ne parle pas du système
    # déployé — mesuré le 10/08/2026, première exécution de ce module.
    try:
        with override_settings(EVKHA_SOCLE_ENABLED=True):
            run_generation_job(job, client=StubClaudeClient())
    except GenerationRunError as erreur:
        rapport.erreur_chaine = str(erreur)
    except Exception as erreur:  # noqa: BLE001 — tout arrêt est un constat, pas un crash
        rapport.erreur_chaine = f"{type(erreur).__name__} : {erreur}"

    job.refresh_from_db()
    chapitres = list(job.chapters.order_by("chapter_number"))
    rapport.chapitres_total = len(chapitres)
    rapport.chapitres_ok = sum(1 for c in chapitres if c.status == ChapterStatus.DONE)
    rapport.chapitres_rates = [
        (c.chapter_number, (c.error_message or "sans motif")[:300])
        for c in chapitres
        if c.status == ChapterStatus.FAILED
    ]
    rapport.chapitres_sans_payload = [
        c.chapter_number
        for c in chapitres
        if c.status == ChapterStatus.DONE and not c.payload
    ]

    # Le gate en lecture seule — ses échecs de CONTENU sont attendus sur une
    # doublure ; ce qu'on surveille, c'est qu'aucun ne soit une contradiction
    # interne, et le test de la répétition le verrouille sur les motifs.
    try:
        verdict = run_delivery_gate(job)
        rapport.gate_passe = bool(verdict.passed)
        details: Any = verdict.as_details()
        rapport.gate_echecs = [
            f"{echec.get('check', '?')} (ch. {echec.get('chapitre', '—')}) : "
            f"{str(echec.get('detail', ''))[:200]}"
            for echec in details.get("failures", [])
        ]
    except Exception as erreur:  # noqa: BLE001
        rapport.erreur_chaine = (
            rapport.erreur_chaine or f"gate : {type(erreur).__name__} : {erreur}"
        )

    return rapport


def jouer_les_quatre() -> list[RapportRepetition]:
    return [jouer_a_blanc(livrable) for livrable in DeliverableType.values]
