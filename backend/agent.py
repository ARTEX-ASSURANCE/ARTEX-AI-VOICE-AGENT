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

# --- Standard Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent.main")

# --- Load Environment Variables ---
load_dotenv()

# --- Initialize heavy objects ONCE when the worker starts ---
# This is the optimized approach to reduce latency for each new call.
try:
    db_driver = ExtranetDatabaseDriver()
    artex_agent = ArtexAgent(db_driver=db_driver)
except Exception as e:
    logger.error(f"Failed to initialize agent components on startup: {e}")
    exit(1)


# --- Main Agent Entrypoint ---
async def entrypoint(ctx: JobContext):
    """
    Main entry point for the agent worker. This function is called for each new job.
    """
    logger.info(f"Received job: {ctx.job.id} for room: {ctx.room.name}")
    
    # --- FIX for TypeError ---
    # AgentSession is now initialized with no arguments.
    session = AgentSession()
    session.userdata = artex_agent.get_initial_userdata()

    # --- Automatic Caller ID Lookup ---
    initial_message = WELCOME_MESSAGE
    try:
        metadata_str = ctx.room.metadata
        if metadata_str:
            metadata = json.loads(metadata_str)
            caller_number = metadata.get('caller_number')
        else:
            caller_number = None

        if caller_number:
            logger.info(f"Found caller_number in metadata: {caller_number}")
            lookup_result = await lookup_adherent_by_telephone(session, telephone=caller_number)
            
            if "Bonjour, je m'adresse bien à" in lookup_result:
                initial_message = lookup_result
            else:
                 logger.warning(f"Phone number lookup for {caller_number} did not find a unique match.")
        else:
            logger.warning("No 'caller_number' in room metadata. Falling back to manual identification.")
    except json.JSONDecodeError:
        logger.error("Room metadata is not valid JSON. Falling back to manual identification.")
    except Exception as e:
        logger.error(f"An error occurred during initial lookup: {e}")

    # --- FIX for TypeError ---
    # The agent and the room context are now both passed to the start() method.
    await session.start(artex_agent, room=ctx.room)
    logger.info("Agent session started.")
    
    await asyncio.sleep(0.5)
    await session.say(initial_message, allow_interruptions=True)
    logger.info("Spoke initial message.")


# --- Standard CLI Runner ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
