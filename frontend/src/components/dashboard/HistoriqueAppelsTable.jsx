import React, { useState, useEffect, useCallback } from 'react';

const HistoriqueAppelsTable = () => {
  const [calls, setCalls] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(10); // Peut être configurable

  const [filters, setFilters] = useState({
    dateDebut: '',
    dateFin: '',
    idAdherent: '',
    numeroAppelant: ''
  });
  const [activeFilters, setActiveFilters] = useState({});

  const fetchCalls = useCallback(async (page, currentFilters) => {
    setIsLoading(true);
    setError(null);
    let queryString = `page=${page}&per_page=${itemsPerPage}`;

    Object.entries(currentFilters).forEach(([key, value]) => {
      if (value) { // Ajouter seulement si le filtre a une valeur
        queryString += `&${key}=${encodeURIComponent(value)}`;
      }
    });

    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5001';
      const response = await fetch(`${backendUrl}/api/dashboard/calls?${queryString}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.erreur || `Erreur HTTP: ${response.status}`);
      }
      const data = await response.json();
      if (data.succes) {
        setCalls(data.donnees);
        setCurrentPage(data.pagination.page);
        setTotalPages(data.pagination.total_pages);
        setTotalItems(data.pagination.total_items);
      } else {
        throw new Error(data.erreur || "Erreur lors de la récupération de l'historique des appels.");
      }
    } catch (err) {
      setError(err.message);
      setCalls([]);
      console.error("Erreur lors de la récupération de l'historique des appels:", err);
    } finally {
      setIsLoading(false);
    }
  }, [itemsPerPage]); // dépendance à itemsPerPage si on le rend configurable

  useEffect(() => {
    fetchCalls(currentPage, activeFilters);
  }, [currentPage, activeFilters, fetchCalls]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleApplyFilters = () => {
    setCurrentPage(1); // Réinitialiser à la première page lors de l'application de nouveaux filtres
    setActiveFilters(filters);
  };

  const handleClearFilters = () => {
    const clearedFilters = {
        dateDebut: '',
        dateFin: '',
        idAdherent: '',
        numeroAppelant: ''
    };
    setFilters(clearedFilters);
    setActiveFilters(clearedFilters); // Appliquer immédiatement les filtres vides
    setCurrentPage(1);
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      return new Date(isoString).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
    } catch (e) {
      return 'Date invalide';
    }
  };

  const formatDuration = (totalSeconds) => {
    if (totalSeconds === null || totalSeconds === undefined) return 'N/A';
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${minutes}m ${seconds}s`;
  };

  const handlePrevPage = () => {
    setCurrentPage(prev => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage(prev => Math.min(totalPages, prev + 1));
  };

  // Styles (peuvent être externalisés)
  const filterContainerStyle = { marginBottom: '20px', padding: '15px', border: '1px solid #eee', borderRadius: '5px', display: 'flex', gap: '10px', flexWrap: 'wrap' };
  const inputStyle = { marginRight: '10px', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' };
  const buttonStyle = { padding: '8px 15px', border: 'none', borderRadius: '4px', cursor: 'pointer' };
  const tableStyle = { width: '100%', borderCollapse: 'collapse', marginTop: '20px' };
  const thTdStyle = { border: '1px solid #ddd', padding: '10px', textAlign: 'left' };
  const thStyle = { ...thTdStyle, backgroundColor: '#f2f2f2', fontWeight: 'bold' };
  const paginationContainerStyle = { marginTop: '20px', textAlign: 'center' };

  if (isLoading) {
    return <p>Chargement de l'historique des appels...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Erreur de chargement de l'historique : {error}</p>;
  }

  return (
    <div className="historique-appels-container">
      <h2>Historique des Appels ({totalItems} appels)</h2>

      <div style={filterContainerStyle}>
        <input type="date" name="dateDebut" value={filters.dateDebut} onChange={handleFilterChange} style={inputStyle} title="Date de début"/>
        <input type="date" name="dateFin" value={filters.dateFin} onChange={handleFilterChange} style={inputStyle} title="Date de fin"/>
        <input type="text" name="idAdherent" placeholder="ID Adhérent" value={filters.idAdherent} onChange={handleFilterChange} style={inputStyle} />
        <input type="text" name="numeroAppelant" placeholder="Numéro Appelant" value={filters.numeroAppelant} onChange={handleFilterChange} style={inputStyle} />
        <button onClick={handleApplyFilters} style={{...buttonStyle, backgroundColor: '#007bff', color: 'white'}}>Appliquer Filtres</button>
        <button onClick={handleClearFilters} style={{...buttonStyle, backgroundColor: '#6c757d', color: 'white'}}>Effacer Filtres</button>
      </div>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>ID Appel</th>
            <th style={thStyle}>Début</th>
            <th style={thStyle}>Durée</th>
            <th style={thStyle}>N° Appelant</th>
            <th style={thStyle}>Adhérent Identifié</th>
            <th style={thStyle}>Évaluation Résolution</th>
            <th style={thStyle}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {calls.length > 0 ? calls.map(call => (
            <tr key={call.id_appel}>
              <td style={thTdStyle}>{call.id_appel}</td>
              <td style={thTdStyle}>{formatDateTime(call.timestamp_debut)}</td>
              <td style={thTdStyle}>{formatDuration(call.duree_secondes)}</td>
              <td style={thTdStyle}>{call.numero_appelant || 'N/A'}</td>
              <td style={thTdStyle}>{call.id_adherent_contexte ? `${call.prenom || ''} ${call.nom || ''} (ID: ${call.id_adherent_contexte})` : 'Non identifié'}</td>
              <td style={thTdStyle} title={call.evaluation_resolution_appel}>{call.evaluation_resolution_appel ? call.evaluation_resolution_appel.substring(0, 50) + (call.evaluation_resolution_appel.length > 50 ? '...' : '') : 'N/A'}</td>
              <td style={thTdStyle}>
                <button onClick={() => alert(`Afficher détails pour appel ID: ${call.id_appel}`)} style={{...buttonStyle, fontSize:'0.9em', padding:'5px 10px'}}>Détails</button>
              </td>
            </tr>
          )) : (
            <tr>
              <td colSpan="7" style={{...thTdStyle, textAlign: 'center'}}>Aucun appel trouvé pour les critères actuels.</td>
            </tr>
          )}
        </tbody>
      </table>

      <div style={paginationContainerStyle}>
        <button onClick={handlePrevPage} disabled={currentPage <= 1} style={buttonStyle}>
          Précédent
        </button>
        <span style={{ margin: '0 15px' }}>
          Page {currentPage} sur {totalPages}
        </span>
        <button onClick={handleNextPage} disabled={currentPage >= totalPages} style={buttonStyle}>
          Suivant
        </button>
      </div>
    </div>
  );
};

export default HistoriqueAppelsTable;
