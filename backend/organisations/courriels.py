"""Les deux courriels que l'espace client envoie lui-même.

Aucun n'existait. `inviter` affichait « EVKHA lui transmettra ses identifiants
de connexion » et n'envoyait rien : la recherche de `send_mail`, `EmailMessage`
et `brevo` dans tout `backend/organisations/` ne renvoyait aucune occurrence.
La fonctionnalité Équipe était donc entièrement décorative.

Le client de messagerie est celui du reste du produit
(`integrations.brevo`), pas un second : il est déjà bouchonné en
développement et en test, déjà branché en production, et déjà surveillé
(règle 5).

**Un échec d'envoi ne fait pas échouer l'action.** Une invitation dont le
courriel n'est pas parti reste une invitation valide : le lien peut être
recopié depuis l'écran. Faire remonter l'erreur annulerait le rattachement pour
un incident de messagerie, et laisserait l'invitant croire qu'il n'a rien fait.
L'échec est journalisé et rendu à l'appelant, qui l'affiche.
"""
from __future__ import annotations

import logging
from html import escape

_log = logging.getLogger(__name__)


def _envoyer(*, destinataire: str, sujet: str, corps_html: str) -> bool:
    """Envoie, et dit si c'est parti. Ne lève jamais."""
    from integrations.brevo import get_transactional_email_client  # noqa: PLC0415

    try:
        get_transactional_email_client().send_delivery_email(
            recipient_email=destinataire,
            subject=sujet,
            html_body=corps_html,
            attachments=(),
        )
    except Exception:  # noqa: BLE001 — voir l'arbitrage en tête de module
        _log.exception("Courriel non envoye a %s (%s)", destinataire, sujet)
        return False
    return True


def _gabarit(*, titre: str, phrases: list[str], lien: str, bouton: str) -> str:
    """Message sobre, sans image ni ressource externe.

    Volontairement en texte simple habillé : un courriel qui charge des images
    distantes finit dans les indésirables, et celui-ci porte un lien qui donne
    accès à un compte — il doit arriver.
    """
    paragraphes = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.55;">{escape(p)}</p>'
        for p in phrases
    )
    return (
        '<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;'
        'color:#21201c;max-width:520px;">'
        f'<h1 style="font-size:20px;margin:0 0 18px;">{escape(titre)}</h1>'
        f"{paragraphes}"
        f'<p style="margin:26px 0;">'
        f'<a href="{escape(lien)}" style="background:#21201c;color:#ffffff;'
        f"padding:13px 24px;text-decoration:none;border-radius:4px;"
        f'font-size:14px;font-weight:600;display:inline-block;">'
        f"{escape(bouton)}</a></p>"
        '<p style="font-size:13px;color:#6b6a65;line-height:1.5;">'
        "Ce lien est valable trois jours et ne sert qu'une fois. "
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
        "rien ne sera modifié.</p>"
        "</div>"
    )


def inviter_un_collaborateur(
    *, destinataire: str, organisation: str, lien: str
) -> bool:
    return _envoyer(
        destinataire=destinataire,
        sujet=f"Votre accès à l'espace {organisation}",
        corps_html=_gabarit(
            titre="Votre accès est prêt",
            phrases=[
                f"Vous avez été ajouté à l'espace de {organisation}.",
                "Choisissez votre mot de passe pour y accéder. Personne d'autre "
                "ne le connaîtra, pas même la personne qui vous a invité.",
            ],
            lien=lien,
            bouton="Choisir mon mot de passe",
        ),
    )


def reinitialiser_le_mot_de_passe(*, destinataire: str, lien: str) -> bool:
    return _envoyer(
        destinataire=destinataire,
        sujet="Réinitialiser votre mot de passe EVKHA",
        corps_html=_gabarit(
            titre="Réinitialiser votre mot de passe",
            phrases=[
                "Vous avez demandé à redéfinir le mot de passe de votre espace.",
                "En le changeant, toutes vos sessions ouvertes seront fermées, "
                "y compris sur les autres appareils.",
            ],
            lien=lien,
            bouton="Définir un nouveau mot de passe",
        ),
    )
