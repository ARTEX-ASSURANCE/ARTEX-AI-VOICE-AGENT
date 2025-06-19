from livekit.agents import llm
import enum
from typing import Annotated, List, Optional
import logging
from datetime import date

# Assumes the driver script is named 'extranet_driver.py'
from db_driver import ExtranetDatabaseDriver, Adherent, Contrat, SinistreArtex

# --- Setup ---
logger = logging.getLogger("extranet-assistant")
logger.setLevel(logging.INFO)

# The driver now loads credentials automatically from your .env file
DB = ExtranetDatabaseDriver()

# --- Context Definitions ---

class AdherentDetails(enum.Enum):
    """Defines the details of an Adherent to be held in the assistant's context."""
    ID = "id_adherent"
    Nom = "nom"
    Prenom = "prenom"
    Email = "email"
    Telephone = "telephone"
    Ville = "ville"


class ExtranetAssistant(llm.FunctionContext):
    def __init__(self):
        super().__init__()
        # The assistant's context is now centered around an Adherent
        self._adherent_context: Optional[Adherent] = None

    def get_adherent_str(self) -> str:
        """Formats the current adherent's details into a readable string."""
        if not self._adherent_context:
            return "No adherent is currently in context."
        
        details = self._adherent_context
        return (f"ID: {details.id_adherent}\n"
                f"Name: {details.prenom} {details.nom}\n"
                f"Email: {details.email}\n"
                f"Telephone: {details.telephone}\n"
                f"City: {details.ville}")

    # --- AI-Callable Functions ---

    def has_adherent_in_context(self):
        """Checks if an adherent is loaded in the context."""
        return self._adherent_context is not None
    
    def __init__(self):
        super().__init__()
        self._adherent_context: Optional[Adherent] = None
        # The driver now loads credentials automatically from your .env file
        self.db_driver = ExtranetDatabaseDriver()

    def _handle_lookup_result(self, result: Optional[Adherent] | List[Adherent]) -> str:
        """Factorise la logique de gestion du résultat d'une recherche."""
        if not result:
            self._adherent_context = None
            return "Désolé, aucun adhérent correspondant n'a été trouvé avec ces informations."

        if isinstance(result, list):
            if len(result) > 1:
                return "J'ai trouvé plusieurs adhérents avec ce nom. Pouvez-vous préciser avec un numéro de sécurité sociale ou une adresse e-mail pour que je puisse identifier le bon dossier ?"
            result = result[0]

        self._adherent_context = result
        return f"J'ai bien trouvé le dossier de {result.prenom} {result.nom}. Que puis-je faire pour vous ?"
        
    @llm.ai_callable(description="Gets the details of the member currently loaded in the assistant's context.")
    def get_adherent_details(self):
        logger.info("Getting current adherent details")
        return self.get_adherent_str()

    @llm.ai_callable(description="Lists all contracts associated with the member currently in context.")
    def list_adherent_contracts(self) -> str:
        if not self._adherent_context:
            return "Please look up an adherent first before asking for their contracts."
        
        logger.info("Listing contracts for adherent ID: %s", self._adherent_context.id_adherent)
        contracts: List[Contrat] = DB.get_contrats_by_adherent_id(self._adherent_context.id_adherent)

        if not contracts:
            return f"No contracts found for {self._adherent_context.prenom} {self._adherent_context.nom}."
        
        response = f"Here are the contracts for {self._adherent_context.prenom} {self._adherent_context.nom}:\n"
        for c in contracts:
            response += (f"  - Contract ID: {c.id_contrat}, "
                         f"Number: {c.numero_contrat}, "
                         f"Status: {c.statut_contrat}, "
                         f"Type: {c.type_contrat}\n")
        return response

    @llm.ai_callable(description="Lists all claims (sinistres) filed by the member currently in context.")
    def list_adherent_claims(self) -> str:
        if not self._adherent_context:
            return "Please look up an adherent first before asking for their claims."
            
        logger.info("Listing claims for adherent ID: %s", self._adherent_context.id_adherent)
        claims: List[SinistreArtex] = DB.get_sinistres_by_adherent_id(self._adherent_context.id_adherent)

        if not claims:
            return f"No claims found for {self._adherent_context.prenom} {self._adherent_context.nom}."
            
        response = f"Here are the claims for {self._adherent_context.prenom} {self._adherent_context.nom}:\n"
        for s in claims:
            response += (f"  - Claim ID: {s.id_sinistre_artex}, "
                         f"Type: {s.type_sinistre}, "
                         f"Status: {s.statut_sinistre_artex}, "
                         f"Date: {s.date_survenance}\n")
        return response
        
    @llm.ai_callable(description="Creates a new claim (sinistre) for the member currently in context.")
    def create_claim(
        self,
        contract_id: Annotated[int, llm.TypeInfo(description="The ID of the contract under which the claim is being made.")],
        claim_type: Annotated[str, llm.TypeInfo(description="The type of claim (e.g., 'Dégât des eaux', 'Vol', 'Incendie').")],
        description: Annotated[str, llm.TypeInfo(description="A detailed description of the incident.")],
        incident_date: Annotated[str, llm.TypeInfo(description="The date the incident occurred, in YYYY-MM-DD format.")]
    ) -> str:
        if not self._adherent_context:
            return "Cannot create a claim. Please look up an adherent first."

        logger.info("Creating a new claim for adherent ID %s under contract ID %s", self._adherent_context.id_adherent, contract_id)

        try:
            parsed_date = date.fromisoformat(incident_date)
            new_claim = DB.create_sinistre(
                id_contrat=contract_id,
                id_adherent=self._adherent_context.id_adherent,
                type_sinistre=claim_type,
                description_sinistre=description,
                date_survenance=parsed_date
            )
            return f"Successfully created new claim with ID: {new_claim.id_sinistre_artex}."
        except ValueError:
            return "Error: The incident_date must be in YYYY-MM-DD format."
        except Exception as e:
            logger.error("Failed to create claim: %s", e)
            return f"An error occurred while creating the claim: {e}"

    
    @llm.ai_callable(description="Consulte les informations d'un adhérent grâce à son adresse e-mail.")
    def lookup_adherent_by_email(self, email: Annotated[str, llm.TypeInfo(description="L'adresse e-mail de l'adhérent.")]):
        logger.info("Recherche de l'adhérent par e-mail : %s", email)
        adherent = self.db_driver.get_adherent_by_email(email)
        return self._handle_lookup_result(adherent)

    # NOUVELLE FONCTION
    @llm.ai_callable(description="Recherche un ou plusieurs adhérents par leur numéro de téléphone.")
    def lookup_adherent_by_telephone(self, telephone: Annotated[str, llm.TypeInfo(description="Le numéro de téléphone de l'adhérent.")]):
        logger.info("Recherche de l'adhérent par numéro de téléphone : %s", telephone)
        adherents = self.db_driver.get_adherents_by_telephone(telephone)
        return self._handle_lookup_result(adherents)
    
    # NOUVELLE FONCTION
    @llm.ai_callable(description="Consulte les informations d'un adhérent grâce à son nom complet.")
    def lookup_adherent_by_fullname(self, nom: Annotated[str, llm.TypeInfo(description="Le nom de famille de l'adhérent.")], prenom: Annotated[str, llm.TypeInfo(description="Le prénom de l'adhérent.")]):
        logger.info("Recherche de l'adhérent par nom complet : %s %s", prenom, nom)
        adherents = self.db_driver.get_adherent_by_fullname(nom, prenom)
        return self._handle_lookup_result(adherents)