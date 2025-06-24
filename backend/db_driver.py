# db_driver.py

import mysql.connector
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, fields
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Dataclasses matching your DB Schema ---

@dataclass
class Adherent:
    id_adherent: int
    nom: str
    prenom: str
    date_adhesion_mutuelle: date
    date_naissance: Optional[date] = None
    adresse: Optional[str] = None
    code_postal: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    numero_securite_sociale: Optional[str] = None

@dataclass
class Formule:
    id_formule: int
    nom_formule: str
    tarif_base_mensuel: Decimal
    description_formule: Optional[str] = None

@dataclass
class Contrat:
    id_contrat: int
    id_adherent_principal: int
    numero_contrat: str
    date_debut_contrat: date
    id_formule: int
    date_fin_contrat: Optional[date] = None
    type_contrat: Optional[str] = None
    statut_contrat: str = 'Actif'

@dataclass
class Garantie:
    id_garantie: int
    libelle: str
    description: Optional[str] = None

@dataclass
class FormuleGarantie:
    id_formule: int
    id_garantie: int
    plafond_remboursement: Optional[Decimal] = None
    taux_remboursement_pourcentage: Optional[Decimal] = None
    franchise: Optional[Decimal] = Decimal('0.00')
    conditions_specifiques: Optional[str] = None

@dataclass
class SinistreArtex:
    id_sinistre_artex: int
    id_contrat: int
    id_adherent: int
    type_sinistre: str
    date_declaration_agent: date
    statut_sinistre_artex: str
    description_sinistre: Optional[str] = None
    date_survenance: Optional[date] = None


# --- Database Driver for all 'extranet' tables ---

class ExtranetDatabaseDriver:
    """
    Handles all database connections and operations for the extranet system.
    This class acts as a centralized data access layer, encapsulating all SQL queries.
    """
    def __init__(self):
        """
        Initializes the driver by loading credentials from environment variables.
        """
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")

        if not all([db_host, db_user, db_password, db_name]):
            raise ValueError("One or more database environment variables are not set.")

        self.connection_params = {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': db_name
        }
        logger.info("Database driver initialized with connection parameters.")

    @contextmanager
    def _get_connection(self):
        """Provides a managed connection to the MySQL database."""
        conn = None
        try:
            conn = mysql.connector.connect(**self.connection_params)
            yield conn
        except mysql.connector.Error as err:
            logger.error(f"Database connection error: {err}")
            raise # Re-raise the exception after logging
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _map_row(self, row: tuple, cursor, dataclass_type):
        """Helper to map a single database row to a dataclass instance."""
        if not row:
            return None
        
        column_names = [desc[0] for desc in cursor.description]
        row_dict = dict(zip(column_names, row))
        
        # Filter the dictionary to only include keys that are fields in the dataclass
        dataclass_fields = {f.name for f in fields(dataclass_type)}
        filtered_dict = {k: v for k, v in row_dict.items() if k in dataclass_fields}
        
        return dataclass_type(**filtered_dict)

    def _map_rows(self, rows: List[tuple], cursor, dataclass_type):
        """Helper to map multiple database rows to a list of dataclass instances."""
        if not rows:
            return []
        return [self._map_row(row, cursor, dataclass_type) for row in rows]

    # --- Adherent Methods ---

    def get_adherent_by_id(self, adherent_id: int) -> Optional[Adherent]:
        """Retrieves a single adherent by their unique ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE id_adherent = %s", (adherent_id,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)

    def get_adherent_by_email(self, email: str) -> Optional[Adherent]:
        """Retrieves a single adherent by their email address."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE email = %s", (email,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)

    def get_adherents_by_telephone(self, telephone: str) -> List[Adherent]:
        """Retrieves a list of adherents by their telephone number."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Search for numbers that end with the provided telephone string to handle international formats
            cursor.execute("SELECT * FROM adherents WHERE telephone LIKE %s", (f"%{telephone}",))
            return self._map_rows(cursor.fetchall(), cursor, Adherent)

    def get_adherents_by_fullname(self, nom: str, prenom: str) -> List[Adherent]:
        """Retrieves a list of adherents by their full name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE nom = %s AND prenom = %s", (nom, prenom))
            return self._map_rows(cursor.fetchall(), cursor, Adherent)

    def update_adherent_contact_info(self, adherent_id: int, address: Optional[str] = None, 
                                     code_postal: Optional[str] = None, ville: Optional[str] = None, 
                                     telephone: Optional[str] = None, email: Optional[str] = None) -> bool:
        """Updates contact information for a given adherent."""
        fields_to_update = {
            "adresse": address, "code_postal": code_postal, "ville": ville,
            "telephone": telephone, "email": email
        }
        updates = {k: v for k, v in fields_to_update.items() if v is not None}
        
        if not updates: return False

        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        query = f"UPDATE adherents SET {set_clause} WHERE id_adherent = %s"
        values = list(updates.values()) + [adherent_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, tuple(values))
                conn.commit()
                return cursor.rowcount > 0
            except mysql.connector.Error as err:
                logger.error(f"Failed to update contact info for adherent {adherent_id}: {err}")
                conn.rollback()
                return False

    # --- Contrat & Formule Methods ---

    def get_contrats_by_adherent_id(self, adherent_id: int) -> List[Contrat]:
        """Retrieves all contracts for a given adherent ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contrats WHERE id_adherent_principal = %s", (adherent_id,))
            return self._map_rows(cursor.fetchall(), cursor, Contrat)

    def get_contract_by_id(self, contract_id: int) -> Optional[Contrat]:
        """Retrieves a single contract by its unique ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contrats WHERE id_contrat = %s", (contract_id,))
            return self._map_row(cursor.fetchone(), cursor, Contrat)

    def get_full_contract_details(self, contract_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves combined contract and formula details for a given contract ID."""
        query = """
            SELECT c.*, f.nom_formule, f.tarif_base_mensuel, f.description_formule
            FROM contrats c JOIN formules f ON c.id_formule = f.id_formule
            WHERE c.id_contrat = %s
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (contract_id,))
            return cursor.fetchone()

    # --- Garantie (Coverage) Methods ---

    def get_guarantees_for_formula(self, formula_id: int) -> List[Dict[str, Any]]:
        """Retrieves all guarantees with their terms for a specific formula."""
        query = """
            SELECT g.libelle, g.description, fg.*
            FROM formules_garanties fg JOIN garanties g ON fg.id_garantie = g.id_garantie
            WHERE fg.id_formule = %s
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (formula_id,))
            return cursor.fetchall()

    def get_specific_guarantee_detail(self, formula_id: int, guarantee_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves the details for a single, specific guarantee within a formula."""
        query = """
            SELECT g.libelle, g.description, fg.*
            FROM formules_garanties fg JOIN garanties g ON fg.id_garantie = g.id_garantie
            WHERE fg.id_formule = %s AND g.libelle LIKE %s
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (formula_id, f"%{guarantee_name}%"))
            return cursor.fetchone()

    # --- Sinistre (Claim) Methods ---

    def get_sinistres_by_adherent_id(self, adherent_id: int) -> List[SinistreArtex]:
        """Retrieves all claims filed by a specific adherent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sinistres_artex WHERE id_adherent = %s", (adherent_id,))
            return self._map_rows(cursor.fetchall(), cursor, SinistreArtex)

    def get_sinistre_by_id(self, sinistre_id: int) -> Optional[SinistreArtex]:
        """Retrieves a single claim by its unique ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sinistres_artex WHERE id_sinistre_artex = %s", (sinistre_id,))
            return self._map_row(cursor.fetchone(), cursor, SinistreArtex)

    def create_sinistre(self, id_contrat: int, id_adherent: int, type_sinistre: str,
                        description_sinistre: str, date_survenance: date) -> Optional[SinistreArtex]:
        """Creates a new claim in the database after validating ownership."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id_adherent_principal FROM contrats WHERE id_contrat = %s", (id_contrat,))
                result = cursor.fetchone()
                if not result or result[0] != id_adherent:
                    logger.warning(f"Attempt to create claim for contract {id_contrat} by non-principal adherent {id_adherent}.")
                    return None

                query = """
                    INSERT INTO sinistres_artex (id_contrat, id_adherent, type_sinistre, date_declaration_agent, 
                                                 statut_sinistre_artex, description_sinistre, date_survenance)
                    VALUES (%s, %s, %s, CURDATE(), %s, %s, %s)
                """
                initial_status = "Soumis"
                values = (id_contrat, id_adherent, type_sinistre,
                          initial_status, description_sinistre, date_survenance)
                
                cursor.execute(query, values)
                new_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Successfully created claim with ID: {new_id}")
                return self.get_sinistre_by_id(new_id)

            except mysql.connector.Error as err:
                logger.error(f"Database error during claim creation: {err}")
                conn.rollback()
                return None

    def update_sinistre_status(self, sinistre_id: int, new_status: str, notes: Optional[str] = None) -> bool:
        """Updates the status of a claim and optionally appends notes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if notes:
                    query = """
                        UPDATE sinistres_artex 
                        SET statut_sinistre_artex = %s, 
                            description_sinistre = CONCAT(IFNULL(description_sinistre, ''), '\n--- NOTE ---', %s)
                        WHERE id_sinistre_artex = %s
                    """
                    cursor.execute(query, (new_status, notes, sinistre_id))
                else:
                    query = "UPDATE sinistres_artex SET statut_sinistre_artex = %s WHERE id_sinistre_artex = %s"
                    cursor.execute(query, (new_status, sinistre_id))
                
                conn.commit()
                return cursor.rowcount > 0
            except mysql.connector.Error as err:
                logger.error(f"Failed to update status for claim {sinistre_id}: {err}")
                conn.rollback()
                return False
