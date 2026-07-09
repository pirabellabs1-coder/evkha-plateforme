from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Affiche le statut de chaque variable d'environnement critique EVKHA.

    Usage :
        python manage.py check_evkha_config

    Concu pour etre execute via SSH / docker exec sans acces a l'interface Coolify.
    Les valeurs secretes ne sont PAS affichees (seulement SET / MANQUANT).
    """

    help = "Verifie les variables d'environnement requises pour la production EVKHA."

    def handle(self, *args: object, **options: object) -> None:
        ok = self.style.SUCCESS
        warn = self.style.WARNING
        err = self.style.ERROR

        self.stdout.write("\n=== Verification configuration EVKHA ===\n")

        # ── Secrets webhooks ──────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("WEBHOOKS"))
        self._check_secret("TALLY_WEBHOOK_SECRET",
                           "endpoint /webhooks/tally/intake/ non securise", warn)
        self._check_secret("SYSTEME_WEBHOOK_SECRET",
                           "endpoint /webhooks/systeme/order/ non securise", warn)

        # ── Generation IA ─────────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\nGENERATION IA"))
        use_stub_ai = getattr(settings, "EVKHA_USE_STUB_AI", True)
        self._check_bool("EVKHA_USE_STUB_AI", use_stub_ai,
                         ok_true="stub actif (demo, pas de vraie generation)",
                         ok_false="production reelle")
        if not use_stub_ai:
            self._check_secret("ANTHROPIC_API_KEY",
                               "toutes les generations echouent (EVKHA_USE_STUB_AI=False)", err)

        model = getattr(settings, "EVKHA_CLAUDE_MODEL", "claude-sonnet")
        model_id_override = getattr(settings, "EVKHA_ANTHROPIC_MODEL_ID", "") or ""
        self.stdout.write(f"  EVKHA_CLAUDE_MODEL          {ok(model)}")
        if model_id_override:
            self.stdout.write(
                f"  EVKHA_ANTHROPIC_MODEL_ID    {ok(model_id_override)} (surcharge activee)"
            )
        else:
            self.stdout.write(
                "  EVKHA_ANTHROPIC_MODEL_ID    (non surcharge — alias resolu automatiquement)"
            )

        # ── Email livraison ───────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\nEMAIL LIVRAISON"))
        use_stub_email = getattr(settings, "EVKHA_USE_STUB_EMAIL", True)
        self._check_bool("EVKHA_USE_STUB_EMAIL", use_stub_email,
                         ok_true="stub actif (emails non envoyes)",
                         ok_false="envoi Brevo reel")
        if not use_stub_email:
            self._check_secret("BREVO_API_KEY",
                               "livraisons email echouent (EVKHA_USE_STUB_EMAIL=False)", err)

        # ── Django / infra ────────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\nDJANGO / INFRA"))
        debug = getattr(settings, "DEBUG", True)
        debug_status = (
            warn("True  <- ATTENTION : ne pas utiliser en production") if debug else ok("False")
        )
        self.stdout.write(f"  DJANGO_DEBUG                {debug_status}")

        base_url = getattr(settings, "EVKHA_BASE_URL", "") or os.environ.get("EVKHA_BASE_URL", "")
        if base_url:
            self.stdout.write(f"  EVKHA_BASE_URL              {ok(str(base_url))}")
        else:
            self.stdout.write(
                f"  EVKHA_BASE_URL              {warn('non defini (liens review invalides)')}"
            )

        # ── Synthese ──────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write("Pour des verifications supplementaires :")
        self.stdout.write("  python manage.py check --deploy")
        self.stdout.write("  (signale aussi les reglages de securite Django standard)\n")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _check_secret(
        self,
        name: str,
        consequence: str,
        style_fn: object,
    ) -> None:
        value = os.environ.get(name, "") or str(getattr(settings, name, "") or "")
        ok = self.style.SUCCESS
        if value:
            masked = value[:4] + "****"
            self.stdout.write(f"  {name:<28} {ok('SET')}  ({masked})")
        else:
            msg = f"  {name:<28} MANQUANT  — {consequence}"
            self.stdout.write(style_fn(msg))  # type: ignore[operator]

    def _check_bool(
        self,
        name: str,
        value: bool,
        *,
        ok_true: str,
        ok_false: str,
    ) -> None:
        ok = self.style.SUCCESS
        warn = self.style.WARNING
        if value:
            self.stdout.write(f"  {name:<28} {warn('True')}   — {ok_true}")
        else:
            self.stdout.write(f"  {name:<28} {ok('False')}  — {ok_false}")
