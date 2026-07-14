"""python manage.py tester_apis [--tavily] [--gamma]

Teste la connectivité des API externes réellement configurées, sans lancer de
génération complète ni de livraison. Sert à valider une clé fraîchement posée
dans l'environnement (Coolify) avant de brancher une brique sur un vrai dossier.

- Tavily : une requête de recherche réelle (~1 crédit) ; affiche le nombre de
  résultats et la première source.
- Gamma : GET /v1.0/themes (aucun crédit de génération) ; valide la clé et
  liste les theme IDs disponibles (à reporter dans GAMMA_THEME_ID).

Sans argument : teste les deux. Chaque brique encore en mode stub est
signalée comme telle (rien n'est appelé).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Teste la connectivité Tavily / Gamma avec les clés configurées."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tavily", action="store_true", help="Tester uniquement Tavily.")
        parser.add_argument("--gamma", action="store_true", help="Tester uniquement Gamma.")

    def handle(self, *args: Any, **options: Any) -> None:
        both = not options["tavily"] and not options["gamma"]
        if options["tavily"] or both:
            self._test_tavily()
        if options["gamma"] or both:
            self._test_gamma()

    def _test_tavily(self) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n== Tavily (recherche web) =="))
        if bool(getattr(settings, "EVKHA_USE_STUB_SEARCH", True)):
            self.stdout.write(self.style.WARNING(
                "Mode STUB actif (EVKHA_USE_STUB_SEARCH=true) — aucune vraie "
                "recherche. Passe à false + TAVILY_API_KEY pour activer."
            ))
            return
        from integrations.search import TavilyWebSearchClient

        try:
            resp = TavilyWebSearchClient().search(
                query="marché du coworking France 2025", max_results=3
            )
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"ÉCHEC : {exc}"))
            return
        self.stdout.write(self.style.SUCCESS(
            f"OK — {len(resp.results)} résultat(s)."
        ))
        for r in resp.results[:3]:
            self.stdout.write(f"  - {r.title[:70]}  [{r.url}]")

    def _test_gamma(self) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n== Gamma (mise en page) =="))
        if bool(getattr(settings, "EVKHA_USE_STUB_GAMMA", True)):
            self.stdout.write(self.style.WARNING(
                "Mode STUB actif (EVKHA_USE_STUB_GAMMA=true) — aucun appel réel. "
                "Passe à false + GAMMA_API_KEY pour activer."
            ))
            return
        from integrations.gamma import GammaApiClient, GammaError

        try:
            themes = GammaApiClient().list_themes()
        except GammaError as exc:
            self.stdout.write(self.style.ERROR(f"ÉCHEC : {exc}"))
            return
        self.stdout.write(self.style.SUCCESS(
            f"OK — clé valide, {len(themes)} thème(s) disponible(s)."
        ))
        for t in themes:
            self.stdout.write(f"  - {t['name'] or '(sans nom)'}  → GAMMA_THEME_ID={t['id']}")
        if not themes:
            self.stdout.write(
                "  (aucun thème listé : Gamma utilisera le thème par défaut si "
                "GAMMA_THEME_ID est vide)"
            )
