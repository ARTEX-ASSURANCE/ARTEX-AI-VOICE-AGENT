# agent.py

from __future__ import annotations
import logging
import asyncio
import json
from dotenv import load_dotenv
from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    AgentSession,
)
from api import ArtexAgent
from db_driver import ExtranetDatabaseDriver
from prompts import WELCOME_MESSAGE
from tools import lookup_adherent_by_telephone

# --- Configuration Standard du Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent.main")

# --- Chargement des Variables d'Environnement ---
load_dotenv()

# --- Initialisation des objets lourds UNE SEULE FOIS au démarrage du worker ---
# Ceci est l'approche optimisée pour réduire la latence pour chaque nouvel appel.
try:
    db_driver = ExtranetDatabaseDriver()
    artex_agent = ArtexAgent(db_driver=db_driver)
except Exception as e:
    logger.error(f"Échec de l'initialisation des composants de l'agent au démarrage : {e}")
    exit(1)


# --- Point d'Entrée Principal de l'Agent ---
async def entrypoint(ctx: JobContext):
    """
    Point d'entrée principal pour le worker de l'agent. Cette fonction est appelée pour chaque nouvelle tâche.
    """
    logger.info(f"Tâche reçue : {ctx.job.id} pour la salle : {ctx.room.name}")
    
    # --- CORRECTIF pour TypeError ---
    # AgentSession est maintenant initialisé sans arguments.
    session = AgentSession()
    session.userdata = artex_agent.get_initial_userdata()

    # --- Recherche Automatique de l'Identifiant de l'Appelant ---
    initial_message = WELCOME_MESSAGE
    try:
        metadata_str = ctx.room.metadata
        if metadata_str:
            metadata = json.loads(metadata_str)
            caller_number = metadata.get('caller_number')
        else:
            caller_number = None

        if caller_number:
            logger.info(f"Numéro de l'appelant trouvé dans les métadonnées : {caller_number}")
            lookup_result = await lookup_adherent_by_telephone(session, telephone=caller_number)
            
            if "Bonjour, je m'adresse bien à" in lookup_result: # Note: This string is already in French from another file.
                initial_message = lookup_result
            else:
                 logger.warning(f"La recherche du numéro de téléphone {caller_number} n'a pas trouvé de correspondance unique.")
        else:
            logger.warning("Aucun 'caller_number' dans les métadonnées de la salle. Retour à l'identification manuelle.")
    except json.JSONDecodeError:
        logger.error("Les métadonnées de la salle ne sont pas un JSON valide. Retour à l'identification manuelle.")
    except Exception as e:
        logger.error(f"Une erreur s'est produite lors de la recherche initiale : {e}")

    # --- CORRECTIF pour TypeError ---
    # L'agent et le contexte de la salle sont maintenant tous deux passés à la méthode start().
    await session.start(artex_agent, room=ctx.room)
    logger.info("Session de l'agent démarrée.")
    
    await asyncio.sleep(0.5)
    await session.say(initial_message, allow_interruptions=True)
    logger.info("Message initial énoncé.")


# --- Exécuteur CLI Standard ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
