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
    # --- LATENCY REDUCTION CHANGE ---
    # The __init__ method is modified to accept a pre-initialized db_driver.
    # This prevents the agent from creating a new database driver for every single job.
    def __init__(self, db_driver: ExtranetDatabaseDriver):
        """
        Initializes the ArtexAgent with all its components and a shared database driver.
        """
        super().__init__(
            instructions=INSTRUCTIONS,
            
            llm=google.LLM(model="gemini-1.5-flash"),
            
            tts=google.TTS(
                language="fr-FR",
                voice_name="fr-FR-Chirp3-HD-Charon" # Changed for a potentially lower latency voice
            ),

            stt=google.STT(
                languages="fr-FR",
                interim_results=True
            ),
            
            vad=silero.VAD.load(),

            # The complete list of available tools for the agent.
            tools=[
                # Identity & Context
                lookup_adherent_by_email,
                lookup_adherent_by_telephone,
                lookup_adherent_by_fullname,
                confirm_identity,
                get_adherent_details,
                clear_context,
                # Self-Service
                update_contact_information,
                # Contract & Coverage
                list_adherent_contracts,
                get_contract_details,
                list_plan_guarantees,
                get_specific_coverage_details,
                simulate_reimbursement,
                # Claims
                list_adherent_claims,
                create_claim,
                get_claim_status,
            ],
        )
        # Store the pre-initialized driver that was passed in.
        self.db_driver = db_driver
        logging.info("ArtexAgent blueprint configured with a shared DB driver to reduce latency.")

    def get_initial_userdata(self) -> dict:
        """
        Creates a fresh user data dictionary for each new session,
        providing the tools with access to the shared database driver
        and initializing session-specific context variables.
        """
        return {
            "db_driver": self.db_driver,
            "adherent_context": None,      # For the fully confirmed member
            "unconfirmed_adherent": None,  # For temporary lookups pending confirmation
        }