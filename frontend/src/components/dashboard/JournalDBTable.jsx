import React, { useState, useEffect, useCallback } from 'react';

const JournalDBTable = () => {
  const [dbLogs, setDbLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(15);

  const [filters, setFilters] = useState({
    dateDebut: '',
    dateFin: '',
    typeRequete: '',
    tableAffectee: ''
  });
  const [activeFilters, setActiveFilters] = useState({});

  const fetchDbLogs = useCallback(async (page, currentFilters) => {
    setIsLoading(true);
    setError(null);
    let queryString = `page=${page}&per_page=${itemsPerPage}`;

    Object.entries(currentFilters).forEach(([key, value]) => {
      if (value) {
        queryString += `&${key}=${encodeURIComponent(value)}`;
      }
    });

    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5001';
      const response = await fetch(`${backendUrl}/api/dashboard/db_log?${queryString}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.erreur || `Erreur HTTP: ${response.status}`);
      }
      const data = await response.json();
      if (data.succes) {
        setDbLogs(data.donnees);
        setCurrentPage(data.pagination.page);
        setTotalPages(data.pagination.total_pages);
        setTotalItems(data.pagination.total_items);
      } else {
        throw new Error(data.erreur || "Erreur lors de la récupération du journal de la base de données.");
      }
    } catch (err) {
      setError(err.message);
      setDbLogs([]);
      console.error("Erreur lors de la récupération du journal de la base de données:", err);
    } finally {
      setIsLoading(false);
    }
  }, [itemsPerPage]);

  useEffect(() => {
    fetchDbLogs(currentPage, activeFilters);
  }, [currentPage, activeFilters, fetchDbLogs]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleApplyFilters = () => {
    setCurrentPage(1);
    setActiveFilters(filters);
  };

  const handleClearFilters = () => {
    const clearedFilters = { dateDebut: '', dateFin: '', typeRequete: '', tableAffectee: '' };
    setFilters(clearedFilters);
    setActiveFilters(clearedFilters);
    setCurrentPage(1);
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      return new Date(isoString).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'medium' });
    } catch (e) { return 'Date invalide'; }
  };

  const handlePrevPage = () => setCurrentPage(prev => Math.max(1, prev - 1));
  const handleNextPage = () => setCurrentPage(prev => Math.min(totalPages, prev + 1));

  // Styles (peuvent être externalisés)
  const filterContainerStyle = { marginBottom: '20px', padding: '15px', border: '1px solid #eee', borderRadius: '5px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' };
  const inputStyle = { marginRight: '10px', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' };
  const buttonStyle = { padding: '8px 15px', border: 'none', borderRadius: '4px', cursor: 'pointer' };
  const tableStyle = { width: '100%', borderCollapse: 'collapse', marginTop: '20px', tableLayout: 'fixed' };
  const thTdStyle = { border: '1px solid #ddd', padding: '10px', textAlign: 'left', wordBreak: 'break-word' };
  const thStyle = { ...thTdStyle, backgroundColor: '#f2f2f2', fontWeight: 'bold' };
  const paginationContainerStyle = { marginTop: '20px', textAlign: 'center' };

  if (isLoading) {
    return <p>Chargement du journal de la base de données...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Erreur de chargement du journal DB : {error}</p>;
  }

  return (
    <div className="journal-db-container">
      <h2>Journal des Interactions avec la Base de Données ({totalItems} entrées)</h2>

      <div style={filterContainerStyle}>
        <input type="date" name="dateDebut" value={filters.dateDebut} onChange={handleFilterChange} style={inputStyle} title="Date de début"/>
        <input type="date" name="dateFin" value={filters.dateFin} onChange={handleFilterChange} style={inputStyle} title="Date de fin"/>
        <input type="text" name="typeRequete" placeholder="Type de Requête (SELECT, INSERT...)" value={filters.typeRequete} onChange={handleFilterChange} style={inputStyle} />
        <input type="text" name="tableAffectee" placeholder="Table Affectée" value={filters.tableAffectee} onChange={handleFilterChange} style={inputStyle} />
        <button onClick={handleApplyFilters} style={{...buttonStyle, backgroundColor: '#007bff', color: 'white'}}>Appliquer Filtres</button>
        <button onClick={handleClearFilters} style={{...buttonStyle, backgroundColor: '#6c757d', color: 'white'}}>Effacer Filtres</button>
      </div>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={{...thStyle, width: '15%'}}>Timestamp</th>
            <th style={{...thStyle, width: '10%'}}>ID Appel</th>
            <th style={{...thStyle, width: '15%'}}>Type Requête</th>
            <th style={{...thStyle, width: '15%'}}>Table Affectée</th>
            <th style={{...thStyle, width: '35%'}}>Description Action</th>
            <th style={{...thStyle, width: '10%'}}>ID Adhérent</th>
          </tr>
        </thead>
        <tbody>
          {dbLogs.length > 0 ? dbLogs.map(log => (
            <tr key={log.id_interaction_bd}>
              <td style={thTdStyle}>{formatDateTime(log.timestamp_interaction)}</td>
              <td style={thTdStyle}>{log.id_appel_fk || 'N/A'}</td>
              <td style={thTdStyle}>{log.type_requete}</td>
              <td style={thTdStyle}>{log.table_affectee}</td>
              <td style={thTdStyle}>{log.description_action}</td>
              <td style={thTdStyle}>{log.id_adherent_concerne || 'N/A'}</td>
            </tr>
          )) : (
            <tr>
              <td colSpan="6" style={{...thTdStyle, textAlign: 'center'}}>Aucune interaction avec la base de données trouvée pour les critères actuels.</td>
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

export default JournalDBTable;
