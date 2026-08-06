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


#: Les couleurs de la plateforme, recopiées de `frontend/src/theme/tokens.css`.
#:
#: Recopiées et non importées, faute de pouvoir lire une feuille de style depuis
#: Python — c'est donc la SEULE duplication assumée de la charte (règle 5), et
#: elle est nommée ici pour qu'on sache où venir le jour où l'or change.
_OR = "#f8c51c"
_NOIR = "#0b0b0b"
_ENCRE = "#1a1a1a"
_GRIS = "#4a4a4a"
_TENU = "#6e6e6e"
_COQUILLE = "#f8f4f4"
_BORDURE = "#e6e2e0"


def _gabarit(*, titre: str, phrases: list[str], lien: str, bouton: str) -> str:
    """Message aux couleurs d'EVKHA, sans image ni ressource externe.

    **Aucune image, et c'est un choix, pas un manque.** Un courriel qui charge
    des ressources distantes finit dans les indésirables, et celui-ci porte le
    lien qui donne accès à un compte : il doit arriver. La marque est donc faite
    de couleur et de typographie — le sceau « E » est un bloc de fond doré, pas
    un logo téléchargé.

    Tout est en style **en ligne** : les clients de messagerie suppriment les
    feuilles de style, et une bonne moitié ignore encore `<style>` dans l'en-tête.

    La largeur est bornée à 520 px et la mise en page tient en blocs empilés :
    pas de tableau de mise en forme, pas de colonne. C'est ce qui se lit aussi
    bien sur un téléphone que dans un volet de prévisualisation étroit.
    """
    paragraphes = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;'
        f'color:{_GRIS};">{escape(p)}</p>'
        for p in phrases
    )
    return (
        f'<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;'
        f'background:{_COQUILLE};padding:28px 16px;">'
        f'<div style="max-width:520px;margin:0 auto;background:#ffffff;'
        f'border:1px solid {_BORDURE};border-radius:14px;overflow:hidden;">'
        # Filet doré en tête : la marque se reconnaît avant même d'être lue.
        f'<div style="height:4px;background:{_OR};"></div>'
        f'<div style="padding:26px 28px 30px;">'
        # Sceau + nom, comme dans l'espace client.
        f'<div style="margin-bottom:22px;">'
        f'<span style="display:inline-block;background:{_OR};color:{_NOIR};'
        f"width:30px;height:30px;line-height:30px;text-align:center;"
        f'border-radius:8px;font-weight:800;font-size:15px;">E</span>'
        f'<span style="display:inline-block;margin-left:10px;font-weight:800;'
        f'font-size:15px;color:{_NOIR};letter-spacing:0.04em;">EVKHA</span>'
        f'<span style="display:inline-block;margin-left:8px;font-size:10px;'
        f'color:{_TENU};letter-spacing:0.14em;">ÉTUDES &amp; STRATÉGIES</span>'
        f"</div>"
        f'<h1 style="font-size:21px;line-height:1.25;margin:0 0 16px;'
        f'color:{_ENCRE};font-weight:700;">{escape(titre)}</h1>'
        f"{paragraphes}"
        # Bouton doré à texte noir : le bouton primaire de la plateforme.
        f'<p style="margin:26px 0 6px;">'
        f'<a href="{escape(lien)}" style="background:{_OR};color:{_NOIR};'
        f"padding:14px 26px;text-decoration:none;border-radius:6px;"
        f'font-size:14px;font-weight:700;display:inline-block;">'
        f"{escape(bouton)}</a></p>"
        # Le lien en clair sous le bouton : certains clients n'affichent pas les
        # boutons, et un lien qu'on ne peut pas recopier est un lien perdu.
        f'<p style="margin:0 0 22px;font-size:12px;color:{_TENU};'
        f'line-height:1.5;word-break:break-all;">'
        f"Si le bouton ne fonctionne pas, copiez cette adresse&nbsp;:<br />"
        f'<span style="color:{_GRIS};">{escape(lien)}</span></p>'
        f'<hr style="border:none;border-top:1px solid {_BORDURE};margin:0 0 16px;" />'
        f'<p style="font-size:12px;color:{_TENU};line-height:1.6;margin:0;">'
        f"Ce lien est valable trois jours et ne sert qu'une fois. "
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez ce "
        f"message&nbsp;: rien ne sera modifié.</p>"
        f"</div></div></div>"
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
                # « Vous avez été ajouté » accorde au masculin et se trompe une
                # fois sur deux. Une tournure sans participe accordé règle le
                # problème sans point médian : elle se lit bien à voix haute, ce
                # qu'un lecteur d'écran fait vraiment.
                f"Vous faites désormais partie de l'espace de {organisation}.",
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
