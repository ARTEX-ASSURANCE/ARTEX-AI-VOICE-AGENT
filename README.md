# Centre d'Appel IA LiveKit pour Voitures (Exemple)

## Instructions de Configuration et d'Exécution du Projet

Ce projet se compose d'un frontend React et d'un backend Python Flask.

### Prérequis

*   Node.js et npm (ou yarn) pour le frontend.
*   Python 3.x et pip pour le backend.
*   Un compte LiveKit et des identifiants (Clé API, Secret API, URL du Serveur).

### 1. Configuration du Backend

1.  **Naviguez vers le répertoire backend :**
    ```bash
    cd backend
    ```

2.  **Créez un environnement virtuel Python (recommandé) :**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sous Windows, utilisez `venv\Scripts\activate`
    ```

3.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurez les variables d'environnement :**
    *   Créez un fichier nommé `.env` dans le répertoire `backend`.
    *   Ajoutez vos identifiants LiveKit à ce fichier :
        ```
        LIVEKIT_API_KEY=votre_clé_api_ici
        LIVEKIT_API_SECRET=votre_secret_api_ici
        LIVEKIT_URL=votre_url_livekit_ici
        ```
        Remplacez les espaces réservés par votre clé API LiveKit, votre secret et l'URL de votre serveur (par exemple, `https://votre-projet-abcdef.livekit.cloud`).

5.  **Lancez le serveur backend :**
    ```bash
    python server.py
    ```
    Le backend devrait maintenant être en cours d'exécution sur `http://localhost:5001`.

### 2. Configuration du Frontend

1.  **Naviguez vers le répertoire frontend (depuis la racine du projet) :**
    ```bash
    cd frontend
    ```

2.  **Installez les dépendances :**
    ```bash
    npm install
    # ou
    # yarn install
    ```

3.  **Configurez les variables d'environnement :**
    *   Créez un fichier nommé `.env` dans le répertoire `frontend`.
    *   Ajoutez l'URL de votre serveur LiveKit et l'URL du backend à ce fichier :
        ```
        VITE_LIVEKIT_URL=wss://votre-domaine-livekit.com
        VITE_BACKEND_URL=http://localhost:5001
        ```
        Remplacez `wss://votre-domaine-livekit.com` par votre URL WebSocket LiveKit réelle (c'est souvent la même que votre `LIVEKIT_URL` mais préfixée par `wss://` et sans le `/` à la fin si `LIVEKIT_URL` l'a, ou cela peut être un point de terminaison WebSocket spécifique comme `wss://votre-projet-abcdef.livekit.cloud`).
        `VITE_BACKEND_URL` doit pointer vers votre serveur backend en cours d'exécution.

4.  **Lancez le serveur de développement frontend :**
    ```bash
    npm run dev
    # ou
    # yarn dev
    ```
    Le frontend devrait maintenant être accessible dans votre navigateur, généralement à `http://localhost:5173` (Vite affichera l'URL exacte).

### 3. Utilisation de l'Application

*   Assurez-vous que les serveurs backend et frontend sont tous deux en cours d'exécution.
*   Ouvrez l'URL du frontend dans votre navigateur.
*   Cliquez sur le bouton "Démarrer l'appel" pour vous connecter à la salle LiveKit.
