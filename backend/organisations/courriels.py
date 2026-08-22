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


#: Type d'incident ouvert quand un courriel ne part pas.
INCIDENT_TYPE_COURRIEL = "courriel_non_envoye"


def _envoyer(*, destinataire: str, sujet: str, corps_html: str) -> bool:
    """Envoie, et dit si c'est parti. Ne lève jamais.

    **L'échec ouvre un incident**, en plus de la ligne de journal.

    Mesuré le 07/08/2026 : `api.resend.com` est derrière Cloudflare, qui
    bannissait l'agent utilisateur par défaut d'`urllib`. AUCUN courriel ne
    partait — ni invitation, ni lien de mot de passe — et rien nulle part ne le
    disait : pas d'erreur à l'écran, rien dans l'interface, aucune trace chez le
    prestataire puisque la requête était refusée avant lui, et une ligne de
    journal dans un conteneur dont les journaux ne sont pas consultables.

    Le silence était donc TOTAL. La ligne de journal donnait l'illusion d'une
    surveillance qui n'existait pas — un contrôle qui n'alerte personne n'est
    pas un contrôle (règle 1). L'incident, lui, se voit depuis l'administration.
    """
    from integrations.brevo import get_transactional_email_client  # noqa: PLC0415

    try:
        get_transactional_email_client().send_delivery_email(
            recipient_email=destinataire,
            subject=sujet,
            html_body=corps_html,
            attachments=(),
        )
    except Exception as erreur:  # noqa: BLE001 — voir l'arbitrage en tête de module
        _log.exception("Courriel non envoye a %s (%s)", destinataire, sujet)
        _ouvrir_incident(destinataire=destinataire, sujet=sujet, erreur=erreur)
        return False
    return True


def _ouvrir_incident(*, destinataire: str, sujet: str, erreur: Exception) -> None:
    """Rend l'échec visible. Ne lève jamais, à son tour.

    Un incident qui ferait échouer l'action qu'il documente serait pire que le
    silence qu'il corrige : une invitation valide serait annulée parce que la
    supervision est indisponible.

    Le corps de la réponse HTTP est conservé quand il existe : c'est lui qui
    porte le motif. Sans lui, l'incident dirait « HTTP Error 403 » et
    n'apprendrait rien — un motif introuvable par son lecteur (règle 2).
    """
    try:
        from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

        motif = f"{type(erreur).__name__} : {erreur}"
        corps = getattr(erreur, "read", None)
        if callable(corps):
            try:
                motif += " — " + corps().decode("utf-8", "replace")[:600]
            except Exception:  # noqa: BLE001, S110 — le motif de base suffit
                pass

        OperationalIncident.objects.create(
            title="Courriel non envoyé",
            severity=IncidentSeverity.HIGH,
            details={
                "type": INCIDENT_TYPE_COURRIEL,
                "destinataire": destinataire,
                "sujet": sujet,
                "motif": motif,
            },
        )
    except Exception:  # noqa: BLE001
        _log.exception("Incident de messagerie non enregistre")


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


def souhaiter_la_bienvenue(*, destinataire: str, livrable: str, lien: str) -> bool:
    """Confirme un achat à l'unité et donne l'accès à l'espace.

    Ce n'est PAS une invitation : personne n'a invité cette personne, elle a
    payé. `inviter_un_collaborateur` lui aurait écrit « vous faites désormais
    partie de l'espace de … » — une phrase qui laisse croire qu'on l'a ajoutée
    quelque part, quand elle vient d'ouvrir le sien.

    Le lien mène au choix du mot de passe, et pas à la connexion : elle n'en a
    pas encore. Elle est déjà entrée par la page de retour de Stripe ; ce
    courriel est ce qui lui permettra de REVENIR, demain, depuis un autre
    appareil.
    """
    return _envoyer(
        destinataire=destinataire,
        sujet=f"Votre {livrable} — votre espace est prêt",
        corps_html=_gabarit(
            titre="Votre paiement est bien reçu",
            phrases=[
                f"Votre espace EVKHA est ouvert, avec votre {livrable} à "
                "lancer quand vous le souhaitez.",
                "Choisissez votre mot de passe pour y revenir à tout moment : "
                "vous y suivrez la production et y retrouverez votre document.",
            ],
            lien=lien,
            bouton="Choisir mon mot de passe",
        ),
    )


def demander_un_avis(*, destinataire: str, etude: str, lien: str) -> bool:
    """Demande son avis à qui a acheté une étude, deux jours plus tôt.

    Deux jours, et pas le lendemain : le délai laisse le temps de lire. Écrire
    le jour même reviendrait à demander un avis sur un document qu'on vient de
    télécharger — la réponse ne porterait que sur la rapidité de la remise.

    Envoyé UNE FOIS. `AchatProduit.avis_demande_le` porte cette garantie : sans
    lui, la tâche horaire redemanderait son avis à la même personne toutes les
    heures. On ne relance pas non plus celle qui ne répond pas : un avis
    réclamé deux fois n'est plus un avis, c'est une corvée.
    """
    return _envoyer(
        destinataire=destinataire,
        sujet=f"Votre avis sur « {etude} » ?",
        corps_html=_gabarit(
            titre="Qu'avez-vous pensé de votre étude ?",
            phrases=[
                f"Vous avez téléchargé « {etude} » il y a deux jours. Si vous "
                "avez eu le temps de la parcourir, votre avis aidera celles "
                "qui hésitent encore.",
                "Deux minutes suffisent : une note, une phrase. Il apparaîtra "
                "sur la fiche de l'étude après relecture.",
            ],
            lien=lien,
            bouton="Donner mon avis",
        ),
    )


def annoncer(
    *, destinataire: str, titre: str, message: str, lien: str, bouton: str
) -> bool:
    """Porte une annonce d'EVKHA a un client, par courriel.

    Le SUJET est le titre de l'annonce, tel que la cliente l'a ecrit. Un sujet
    generique — « Nouvelle information EVKHA » — se ferait ignorer, et rendrait
    l'annonce invisible pour ceux qui ne se connectent pas.

    Le meme texte s'affiche dans l'espace client a la connexion suivante. Deux
    formulations pour une meme nouvelle finiraient par diverger (regle 5) :
    l'appelant passe ici le texte qu'il affiche la-bas.
    """
    return _envoyer(
        destinataire=destinataire,
        sujet=titre,
        corps_html=_gabarit(
            titre=titre,
            # Les paragraphes sont ceux de la cliente : on decoupe sur les
            # lignes vides plutot que de recomposer son texte.
            phrases=[p.strip() for p in message.split("\n\n") if p.strip()],
            lien=lien,
            bouton=bouton,
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


def confirmer_la_nouvelle_adresse(*, destinataire: str, lien: str) -> bool:
    """Part vers la NOUVELLE adresse : c'est elle qu'il faut prouver.

    L'envoyer à l'ancienne ne démontrerait rien — on saurait que le titulaire
    est d'accord, jamais que la boîte visée existe et lui appartient.
    """
    return _envoyer(
        destinataire=destinataire,
        sujet="Confirmez votre nouvelle adresse EVKHA",
        corps_html=_gabarit(
            titre="Confirmez cette adresse",
            phrases=[
                "Quelqu'un a demandé que cette adresse devienne l'identifiant "
                "de connexion d'un espace EVKHA.",
                "Si c'est bien vous, confirmez-le ci-dessous. Tant que vous ne "
                "l'aurez pas fait, rien ne change.",
            ],
            lien=lien,
            bouton="Confirmer cette adresse",
        ),
    )


def prevenir_l_ancienne_adresse(*, destinataire: str, nouvelle: str) -> bool:
    """Prévient la boîte qui PERD le compte.

    Sans ce message, une reprise de compte serait silencieuse : le voleur change
    l'adresse, et le titulaire ne l'apprend qu'en ne recevant plus rien. C'est
    le seul avertissement qui atteint quelqu'un dont on est en train de prendre
    l'accès — il est donc court et sans bouton, pour ne pas se faire prendre
    lui-même pour une tentative d'hameçonnage.
    """
    return _envoyer(
        destinataire=destinataire,
        sujet="L'adresse de votre espace EVKHA a changé",
        corps_html=(
            f'<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;'
            f'background:{_COQUILLE};padding:28px 16px;">'
            f'<div style="max-width:520px;margin:0 auto;background:#ffffff;'
            f'border:1px solid {_BORDURE};border-radius:14px;overflow:hidden;">'
            f'<div style="height:4px;background:{_OR};"></div>'
            f'<div style="padding:26px 28px 30px;">'
            f'<h1 style="font-size:20px;margin:0 0 16px;color:{_ENCRE};">'
            f"L'adresse de votre espace a changé</h1>"
            f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;'
            f'color:{_GRIS};">Votre espace EVKHA utilise désormais '
            f"<b>{escape(nouvelle)}</b> comme adresse de connexion.</p>"
            f'<p style="margin:0;font-size:15px;line-height:1.6;color:{_GRIS};">'
            f"Si vous n'êtes pas à l'origine de ce changement, répondez à ce "
            f"message immédiatement&nbsp;: nous rétablirons votre accès.</p>"
            f"</div></div></div>"
        ),
    )


def relancer_un_paiement(
    *,
    destinataire: str,
    organisation: str,
    objet: str,
    montant_cents: int,
    devise: str = "EUR",
) -> bool:
    """Invite à terminer un paiement resté en suspens.

    **Aucun lien de paiement n'est renvoyé.** Une session Stripe expire au bout
    de vingt-quatre heures : un lien mort dans un courriel de relance donnerait
    l'impression d'un service en panne au moment précis où l'on cherche à
    rassurer. On renvoie vers l'espace, où le geste est à un clic et toujours
    valable.

    Le ton n'insiste pas. Quelqu'un qui a renoncé à payer a peut-être une bonne
    raison — un doute, un budget, un empêchement. Une relance qui presse
    transforme une hésitation en refus.
    """
    montant = f"{montant_cents / 100:.2f} {devise}".replace(".", ",")
    return _envoyer(
        destinataire=destinataire,
        sujet="Votre commande EVKHA n'a pas été finalisée",
        corps_html=_gabarit(
            titre="Votre commande est restée en attente",
            phrases=[
                f"Vous avez commencé une {objet.lower()} pour "
                f"{escape(organisation)} — {montant} — sans aller au bout du "
                "paiement.",
                "Rien n'a été débité et rien n'est perdu : vous pouvez "
                "reprendre depuis votre espace quand vous le souhaitez.",
                "Si vous avez une question sur la formule ou sur les crédits, "
                "répondez simplement à ce message.",
            ],
            lien=_adresse_de_l_espace(),
            bouton="Reprendre depuis mon espace",
        ),
    )


def _adresse_de_l_espace() -> str:
    """L'adresse publique de l'espace client, telle que la configuration la dit.

    Lue dans les réglages plutôt qu'écrite ici : un domaine en dur dans un
    courriel survit aux déménagements, et envoie les clients sur une adresse
    morte sans que personne ne s'en aperçoive.
    """
    from django.conf import settings  # noqa: PLC0415

    base = str(getattr(settings, "EVKHA_APP_URL", "") or "").rstrip("/")
    return f"{base}/espace/abonnement" if base else "https://app2.evkha.fr/espace"
