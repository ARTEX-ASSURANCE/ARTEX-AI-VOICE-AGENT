from __future__ import annotations
import json
import asyncio
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm
)
#from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
from api import ExtranetAssistant
from prompts import WELCOME_MESSAGE, INSTRUCTIONS, LOOKUP_ADHERENT_MESSAGE
import os
import logging

# --- Configuration du logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent")

load_dotenv()

# --- Entrypoint de l'agent ---
async def entrypoint(ctx: JobContext):
    """
    Point d'entrée principal pour le worker de l'agent.
    Cette fonction est appelée chaque fois qu'un nouveau job (par exemple, une nouvelle connexion à une room) est démarré.
    """
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    logger.info("Agent connecté à la room LiveKit.")
    
    room = ctx.room

    # --- Initialisation de l'assistant et du modèle ---
    assistant_fnc = ExtranetAssistant()
    model = openai.realtime.RealtimeModel(
        instructions=INSTRUCTIONS,
        voice="shimmer",
        temperature=0.8,
        modalities=["audio", "text"]
    )
    assistant = MultimodalAgent(model=model, fnc_ctx=assistant_fnc)
    
    logger.info("En attente d'un participant...")
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant '{participant.identity}' rejoint la room.")

    # Envoyer un événement KPI pour le début de l'appel
    kpi_payload = {
        "type": "kpi_update",
        "data": { "kpi": "call_started", "value": 1 }
    }
    await room.send_data(json.dumps(kpi_payload))

    # Démarrer l'agent pour ce participant
    assistant.start(room)
    session = model.sessions[0]
    initial_message = WELCOME_MESSAGE
    
    # --- Logique d'identification automatique de l'appelant ---
    try:
        caller_phone_number = participant.identity
        logger.info(f"Tentative d'identification avec l'identité : {caller_phone_number}")
        
        # On tente de trouver l'adhérent avec ce numéro
        # Note : La fonction `lookup_adherent_by_telephone` est une fonction "tool" pour le LLM.
        # Ici, nous l'appelons directement pour une vérification initiale.
        assistant_fnc.lookup_adherent_by_telephone(caller_phone_number)

        if assistant_fnc.has_adherent_in_context():
            adherent = assistant_fnc._adherent_context
            initial_message = (f"Bonjour, vous êtes en communication avec ARIA, votre assistante chez ARTEX ASSURANCES. "
                               f"J'ai identifié un dossier au nom de {adherent.prenom} {adherent.nom} associé à ce numéro. "
                               "Est-ce bien vous ?")
            logger.info(f"Adhérent trouvé : {adherent.prenom} {adherent.nom}. Message d'accueil personnalisé.")
        else:
            logger.info(f"Aucun adhérent trouvé pour l'identité {caller_phone_number}.")

    except Exception as e:
        logger.error(f"Erreur lors de l'identification automatique : {e}")
    
    # Envoi du message d'accueil (standard ou personnalisé) à la conversation LLM
    session.conversation.item.create(
        llm.ChatMessage(
            role="assistant",
            content=initial_message
        )
    )
    session.response.create()
    
    # --- Gestionnaires d'événements de la session ---
    
    @session.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        """
        Déclenché lorsque l'utilisateur a fini de parler et que la transcription est prête.
        """
        logger.info(f"Message de l'utilisateur reçu : {msg.content}")
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
            
        if assistant_fnc.has_adherent_in_context():
            handle_query(msg)
        else:
            find_adherent_profile(msg)
            
    def find_adherent_profile(msg: llm.ChatMessage):
        """
        Appelée lorsqu'aucun adhérent n'est dans le contexte.
        Guide le LLM pour qu'il pose des questions afin d'identifier l'utilisateur.
        """
        logger.info("Aucun adhérent en contexte. Guidage du LLM pour l'identification.")
        system_prompt = LOOKUP_ADHERENT_MESSAGE(msg)

        # Envoi des données de raisonnement au frontend
        reasoning_payload = {
            "type": "agent_reasoning",
            "data": {
                "prompt": system_prompt,
                "search_results": "L'agent demande des informations pour identifier l'adhérent."
            }
        }
        asyncio.create_task(room.send_data(json.dumps(reasoning_payload)))

        session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=system_prompt
            )
        )
        session.response.create()
        
    def handle_query(msg: llm.ChatMessage):
        """
        Appelée lorsqu'un adhérent est identifié.
        Traite les demandes de l'utilisateur.
        """
        logger.info(f"Adhérent en contexte. Traitement de la requête : {msg.content}")

        # Envoi des données de raisonnement au frontend
        # Dans ce cas, le "prompt" est simplement la retranscription de la requête de l'utilisateur.
        reasoning_payload = {
            "type": "agent_reasoning",
            "data": {
                "prompt": msg.content,
                "search_results": "L'agent traite la requête de l'utilisateur identifié."
            }
        }
        asyncio.create_task(room.send_data(json.dumps(reasoning_payload)))

        session.conversation.item.create(
            llm.ChatMessage(
                role="user",
                content=msg.content
            )
        )
        session.response.create()
    
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))