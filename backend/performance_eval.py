import logging
from typing import Optional
from .db_driver import ExtranetDatabaseDriver # Assumes db_driver.py is in the same directory or accessible
# from .error_logger import log_system_error # If we want to log errors from evaluation itself

logger = logging.getLogger(__name__)

# This function will be called after a call ends.
# It needs access to the database to fetch call details and then update the call journal.
def evaluate_call_performance(id_appel: int):
    """
    Évalue la performance d'un appel terminé en se basant sur des heuristiques
    et met à jour l'enregistrement de l'appel dans journal_appels.
    """
    if id_appel is None: # Should not happen if called correctly
        logger.warning("evaluate_call_performance a été appelé avec id_appel=None.")
        return

    logger.info(f"Début de l'évaluation de la performance pour l'appel ID: {id_appel}")
    db = ExtranetDatabaseDriver() # Create a new instance or get from a shared context if available

    prompt_adherence_notes = []
    call_resolution_notes = []

    identity_confirmed_in_journal = False
    identity_confirmed_by_tool_action = False
    modification_tool_used_before_id = False
    identity_confirmation_action_found = False # To track if confirm_identity tool was even called

    key_action_tool_success = False
    critical_errors_in_call = 0

    try:
        with db._get_connection() as conn: # Using with statement for connection management
            cursor = conn.cursor(dictionary=True)

            # 1. Vérifier la confirmation d'identité depuis journal_appels (devrait être la source de vérité finale)
            cursor.execute("SELECT id_adherent_contexte FROM journal_appels WHERE id_appel = %s", (id_appel,))
            call_journal_entry = cursor.fetchone()
            if call_journal_entry and call_journal_entry['id_adherent_contexte']:
                identity_confirmed_in_journal = True
                # prompt_adherence_notes.append("Identité confirmée (contexte adhérent défini dans journal_appels).")
                logger.info(f"Appel {id_appel}: Identité confirmée via journal_appels.id_adherent_contexte.")


            # 2. Analyser les actions de l'agent pour des détails plus fins
            cursor.execute("""
                SELECT type_action, nom_outil, resultat_outil
                FROM actions_agent
                WHERE id_appel_fk = %s
                ORDER BY timestamp_action ASC
            """, (id_appel,))
            actions = cursor.fetchall()

            # Itérer sur les actions pour vérifier la séquence de confirmation d'identité et l'utilisation des outils
            # Cette logique peut devenir complexe pour tracer l'état 'identité confirmée' au fil du temps.
            # Pour une première version, on se base sur l'état final dans journal_appels et l'usage de confirm_identity.

            for action in actions:
                if action['type_action'] == 'TOOL_CALL' and action['nom_outil'] == 'confirm_identity':
                    identity_confirmation_action_found = True # L'outil a été appelé
                    # Vérifier si le résultat de l'outil indique un succès.
                    # C'est fragile et dépend du texte exact retourné par l'outil.
                    # Idéalement, les outils retourneraient un statut structuré.
                    if action['resultat_outil'] and "Merci ! Identité confirmée." in action['resultat_outil']:
                        identity_confirmed_by_tool_action = True
                        logger.info(f"Appel {id_appel}: Outil confirm_identity a réussi.")
                    break # On suppose qu'une seule tentative de confirmation réussie est pertinente

            if identity_confirmed_in_journal or identity_confirmed_by_tool_action:
                prompt_adherence_notes.append("Identité de l'adhérent confirmée pendant l'appel.")
            elif identity_confirmation_action_found: # Outil appelé mais n'a pas confirmé
                prompt_adherence_notes.append("Tentative de confirmation d'identité effectuée, mais sans succès apparent via l'outil.")
            else: # Aucun appel à confirm_identity et pas de contexte dans journal_appels
                prompt_adherence_notes.append("ALERTE: Aucune confirmation d'identité explicite trouvée pour l'appel.")

            # Vérifier l'utilisation d'outils de modification avant la confirmation d'identité (simplifié)
            # Cette heuristique est basique: si l'identité n'est PAS confirmée (état final), et qu'un outil de modif a été utilisé.
            if not (identity_confirmed_in_journal or identity_confirmed_by_tool_action):
                for action in actions:
                    modification_tools = ['update_contact_information', 'create_claim']
                    if action['type_action'] == 'TOOL_CALL' and action['nom_outil'] in modification_tools:
                        modification_tool_used_before_id = True
                        prompt_adherence_notes.append(f"ALERTE: Outil de modification '{action['nom_outil']}' utilisé sans confirmation d'identité préalable (basé sur l'état final).")
                        break

            # Évaluation de la résolution de l'appel
            for action in actions:
                if action['type_action'] == 'TOOL_RESULT': # Ou 'TOOL_CALL' si on ne logge pas séparément TOOL_RESULT
                    tool_name = action['nom_outil']
                    # Encore une fois, la vérification du succès basée sur le texte est fragile.
                    is_successful_tool_result = action['resultat_outil'] and \
                                                "erreur" not in (action['resultat_outil'] or "").lower() and \
                                                "échec" not in (action['resultat_outil'] or "").lower() and \
                                                "pas trouvé" not in (action['resultat_outil'] or "").lower()

                    key_action_tools = ['create_claim', 'update_contact_information']
                    if tool_name in key_action_tools and is_successful_tool_result:
                        key_action_tool_success = True
                        call_resolution_notes.append(f"Action clé '{tool_name}' complétée avec succès.")
                        break # Une action clé réussie est un bon indicateur.
                    elif tool_name in key_action_tools and not is_successful_tool_result:
                        call_resolution_notes.append(f"Échec de l'action clé '{tool_name}'.")


            # 3. Vérifier les erreurs critiques pendant l'appel
            cursor.execute("SELECT COUNT(*) as count FROM erreurs_systeme WHERE id_appel_fk = %s", (id_appel,))
            error_result = cursor.fetchone()
            if error_result:
                critical_errors_in_call = error_result['count']

            if critical_errors_in_call > 0:
                call_resolution_notes.append(f"{critical_errors_in_call} erreur(s) critique(s) enregistrée(s) pendant l'appel.")

        # Compiler les notes finales
        final_prompt_evaluation = " ".join(prompt_adherence_notes) if prompt_adherence_notes else "Aucune observation spécifique sur l'adhérence aux instructions."

        if key_action_tool_success:
            call_resolution_notes.insert(0, "Indicateur de résolution positive (action clé réussie).")
        elif not call_resolution_notes and critical_errors_in_call == 0:
            call_resolution_notes.append("Résolution de l'appel non déterminée (pas d'action clé majeure ni d'erreur critique).")
        elif not call_resolution_notes and critical_errors_in_call > 0:
             call_resolution_notes.append("Résolution de l'appel probablement négative en raison d'erreurs.")

        final_resolution_evaluation = " ".join(call_resolution_notes) if call_resolution_notes else "Pas d'indicateur clair de résolution."

        # 4. Mettre à jour journal_appels avec ces évaluations
        update_query = """
            UPDATE journal_appels
            SET evaluation_performance_prompt = %s, evaluation_resolution_appel = %s
            WHERE id_appel = %s
        """
        # Utiliser une nouvelle connexion/curseur pour la mise à jour pour s'assurer qu'elle est commise
        with db._get_connection() as update_conn:
            update_cursor = update_conn.cursor()
            update_cursor.execute(update_query, (final_prompt_evaluation, final_resolution_evaluation, id_appel))
            update_conn.commit()
            if update_cursor.rowcount > 0:
                logger.info(f"Évaluation de la performance enregistrée pour l'appel ID: {id_appel}")
            else:
                logger.warning(f"Aucune ligne mise à jour lors de l'enregistrement de l'évaluation pour l'appel ID: {id_appel}")

    except mysql.connector.Error as db_err:
        logger.error(f"Erreur BD lors de l'évaluation de la performance pour l'appel {id_appel}: {db_err}")
        # log_system_error("performance_eval.evaluate_call_performance", f"DB Error: {db_err}", db_err, id_appel_fk=id_appel)
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'évaluation de la performance pour l'appel {id_appel}: {e}", exc_info=True)
        # log_system_error("performance_eval.evaluate_call_performance", f"Unexpected Error: {e}", e, id_appel_fk=id_appel)

# Exemple d'appel (pourrait être dans agent.py)
# if __name__ == '__main__':
#     # Ceci est juste pour un test local si vous exécutez ce fichier directement
#     # Vous auriez besoin de configurer les params DB pour error_logger et db_driver
#     # et d'avoir des données de test dans votre base.
#     # from error_logger import set_db_connection_params
#     # test_db_params = { ... }
#     # set_db_connection_params(test_db_params) # Si error_logger est utilisé ici
#     evaluate_call_performance(1) # Remplacer 1 par un ID d'appel de test existant
