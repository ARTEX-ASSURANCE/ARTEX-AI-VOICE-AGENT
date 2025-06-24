# tools.py

import logging
from typing import List, Optional
from datetime import date
from decimal import Decimal
from livekit.agents import function_tool, RunContext
from db_driver import ExtranetDatabaseDriver, Adherent, Contrat, SinistreArtex

logger = logging.getLogger("artex_agent.tools")

# --- Assistants de Gestion de Contexte ---

def _handle_lookup_result(context: RunContext, result: Optional[Adherent] | List[Adherent], source: str) -> str:
    """
    Utilitaire pour gérer le résultat d'une recherche d'adhérent. NE confirme PAS l'identité.
    Stocke les correspondances potentielles dans une variable de contexte temporaire pour confirmation.
    """
    if not result:
        context.userdata["unconfirmed_adherent"] = None
        return "Désolé, aucun adhérent correspondant n'a été trouvé avec ces informations."

    if isinstance(result, list):
        if len(result) > 1:
            response = "J'ai trouvé plusieurs adhérents correspondants. Pour vous identifier précisément, pouvez-vous me donner votre adresse e-mail ou votre numéro de contrat ?"
            return response
        if not result: # Ce cas devrait être couvert par le premier 'if not result', mais inclus pour la robustesse
             context.userdata["unconfirmed_adherent"] = None
             return "Désolé, aucun adhérent correspondant n'a été trouvé."
        result = result[0] # Prendre le premier si la liste en contient un seul après filtrage potentiel

    # Une seule correspondance potentielle trouvée. La stocker pour confirmation.
    context.userdata["unconfirmed_adherent"] = result
    logger.info(f"Adhérent non confirmé trouvé via {source}: {result.prenom} {result.nom} (ID: {result.id_adherent})")
    
    # Si la recherche a été faite par téléphone (automatique), on passe à la confirmation directe.
    if source == "phone":
        return f"Bonjour, je m'adresse bien à {result.prenom} {result.nom} ?" # Déjà en français
    
    # Pour les recherches manuelles, on demande le deuxième facteur.
    return (f"J'ai trouvé un dossier au nom de {result.prenom} {result.nom}. " # Déjà en français
            "Pour sécuriser l'accès, pouvez-vous me confirmer votre date de naissance et votre code postal ?") # Déjà en français


# --- Outils d'Identité et de Contexte ---

@function_tool
async def confirm_identity(context: RunContext, date_of_birth: str, postal_code: str) -> str:
    """
    Confirme l'identité de l'utilisateur en utilisant sa date de naissance ET son code postal.
    Cet outil DOIT être appelé après qu'un outil de recherche a trouvé un adhérent potentiel.
    """
    unconfirmed: Optional[Adherent] = context.userdata.get("unconfirmed_adherent")
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "confirm_identity"
    params = {"date_of_birth": date_of_birth, "postal_code": postal_code}
    result_str = ""

    if current_call_id:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")

    if not unconfirmed:
        result_str = "Veuillez d'abord rechercher un adhérent avant de confirmer une identité."
    else:
        try:
            dob = date.fromisoformat(date_of_birth)
            if unconfirmed.date_naissance == dob and unconfirmed.code_postal == postal_code:
                context.userdata["adherent_context"] = unconfirmed
                context.userdata["unconfirmed_adherent"] = None # Effacer l'adhérent non confirmé

                # Enregistrer le contexte adhérent dans journal_appels
                if current_call_id:
                    db.enregistrer_contexte_adherent_appel(current_call_id, unconfirmed.id_adherent)
                    logger.info(f"Contexte adhérent {unconfirmed.id_adherent} enregistré pour l'appel ID {current_call_id}.")

                logger.info(f"Identité confirmée pour : {unconfirmed.prenom} {unconfirmed.nom} (ID: {unconfirmed.id_adherent}) pour l'appel ID {current_call_id}")
                result_str = f"Merci ! Identité confirmée. Le dossier de {unconfirmed.prenom} {unconfirmed.nom} est maintenant ouvert. Comment puis-je vous aider ?"
            else:
                logger.warning(f"Échec de la confirmation d'identité pour l'ID adhérent : {unconfirmed.id_adherent} pour l'appel ID {current_call_id}")
                result_str = "Les informations ne correspondent pas. Pour votre sécurité, je ne peux pas accéder à ce dossier."
        except (ValueError, TypeError):
            logger.warning(f"Format de date de naissance invalide fourni: {date_of_birth} pour l'appel ID {current_call_id}")
            result_str = "Format de date de naissance invalide. Veuillez utiliser le format AAAA-MM-JJ, par exemple 2001-05-28."

    if current_call_id:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def clear_context(context: RunContext) -> str:
    """
    Efface l'adhérent actuellement sélectionné du contexte de l'assistant. À utiliser si la mauvaise personne a été identifiée ou pour terminer la session.
    """
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver") # db_driver pourrait ne pas être là si get_initial_userdata échoue
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "clear_context"
    params = {} # Pas de paramètres d'entrée spécifiques pour cette fonction à part le contexte lui-même
    result_str = ""

    # Enregistrer l'appel de l'outil même si db est None, pour la traçabilité de l'intention
    # Mais seulement si current_call_id existe, car une action est liée à un appel.
    # Si db est None, on ne pourra pas enregistrer dans la DB.
    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")

    try:
        context.userdata["adherent_context"] = None
        context.userdata["unconfirmed_adherent"] = None
        # On pourrait aussi effacer d'autres champs liés à l'adhérent dans userdata si nécessaire.

        logger.info(f"Le contexte de l'agent a été effacé pour l'appel ID {current_call_id}.")
        result_str = "Le contexte a été réinitialisé. Comment puis-je vous aider ?" # Déjà en français
    except Exception as e:
        # Il est peu probable qu'une simple affectation à None lève une exception, mais par sécurité :
        logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
        result_str = "Une erreur s'est produite lors de la réinitialisation du contexte."
        if current_call_id: # S'assurer que current_call_id est défini
            # Assumer que log_system_error est importé globalement dans ce fichier
            log_system_error(
                source_erreur=f"tools.{tool_name}",
                message_erreur=f"Erreur inattendue: {e}",
                exception_obj=e,
                id_appel_fk=current_call_id,
                contexte_supplementaire=params
            )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

# --- Outils de Recherche et de Gestion des Adhérents ---

import json # Assurez-vous que json est importé
from .error_logger import log_system_error # Ajout de l'importation

@function_tool
async def lookup_adherent_by_email(context: RunContext, email: str) -> str:
    """Recherche un adhérent en utilisant son adresse e-mail pour commencer le processus d'identification."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "lookup_adherent_by_email"
    params = {"email": email}

    if current_call_id:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )

    logger.info(f"Outil : {tool_name} appelé avec email : {email} pour l'appel ID {current_call_id}")

    # Logique actuelle de l'outil
    # La ligne suivante était un placeholder incorrect et a été supprimée:
    # adherent_obj = db.get_adherent_by_id(1)

    # L'appel à db.get_adherent_by_email doit se faire sans passer call_id directement ici,
    # car la journalisation de l'interaction DB spécifique se fait DANS la méthode db_driver elle-même.
    # Si db_driver.py est modifié pour accepter call_id, alors on pourrait le passer.
    # Pour l'instant, on suppose que db_driver.get_adherent_by_email NE PREND PAS call_id.
    adherent = db.get_adherent_by_email(email.strip())

    result_str = _handle_lookup_result(context, adherent, "email")

    if current_call_id:
        db.enregistrer_action_agent( # On pourrait aussi mettre à jour l'enregistrement précédent si on stockait son ID
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT', # Ou mettre à jour l'action 'TOOL_CALL' existante
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def lookup_adherent_by_telephone(context: RunContext, telephone: str) -> str:
    """Recherche un adhérent par son numéro de téléphone. Destiné à la recherche automatique au début d'un appel."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "lookup_adherent_by_telephone"
    params = {"telephone": telephone}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec téléphone : {telephone} pour l'appel ID {current_call_id}")

    try:
        # La méthode db_driver.get_adherents_by_telephone devrait être modifiée pour accepter id_appel_fk_param
        # et faire sa propre journalisation d'interaction BD.
        # adherent = db.get_adherents_by_telephone(telephone.strip(), id_appel_fk_param=current_call_id)
        adherents = db.get_adherents_by_telephone(telephone.strip()) # Version actuelle
        result_str = _handle_lookup_result(context, adherents, "phone")
    except Exception as e:
        logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
        result_str = "Une erreur s'est produite lors de la recherche par téléphone."
        if current_call_id:
            log_system_error(
                source_erreur=f"tools.{tool_name}",
                message_erreur=f"Erreur inattendue: {e}",
                exception_obj=e,
                id_appel_fk=current_call_id,
                contexte_supplementaire=params
            )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def lookup_adherent_by_fullname(context: RunContext, nom: str, prenom: str) -> str:
    """Recherche un adhérent en utilisant son nom complet pour commencer le processus d'identification."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "lookup_adherent_by_fullname"
    params = {"nom": nom, "prenom": prenom}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec nom : {nom}, prénom : {prenom} pour l'appel ID {current_call_id}")

    try:
        # La méthode db_driver.get_adherents_by_fullname devrait aussi être modifiée pour accepter id_appel_fk_param
        # et faire sa propre journalisation d'interaction BD.
        # adherents = db.get_adherents_by_fullname(nom.strip(), prenom.strip(), id_appel_fk_param=current_call_id)
        adherents = db.get_adherents_by_fullname(nom.strip(), prenom.strip()) # Version actuelle
        result_str = _handle_lookup_result(context, adherents, "fullname")
    except Exception as e:
        logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
        result_str = "Une erreur s'est produite lors de la recherche par nom complet."
        if current_call_id:
            log_system_error(
                source_erreur=f"tools.{tool_name}",
                message_erreur=f"Erreur inattendue: {e}",
                exception_obj=e,
                id_appel_fk=current_call_id,
                contexte_supplementaire=params
            )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def get_adherent_details(context: RunContext) -> str:
    """Obtient les détails personnels de l'adhérent actuellement chargé et confirmé dans le contexte de l'assistant."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "get_adherent_details"
    params = {} # Pas de paramètres d'entrée directs, dépend du contexte
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params # On pourrait logguer l'ID de l'adhérent du contexte ici si pertinent
        )
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")

    try:
        adherent: Optional[Adherent] = context.userdata.get("adherent_context")
        if not adherent:
            result_str = "Aucun adhérent n'est actuellement sélectionné et confirmé. Veuillez d'abord rechercher et confirmer l'identité d'un adhérent."
        else:
            # L'objet Adherent est déjà en contexte, pas d'appel BD direct ici.
            # Les appels BD pour peupler cet objet ont été loggués par les outils précédents.
            result_str = (f"Détails pour {adherent.prenom} {adherent.nom} (ID: {adherent.id_adherent}): "
                          f"Email: {adherent.email}, Téléphone: {adherent.telephone}, "
                          f"Adresse: {adherent.adresse}, {adherent.code_postal} {adherent.ville}.")
            # Si l'on voulait logguer une "consultation" même sans appel DB direct :
            # if current_call_id and db:
            #     db._log_db_interaction(type_requete="CONTEXT_READ", table_affectee="adherents_context",
            #                            description_action=f"Consultation détails adhérent ID {adherent.id_adherent} depuis contexte",
            #                            id_appel_fk=current_call_id, id_adherent_concerne=adherent.id_adherent)

    except Exception as e:
        logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
        result_str = "Une erreur s'est produite lors de la récupération des détails de l'adhérent."
        if current_call_id:
            log_system_error(
                source_erreur=f"tools.{tool_name}",
                message_erreur=f"Erreur inattendue: {e}",
                exception_obj=e,
                id_appel_fk=current_call_id,
                contexte_supplementaire=params
            )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def update_contact_information(context: RunContext, address: Optional[str] = None, postal_code: Optional[str] = None, 
                                     city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Met à jour les informations de contact (adresse, téléphone, e-mail) de l'adhérent actuellement confirmé."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "update_contact_information"
    params = {
        "address": address, "postal_code": postal_code, "city": city,
        "phone": phone, "email": email
    }
    # Filtrer les paramètres None pour ne pas les logger inutilement si non fournis
    params_to_log = {k: v for k, v in params.items() if v is not None}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params_to_log
        )
    logger.info(f"Outil : {tool_name} appelé avec params: {params_to_log} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Action impossible. L'identité de l'adhérent doit être confirmée avant de pouvoir modifier des informations."
    else:
        try:
            # Passer current_call_id à la méthode du db_driver
            success = db.update_adherent_contact_info(
                adherent_id=adherent.id_adherent,
                address=address,
                code_postal=postal_code,
                ville=city,
                telephone=phone,
                email=email,
                id_appel_fk_param=current_call_id # Ajout crucial ici
            )

            if success:
                # Rafraîchir le contexte avec les nouvelles informations
                # L'appel à get_adherent_by_id logguera sa propre interaction DB
                updated_adherent = db.get_adherent_by_id(adherent.id_adherent, id_appel_fk_param=current_call_id)
                if updated_adherent:
                    context.userdata["adherent_context"] = updated_adherent
                else: # Ne devrait pas arriver si la mise à jour a réussi et l'ID est correct
                    logger.warning(f"Adhérent ID {adherent.id_adherent} non trouvé après mise à jour pour l'appel {current_call_id}")

                result_str = "Les informations de contact ont été mises à jour avec succès."
            else:
                result_str = "Une erreur s'est produite lors de la mise à jour des informations, ou aucune information n'a été modifiée."
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur technique s'est produite lors de la mise à jour des informations."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params_to_log
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

# --- Outils de Contrat et de Couverture ---

@function_tool
async def list_adherent_contracts(context: RunContext) -> str:
    """Liste tous les contrats associés à l'adhérent actuellement confirmé dans le contexte."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "list_adherent_contracts"
    params = {} # Dépend du contexte adhérent
    result_str = ""

    if current_call_id and db:
        # On pourrait logguer l'ID de l'adhérent du contexte ici si pertinent
        adherent_in_context: Optional[Adherent] = context.userdata.get("adherent_context")
        logged_params = {"adherent_id_contexte": adherent_in_context.id_adherent if adherent_in_context else None}
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=logged_params
        )
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            # Passer current_call_id à la méthode du db_driver
            contracts = db.get_contrats_by_adherent_id(adherent.id_adherent, id_appel_fk_param=current_call_id)

            if not contracts:
                result_str = f"Aucun contrat trouvé pour {adherent.prenom} {adherent.nom}."
            else:
                response_lines = [f"Voici les contrats de {adherent.prenom} {adherent.nom}:"]
                for c in contracts:
                    response_lines.append(f"- Contrat N° {c.numero_contrat} (ID: {c.id_contrat}), Statut: {c.statut_contrat}")
                result_str = "\n".join(response_lines)
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur s'est produite lors de la récupération de la liste des contrats."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire={"adherent_id": adherent.id_adherent if adherent else None}
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def get_contract_details(context: RunContext, contract_id: int) -> str:
    """Fournit les détails complets d'un contrat spécifique, y compris le nom du plan associé et le coût mensuel."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "get_contract_details"
    params = {"contract_id": contract_id}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec contract_id: {contract_id} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            # Vérification de sécurité
            # db.get_contrats_by_adherent_id a déjà été modifié pour prendre id_appel_fk_param
            user_contracts = db.get_contrats_by_adherent_id(adherent.id_adherent, id_appel_fk_param=current_call_id)
            if contract_id not in [c.id_contrat for c in user_contracts]:
                result_str = f"Erreur: Le contrat ID {contract_id} n'appartient pas à {adherent.prenom} {adherent.nom}."
            else:
                # db.get_full_contract_details a déjà été modifié pour prendre id_appel_fk_param
                details = db.get_full_contract_details(contract_id, id_appel_fk_param=current_call_id)
                if not details:
                    result_str = f"Impossible de trouver les détails pour le contrat ID {contract_id}."
                else:
                    result_str = (f"Détails du Contrat {details['numero_contrat']}: "
                                  f"Plan: {details['nom_formule']}, Tarif: {details['tarif_base_mensuel']:.2f}€/mois, "
                                  f"Statut: {details['statut_contrat']}, "
                                  f"Période: du {details['date_debut_contrat']} au {details.get('date_fin_contrat', 'en cours')}.")
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur s'est produite lors de la récupération des détails du contrat."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def list_plan_guarantees(context: RunContext, contract_id: int) -> str:
    """Liste toutes les garanties (couvertures) incluses dans le plan pour un contrat spécifique."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "list_plan_guarantees"
    params = {"contract_id": contract_id}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec contract_id: {contract_id} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            # db_driver.get_contract_by_id et db_driver.get_guarantees_for_formula devraient être mis à jour
            # pour accepter id_appel_fk_param et journaliser leurs propres interactions.
            contract = db.get_contract_by_id(contract_id, id_appel_fk_param=current_call_id)
            if not contract or contract.id_adherent_principal != adherent.id_adherent:
                result_str = f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent."
            else:
                guarantees = db.get_guarantees_for_formula(contract.id_formule, id_appel_fk_param=current_call_id)
                if not guarantees:
                    result_str = "Aucune garantie spécifique n'a été trouvée pour ce plan."
                else:
                    result_str = f"Garanties pour le contrat {contract.numero_contrat}:\n" + ", ".join([g['libelle'] for g in guarantees])
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur s'est produite lors de la récupération des garanties du plan."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def get_specific_coverage_details(context: RunContext, guarantee_name: str, contract_id: int) -> str:
    """Obtient les conditions de remboursement détaillées (taux, plafond, franchise) pour une couverture spécifique unique sur un contrat donné."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "get_specific_coverage_details"
    params = {"guarantee_name": guarantee_name, "contract_id": contract_id}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec params: {params} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            contract = db.get_contract_by_id(contract_id, id_appel_fk_param=current_call_id)
            if not contract or contract.id_adherent_principal != adherent.id_adherent:
                result_str = f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent."
            else:
                detail = db.get_specific_guarantee_detail(contract.id_formule, guarantee_name, id_appel_fk_param=current_call_id)
                if not detail:
                    result_str = f"Désolé, je n'ai pas trouvé de garantie nommée '{guarantee_name}' dans votre plan pour le contrat {contract.numero_contrat}."
                else:
                    result_str = (f"Détails pour la garantie '{detail['libelle']}' du contrat {contract.numero_contrat}: "
                                  f"Taux: {detail.get('taux_remboursement_pourcentage', 'N/A')}%, "
                                  f"Plafond: {detail.get('plafond_remboursement', 'N/A')}€, "
                                  f"Franchise: {detail.get('franchise', '0.00')}€.")
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur s'est produite lors de la récupération des détails de la garantie."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def simulate_reimbursement(context: RunContext, guarantee_name: str, expense_amount: float, contract_id: int) -> str:
    """Calcule le montant estimé du remboursement pour une dépense donnée sous une garantie spécifique."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "simulate_reimbursement"
    params = {"guarantee_name": guarantee_name, "expense_amount": expense_amount, "contract_id": contract_id}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec params: {params} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            contract = db.get_contract_by_id(contract_id, id_appel_fk_param=current_call_id)
            if not contract or contract.id_adherent_principal != adherent.id_adherent:
                result_str = f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent."
            else:
                detail = db.get_specific_guarantee_detail(contract.id_formule, guarantee_name, id_appel_fk_param=current_call_id)
                if not detail:
                    result_str = f"Garantie '{guarantee_name}' non trouvée pour le contrat {contract.numero_contrat}."
                else:
                    expense = Decimal(str(expense_amount))
                    franchise = detail.get('franchise', Decimal('0.00')) or Decimal('0.00') # Assurer une Decimal pour la franchise
                    taux_pourcentage = detail.get('taux_remboursement_pourcentage')
                    taux = (taux_pourcentage / Decimal('100.0')) if taux_pourcentage is not None else Decimal('0.0')
                    plafond = detail.get('plafond_remboursement') # Peut être None

                    remboursable_avant_plafond = (expense - franchise) * taux
                    if remboursable_avant_plafond < Decimal('0.00'): # Eviter remboursement négatif
                        remboursable_avant_plafond = Decimal('0.00')

                    if plafond is not None:
                        remboursement = min(remboursable_avant_plafond, plafond)
                    else:
                        remboursement = remboursable_avant_plafond

                    result_str = f"Pour une dépense de {expense:.2f}€ en {guarantee_name} sur le contrat {contract.numero_contrat}, le remboursement estimé est de {remboursement:.2f}€."
        except TypeError as te: # Spécifiquement pour les erreurs potentielles avec Decimal si les données sont mauvaises
            logger.error(f"Erreur de type dans {tool_name} (probable Decimal conversion) pour appel ID {current_call_id}: {te}", exc_info=True)
            result_str = f"Erreur de calcul lors de la simulation du remboursement: {te}"
            if current_call_id:
                log_system_error(source_erreur=f"tools.{tool_name}", message_erreur=result_str, exception_obj=te, id_appel_fk=current_call_id, contexte_supplementaire=params)
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = f"Erreur de calcul: {e}"
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str


# --- Outils de Gestion des Sinistres ---

@function_tool
async def list_adherent_claims(context: RunContext) -> str:
    """Liste tous les sinistres déclarés par l'adhérent actuellement confirmé dans le contexte."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "list_adherent_claims"
    # Paramètres contextuels, l'ID de l'adhérent sera loggué si disponible
    adherent_in_context: Optional[Adherent] = context.userdata.get("adherent_context")
    params = {"adherent_id_contexte": adherent_in_context.id_adherent if adherent_in_context else None}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context") # Récupérer à nouveau pour la logique
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            # Passer current_call_id à la méthode du db_driver
            claims = db.get_sinistres_by_adherent_id(adherent.id_adherent, id_appel_fk_param=current_call_id)

            if not claims:
                result_str = f"Aucun sinistre trouvé pour {adherent.prenom} {adherent.nom}."
            else:
                response_lines = [f"Voici les sinistres de {adherent.prenom} {adherent.nom}:"]
                for s in claims:
                    response_lines.append(f"- Sinistre ID: {s.id_sinistre_artex}, Type: {s.type_sinistre}, Statut: {s.statut_sinistre_artex}")
                result_str = "\n".join(response_lines)
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur s'est produite lors de la récupération de la liste des sinistres."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire={"adherent_id": adherent.id_adherent if adherent else None}
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def create_claim(context: RunContext, contract_id: int, claim_type: str, description: str, incident_date: str) -> str:
    """Crée un nouveau sinistre pour l'adhérent actuellement confirmé dans le contexte, lié à un contrat spécifique."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "create_claim"
    params = {
        "contract_id": contract_id,
        "claim_type": claim_type,
        "description": description,
        "incident_date": incident_date
    }
    result_str = "" # Initialisation de result_str

    if current_call_id:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec params: {params} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Impossible de créer un sinistre. L'identité de l'adhérent doit d'abord être confirmée."
    else:
        try:
            parsed_date = date.fromisoformat(incident_date)
            # Passer current_call_id à la méthode du db_driver pour qu'elle puisse le logguer
            new_claim = db.create_sinistre(
                id_contrat=contract_id,
                id_adherent=adherent.id_adherent,
                type_sinistre=claim_type,
                description_sinistre=description,
                date_survenance=parsed_date,
                id_appel_fk_param=current_call_id # Ajout du passage de l'ID d'appel
            )
            if new_claim:
                result_str = f"Sinistre créé avec succès! Numéro de sinistre: {new_claim.id_sinistre_artex}."
            else:
                # Ce cas est géré par db_driver.create_sinistre retournant None et journalisant INSERT_FAIL.
                result_str = "Erreur lors de la création du sinistre. Vérifiez que le contrat vous appartient ou que les informations sont correctes."
        except ValueError as ve:
            result_str = "Erreur: La date d'incident doit être au format AAAA-MM-JJ (exemple: 2024-06-23)."
            if current_call_id: # S'assurer que current_call_id est défini avant de l'utiliser
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=result_str,
                    exception_obj=ve,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )
        except Exception as e:
            result_str = "Une erreur inattendue s'est produite lors de la création du sinistre."
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            if current_call_id: # S'assurer que current_call_id est défini
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )

    if current_call_id:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str

@function_tool
async def get_claim_status(context: RunContext, claim_id: int) -> str:
    """Obtient le statut actuel et les détails d'un ID de sinistre spécifique."""
    db: ExtranetDatabaseDriver = context.userdata.get("db_driver")
    current_call_id: Optional[int] = context.userdata.get("current_call_journal_id")
    tool_name = "get_claim_status"
    params = {"claim_id": claim_id}
    result_str = ""

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_CALL',
            nom_outil=tool_name,
            parametres_outil=params
        )
    logger.info(f"Outil : {tool_name} appelé avec claim_id: {claim_id} pour l'appel ID {current_call_id}")

    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        result_str = "Veuillez d'abord confirmer l'identité d'un adhérent."
    else:
        try:
            # Passer current_call_id à la méthode du db_driver
            claim = db.get_sinistre_by_id(claim_id, id_appel_fk_param=current_call_id)

            if not claim:
                result_str = f"Aucun sinistre trouvé avec l'ID {claim_id}."
            elif claim.id_adherent != adherent.id_adherent: # Vérification de sécurité
                result_str = f"Erreur: Vous n'avez pas l'autorisation de consulter le sinistre ID {claim_id}."
            else:
                result_str = (f"Statut du sinistre {claim.id_sinistre_artex}: {claim.statut_sinistre_artex}. "
                              f"Type: {claim.type_sinistre}. Déclaré le: {claim.date_declaration_agent}.")
        except Exception as e:
            logger.error(f"Erreur inattendue dans {tool_name} pour appel ID {current_call_id}: {e}", exc_info=True)
            result_str = "Une erreur s'est produite lors de la récupération du statut du sinistre."
            if current_call_id:
                log_system_error(
                    source_erreur=f"tools.{tool_name}",
                    message_erreur=f"Erreur inattendue: {e}",
                    exception_obj=e,
                    id_appel_fk=current_call_id,
                    contexte_supplementaire=params
                )

    if current_call_id and db:
        db.enregistrer_action_agent(
            id_appel_fk=current_call_id,
            type_action='TOOL_RESULT',
            nom_outil=tool_name,
            resultat_outil=result_str
        )
    return result_str
