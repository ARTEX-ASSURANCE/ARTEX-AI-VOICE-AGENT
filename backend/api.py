# api.py

import logging
from livekit.agents import Agent
from livekit.plugins import google, silero
from db_driver import ExtranetDatabaseDriver
from prompts import INSTRUCTIONS
from tools import (
    get_adherent_details,
    list_adherent_contracts,
    list_adherent_claims,
    create_claim,
    lookup_adherent_by_email,
    lookup_adherent_by_telephone,
    lookup_adherent_by_fullname,
    confirm_identity,
    clear_context,
    update_contact_information,
    get_contract_details,
    list_plan_guarantees,
    get_specific_coverage_details,
    simulate_reimbursement,
    get_claim_status,
)

class ArtexAgent(Agent):
    # --- CHANGEMENT POUR RÉDUCTION DE LATENCE ---
    # La méthode __init__ est modifiée pour accepter un db_driver pré-initialisé.
    # Cela empêche l'agent de créer un nouveau pilote de base de données pour chaque tâche.
    def __init__(self, db_driver: ExtranetDatabaseDriver):
        """
        Initialise l'ArtexAgent avec tous ses composants et un pilote de base de données partagé.
        """
        super().__init__(
            instructions=INSTRUCTIONS,
            
            llm=google.LLM(model="gemini-1.5-flash"),
            
            tts=google.TTS(
                language="fr-FR",
                voice_name="fr-FR-Chirp3-HD-Charon" # Voix changée pour une latence potentiellement plus faible
            ),

            stt=google.STT(
                languages="fr-FR",
                interim_results=True
            ),
            
            vad=silero.VAD.load(),

            # La liste complète des outils disponibles pour l'agent.
            tools=[
                # Identité & Contexte
                lookup_adherent_by_email,
                lookup_adherent_by_telephone,
                lookup_adherent_by_fullname,
                confirm_identity,
                get_adherent_details,
                clear_context,
                # Libre-Service
                update_contact_information,
                # Contrat & Couverture
                list_adherent_contracts,
                get_contract_details,
                list_plan_guarantees,
                get_specific_coverage_details,
                simulate_reimbursement,
                # Sinistres
                list_adherent_claims,
                create_claim,
                get_claim_status,
            ],
        )
        # Stocker le pilote pré-initialisé qui a été passé.
        self.db_driver = db_driver
        logging.info("Schéma ArtexAgent configuré avec un pilote de BD partagé pour réduire la latence.")

    def get_initial_userdata(self) -> dict:
        """
        Crée un nouveau dictionnaire de données utilisateur pour chaque nouvelle session,
        fournissant aux outils un accès au pilote de base de données partagé
        et initialisant les variables de contexte spécifiques à la session.
        """
        return {
            "db_driver": self.db_driver,
            "adherent_context": None,      # Pour l'adhérent entièrement confirmé
            "unconfirmed_adherent": None,  # Pour les recherches temporaires en attente de confirmation
        }