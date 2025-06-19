import mysql.connector
import os
from dotenv import load_dotenv
from typing import Optional, List
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

# Load environment variables from .env file
load_dotenv()

# --- Dataclasses matching your DB Schema ---

@dataclass
class Adherent:
    # ... (dataclass definition remains the same)
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
    # ... (dataclass definition remains the same)
    id_formule: int
    nom_formule: str
    tarif_base_mensuel: Decimal
    description_formule: Optional[str] = None

@dataclass
class Contrat:
    # ... (dataclass definition remains the same)
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
    # ... (dataclass definition remains the same)
    id_garantie: int
    libelle: str
    description: Optional[str] = None

@dataclass
class FormuleGarantie:
    # ... (dataclass definition remains the same)
    id_formule: int
    id_garantie: int
    plafond_remboursement: Optional[Decimal] = None
    taux_remboursement_pourcentage: Optional[Decimal] = None
    franchise: Optional[Decimal] = Decimal('0.00')
    conditions_specifiques: Optional[str] = None

@dataclass
class SinistreArtex:
    # ... (dataclass definition remains the same)
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

    @contextmanager
    def _get_connection(self):
        """Provides a managed connection to the MySQL database."""
        # ... (method remains the same)
        conn = mysql.connector.connect(**self.connection_params)
        try:
            yield conn
        finally:
            if conn and conn.is_connected():
                conn.close()

    # --- Data Mapping Helpers ---
    def _map_row(self, row: tuple, cursor, dataclass_type):
        # ... (method remains the same)
        if not row: return None
        cols = [desc[0] for desc in cursor.description]
        return dataclass_type(**dict(zip(cols, row)))

    def __init__(self, host: str, user: str, password: str, database: str):
        """Initializes the driver with MySQL connection details."""
        self.connection_params = {'host': host, 'user': user, 'password': password, 'database': database}

    @contextmanager
    def _get_connection(self):
        """Provides a managed connection to the MySQL database."""
        conn = mysql.connector.connect(**self.connection_params)
        try:
            yield conn
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _map_row(self, row: tuple, cursor, dataclass_type):
        if not row: return None
        cols = [desc[0] for desc in cursor.description]
        return dataclass_type(**dict(zip(cols, row)))

    # --- Adherent Operations ---
    def get_adherent_by_id(self, adherent_id: int) -> Optional[Adherent]:
        # ... (inchangé)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE id_adherent = %s", (adherent_id,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)

        # NOUVELLE MÉTHODE AJOUTÉE
    def get_adherent_by_contract_id(self, contract_id: int) -> Optional[Adherent]:
        """
        Récupère l'adhérent principal associé à un ID de contrat en utilisant une jointure.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT a.*
                FROM adherents a
                JOIN contrats c ON a.id_adherent = c.id_adherent_principal
                WHERE c.id_contrat = %s
            """
            cursor.execute(query, (contract_id,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)
        
    def get_adherent_by_email(self, email: str) -> Optional[Adherent]:
        # ... (inchangé)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE email = %s", (email,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)

    # NOUVELLE MÉTHODE
    def get_adherents_by_telephone(self, telephone: str) -> List[Adherent]:
        """
        Récupère une liste d'adhérents par leur numéro de téléphone.
        Retourne une liste car le numéro peut ne pas être unique.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE telephone = %s", (telephone,))
            rows = cursor.fetchall()
            if not rows: return []
            return [self._map_row(row, cursor, Adherent) for row in rows]
    # NOUVELLE MÉTHODE
    def get_adherent_by_fullname(self, nom: str, prenom: str) -> List[Adherent]:
        """Récupère une liste d'adhérents par leur nom et prénom."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE nom = %s AND prenom = %s", (nom, prenom))
            rows = cursor.fetchall()
            if not rows: return []
            return [self._map_row(row, cursor, Adherent) for row in rows]

    # --- All database operation methods (get_adherent_by_id, etc.) remain the same ---
    # ... (all previously defined methods are unchanged)
    def get_adherent_by_id(self, adherent_id: int) -> Optional[Adherent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM adherents WHERE id_adherent = %s", (adherent_id,))
            return self._map_row(cursor.fetchone(), cursor, Adherent)
            
    def get_contrats_by_adherent_id(self, adherent_id: int) -> List[Contrat]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contrats WHERE id_adherent_principal = %s", (adherent_id,))
            rows = cursor.fetchall()
            if not rows: return []
            return [self._map_row(row, cursor, Contrat) for row in rows]
            
    def get_sinistres_by_adherent_id(self, adherent_id: int) -> List[SinistreArtex]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sinistres_artex WHERE id_adherent = %s", (adherent_id,))
            rows = cursor.fetchall()
            if not rows: return []
            return [self._map_row(row, cursor, SinistreArtex) for row in rows]
            
# --- Example of how to use the updated driver ---

if __name__ == '__main__':
    try:
        # Now, you create the driver instance without passing any arguments.
        db_driver = ExtranetDatabaseDriver()
        print("Successfully connected to the database using credentials from .env file.")

        # You can now use the driver to fetch data.
        print("\nFetching adherent with ID 1...")
        adherent = db_driver.get_adherent_by_id(1)
        if adherent:
            print(f"Found: {adherent.prenom} {adherent.nom}")
            
            print(f"\nFetching contracts for {adherent.prenom} {adherent.nom}...")
            contracts = db_driver.get_contrats_by_adherent_id(adherent.id_adherent)
            for contract in contracts:
                print(f"  - Contract ID: {contract.id_contrat}, Status: {contract.statut_contrat}")

            print(f"\nFetching claims for {adherent.prenom} {adherent.nom}...")
            claims = db_driver.get_sinistres_by_adherent_id(adherent.id_adherent)
            for claim in claims:
                print(f"  - Claim ID: {claim.id_sinistre_artex}, Type: {claim.type_sinistre}")

    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Please ensure your .env file is correctly set up with DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME.")
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")