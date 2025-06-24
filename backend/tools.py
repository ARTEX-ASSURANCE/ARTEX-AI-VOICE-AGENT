# tools.py

import logging
from typing import List, Optional
from datetime import date
from decimal import Decimal
from livekit.agents import function_tool, RunContext
from db_driver import ExtranetDatabaseDriver, Adherent, Contrat, SinistreArtex

logger = logging.getLogger("artex_agent.tools")

# --- Context Management Helpers ---

def _handle_lookup_result(context: RunContext, result: Optional[Adherent] | List[Adherent], source: str) -> str:
    """
    Helper to handle the result of a member lookup. It does NOT confirm identity.
    It stores potential matches in a temporary context variable for confirmation.
    """
    if not result:
        context.userdata["unconfirmed_adherent"] = None
        return "Désolé, aucun adhérent correspondant n'a été trouvé avec ces informations."

    if isinstance(result, list):
        if len(result) > 1:
            response = "J'ai trouvé plusieurs adhérents correspondants. Pour vous identifier précisément, pouvez-vous me donner votre adresse e-mail ou votre numéro de contrat ?"
            return response
        if not result:
             context.userdata["unconfirmed_adherent"] = None
             return "Désolé, aucun adhérent correspondant n'a été trouvé."
        result = result[0]

    # Found a single potential match. Store it for confirmation.
    context.userdata["unconfirmed_adherent"] = result
    logger.info(f"Unconfirmed adherent found via {source}: {result.prenom} {result.nom} (ID: {result.id_adherent})")
    
    # If lookup was by phone (automatic), we move to direct confirmation.
    if source == "phone":
        return f"Bonjour, je m'adresse bien à {result.prenom} {result.nom} ?"
    
    # For manual lookups, we ask for the second factor.
    return (f"J'ai trouvé un dossier au nom de {result.prenom} {result.nom}. "
            "Pour sécuriser l'accès, pouvez-vous me confirmer votre date de naissance et votre code postal ?")


# --- Identity and Context Tools ---

@function_tool
async def confirm_identity(context: RunContext, date_of_birth: str, postal_code: str) -> str:
    """
    Confirms the user's identity using their date of birth AND postal code. 
    This tool MUST be called after a lookup tool has found a potential member.
    """
    unconfirmed: Optional[Adherent] = context.userdata.get("unconfirmed_adherent")
    if not unconfirmed:
        return "Veuillez d'abord rechercher un adhérent avant de confirmer une identité."
    
    try:
        dob = date.fromisoformat(date_of_birth)
    except (ValueError, TypeError):
        return "Format de date de naissance invalide. Veuillez utiliser le format AAAA-MM-JJ, par exemple 2001-05-28."

    if unconfirmed.date_naissance == dob and unconfirmed.code_postal == postal_code:
        context.userdata["adherent_context"] = unconfirmed
        context.userdata["unconfirmed_adherent"] = None
        logger.info(f"Identity confirmed for: {unconfirmed.prenom} {unconfirmed.nom} (ID: {unconfirmed.id_adherent})")
        return f"Merci ! Identité confirmée. Le dossier de {unconfirmed.prenom} {unconfirmed.nom} est maintenant ouvert. Comment puis-je vous aider ?"
    else:
        logger.warning(f"Identity confirmation failed for adherent ID: {unconfirmed.id_adherent}")
        return "Les informations ne correspondent pas. Pour votre sécurité, je ne peux pas accéder à ce dossier."

@function_tool
async def clear_context(context: RunContext) -> str:
    """
    Clears the currently selected member from the assistant's context. Use this if the wrong person was identified or to end the session.
    """
    context.userdata["adherent_context"] = None
    context.userdata["unconfirmed_adherent"] = None
    logger.info("Agent context has been cleared.")
    return "Le contexte a été réinitialisé. Comment puis-je vous aider ?"

# --- Adherent Lookup and Management Tools ---

@function_tool
async def lookup_adherent_by_email(context: RunContext, email: str) -> str:
    """Looks up a member using their email address to begin the identification process."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Tool: Looking up adherent by email: {email}")
    adherent = db.get_adherent_by_email(email.strip())
    return _handle_lookup_result(context, adherent, "email")

@function_tool
async def lookup_adherent_by_telephone(context: RunContext, telephone: str) -> str:
    """Searches for a member by their telephone number. Intended for automatic lookup at the start of a call."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Tool: Looking up adherent by telephone: {telephone}")
    adherents = db.get_adherents_by_telephone(telephone.strip())
    return _handle_lookup_result(context, adherents, "phone")

@function_tool
async def lookup_adherent_by_fullname(context: RunContext, nom: str, prenom: str) -> str:
    """Looks up a member using their full name to begin the identification process."""
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    logger.info(f"Tool: Looking up adherent by full name: {prenom} {nom}")
    adherents = db.get_adherents_by_fullname(nom.strip(), prenom.strip())
    return _handle_lookup_result(context, adherents, "fullname")

@function_tool
async def get_adherent_details(context: RunContext) -> str:
    """Gets the personal details of the member currently loaded and confirmed in the assistant's context."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Aucun adhérent n'est actuellement sélectionné et confirmé. Veuillez d'abord rechercher et confirmer l'identité d'un adhérent."
    
    return (f"Détails pour {adherent.prenom} {adherent.nom} (ID: {adherent.id_adherent}): "
            f"Email: {adherent.email}, Téléphone: {adherent.telephone}, "
            f"Adresse: {adherent.adresse}, {adherent.code_postal} {adherent.ville}.")

@function_tool
async def update_contact_information(context: RunContext, address: Optional[str] = None, postal_code: Optional[str] = None, 
                                     city: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Updates the contact information (address, phone, email) for the currently confirmed member."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Action impossible. L'identité de l'adhérent doit être confirmée avant de pouvoir modifier des informations."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    success = db.update_adherent_contact_info(adherent.id_adherent, address, postal_code, city, phone, email)

    if success:
        context.userdata["adherent_context"] = db.get_adherent_by_id(adherent.id_adherent) # Refresh context
        return "Les informations de contact ont été mises à jour avec succès."
    else:
        return "Une erreur s'est produite lors de la mise à jour des informations."

# --- Contract and Coverage Tools ---

@function_tool
async def list_adherent_contracts(context: RunContext) -> str:
    """Lists all contracts associated with the member currently confirmed in context."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."
    
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contracts = db.get_contrats_by_adherent_id(adherent.id_adherent)

    if not contracts:
        return f"Aucun contrat trouvé pour {adherent.prenom} {adherent.nom}."
    
    response = f"Voici les contrats de {adherent.prenom} {adherent.nom}:\n"
    for c in contracts:
        response += f"- Contrat N° {c.numero_contrat} (ID: {c.id_contrat}), Statut: {c.statut_contrat}\n"
    return response

@function_tool
async def get_contract_details(context: RunContext, contract_id: int) -> str:
    """Provides full details for a specific contract, including the associated plan name and monthly cost."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    # Security check
    user_contracts = db.get_contrats_by_adherent_id(adherent.id_adherent)
    if contract_id not in [c.id_contrat for c in user_contracts]:
        return f"Erreur: Le contrat ID {contract_id} n'appartient pas à {adherent.prenom} {adherent.nom}."

    details = db.get_full_contract_details(contract_id)
    if not details:
        return f"Impossible de trouver les détails pour le contrat ID {contract_id}."

    return (f"Détails du Contrat {details['numero_contrat']}: "
            f"Plan: {details['nom_formule']}, Tarif: {details['tarif_base_mensuel']:.2f}€/mois, "
            f"Statut: {details['statut_contrat']}, "
            f"Période: du {details['date_debut_contrat']} au {details.get('date_fin_contrat', 'en cours')}.")

@function_tool
async def list_plan_guarantees(context: RunContext, contract_id: int) -> str:
    """Lists all the guarantees (coverages) included in the plan for a specific contract."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contract = db.get_contract_by_id(contract_id)
    if not contract or contract.id_adherent_principal != adherent.id_adherent:
        return f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent."

    guarantees = db.get_guarantees_for_formula(contract.id_formule)
    if not guarantees:
        return "Aucune garantie spécifique n'a été trouvée pour ce plan."

    response = f"Garanties pour le contrat {contract.numero_contrat}:\n" + ", ".join([g['libelle'] for g in guarantees])
    return response

@function_tool
async def get_specific_coverage_details(context: RunContext, guarantee_name: str, contract_id: int) -> str:
    """Gets the detailed reimbursement terms (rate, ceiling, deductible) for a single specific coverage on a given contract."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contract = db.get_contract_by_id(contract_id)
    if not contract or contract.id_adherent_principal != adherent.id_adherent:
        return f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent."

    detail = db.get_specific_guarantee_detail(contract.id_formule, guarantee_name)
    if not detail:
        return f"Désolé, je n'ai pas trouvé de garantie nommée '{guarantee_name}' dans votre plan."
    
    return (f"Détails pour '{detail['libelle']}': "
            f"Taux: {detail.get('taux_remboursement_pourcentage', 'N/A')}%, "
            f"Plafond: {detail.get('plafond_remboursement', 'N/A')}€, "
            f"Franchise: {detail.get('franchise', '0.00')}€.")

@function_tool
async def simulate_reimbursement(context: RunContext, guarantee_name: str, expense_amount: float, contract_id: int) -> str:
    """Calculates the estimated reimbursement amount for a given expense under a specific guarantee."""
    # This tool's implementation is complex and remains the same as in the architectural blueprint.
    # For brevity, the logic is assumed to be correctly implemented here.
    # It requires fetching guarantee details and performing the calculation.
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    contract = db.get_contract_by_id(contract_id)

    if not contract or contract.id_adherent_principal != adherent.id_adherent:
        return f"Erreur: Le contrat ID {contract_id} est invalide ou n'appartient pas à l'adhérent."
    
    detail = db.get_specific_guarantee_detail(contract.id_formule, guarantee_name)
    if not detail:
        return f"Garantie '{guarantee_name}' non trouvée."

    try:
        expense = Decimal(str(expense_amount))
        franchise = detail.get('franchise', Decimal('0.00')) or Decimal('0.00')
        taux = (detail.get('taux_remboursement_pourcentage') or Decimal('0.0')) / Decimal('100.0')
        plafond = detail.get('plafond_remboursement')

        remboursable = (expense - franchise) * taux
        remboursement = min(remboursable, plafond) if plafond is not None else remboursable
        return f"Pour une dépense de {expense:.2f}€ en {guarantee_name}, le remboursement estimé est de {remboursement:.2f}€."

    except Exception as e:
        return f"Erreur de calcul: {e}"


# --- Claim (Sinistre) Management Tools ---

@function_tool
async def list_adherent_claims(context: RunContext) -> str:
    """Lists all claims (sinistres) filed by the member currently confirmed in context."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."
            
    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    claims = db.get_sinistres_by_adherent_id(adherent.id_adherent)

    if not claims:
        return f"Aucun sinistre trouvé pour {adherent.prenom} {adherent.nom}."
            
    response = f"Voici les sinistres de {adherent.prenom} {adherent.nom}:\n"
    for s in claims:
        response += f"- Sinistre ID: {s.id_sinistre_artex}, Type: {s.type_sinistre}, Statut: {s.statut_sinistre_artex}\n"
    return response

@function_tool
async def create_claim(context: RunContext, contract_id: int, claim_type: str, description: str, incident_date: str) -> str:
    """Creates a new claim (sinistre) for the member currently confirmed in context, linked to a specific contract."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Impossible de créer un sinistre. L'identité de l'adhérent doit d'abord être confirmée."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    try:
        parsed_date = date.fromisoformat(incident_date)
        new_claim = db.create_sinistre(
            id_contrat=contract_id, id_adherent=adherent.id_adherent,
            type_sinistre=claim_type, description_sinistre=description,
            date_survenance=parsed_date
        )
        if new_claim:
            return f"Sinistre créé avec succès! Numéro de sinistre: {new_claim.id_sinistre_artex}."
        else:
            return "Erreur lors de la création du sinistre. Vérifiez que le contrat vous appartient."
    except ValueError:
        return "Erreur: La date d'incident doit être au format AAAA-MM-JJ (exemple: 2024-06-23)."
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la création du sinistre: {e}")
        return "Une erreur inattendue s'est produite."

@function_tool
async def get_claim_status(context: RunContext, claim_id: int) -> str:
    """Gets the current status and details for a specific claim ID."""
    adherent: Optional[Adherent] = context.userdata.get("adherent_context")
    if not adherent:
        return "Veuillez d'abord confirmer l'identité d'un adhérent."

    db: ExtranetDatabaseDriver = context.userdata["db_driver"]
    claim = db.get_sinistre_by_id(claim_id)

    if not claim:
        return f"Aucun sinistre trouvé avec l'ID {claim_id}."
    
    if claim.id_adherent != adherent.id_adherent:
        return f"Erreur: Vous n'avez pas l'autorisation de consulter le sinistre ID {claim_id}."
    
    return (f"Statut du sinistre {claim.id_sinistre_artex}: {claim.statut_sinistre_artex}. "
            f"Type: {claim.type_sinistre}. Déclaré le: {claim.date_declaration_agent}.")
