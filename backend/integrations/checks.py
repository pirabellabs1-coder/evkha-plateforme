from __future__ import annotations

import os

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_webhook_secrets(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Risque 2 — endpoints webhook publics si les secrets ne sont pas configures."""
    issues: list[Error | Warning] = []
    is_prod = not settings.DEBUG

    for setting_name, endpoint, code in (
        ("TALLY_WEBHOOK_SECRET", "/webhooks/tally/intake/", "W001"),
        ("SYSTEME_WEBHOOK_SECRET", "/webhooks/systeme/order/", "W002"),
    ):
        if not getattr(settings, setting_name, ""):
            msg = (
                f"{setting_name} non configure : "
                f"l'endpoint {endpoint} accepte toutes les requetes sans verification."
            )
            hint = f"Definir {setting_name} dans les variables d'environnement du VPS (Coolify)."
            cls = Error if is_prod else Warning
            issues.append(cls(msg, hint=hint, id=f"evkha.{code}"))

    return issues


@register()
def check_stripe_credentials(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Sans ces deux valeurs, personne ne peut payer — et donc personne n'entre.

    Le ton differe volontairement de `check_webhook_secrets` juste au-dessus.
    La-bas, un secret manquant rend un endpoint PERMISSIF : le defaut est
    silencieux et dangereux, d'ou l'alerte. Ici le defaut est bruyant — le
    paiement refuse de demarrer et le webhook rejette tout — donc le check ne
    protege de rien, il informe : il dit ce qui est en panne avant qu'un
    visiteur ne le decouvre a notre place.

    Les deux valeurs sont verifiees separement parce qu'elles s'oublient
    separement : la cle secrete se copie au moment de brancher le paiement, le
    secret de signature seulement au moment de creer le point de terminaison,
    souvent un autre jour. N'en avoir qu'une donne un tunnel qui encaisse sans
    jamais ouvrir l'espace — le pire des trois etats.

    **Toujours `Warning`, jamais `Error`, meme en production** — et c'est la
    seule difference de forme avec `check_webhook_secrets`. Un `Error` fait
    echouer les commandes de gestion, `migrate` compris : il empecherait le
    deploiement de la version qui apporte le paiement, faute de cles qu'on ne
    peut precisement poser qu'une fois cette version en ligne. Le check
    refuserait de demarrer parce qu'il n'a rien a dire d'autre que « ce n'est
    pas encore branche ».

    Ce n'est pas un relachement : ce qui protege ici, ce n'est pas ce check,
    c'est que `stripe_api` leve sans cle et que le webhook repond 503 sans
    secret. Le check ne fait que le dire tot.
    """
    issues: list[Error | Warning] = []

    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        issues.append(Warning(
            "STRIPE_SECRET_KEY non configuree : aucune souscription ne peut "
            "etre payee, donc aucun nouvel abonne n'accede a son espace.",
            hint=(
                "Definir STRIPE_SECRET_KEY dans les variables d'environnement "
                "du VPS (Coolify). sk_test_… en recette, sk_live_… en reel."
            ),
            id="evkha.W003",
        ))

    if not getattr(settings, "STRIPE_WEBHOOK_SECRET", ""):
        issues.append(Warning(
            "STRIPE_WEBHOOK_SECRET non configure : les evenements de paiement "
            "seront TOUS rejetes. Un client pourra payer sans jamais recevoir "
            "ses credits.",
            hint=(
                "Copier le secret de signature du point de terminaison Stripe "
                "(whsec_…) dans les variables d'environnement du VPS. Il est "
                "propre a chaque point de terminaison : celui de la recette ne "
                "valide pas les evenements du reel."
            ),
            id="evkha.W004",
        ))

    return issues


@register()
def check_ai_credentials(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Risque 3 — generation en mode stub si ANTHROPIC_API_KEY absente."""
    issues: list[Error | Warning] = []

    use_stub = getattr(settings, "EVKHA_USE_STUB_AI", True)
    if not use_stub and not os.environ.get("ANTHROPIC_API_KEY", ""):
        issues.append(Error(
            "ANTHROPIC_API_KEY absente alors que EVKHA_USE_STUB_AI=False. "
            "Toutes les generations produiront du contenu de demonstration.",
            hint="Definir ANTHROPIC_API_KEY dans les variables d'environnement du VPS.",
            id="evkha.E001",
        ))

    return issues


#: Cle attendue pour chaque fournisseur de courriel. Meme table que celle de
#: `integrations.brevo` — au sens ou elle doit lister les MEMES fournisseurs.
#: Un fournisseur ajoute la-bas et oublie ici demarrerait sans sa cle.
_CLE_PAR_FOURNISSEUR = {
    "brevo": "BREVO_API_KEY",
    "resend": "RESEND_API_KEY",
}


@register()
def check_email_credentials(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Risque 4 — livraison email bloquee si la cle du fournisseur ACTIF manque.

    Ce controle a mis la production a terre le 07/08/2026. Il exigeait
    `BREVO_API_KEY` des que la doublure etait desactivee — sans savoir que le
    fournisseur venait de passer a Resend. La cle Resend etait posee, celle de
    Brevo ne l'etait pas : `manage.py migrate` a leve `SystemCheckError`, la
    chaine de demarrage s'est arretee, et les conteneurs sont sortis. Le site
    entier est tombe pour une cle dont personne n'avait besoin.

    C'est la regle 2 du depot : un controle qui compare a la mauvaise donnee
    est PIRE qu'absent. Celui-ci ne se plaignait pas d'un defaut, il en
    fabriquait un. Il juge desormais le fournisseur reellement en service.
    """
    issues: list[Error | Warning] = []

    if getattr(settings, "EVKHA_USE_STUB_EMAIL", True):
        return issues

    fournisseur = str(
        getattr(settings, "EVKHA_EMAIL_PROVIDER", "resend") or ""
    ).lower().strip()
    cle = _CLE_PAR_FOURNISSEUR.get(fournisseur)

    if cle is None:
        issues.append(Error(
            f"EVKHA_EMAIL_PROVIDER vaut « {fournisseur} », qui n'est pas un "
            "fournisseur connu. Aucun courriel ne partira.",
            hint="Valeurs acceptees : " + ", ".join(sorted(_CLE_PAR_FOURNISSEUR)) + ".",
            id="evkha.E003",
        ))
    elif not getattr(settings, cle, ""):
        issues.append(Error(
            f"{cle} absente alors que EVKHA_USE_STUB_EMAIL=False et que le "
            f"fournisseur actif est « {fournisseur} ». Les courriels "
            "echoueront systematiquement.",
            hint=f"Definir {cle} dans les variables d'environnement du VPS.",
            id="evkha.E002",
        ))

    return issues
