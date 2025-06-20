# LiveKit AI Car Call Centre

## Project Setup and Running Instructions

This project consists of a React frontend and a Python Flask backend.

### Prerequisites

*   Node.js and npm (or yarn) for the frontend.
*   Python 3.x and pip for the backend.
*   A LiveKit account and credentials (API Key, API Secret, Server URL).

### 1. Backend Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    *   Create a file named `.env` in the `backend` directory.
    *   Add your LiveKit credentials to this file:
        ```
        LIVEKIT_API_KEY=your_api_key_here
        LIVEKIT_API_SECRET=your_api_secret_here
        LIVEKIT_URL=your_livekit_url_here
        ```
        Replace placeholders with your actual LiveKit API key, secret, and server URL (e.g., `https://your-project-abcdef.livekit.cloud`).

5.  **Run the backend server:**
    ```bash
    python server.py
    ```
    The backend should now be running on `http://localhost:5001`.

### 2. Frontend Setup

1.  **Navigate to the frontend directory (from the project root):**
    ```bash
    cd frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    ```

3.  **Configure environment variables:**
    *   Create a file named `.env` in the `frontend` directory.
    *   Add your LiveKit server URL and the backend URL to this file:
        ```
        VITE_LIVEKIT_URL=wss://your-livekit-domain.com
        VITE_BACKEND_URL=http://localhost:5001
        ```
        Replace `wss://your-livekit-domain.com` with your actual LiveKit WebSocket URL (this is often the same as your `LIVEKIT_URL` but prefixed with `wss://` and without the `/` at the end if `LIVEKIT_URL` has it, or it might be a specific WebSocket endpoint like `wss://your-project-abcdef.livekit.cloud`).
        `VITE_BACKEND_URL` should point to your running backend server.

4.  **Run the frontend development server:**
    ```bash
    npm run dev
    # or
    # yarn dev
    ```
    The frontend should now be accessible in your browser, typically at `http://localhost:5173` (Vite will show the exact URL).

### 3. Using the Application

*   Ensure both the backend and frontend servers are running.
*   Open the frontend URL in your browser.
*   Click the "Démarrer l'appel" (Start Call) button to connect to the LiveKit room.
