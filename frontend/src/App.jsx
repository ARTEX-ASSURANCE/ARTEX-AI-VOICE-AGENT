import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Link } from 'react-router-dom'; // Import pour le routage
import SimpleVoiceAssistant from './components/SimpleVoiceAssistant';
import InsightsPanel from './components/InsightsPanel';
import DashboardPage from './pages/DashboardPage'; // Importer la future page
import './App.css';

// Génère une identité unique pour chaque session utilisateur
const identity = 'user-' + Math.random().toString(36).substring(7);
// Nom de la room LiveKit, peut être statique ou dynamique
const roomName = 'artex-call'; // Ceci est un nom de salle, pas à traduire


// Composant pour l'interface d'appel principale
const CallInterface = () => {
    const [token, setToken] = useState(null);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState(null);
    const [insights, setInsights] = useState({ kpis: {}, reasoning: {} });
    const [duration, setDuration] = useState(0);

    useEffect(() => {
        if (!token) return;
        const timer = setInterval(() => {
            setDuration((prevDuration) => prevDuration + 1);
        }, 1000);
        return () => clearInterval(timer);
    }, [token]);

    const handleConnect = async () => {
        setIsConnecting(true);
        setError(null);
        try {
            const backendUrl = import.meta.env.VITE_BACKEND_URL;
            if (!backendUrl) {
                throw new Error("VITE_BACKEND_URL n'est pas configuré. Veuillez créer un fichier .env à la racine du dossier 'frontend' et y ajouter cette variable.");
            }
            const response = await fetch(`${backendUrl}/create-token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ room_name: roomName, identity: identity }),
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || "Erreur lors de la récupération du token depuis le serveur.");
            }
            const data = await response.json();
            setToken(data.token);
        } catch (e) {
            console.error(e);
            setError(e.message);
        } finally {
            setIsConnecting(false);
        }
    };
    
    const onDataReceived = useCallback((data) => {
        try {
            const message = JSON.parse(data);
            console.log("Données reçues de l'agent:", message);
            if (message.type === 'kpi_update') {
                setInsights(prev => ({ ...prev, kpis: { ...prev.kpis, [message.data.kpi]: message.data.value }}));
            } else if (message.type === 'agent_reasoning') {
                setInsights(prev => ({ ...prev, reasoning: message.data }));
            }
        } catch (e) {
            console.error("Erreur lors du parsing des données de l'agent:", e);
        }
    }, []);

    if (!token) {
        return (
            <div className="app-container-centered">
                <div className="welcome-box">
                    <h1 className="welcome-title">ARIA</h1>
                    <p className="welcome-subtitle">Votre Assistante Virtuelle ARTEX</p>
                    <p className="welcome-text">Cliquez sur le bouton ci-dessous pour démarrer un appel.</p>
                    <button className="connect-button" onClick={handleConnect} disabled={isConnecting}>
                        {isConnecting ? 'Connexion en cours...' : "Démarrer l'appel"}
                    </button>
                    {error && <p className="error-message">{error}</p>}
                </div>
            </div>
        );
    }

    return (
        <div className="app-container-split">
            <SimpleVoiceAssistant token={token} onDataReceived={onDataReceived} />
            <InsightsPanel insights={insights} duration={duration} />
        </div>
    );
};


const App = () => {
    // Le state de l'appel (token, error, etc.) est maintenant géré dans CallInterface
    // App se concentre sur le routage et la navigation globale.

    return (
        <> {/* Utiliser un fragment pour envelopper la navigation et les routes */}
            <nav style={{ padding: '10px', background: '#f0f0f0', marginBottom: '20px', textAlign: 'center' }}>
                <Link to="/" style={{ marginRight: '20px' }}>Interface d'Appel</Link>
                <Link to="/dashboard">Tableau de Bord</Link>
            </nav>
            <Routes>
                <Route path="/" element={<CallInterface />} />
                <Route path="/dashboard" element={<DashboardPage />} />
            </Routes>
        </>
    );
};

export default App;