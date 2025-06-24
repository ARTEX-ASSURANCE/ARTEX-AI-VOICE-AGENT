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
    context.userdata["adherent_context"] = None
    context.userdata["unconfirmed_adherent"] = None
    logger.info("Le contexte de l'agent a été effacé.")
    return "Le contexte a été réinitialisé. Comment puis-je vous aider ?" # Déjà en français

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
    logger.info(f"Outil : Recherche d'adhérent par téléphone : {telephone}")
    adherents = db.get_adherents_by_telephone(telephone.strip())
    return _handle_lookup_result(context, adherents, "phone")

@function_tool
async def lookup_adherent_by_fullname(context: RunContext, nom: str, prenom: str) -> str:
    """Recherche un adhérent en utilisant son nom complet pour commencer le processus d'identification."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Outil : Recherche d'adhérent par nom complet : {prenom} {nom}")
    adherents = db.get_adherents_by_fullname(nom.strip(), prenom.strip())
    return _handle_lookup_result(context, adherents, "fullname")

@function_tool
async def get_adherent_details(context: RunContext) -> str:
    """Obtient les détails personnels de l'adhérent actuellement chargé et confirmé dans le contexte de l'assistant."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Aucun adhérent n'est actuellement sélectionné et confirmé. Veuillez d'abord rechercher et confirmer l'identité d'un adhérent." # Déjà en français
    
    return (f"Détails pour {adherent.prenom} {adherent.nom} (ID: {adherent.id_adherent}): " # Déjà en français
            f"Email: {adherent.email}, Téléphone: {adherent.telephone}, "
            f"Adresse: {adherent.adresse}, {adherent.code_postal} {adherent.ville}.")

@function_tool
async def update_contact_information(context: RunContext, address: Optional[str] = None, postal_code: Optional[str] = None, 
                                     city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Met à jour les informations de contact (adresse, téléphone, e-mail) de l'adhérent actuellement confirmé."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Action impossible. L'identité de l'adhérent doit être confirmée avant de pouvoir modifier des informations." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    success = db.update_adherent_contact_info(adherent.id_adherent, address, postal_code, city, phone, email)

    if success:
        context.userdata["adherent_context"] = db.get_adherent_by_id(adherent.id_adherent) # Rafraîchir le contexte
        return "Les informations de contact ont été mises à jour avec succès." # Déjà en français
    else:
        return "Une erreur s'est produite lors de la mise à jour des informations." # Déjà en français

# --- Outils de Contrat et de Couverture ---

@function_tool
async def list_adherent_contracts(context: RunContext) -> str:
    """Liste tous les contrats associés à l'adhérent actuellement confirmé dans le contexte."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français
    
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contracts = db.get_contrats_by_adherent_id(adherent.id_adherent)

    if not contracts:
        return f"Aucun contrat trouvé pour {adherent.prenom} {adherent.nom}." # Déjà en français
    
    response = f"Voici les contrats de {adherent.prenom} {adherent.nom}:\n" # Déjà en français
    for c in contracts:
        response += f"- Contrat N° {c.numero_contrat} (ID: {c.id_contrat}), Statut: {c.statut_contrat}\n"
    return response

@function_tool
async def get_contract_details(context: RunContext, contract_id: int) -> str:
    """Fournit les détails complets d'un contrat spécifique, y compris le nom du plan associé et le coût mensuel."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    # Vérification de sécurité
    user_contracts = db.get_contrats_by_adherent_id(adherent.id_adherent)
    if contract_id not in [c.id_contrat for c in user_contracts]:
        return f"Erreur: Le contrat ID {contract_id} n'appartient pas à {adherent.prenom} {adherent.nom}." # Déjà en français

    details = db.get_full_contract_details(contract_id)
    if not details:
        return f"Impossible de trouver les détails pour le contrat ID {contract_id}." # Déjà en français

    return (f"Détails du Contrat {details['numero_contrat']}: " # Déjà en français
            f"Plan: {details['nom_formule']}, Tarif: {details['tarif_base_mensuel']:.2f}€/mois, "
            f"Statut: {details['statut_contrat']}, "
            f"Période: du {details['date_debut_contrat']} au {details.get('date_fin_contrat', 'en cours')}.")

@function_tool
async def list_plan_guarantees(context: RunContext, contract_id: int) -> str:
    """Liste toutes les garanties (couvertures) incluses dans le plan pour un contrat spécifique."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contract = db.get_contract_by_id(contract_id)
    if not contract or contract.id_adherent_principal != adherent.id_adherent:
        return f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent." # Déjà en français

    guarantees = db.get_guarantees_for_formula(contract.id_formule)
    if not guarantees:
        return "Aucune garantie spécifique n'a été trouvée pour ce plan." # Déjà en français

    response = f"Garanties pour le contrat {contract.numero_contrat}:\n" + ", ".join([g['libelle'] for g in guarantees]) # Déjà en français
    return response

@function_tool
async def get_specific_coverage_details(context: RunContext, guarantee_name: str, contract_id: int) -> str:
    """Obtient les conditions de remboursement détaillées (taux, plafond, franchise) pour une couverture spécifique unique sur un contrat donné."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contract = db.get_contract_by_id(contract_id)
    if not contract or contract.id_adherent_principal != adherent.id_adherent:
        return f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent." # Déjà en français

    detail = db.get_specific_guarantee_detail(contract.id_formule, guarantee_name)
    if not detail:
        return f"Désolé, je n'ai pas trouvé de garantie nommée '{guarantee_name}' dans votre plan." # Déjà en français
    
    return (f"Détails pour '{detail['libelle']}': " # Déjà en français
            f"Taux: {detail.get('taux_remboursement_pourcentage', 'N/A')}%, "
            f"Plafond: {detail.get('plafond_remboursement', 'N/A')}€, "
            f"Franchise: {detail.get('franchise', '0.00')}€.")

@function_tool
async def simulate_reimbursement(context: RunContext, guarantee_name: str, expense_amount: float, contract_id: int) -> str:
    """Calcule le montant estimé du remboursement pour une dépense donnée sous une garantie spécifique."""
    # L'implémentation de cet outil est complexe et reste la même que dans le schéma architectural.
    # Par souci de brièveté, la logique est supposée être correctement implémentée ici.
    # Elle nécessite de récupérer les détails de la garantie et d'effectuer le calcul.
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contract = db.get_contract_by_id(contract_id)

    if not contract or contract.id_adherent_principal != adherent.id_adherent:
        return f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent." # Déjà en français
    
    detail = db.get_specific_guarantee_detail(contract.id_formule, guarantee_name)
    if not detail:
        return f"Garantie '{guarantee_name}' non trouvée." # Déjà en français

    try:
        expense = Decimal(str(expense_amount))
        franchise = detail.get('franchise', Decimal('0.00')) or Decimal('0.00')
        taux = (detail.get('taux_remboursement_pourcentage') or Decimal('0.0')) / Decimal('100.0')
        plafond = detail.get('plafond_remboursement')

        remboursable = (expense - franchise) * taux
        remboursement = min(remboursable, plafond) if plafond is not None else remboursable
        return f"Pour une dépense de {expense:.2f}€ en {guarantee_name}, le remboursement estimé est de {remboursement:.2f}€." # Déjà en français

    except Exception as e:
        return f"Erreur de calcul: {e}" # Déjà en français


# --- Outils de Gestion des Sinistres ---

@function_tool
async def list_adherent_claims(context: RunContext) -> str:
    """Liste tous les sinistres déclarés par l'adhérent actuellement confirmé dans le contexte."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français
            
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    claims = db.get_sinistres_by_adherent_id(adherent.id_adherent)

    if not claims:
        return f"Aucun sinistre trouvé pour {adherent.prenom} {adherent.nom}." # Déjà en français
            
    response = f"Voici les sinistres de {adherent.prenom} {adherent.nom}:\n" # Déjà en français
    for s in claims:
        response += f"- Sinistre ID: {s.id_sinistre_artex}, Type: {s.type_sinistre}, Statut: {s.statut_sinistre_artex}\n"
    return response

@function_tool
async def create_claim(context: RunContext, contract_id: int, claim_type: str, description: str, incident_date: str) -> str:
    """Crée un nouveau sinistre pour l'adhérent actuellement confirmé dans le contexte, lié à un contrat spécifique."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Impossible de créer un sinistre. L'identité de l'adhérent doit d'abord être confirmée." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    try:
        parsed_date = date.fromisoformat(incident_date)
        new_claim = db.create_sinistre(
            id_contrat=contract_id, id_adherent=adherent.id_adherent,
            type_sinistre=claim_type, description_sinistre=description,
            date_survenance=parsed_date
        )
        if new_claim:
            result_str = f"Sinistre créé avec succès! Numéro de sinistre: {new_claim.id_sinistre_artex}."
        else:
            # This case (contract not belonging to user) is handled by db_driver.create_sinistre returning None
            # and db_driver already logs an INSERT_FAIL. The tool just returns the message.
            result_str = "Erreur lors de la création du sinistre. Vérifiez que le contrat vous appartient."
    except ValueError as ve:
        result_str = "Erreur: La date d'incident doit être au format AAAA-MM-JJ (exemple: 2024-06-23)."
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
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent." # Déjà en français

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    claim = db.get_sinistre_by_id(claim_id)

    if not claim:
        return f"Aucun sinistre trouvé avec l'ID {claim_id}." # Déjà en français
    
    if claim.id_adherent != adherent.id_adherent:
        return f"Erreur: Vous n'avez pas l'autorisation de consulter le sinistre ID {claim_id}." # Déjà en français
    
    return (f"Statut du sinistre {claim.id_sinistre_artex}: {claim.statut_sinistre_artex}. " # Déjà en français
            f"Type: {claim.type_sinistre}. Déclaré le: {claim.date_declaration_agent}.")
