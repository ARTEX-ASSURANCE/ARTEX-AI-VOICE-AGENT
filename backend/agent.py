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
from .error_logger import log_system_error # Ajout de l'importation

# --- Configuration Standard du Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("artex_agent.main")

# --- Chargement des Variables d'Environnement ---
load_dotenv()

# --- Initialisation des objets lourds UNE SEULE FOIS au démarrage du worker ---
# Ceci est l'approche optimisée pour réduire la latence pour chaque nouvel appel.
try:
    db_driver = ExtranetDatabaseDriver() # db_driver est global pour ce module agent.py
    artex_agent = ArtexAgent(db_driver=db_driver)
except Exception as e:
    logger.error(f"Échec de l'initialisation des composants de l'agent au démarrage : {e}")
    # from .error_logger import log_system_error # Importer et utiliser si error_logger.py est prêt
    # log_system_error("agent.py_startup", f"Échec initialisation: {e}", e)
    exit(1)


# --- Point d'Entrée Principal de l'Agent ---
async def entrypoint(ctx: JobContext):
    """
    Point d'entrée principal pour le worker de l'agent. Cette fonction est appelée pour chaque nouvelle tâche.
    """
    logger.info(f"Tâche reçue : {ctx.job.id} pour la salle : {ctx.room.name}")
    current_call_journal_id = None
    caller_number = None

    try:
        # Extraire le numéro de l'appelant des métadonnées
        metadata_str = ctx.room.metadata
        if metadata_str:
            try:
                metadata = json.loads(metadata_str)
                caller_number = metadata.get('caller_number')
            except json.JSONDecodeError as je:
                logger.error("Les métadonnées de la salle ne sont pas un JSON valide.")
                log_system_error(
                    source_erreur="agent.py_entrypoint_metadata",
                    message_erreur="Les métadonnées de la salle ne sont pas un JSON valide.",
                    exception_obj=je,
                    contexte_supplementaire={"metadata_str": metadata_str[:500]}
                )

        # Enregistrer le début de l'appel dans la base de données
        # db_driver est maintenant défini globalement dans ce module lors de l'initialisation
        current_call_journal_id = db_driver.enregistrer_debut_appel(
            id_livekit_room=ctx.job.id,
            numero_appelant=caller_number
        )

        if not current_call_journal_id:
            logger.error(f"ÉCHEC CRITIQUE: Impossible d'enregistrer le début de l'appel pour la tâche {ctx.job.id}. Certaines fonctionnalités de journalisation seront désactivées.")
            # log_system_error("agent.py_entrypoint", f"Échec enregistrement début appel pour tâche {ctx.job.id}")
        else:
            logger.info(f"Début d'appel enregistré avec ID Journal: {current_call_journal_id} pour tâche {ctx.job.id}")

        # Initialiser la session de l'agent
        session = AgentSession()
        initial_userdata = artex_agent.get_initial_userdata()
        initial_userdata["current_call_journal_id"] = current_call_journal_id
        session.userdata = initial_userdata

        # --- Recherche Automatique de l'Identifiant de l'Appelant ---
        initial_message = WELCOME_MESSAGE

        if caller_number:
            logger.info(f"Numéro de l'appelant trouvé dans les métadonnées : {caller_number} pour l'appel ID Journal {current_call_journal_id}")
            lookup_result = await lookup_adherent_by_telephone(session, telephone=caller_number)
            
            if "Bonjour, je m'adresse bien à" in lookup_result:
                initial_message = lookup_result
                # La logique pour appeler db_driver.enregistrer_contexte_adherent_appel(current_call_journal_id, adherent.id_adherent)
                # sera typiquement dans l'outil `confirm_identity` après que l'utilisateur confirme verbalement,
                # ou si `lookup_adherent_by_telephone` est modifié pour confirmer automatiquement et retourner l'ID adhérent.
                # Pour l'instant, l'ID adhérent sera mis à jour dans journal_appels via l'outil `confirm_identity`.
            else:
                 logger.warning(f"La recherche du numéro de téléphone {caller_number} n'a pas trouvé de correspondance unique pour l'appel ID Journal {current_call_journal_id}.")
        else:
            logger.warning(f"Aucun 'caller_number' dans les métadonnées de la salle pour l'appel ID Journal {current_call_journal_id}. Retour à l'identification manuelle.")

        # Démarrer la session de l'agent
        await session.start(artex_agent, room=ctx.room)
        logger.info(f"Session de l'agent démarrée pour l'appel ID Journal {current_call_journal_id}.")

        await asyncio.sleep(0.5)
        if current_call_journal_id:
            db_driver.enregistrer_action_agent(
                id_appel_fk=current_call_journal_id,
                type_action='MESSAGE_SAID', # MESSAGE_DIT en français
                message_dit=initial_message
            )
        await session.say(initial_message, allow_interruptions=True)
        logger.info(f"Message initial énoncé pour l'appel ID Journal {current_call_journal_id}.")

    except Exception as e:
        logger.error(f"Erreur majeure dans l'agent pour la tâche {ctx.job.id} (ID Appel Journal: {current_call_journal_id}): {e}", exc_info=True)
        if current_call_journal_id:
            log_system_error(
                source_erreur="agent.py_entrypoint_main",
                message_erreur=f"Erreur principale de l'agent: {e}",
                exception_obj=e,
                id_appel_fk=current_call_journal_id
            )
        else: # Erreur avant même que current_call_journal_id soit défini ou si sa création a échoué
            log_system_error(
                source_erreur="agent.py_entrypoint_early_error",
                message_erreur=f"Erreur principale de l'agent (avant/pendant init journal appel): {e}",
                exception_obj=e,
                contexte_supplementaire={"job_id": ctx.job.id, "room_name": ctx.room.name}
            )
    finally:
        if current_call_journal_id:
            logger.info(f"Bloc finally pour l'appel ID Journal {current_call_journal_id}, tâche {ctx.job.id}.")
            resume_final_appel = session.userdata.get("call_summary_for_db", "Résumé non disponible.")

            fin_enregistree = db_driver.enregistrer_fin_appel(current_call_journal_id, resume_appel=resume_final_appel)
            if fin_enregistree:
                logger.info(f"Fin de l'appel {current_call_journal_id} enregistrée avec succès pour la tâche {ctx.job.id}.")
            else:
                logger.error(f"ÉCHEC de l'enregistrement de la fin de l'appel {current_call_journal_id} pour la tâche {ctx.job.id}.")
                # log_system_error("agent.py_finally", f"Échec enregistrement fin appel {current_call_journal_id}", id_appel_fk=current_call_journal_id)

            try:
                from .performance_eval import evaluate_call_performance # Importation ici pour éviter les problèmes d'import circulaire au niveau du module si perf_eval importe des choses de agent
                logger.info(f"Tentative d'évaluation de la performance pour l'appel ID {current_call_journal_id}.")
                # Exécuter l'évaluation dans un thread séparé pour ne pas bloquer le worker de l'agent si elle est longue
                # Pour l'instant, appel direct. Si evaluate_call_performance fait des I/O lourdes, envisager asyncio.to_thread (Python 3.9+)
                # ou un gestionnaire de tâches séparé.
                evaluate_call_performance(current_call_journal_id)
                logger.info(f"Évaluation de la performance potentiellement terminée (ou lancée) pour l'appel ID {current_call_journal_id}.")
            except ImportError:
                logger.warning("Module performance_eval non trouvé ou erreur d'importation. Évaluation de la performance sautée.")
                # log_system_error("agent.py_finally", "ImportError pour performance_eval", id_appel_fk=current_call_journal_id)
            except Exception as eval_err:
                logger.error(f"Erreur lors de l'appel à l'évaluation de la performance pour l'appel {current_call_journal_id}: {eval_err}", exc_info=True)
                log_system_error("agent.py_finally_eval_call", f"Erreur appel évaluation performance: {eval_err}", eval_err, id_appel_fk=current_call_journal_id)
        else:
            logger.warning(f"current_call_journal_id non défini dans finally pour la tâche {ctx.job.id}. Fin d'appel non enregistrée, évaluation non effectuée.")
        logger.info(f"Fin du traitement pour la tâche {ctx.job.id}.")


# --- Exécuteur CLI Standard ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
