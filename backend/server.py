import os
from flask import Flask, request
from dotenv import load_dotenv
from flask_cors import CORS
from livekit.api import LiveKitAPI, AccessToken, VideoGrants, ListRoomsRequest # Importations mises à jour
import uuid

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

async def generate_room_name():
    name = "room-" + str(uuid.uuid4())[:8]
    rooms = await get_rooms()
    while name in rooms:
        name = "room-" + str(uuid.uuid4())[:8]
    return name

async def get_rooms():
    livekit_host = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_host, livekit_api_key, livekit_api_secret]):
        print("Avertissement : L'URL du serveur LiveKit, la clé API ou le secret API ne sont pas entièrement configurés pour get_rooms.")
        return [] # Retourner une liste vide car l'appel API échouera

    # Utiliser l'importation directe de LiveKitAPI, ListRoomsRequest
    lk_api = LiveKitAPI(host=livekit_host, api_key=livekit_api_key, api_secret=livekit_api_secret)
    try:
        rooms_response = await lk_api.room.list_rooms(ListRoomsRequest())
    finally:
        await lk_api.aclose()
    
    return [room.name for room in rooms_response.rooms]

@app.route("/create-token", methods=['POST'])
async def get_token():
    data = request.get_json()
    room_name = data.get("room_name")
    identity = data.get("identity", "default-identity") # Identité par défaut

    if not room_name:
        room_name = await generate_room_name() # Conserver la logique originale pour générer la salle si non fournie

    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_api_key, livekit_api_secret]): # L'hôte n'est pas strictement nécessaire pour la génération de token elle-même
        return {"error": "La clé API ou le secret API LiveKit ne sont pas configurés"}, 500

    # Utiliser l'importation directe de AccessToken, VideoGrants
    token_builder = AccessToken(livekit_api_key, livekit_api_secret) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name
        ))
    
    return {"token": token_builder.to_jwt()} # Retourner comme objet JSON

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)