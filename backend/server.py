import os
from flask import Flask, request
from dotenv import load_dotenv
from flask_cors import CORS
from livekit.api import LiveKitAPI, AccessToken, VideoGrants, ListRoomsRequest # Updated imports
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
        print("Warning: LiveKit server URL, API Key or API Secret are not fully configured for get_rooms.")
        return [] # Return empty list as the API call will fail

    # Use direct import LiveKitAPI, ListRoomsRequest
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
    identity = data.get("identity", "default-identity")

    if not room_name:
        room_name = await generate_room_name() # Keep original logic for generating room if not provided

    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_api_key, livekit_api_secret]): # Host isn't strictly needed for token generation itself
        return {"error": "LiveKit API Key or API Secret are not configured"}, 500

    # Use direct import AccessToken, VideoGrants
    token_builder = AccessToken(livekit_api_key, livekit_api_secret) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name
        ))
    
    return {"token": token_builder.to_jwt()} # Return as JSON object

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)