import React, { useEffect } from 'react';
import '@livekit/components-styles';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  ControlBar,
  useDataChannel,
  AudioConference
} from '@livekit/components-react';
import './SimpleVoiceAssistant.css';

// Ce composant interne gère la réception des données de l'agent
const DataReceiver = ({ onDataReceived }) => {
  // Le hook useDataChannel nous abonne aux messages entrants.
  // 'data' contient le dernier message reçu sous forme de Uint8Array.
  const { data } = useDataChannel();

  useEffect(() => {
    if (data) {
      // Les données arrivent sous forme de buffer, il faut les décoder en texte.
      const messageText = new TextDecoder().decode(data);
      onDataReceived(messageText);
    }
  }, [data, onDataReceived]); // Se déclenche à chaque nouveau message

  return null; // Ce composant n'a pas de rendu visuel
};

const SimpleVoiceAssistant = ({ token, onDataReceived }) => {
  // Récupère l'URL du serveur LiveKit depuis les variables d'environnement
  const serverUrl = import.meta.env.VITE_LIVEKIT_URL;

  // Affiche un message d'erreur clair si l'URL n'est pas configurée
  if (!serverUrl) {
    return (
      <div className="error-container">
        <h2>Erreur de Configuration</h2>
        <p>L'URL de votre serveur LiveKit (VITE_LIVEKIT_URL) n'est pas définie.</p>
        <p>Veuillez créer un fichier <code>.env</code> dans le dossier <code>frontend</code> et ajouter la ligne :</p>
        <code>VITE_LIVEKIT_URL=wss://your-livekit-url.com</code>
      </div>
    );
  }

  return (
    <main className="voice-assistant-container">
      <LiveKitRoom
        token={token}
        serverUrl={serverUrl}
        audio={true}
        video={false}
        data-lk-theme="default"
        connectOptions={{ autoSubscribe: true }}
      >
        {/* Le composant AudioConference gère l'affichage des participants */}
        <AudioConference />
        {/* Le composant RoomAudioRenderer gère la lecture de tous les flux audio */}
        <RoomAudioRenderer />
        {/* Notre composant personnalisé pour écouter les données de l'agent */}
        <DataReceiver onDataReceived={onDataReceived} />
        {/* La barre de contrôle permet à l'utilisateur de se mettre en sourdine et de quitter */}
        <ControlBar controls={{ microphone: true, screenShare: false, camera: false, chat: false, leave: true }} />
      </LiveKitRoom>
    </main>
  );
};

export default SimpleVoiceAssistant;