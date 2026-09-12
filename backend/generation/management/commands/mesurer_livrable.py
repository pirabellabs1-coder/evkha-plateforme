"""Les trois nombres qui disent si l'entraînement des prompts a servi.

    python manage.py mesurer_livrable <job_id>
    python manage.py mesurer_livrable <job_id> <job_id> ...

Aucun appel d'API, aucune écriture : la commande re-rend le document depuis
les chapitres déjà payés, le relit, et compte. Elle coûte zéro centime et peut
donc tourner sur les dossiers ANCIENS — c'est tout son intérêt : sans point de
comparaison, un nombre sur la génération de lundi ne voudrait rien dire.

Trois mesures, trois défauts nommés par le client le 12/09/2026 :

    FIGURES        rendues sur demandées. Stratégie Zenitek `b098ded3` :
                   31 demandées, 31 impossibles, zéro dessinée.
    SOURCES        celles qui n'ont pas d'adresse vérifiable. Reprise
                   `8ad03a60` : « 0 URL vérifiable pour 3 sources
                   extérieures ». Les sources du CLIENT sont comptées à part :
                   son prévisionnel n'est pas publié et ne le sera jamais.
    CHIFFRES       ceux que le document avance sans que le socle les porte.

La commande ne juge pas : elle compte. Le verdict se lit dans l'écart entre
deux passages, pas dans une seule colonne de nombres (règle 1 — un contrôle
qui n'a rien à comparer n'est pas un succès).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from generation.checks_post_rendu import (
    _SOURCE_DU_CLIENT_RE,
    _URL_BIDON_RE,
    _URL_RE,
    _sources_listees,
    _trouver_chapitre_sources,
)
from generation.console import console_en_utf8
from generation.models import GenerationJob
from generation.rendu_word.services import produire_docx
from generation.verification.services import verifier_livrable

#: Le motif que porte une anomalie « ce chiffre n'est pas dans le socle ».
_MOTIF_HORS_SOCLE = "chiffres_hors_socle"


def _corps_markdown(job: GenerationJob) -> str:
    """La prose des chapitres terminés, dans l'ordre de lecture."""
    from generation.chapitres import payload_vers_markdown
    from generation.rendu_word.services import payloads_du_job

    return "\n\n".join(payload_vers_markdown(p) for p in payloads_du_job(job))


def _sections(corps: str) -> list[tuple[int, str, str]]:
    """Découpe grossière en (numéro, titre, corps) pour trouver les Sources."""
    sections: list[tuple[int, str, str]] = []
    lignes: list[str] = []
    numero, titre = 0, ""
    for ligne in corps.splitlines():
        if ligne.startswith("# ") or ligne.startswith("## "):
            if titre:
                sections.append((numero, titre, "\n".join(lignes)))
            numero += 1
            titre = ligne.lstrip("# ").strip()
            lignes = []
        else:
            lignes.append(ligne)
    if titre:
        sections.append((numero, titre, "\n".join(lignes)))
    return sections


def _mesurer_les_sources(corps: str) -> tuple[int, int, int] | None:
    """(extérieures, extérieures sans adresse, venant du client) — ou None.

    `None` veut dire « pas de chapitre Sources dans ce document », ce qui
    n'est PAS la même chose que zéro source. Rendre `(0, 0, 0)` ferait passer
    une mesure impossible pour un résultat parfait — le défaut exact que la
    règle 1 du dépôt interdit.
    """
    section = _trouver_chapitre_sources(_sections(corps))
    if section is None:
        return None
    exterieures, sans_adresse, du_client = 0, 0, 0
    for ligne in _sources_listees(section[2]):
        if _SOURCE_DU_CLIENT_RE.search(ligne):
            du_client += 1
            continue
        exterieures += 1
        url = _URL_RE.search(ligne)
        # Une adresse inventée ne vaut pas mieux qu'une absence : elle est
        # pire, puisqu'elle a l'apparence du sérieux.
        if url is None or _URL_BIDON_RE.search(url.group(0)):
            sans_adresse += 1
    return exterieures, sans_adresse, du_client


def _resoudre(reference: str) -> GenerationJob:
    """Un dossier par son UUID complet — ou par son PRÉFIXE.

    On ne lit jamais un dossier autrement que par ses huit premiers caractères
    (journaux, écrans, incidents, conversations). Exiger l'UUID entier ferait
    de cette commande un outil qu'on n'ouvre pas.

    Un préfixe ambigu est une erreur, pas un choix silencieux : rendre la
    mesure du mauvais dossier serait pire que ne rien rendre (règle 2).
    """
    candidats = list(GenerationJob.objects.filter(id__startswith=reference)[:5])
    if len(candidats) == 1:
        return candidats[0]
    if not candidats:
        raise CommandError(f"Dossier introuvable : {reference}")
    trouves = ", ".join(str(j.id)[:12] for j in candidats)
    raise CommandError(f"Préfixe ambigu « {reference} » : {trouves}")


class Command(BaseCommand):
    help = "Compte figures, sources sans adresse et chiffres hors socle d'un livrable."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("job_ids", nargs="+")

    def handle(self, *args: Any, **options: Any) -> None:
        console_en_utf8()
        for job_id in options["job_ids"]:
            self._mesurer(_resoudre(job_id))

    def _mesurer(self, job: GenerationJob) -> None:
        titre = f"{str(job.id)[:8]} — {job.deliverable_type}"
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n═══ {titre}"))

        with tempfile.TemporaryDirectory() as dossier:
            try:
                livrable = produire_docx(job, destination=Path(dossier) / "mesure.docx")
            except Exception as exc:  # noqa: BLE001
                # Ne pas pouvoir rendre EST la mesure : on le dit, on continue.
                self.stdout.write(self.style.ERROR(f"  rendu impossible : {exc}"))
                return
            rapport = livrable.rapport
            controle = verifier_livrable(
                job, livrable.chemin,
                assemblage=rapport, ouvrir_incident=False,
            )

        # Les figures AJOUTÉES par la passe de complétion n'ont été demandées
        # par personne : les compter dans les « rendues » donnait un taux de
        # 121 %, c'est-à-dire un motif faux — pire qu'absent (règle 2). Ce
        # qu'on veut savoir est ce que le MODÈLE a demandé et obtenu.
        demandees = rapport.graphiques_demandes
        completees = len(rapport.graphiques_completes)
        du_modele = max(rapport.graphiques_rendus - completees, 0)
        part = f"{100 * du_modele // demandees} %" if demandees else "—"
        self.stdout.write(
            f"  FIGURES   {du_modele}/{demandees} demandées par le modèle et "
            f"obtenues ({part}) · {completees} ajoutées par complétion · "
            f"{len(rapport.graphiques_en_tableau)} repliées en tableau · "
            f"{len(rapport.graphiques_abandonnes)} perdues"
        )

        mesure = _mesurer_les_sources(_corps_markdown(job))
        if mesure is None:
            # Ne PAS écrire « 0 source » : un chapitre introuvable et un
            # chapitre vide sont deux constats différents, et les confondre
            # ferait passer une mesure impossible pour un résultat propre
            # (règle 1).
            self.stdout.write(self.style.WARNING(
                "  SOURCES   chapitre Sources INTROUVABLE — rien à mesurer"
            ))
        else:
            exterieures, sans_adresse, du_client = mesure
            self.stdout.write(
                f"  SOURCES   {exterieures} extérieures dont "
                f"{sans_adresse} SANS adresse utilisable · "
                f"{du_client} venant du client"
            )

        hors_socle = [a for a in controle.anomalies if a.controle == _MOTIF_HORS_SOCLE]
        self.stdout.write(f"  CHIFFRES  {len(hors_socle)} hors socle")
        for anomalie in hors_socle[:5]:
            self.stdout.write(f"            · {anomalie.detail[:110]}")

        autres = len(controle.anomalies) - len(hors_socle)
        self.stdout.write(f"  RESTE     {autres} autres anomalies relevées")
