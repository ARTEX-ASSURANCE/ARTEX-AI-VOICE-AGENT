import React, { useState, useEffect } from 'react';

const KPIsApercu = () => {
  const [kpiData, setKpiData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchKpiData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // L'URL du backend est nécessaire ici. Assumons qu'elle est disponible via import.meta.env.VITE_BACKEND_URL
        // ou qu'elle est configurée globalement. Pour l'instant, codée en dur pour l'exemple.
        // Dans une vraie application, utilisez import.meta.env.VITE_BACKEND_URL ou une config.
        const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5001';
        const response = await fetch(`${backendUrl}/api/dashboard/kpis`);

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.erreur || `Erreur HTTP: ${response.status}`);
        }
        const data = await response.json();
        if (data.succes) {
          setKpiData(data.donnees);
        } else {
          throw new Error(data.erreur || "Erreur lors de la récupération des données KPIs.");
        }
      } catch (err) {
        setError(err.message);
        setKpiData(null); // Réinitialiser les données en cas d'erreur
        console.error("Erreur lors de la récupération des KPIs:", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchKpiData();
  }, []); // Le tableau vide signifie que cet effet ne s'exécute qu патриарх (mount) et démontage (unmount)

  const formatDuration = (totalSeconds) => {
    if (totalSeconds === null || totalSeconds === undefined) return 'N/A';
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${minutes}m ${seconds}s`;
  };

  if (isLoading) {
    return <p>Chargement des indicateurs clés de performance...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Erreur de chargement des KPIs : {error}</p>;
  }

  if (!kpiData) {
    return <p>Aucune donnée KPI disponible pour le moment.</p>;
  }

  return (
    <div className="kpi-apercu" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
      <div className="kpi-card" style={cardStyle}>
        <h3>Nombre Total d'Appels</h3>
        <p style={valueStyle}>{kpiData.nombre_total_appels ?? 'N/A'}</p>
      </div>
      <div className="kpi-card" style={cardStyle}>
        <h3>Durée Moyenne des Appels</h3>
        <p style={valueStyle}>{formatDuration(kpiData.duree_moyenne_appels_secondes)}</p>
      </div>
      <div className="kpi-card" style={cardStyle}>
        <h3>Nombre d'Erreurs Critiques</h3>
        <p style={valueStyle}>{kpiData.nombre_erreurs_critiques ?? 'N/A'}</p>
      </div>
      <div className="kpi-card" style={cardStyle}>
        <h3>Taux de Confirmation d'Identité</h3>
        <p style={valueStyle}>{(kpiData.taux_confirmation_identite ?? 0).toFixed(2)} %</p>
      </div>
      <div className="kpi-card" style={cardStyle}>
        <h3>Appels sans Confirmation d'Identité</h3>
        <p style={valueStyle}>{kpiData.appels_sans_confirmation_identite ?? 'N/A'}</p>
      </div>
      <div className="kpi-card" style={{ ...cardStyle, gridColumn: 'span 2' }}> {/* Fait en sorte que cette carte prenne plus de place si possible */}
        <h3>Utilisation des Outils (Top 5)</h3>
        {kpiData.utilisation_outils_top5 && kpiData.utilisation_outils_top5.length > 0 ? (
          <ul style={{ listStyleType: 'none', paddingLeft: 0 }}>
            {kpiData.utilisation_outils_top5.map((outil, index) => (
              <li key={index} style={{ marginBottom: '5px' }}>
                {outil.nom_outil}: {outil.count} utilisations
              </li>
            ))}
          </ul>
        ) : (
          <p>Aucune donnée d'utilisation d'outil.</p>
        )}
      </div>
    </div>
  );
};

// Styles basiques pour les cartes KPI (peuvent être déplacés dans un fichier CSS)
const cardStyle = {
  border: '1px solid #e0e0e0',
  borderRadius: '8px',
  padding: '20px',
  textAlign: 'center',
  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
};

const valueStyle = {
  fontSize: '2em',
  fontWeight: 'bold',
  margin: '10px 0 0 0',
};

export default KPIsApercu;
