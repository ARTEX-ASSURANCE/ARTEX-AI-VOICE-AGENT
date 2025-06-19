from __future__ import annotations
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
from api import ExtranetAssistant
from prompts import WELCOME_MESSAGE, INSTRUCTIONS, LOOKUP_ADHERENT_MESSAGE
import os
import logging

# --- Configuration du logger ---
# Configure le logging pour afficher les messages dans la console.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main_app") 

load_dotenv()

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    
    # Création de l'assistant
    assistant_fnc = ExtranetAssistant()
    model = openai.realtime.RealtimeModel(
        instructions=INSTRUCTIONS,
        voice="shimmer",
        temperature=0.8,
        modalities=["audio", "text"]
    )
    assistant = MultimodalAgent(model=model, fnc_ctx=assistant_fnc)
    
    # Attendre qu'un participant (le client) se connecte
    participant = await ctx.wait_for_participant()
    
    # Démarrer l'agent pour ce participant
    assistant.start(ctx.room)
    session = model.sessions[0]
    initial_message = WELCOME_MESSAGE
    
        # --- NOUVELLE LOGIQUE D'IDENTIFICATION AUTOMATIQUE ---
    try:
        # L'identité du participant est souvent le numéro de téléphone de l'appelant
        caller_phone_number = participant.identity
        logger.info("Détection du numéro de l'appelant : %s", caller_phone_number)
        
        # On tente de trouver l'adhérent avec ce numéro
        assistant_fnc.lookup_adherent_by_telephone(caller_phone_number)

        # Si l'adhérent est trouvé, on prépare un message d'accueil personnalisé
        if assistant_fnc.has_adherent_in_context():
            adherent = assistant_fnc._adherent_context
            initial_message = (f"Bonjour, vous êtes en communication avec ARIA, votre assistante chez ARTEX ASSURANCES. "
                               f"J'ai identifié un dossier au nom de {adherent.prenom} {adherent.nom} associé à ce numéro. "
                               "Est-ce bien vous ?")
        else:
            logger.info("Aucun adhérent trouvé pour le numéro %s.", caller_phone_number)
            # Si non trouvé, on utilise le message d'accueil standard

    except Exception as e:
        logger.error("Erreur lors de l'identification automatique : %s", e)
        # En cas d'erreur, on continue avec le message standard
    
    # Envoi du message d'accueil (standard ou personnalisé)
    session.conversation.item.create(
        llm.ChatMessage(
            role="assistant",
            content=initial_message
        )
    )
    session.response.create()
    
    @session.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
            
        # --- Updated Logic ---
        # Check for an adherent in context, not a car
        if assistant_fnc.has_adherent_in_context():
            handle_query(msg)
        else:
            find_adherent_profile(msg)
            
    def find_adherent_profile(msg: llm.ChatMessage):
        """Called when no adherent is in context to guide the LLM to find one."""
        session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                # Use the new LOOKUP_ADHERENT_MESSAGE
                content=LOOKUP_ADHERENT_MESSAGE(msg)
            )
        )
        session.response.create()
        
    def handle_query(msg: llm.ChatMessage):
        """Called when an adherent is in context to handle follow-up questions."""
        session.conversation.item.create(
            llm.ChatMessage(
                role="user",
                content=msg.content
            )
        )
        session.response.create()
    
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))