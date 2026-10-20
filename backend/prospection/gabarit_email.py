"""Le gabarit d'e-mail de la prospection : une vraie mise en page, pas du HTML nu.

Les agents rédigent le CORPS (des paragraphes). Au moment de l'envoi, on l'enrobe
dans un gabarit de marque EVKHA — en-tête, cadre, pied avec désinscription — en
styles EN LIGNE : les clients de messagerie (Gmail, Outlook) ignorent les
feuilles `<style>`, donc tout style doit vivre sur l'attribut `style` de chaque
balise. Largeur bornée à 600 px, la norme e-mail.
"""
from __future__ import annotations

#: L'or EVKHA, repris de la charte de l'espace admin.
_OR = "#c8a24a"

#: Police sûre pour l'e-mail (les clients ignorent les webfonts non chargées).
_POLICE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_GABARIT = """\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{objet}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;">
<div style="max-width:600px;margin:0 auto;padding:24px 16px;font-family:{police};">
  <div style="background:#ffffff;border:1px solid #e6e6e6;border-radius:12px;overflow:hidden;">
    <div style="padding:22px 28px;border-bottom:3px solid {accent};">
      <span style="font-size:20px;font-weight:700;letter-spacing:3px;color:#1a1a1a;">EVKHA</span>
    </div>
    <div style="padding:28px;font-size:15px;line-height:1.65;color:#2a2a2a;">
      {corps}
    </div>
    <div style="padding:18px 28px;border-top:1px solid #eeeeee;font-size:12px;color:#999999;">
      <p style="margin:0 0 6px 0;">EVKHA — documents d'entreprise sur mesure.</p>
      <p style="margin:0;">Vous ne souhaitez plus recevoir nos messages&nbsp;?
        <a href="{lien}" style="color:#999999;text-decoration:underline;">Se désinscrire</a>.</p>
    </div>
  </div>
</div>
</body>
</html>"""


def enrober(objet: str, corps_html: str, lien_desinscription: str) -> str:
    """Rend l'e-mail complet : le corps mis en page dans le gabarit EVKHA."""
    return _GABARIT.format(
        objet=objet,
        corps=corps_html,
        lien=lien_desinscription,
        accent=_OR,
        police=_POLICE,
    )
