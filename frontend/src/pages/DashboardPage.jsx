import React, { useState } from 'react';
import KPIsApercu from '../components/dashboard/KPIsApercu';
import HistoriqueAppelsTable from '../components/dashboard/HistoriqueAppelsTable'; // Importer le nouveau composant
// import JournalErreursTable from '../components/dashboard/JournalErreursTable';
// import JournalDBTable from '../components/dashboard/JournalDBTable';

// Définir les types de vues possibles pour une meilleure gestion
const VIEW_TYPES = {
  APERCU: 'apercu',
  APPELS: 'appels',
  ERREURS: 'erreurs',
  DB_LOG: 'db_log',
};

const DashboardPage = () => {
  const [activeView, setActiveView] = useState(VIEW_TYPES.APERCU); // Vue par défaut

  const renderActiveView = () => {
    switch (activeView) {
      case VIEW_TYPES.APERCU:
        return <KPIsApercu />;
      case VIEW_TYPES.APPELS:
        return <HistoriqueAppelsTable />; // Afficher le composant
      case VIEW_TYPES.ERREURS:
        // return <JournalErreursTable />;
        return <p>Section Journal des Erreurs à implémenter.</p>;
      case VIEW_TYPES.DB_LOG:
        // return <JournalDBTable />;
        return <p>Section Journal Base de Données à implémenter.</p>;
      default:
        return <p>Veuillez sélectionner une vue.</p>;
    }
  };

  // Styles pour les boutons de navigation
  const navButtonStyle = {
    padding: '10px 15px',
    marginRight: '10px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    cursor: 'pointer',
    backgroundColor: '#f8f9fa',
  };

  const activeNavButtonStyle = {
    ...navButtonStyle,
    backgroundColor: '#007bff',
    color: 'white',
    borderColor: '#007bff',
  };

  return (
    <div className="dashboard-container" style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <header style={{ marginBottom: '20px', borderBottom: '1px solid #ccc', paddingBottom: '10px' }}>
        <h1 style={{ fontSize: '1.8em', color: '#333' }}>Tableau de Bord de Supervision de l'Agent</h1>
      </header>

      <nav style={{ marginBottom: '30px', paddingBottom: '15px', borderBottom: '1px solid #eee' }}>
        <button
          style={activeView === VIEW_TYPES.APERCU ? activeNavButtonStyle : navButtonStyle}
          onClick={() => setActiveView(VIEW_TYPES.APERCU)}>
          Aperçu (KPIs)
        </button>
        <button
          style={activeView === VIEW_TYPES.APPELS ? activeNavButtonStyle : navButtonStyle}
          onClick={() => setActiveView(VIEW_TYPES.APPELS)}>
          Historique des Appels
        </button>
        <button
          style={activeView === VIEW_TYPES.ERREURS ? activeNavButtonStyle : navButtonStyle}
          onClick={() => setActiveView(VIEW_TYPES.ERREURS)}>
          Journal des Erreurs
        </button>
        <button
          style={activeView === VIEW_TYPES.DB_LOG ? activeNavButtonStyle : navButtonStyle}
          onClick={() => setActiveView(VIEW_TYPES.DB_LOG)}>
          Journal Base de Données
        </button>
      </nav>

      <section className="dashboard-content">
        {renderActiveView()}
      </section>
    </div>
  );
};

export default DashboardPage;
