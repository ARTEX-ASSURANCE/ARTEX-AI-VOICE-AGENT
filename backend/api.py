from livekit.agents.llm import ToolContext, find_function_tools
from livekit.agents import llm
import enum
from typing import Annotated, List, Optional
import logging
from datetime import date

# Database driver import
from db_driver import ExtranetDatabaseDriver, Adherent, Contrat, SinistreArtex
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants
import os

load_dotenv()

# --- Load LiveKit Configuration from .env file ---
LIVEKIT_HOST = os.getenv("LIVEKIT_HOST")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# --- Setup ---
logger = logging.getLogger("extranet-assistant")
logger.setLevel(logging.INFO)

# Create console handler if not exists to ensure logging works
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

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


class ExtranetAssistant(ToolContext):
    """
    ARTEX Insurance Assistant for handling member inquiries, claims, and contracts.
    Provides voice-based interaction through LiveKit agents.
    """
    
    def __init__(self):
        # Initialize context before discovering tools
        self._adherent_context: Optional[Adherent] = None
        self.db_driver = ExtranetDatabaseDriver()
        
        # Discover tools using find_function_tools
        tools = find_function_tools(self)
        
        # Enhanced debug output for troubleshooting
        print("--- DEBUG: Discovered tools by find_function_tools ---")
        if not tools:
            print("  No tools found.")
        else:
            for i, tool_info in enumerate(tools):
                try:
                    # Safely extract tool information
                    tool_name = getattr(tool_info, 'name', 'Unknown')
                    tool_desc = getattr(tool_info, 'description', 'No description')
                    tool_fn = getattr(tool_info, 'fn', None)
                    tool_fn_name = getattr(tool_fn, '__name__', 'Unknown') if tool_fn else 'No function'
                    
                    print(f"  Tool {i+1}: Name='{tool_name}', Description='{tool_desc}', Method='{tool_fn_name}'")
                except Exception as e:
                    print(f"  Tool {i+1}: Error reading tool info - {e}")
        print("--- END DEBUG ---")
        
        # Initialize parent class with discovered tools
        super().__init__(tools=tools)

    def get_adherent_str(self) -> str:
        """Formats the current adherent's details into a readable string."""
        if not self._adherent_context:
            return "Aucun adhérent n'est actuellement chargé dans le contexte."
        
        details = self._adherent_context
        return (f"ID: {details.id_adherent}\n"
                f"Nom: {details.prenom} {details.nom}\n"
                f"Email: {details.email}\n"
                f"Téléphone: {details.telephone}\n"
                f"Ville: {details.ville}")

    def has_adherent_in_context(self) -> bool:
        """Checks if an adherent is loaded in the context."""
        return self._adherent_context is not None

    def _handle_lookup_result(self, result: Optional[Adherent] | List[Adherent]) -> str:
        """Handles the result of adherent lookup operations consistently."""
        if not result:
            self._adherent_context = None
            return "Désolé, aucun adhérent correspondant n'a été trouvé avec ces informations. Pouvez-vous vérifier les données et réessayer ?"

        if isinstance(result, list):
            if len(result) > 1:
                # Multiple results found
                response = "J'ai trouvé plusieurs adhérents correspondants :\n"
                for i, adherent in enumerate(result[:3], 1):  # Limit to first 3 results
                    response += f"{i}. {adherent.prenom} {adherent.nom} - {adherent.email}\n"
                response += "Pouvez-vous préciser avec une adresse e-mail ou un numéro de téléphone pour identifier le bon dossier ?"
                return response
            result = result[0]

        # Single result found
        self._adherent_context = result
        logger.info(f"Adherent loaded into context: {result.prenom} {result.nom} (ID: {result.id_adherent})")
        return f"Parfait ! J'ai trouvé le dossier de {result.prenom} {result.nom}. Comment puis-je vous aider aujourd'hui ?"
        
    # --- AI-Callable Functions (Tools) ---

    @llm.function_tool(description="Affiche les détails de l'adhérent actuellement chargé dans le contexte de l'assistant.")
    def get_adherent_details(self) -> str:
        """Gets the details of the member currently loaded in the assistant's context."""
        logger.info("Récupération des détails de l'adhérent en contexte")
        if not self._adherent_context:
            return "Aucun adhérent n'est actuellement sélectionné. Veuillez d'abord rechercher un adhérent."
        return self.get_adherent_str()

    @llm.function_tool(description="Liste tous les contrats associés à l'adhérent actuellement en contexte.")
    def list_adherent_contracts(self) -> str:
        """Lists all contracts associated with the member currently in context."""
        if not self._adherent_context:
            return "Veuillez d'abord rechercher un adhérent avant de consulter ses contrats."
        
        logger.info(f"Récupération des contrats pour l'adhérent ID: {self._adherent_context.id_adherent}")
        
        try:
            contracts: List[Contrat] = DB.get_contrats_by_adherent_id(self._adherent_context.id_adherent)

            if not contracts:
                return f"Aucun contrat trouvé pour {self._adherent_context.prenom} {self._adherent_context.nom}."
            
            response = f"Voici les contrats de {self._adherent_context.prenom} {self._adherent_context.nom} :\n\n"
            for i, c in enumerate(contracts, 1):
                response += (f"{i}. Contrat ID: {c.id_contrat}\n"
                           f"   Numéro: {c.numero_contrat}\n"
                           f"   Statut: {c.statut_contrat}\n"
                           f"   Type: {c.type_contrat}\n\n")
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des contrats: {e}")
            return "Une erreur s'est produite lors de la récupération des contrats. Veuillez réessayer."

    @llm.function_tool(description="Liste tous les sinistres déclarés par l'adhérent actuellement en contexte.")
    def list_adherent_claims(self) -> str:
        """Lists all claims (sinistres) filed by the member currently in context."""
        if not self._adherent_context:
            return "Veuillez d'abord rechercher un adhérent avant de consulter ses sinistres."
            
        logger.info(f"Récupération des sinistres pour l'adhérent ID: {self._adherent_context.id_adherent}")
        
        try:
            claims: List[SinistreArtex] = DB.get_sinistres_by_adherent_id(self._adherent_context.id_adherent)

            if not claims:
                return f"Aucun sinistre trouvé pour {self._adherent_context.prenom} {self._adherent_context.nom}."
                
            response = f"Voici les sinistres de {self._adherent_context.prenom} {self._adherent_context.nom} :\n\n"
            for i, s in enumerate(claims, 1):
                response += (f"{i}. Sinistre ID: {s.id_sinistre_artex}\n"
                           f"   Type: {s.type_sinistre}\n"  
                           f"   Statut: {s.statut_sinistre_artex}\n"
                           f"   Date: {s.date_survenance}\n\n")
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des sinistres: {e}")
            return "Une erreur s'est produite lors de la récupération des sinistres. Veuillez réessayer."
        
    @llm.function_tool(description="Crée un nouveau sinistre pour l'adhérent actuellement en contexte. Paramètres requis: contract_id (int), claim_type (str), description (str), incident_date (str au format YYYY-MM-DD).")
    def create_claim(
        self,
        contract_id: int,
        claim_type: str,
        description: str,
        incident_date: str
    ) -> str:
        """Creates a new claim (sinistre) for the member currently in context."""
        if not self._adherent_context:
            return "Impossible de créer un sinistre. Veuillez d'abord rechercher un adhérent."

        logger.info(f"Création d'un nouveau sinistre pour l'adhérent ID {self._adherent_context.id_adherent} sous le contrat ID {contract_id}")

        try:
            # Validate date format
            parsed_date = date.fromisoformat(incident_date)
            
            # Create the claim
            new_claim = DB.create_sinistre(
                id_contrat=contract_id,
                id_adherent=self._adherent_context.id_adherent,
                type_sinistre=claim_type,
                description_sinistre=description,
                date_survenance=parsed_date
            )
            
            success_msg = f"Sinistre créé avec succès !\nNuméro de sinistre: {new_claim.id_sinistre_artex}\nType: {claim_type}\nDate: {incident_date}"
            logger.info(f"Sinistre créé avec succès - ID: {new_claim.id_sinistre_artex}")
            return success_msg
            
        except ValueError as ve:
            error_msg = "Erreur: La date d'incident doit être au format YYYY-MM-DD (exemple: 2024-06-23)."
            logger.error(f"Erreur de format de date: {ve}")
            return error_msg
        except Exception as e:
            error_msg = f"Une erreur s'est produite lors de la création du sinistre. Veuillez contacter le support technique."
            logger.error(f"Erreur lors de la création du sinistre: {e}")
            return error_msg

    @llm.function_tool(description="Recherche un adhérent par son adresse e-mail. Paramètre requis: email (str).")
    def lookup_adherent_by_email(self, email: str) -> str:
        """Looks up member information using their email address."""
        if not email or not email.strip():
            return "Veuillez fournir une adresse e-mail valide."
            
        logger.info(f"Recherche de l'adhérent par e-mail: {email}")
        
        try:
            adherent = self.db_driver.get_adherent_by_email(email.strip())
            return self._handle_lookup_result(adherent)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par e-mail: {e}")
            return "Une erreur s'est produite lors de la recherche. Veuillez réessayer."

    @llm.function_tool(description="Recherche un ou plusieurs adhérents par leur numéro de téléphone. Paramètre requis: telephone (str).")
    def lookup_adherent_by_telephone(self, telephone: str) -> str:
        """Searches for members by their telephone number."""
        if not telephone or not telephone.strip():
            return "Veuillez fournir un numéro de téléphone valide."
            
        logger.info(f"Recherche de l'adhérent par téléphone: {telephone}")
        
        try:
            adherents = self.db_driver.get_adherents_by_telephone(telephone.strip())
            return self._handle_lookup_result(adherents)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par téléphone: {e}")
            return "Une erreur s'est produite lors de la recherche. Veuillez réessayer."
    
    @llm.function_tool(description="Recherche un adhérent par son nom complet. Paramètres requis: nom (str), prenom (str).")
    def lookup_adherent_by_fullname(self, nom: str, prenom: str) -> str:
        """Looks up member information using their full name."""
        if not nom or not prenom or not nom.strip() or not prenom.strip():
            return "Veuillez fournir un nom et un prénom valides."
            
        logger.info(f"Recherche de l'adhérent par nom complet: {prenom} {nom}")
        
        try:
            adherents = self.db_driver.get_adherent_by_fullname(nom.strip(), prenom.strip())
            return self._handle_lookup_result(adherents)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par nom: {e}")
            return "Une erreur s'est produite lors de la recherche. Veuillez réessayer."


# --- FastAPI App Initialization ---
app = FastAPI(
    title="ARTEX AI Voice Agent Backend",
    description="Backend API for ARTEX Insurance AI Voice Agent",
    version="1.0.0"
)

# --- CORS Middleware Configuration ---
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # React default port
    "http://127.0.0.1:3000",
    # Add your production frontend URL when deployed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "ARTEX AI Voice Agent Backend is running.",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    try:
        # Test database connection
        test_db = ExtranetDatabaseDriver()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "livekit_configured": bool(LIVEKIT_API_KEY and LIVEKIT_API_SECRET),
        "timestamp": date.today().isoformat()
    }

@app.post("/create-token")
async def create_token(body: dict):
    """Creates a LiveKit access token for room access."""
    identity = body.get("identity")
    room_name = body.get("room_name")

    # Validation
    if not identity or not room_name:
        raise HTTPException(
            status_code=400, 
            detail="Both 'identity' and 'room_name' are required fields"
        )
    
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured properly"
        )

    try:
        # Create a LiveKit access token
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )
        token.add_grant(grant).with_identity(identity).with_name(identity)

        logger.info(f"Token created for identity: {identity}, room: {room_name}")
        
        return {
            "token": token.to_jwt(),
            "identity": identity,
            "room_name": room_name
        }
        
    except Exception as e:
        logger.error(f"Error creating token: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create access token"
        )

# --- Error Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return {
        "error": exc.detail,
        "status_code": exc.status_code
    }

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler for unexpected errors."""
    logger.error(f"Unexpected error: {exc}")
    return {
        "error": "An unexpected error occurred",
        "status_code": 500
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)