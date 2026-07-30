"""Prépare le bloc de variables d'environnement à coller dans Coolify.

Les secrets sont **générés localement** et écrits dans un fichier qui reste sur
votre poste. Ils ne transitent nulle part.

    python scripts/preparer_env_coolify.py

Le fichier produit, `env-coolify.txt`, est ignoré par Git. Ouvrez-le,
copiez-le, collez-le dans Coolify → Environment Variables → Developer view.
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "env-coolify.txt"


def cle(octets: int = 32) -> str:
    """Secret aléatoire. `secrets` et non `random` : le second est prévisible."""
    return secrets.token_hex(octets)


def mot_de_passe() -> str:
    """Mot de passe de base de données, sans caractère qui casserait une URL."""
    return secrets.token_urlsafe(24).replace("-", "").replace("_", "")


def construire(domaine_api: str, domaine_front: str) -> str:
    motdepasse = mot_de_passe()
    lignes = [
        "# ─────────────────────────────────────────────────────────────────",
        "# EVKHA — variables à coller dans Coolify",
        "#",
        "# Les valeurs marquées « À REMPLIR » sont vos clés externes : allez",
        "# les chercher dans Anthropic, Brevo, Tally et Systeme.io.",
        "#",
        "# Les drapeaux STUB sont tous à `true` : la plateforme fonctionne de",
        "# bout en bout SANS dépenser un euro et SANS écrire à un vrai client.",
        "# Vous les basculerez un par un, après vérification.",
        "# ─────────────────────────────────────────────────────────────────",
        "",
        "# ── Identite de la pile et domaines ──",
        "# STACK_NAME rend les noms de routeurs Traefik UNIQUES : sans lui, deux",
        "# deploiements se disputent les memes et l'ancien tombe.",
        "STACK_NAME=evkha2",
        f"API_DOMAIN={domaine_api}",
        f"FRONT_DOMAIN={domaine_front}",
        "",
        "# ── Django ──",
        f"DJANGO_SECRET_KEY={cle()}",
        "DJANGO_DEBUG=false",
        f"DJANGO_ALLOWED_HOSTS={domaine_api},{domaine_front}",
        "DJANGO_TIME_ZONE=Europe/Paris",
        "EVKHA_BEHIND_PROXY=true",
        f"CSRF_TRUSTED_ORIGINS=https://{domaine_api},https://{domaine_front}",
        f"EVKHA_BASE_URL=https://{domaine_api}",
        "",
        "# ── Base de données ──",
        "POSTGRES_DB=evkha",
        "POSTGRES_USER=evkha",
        f"POSTGRES_PASSWORD={motdepasse}",
        f"DATABASE_URL=postgres://evkha:{motdepasse}@postgres:5432/evkha",
        "",
        "# ── File de tâches ──",
        "CELERY_BROKER_URL=redis://redis:6379/0",
        "CELERY_RESULT_BACKEND=redis://redis:6379/1",
        "",
        "# ── Services externes — À REMPLIR ──",
        "ANTHROPIC_API_KEY=",
        "BREVO_API_KEY=",
        "BREVO_SENDER_EMAIL=contact@evkha.fr",
        "BREVO_SENDER_NAME=Evkha",
        f"SYSTEME_WEBHOOK_SECRET={cle(16)}",
        f"TALLY_WEBHOOK_SECRET={cle(16)}",
        "",
        "# ── Génération ──",
        "EVKHA_CLAUDE_MODEL=claude-sonnet",
        "EVKHA_ANTHROPIC_MODEL_ID=",
        "",
        "# ── Mode bouchon : TOUT À `true` AU DÉPART ──",
        "# true  = rien n'est appelé, rien n'est facturé, rien n'est envoyé",
        "# false = appels réels. Ne basculez qu'après avoir vérifié l'étape",
        "#         précédente (voir docs/09-deploiement-coolify-neuf.md).",
        "EVKHA_USE_STUB_AI=true",
        "EVKHA_USE_STUB_PDF=true",
        "EVKHA_USE_STUB_EMAIL=true",
        "EVKHA_USE_STUB_DOCS=true",
        "EVKHA_USE_STUB_GAMMA=true",
        "",
        "# ── Accès à l'espace administrateur ──",
        "EVKHA_DASHBOARD_AUTH_DISABLED=false",
        f"EVKHA_DASHBOARD_TOKEN={cle()}",
        "",
        "# ── Divers ──",
        "EVKHA_DEFAULT_RETENTION_DAYS=7",
        "EVKHA_EMAIL_PROVIDER=brevo",
    ]
    return "\n".join(lignes) + "\n"


def main() -> int:
    # La console Windows tourne en cp1252 : un simple « → » dans un message
    # fait planter le script APRÈS avoir écrit le fichier, ce qui laisse croire
    # à un échec alors que tout s'est bien passé.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Préparation des variables Coolify.\n")
    api = input("Domaine de l'API      [api.evkha.fr]  : ").strip() or "api.evkha.fr"
    front = input("Domaine de la plateforme [app.evkha.fr] : ").strip() or "app.evkha.fr"

    SORTIE.write_text(construire(api, front), encoding="utf-8")

    print(f"\nFichier écrit : {SORTIE}")
    print("\nCe qu'il vous reste à faire :")
    print("  1. Ouvrez ce fichier.")
    print("  2. Remplissez ANTHROPIC_API_KEY et BREVO_API_KEY.")
    print("  3. Copiez tout, collez dans Coolify → Environment Variables.")
    print("\nLes secrets ont été générés sur votre poste. Ils ne sont partis")
    print("nulle part, et ce fichier est ignoré par Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
