"""La mise en page des courriels de la lettre : en-tête, cadre, pied.

Styles EN LIGNE (les messageries ignorent `<style>`), largeur bornée à 600 px,
comme le gabarit de la prospection (`prospection.gabarit_email`). Le pied
porte TOUJOURS le lien de désinscription : il n'est pas dans le corps rédigé,
donc personne ne peut l'oublier ni l'effacer.
"""
from __future__ import annotations

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils.html import escape

from audience.models import Contact

_OR = "#c8a24a"
_POLICE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_PIED = (
    "padding:18px 28px;border-top:1px solid #eeeeee;font-size:12px;"
    "line-height:1.5;color:#888888;"
)

_GABARIT = """\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{objet}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;color:#f4f4f5;">{apercu}</span>
<div style="max-width:600px;margin:0 auto;padding:24px 16px;font-family:{police};">
  <div style="background:#ffffff;border:1px solid #e6e6e6;border-radius:12px;overflow:hidden;">
    <div style="padding:22px 28px;border-bottom:3px solid {accent};">
      <span style="font-size:20px;font-weight:700;letter-spacing:3px;color:#1a1a1a;">EVKHA</span>
    </div>
    <div style="padding:28px;font-size:15px;line-height:1.65;color:#2a2a2a;">
      {corps}
    </div>
    <div style="{pied}">
      <p style="margin:0 0 6px 0;">{raison}</p>
      <p style="margin:0;">{sortie}</p>
    </div>
  </div>
</div>
</body>
</html>"""


def _base() -> str:
    return str(getattr(settings, "EVKHA_BASE_URL", "")).rstrip("/")


def lien_de_desinscription(contact: Contact) -> str:
    """Adresse ABSOLUE, jeton opaque : aucune donnée personnelle dans l'URL."""
    return _base() + reverse("lettre-desinscription", kwargs={"jeton": contact.jeton})


#: Un lien de confirmation vaut sept jours, et pour UNE demande : une demande
#: plus récente, ou la confirmation elle-même, le rend caduc.
VALIDITE_CONFIRMATION_S = 7 * 24 * 3600
_SEL_CONFIRMATION = "lettre.confirmation"


def jeton_de_confirmation(contact: Contact) -> str:
    """Signé, daté, lié à la demande en cours. Distinct du jeton de
    désinscription : celui-là circule dans chaque lettre (transferts, boîtes
    partagées) et ne doit pas suffire à réinscrire quelqu'un."""
    demandee = contact.confirmation_demandee_le
    return signing.dumps(
        {"c": str(contact.pk), "d": demandee.isoformat() if demandee else ""},
        salt=_SEL_CONFIRMATION,
        compress=True,
    )


def contact_a_confirmer(jeton: str) -> Contact | None:
    """Le contact dont ce lien confirme la demande EN COURS, ou `None`."""
    try:
        charge = signing.loads(jeton, salt=_SEL_CONFIRMATION, max_age=VALIDITE_CONFIRMATION_S)
    except signing.BadSignature:  # y compris SignatureExpired
        return None
    if not isinstance(charge, dict):
        return None
    cle = charge.get("c")
    if not isinstance(cle, str):
        return None
    contact = Contact.objects.filter(pk=cle).first()
    if contact is None or contact.confirmation_demandee_le is None:
        return None
    if charge.get("d") != contact.confirmation_demandee_le.isoformat():
        return None
    return contact


def lien_de_confirmation(contact: Contact) -> str:
    return _base() + reverse(
        "lettre-confirmation", kwargs={"jeton": jeton_de_confirmation(contact)}
    )


def enrober(
    *, objet: str, apercu: str, corps_html: str, lien_sortie: str | None
) -> str:
    """Le courriel complet. `lien_sortie` vide : aperçu ou essai, sans abonné."""
    if lien_sortie:
        sortie = (
            "Vous ne souhaitez plus recevoir cette newsletter ? "
            f'<a href="{escape(lien_sortie)}" style="color:#888888;text-decoration:underline;">'
            "Se désinscrire</a>."
        )
    else:
        sortie = "Lien de désinscription : il est ajouté à chaque destinataire à l'envoi."
    return _GABARIT.format(
        objet=escape(objet),
        apercu=escape(apercu),
        corps=corps_html,
        raison=(
            "Vous recevez ce message parce que vous vous êtes inscrit·e à la "
            "newsletter d'EVKHA sur evkha.fr."
        ),
        sortie=sortie,
        accent=_OR,
        police=_POLICE,
        pied=_PIED,
    )


def courriel_de_confirmation(contact: Contact) -> tuple[str, str]:
    """(objet, html) du courriel qui demande de confirmer l'inscription."""
    lien = escape(lien_de_confirmation(contact))
    corps = (
        "<p>Bonjour,</p>"
        "<p>Vous avez demandé à recevoir la newsletter d'EVKHA. Pour la recevoir, "
        "confirmez votre adresse :</p>"
        f'<p style="text-align:center;margin:24px 0;"><a href="{lien}" '
        f'style="display:inline-block;padding:12px 22px;background:#1a1a1a;color:#ffffff;'
        'border-radius:8px;text-decoration:none;font-weight:600;">'
        "Confirmer mon inscription</a></p>"
        "<p>Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
        "vous ne recevrez rien d'autre.</p>"
    )
    objet = "Confirmez votre inscription à la newsletter d'EVKHA"
    html = _GABARIT.format(
        objet=escape(objet),
        apercu="Un clic pour confirmer votre adresse.",
        corps=corps,
        raison="Ce message fait suite à une demande faite sur evkha.fr.",
        sortie="Sans confirmation, votre adresse ne recevra aucune newsletter.",
        accent=_OR,
        police=_POLICE,
        pied=_PIED,
    )
    return objet, html
