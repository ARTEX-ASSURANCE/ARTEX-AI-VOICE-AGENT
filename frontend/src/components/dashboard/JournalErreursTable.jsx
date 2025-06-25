import React, { useState, useEffect, useCallback } from 'react';

const JournalErreursTable = () => {
  const [errorsLog, setErrorsLog] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(15);

  const [filters, setFilters] = useState({
    dateDebut: '',
    dateFin: '',
    sourceErreur: ''
  });
  const [activeFilters, setActiveFilters] = useState({});
  const [expandedTrace, setExpandedTrace] = useState(null); // id_erreur of the expanded trace
  const [expandedContext, setExpandedContext] = useState(null); // id_erreur of the expanded context


  const fetchErrorLog = useCallback(async (page, currentFilters) => {
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
      const response = await fetch(`${backendUrl}/api/dashboard/errors?${queryString}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.erreur || `Erreur HTTP: ${response.status}`);
      }
      const data = await response.json();
      if (data.succes) {
        setErrorsLog(data.donnees);
        setCurrentPage(data.pagination.page);
        setTotalPages(data.pagination.total_pages);
        setTotalItems(data.pagination.total_items);
      } else {
        throw new Error(data.erreur || "Erreur lors de la récupération du journal des erreurs.");
      }
    } catch (err) {
      setError(err.message);
      setErrorsLog([]);
      console.error("Erreur lors de la récupération du journal des erreurs:", err);
    } finally {
      setIsLoading(false);
    }
  }, [itemsPerPage]);

  useEffect(() => {
    fetchErrorLog(currentPage, activeFilters);
  }, [currentPage, activeFilters, fetchErrorLog]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleApplyFilters = () => {
    setCurrentPage(1);
    setActiveFilters(filters);
  };

  const handleClearFilters = () => {
    const clearedFilters = { dateDebut: '', dateFin: '', sourceErreur: '' };
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

  const toggleTrace = (id) => setExpandedTrace(expandedTrace === id ? null : id);
  const toggleContext = (id) => setExpandedContext(expandedContext === id ? null : id);

  // Styles (peuvent être externalisés)
  const filterContainerStyle = { marginBottom: '20px', padding: '15px', border: '1px solid #eee', borderRadius: '5px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' };
  const inputStyle = { marginRight: '10px', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' };
  const buttonStyle = { padding: '8px 15px', border: 'none', borderRadius: '4px', cursor: 'pointer' };
  const tableStyle = { width: '100%', borderCollapse: 'collapse', marginTop: '20px', tableLayout: 'fixed' };
  const thTdStyle = { border: '1px solid #ddd', padding: '10px', textAlign: 'left', wordBreak: 'break-word' };
  const thStyle = { ...thTdStyle, backgroundColor: '#f2f2f2', fontWeight: 'bold' };
  const paginationContainerStyle = { marginTop: '20px', textAlign: 'center' };
  const preStyle = { whiteSpace: 'pre-wrap', wordBreak: 'break-all', background:'#f0f0f0', padding:'10px', borderRadius:'5px', maxHeight:'200px', overflowY:'auto', marginTop:'5px' };


  if (isLoading) {
    return <p>Chargement du journal des erreurs...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Erreur de chargement du journal des erreurs : {error}</p>;
  }

  return (
    <div className="journal-erreurs-container">
      <h2>Journal des Erreurs Système ({totalItems} erreurs)</h2>

      <div style={filterContainerStyle}>
        <input type="date" name="dateDebut" value={filters.dateDebut} onChange={handleFilterChange} style={inputStyle} title="Date de début"/>
        <input type="date" name="dateFin" value={filters.dateFin} onChange={handleFilterChange} style={inputStyle} title="Date de fin"/>
        <input type="text" name="sourceErreur" placeholder="Source de l'erreur" value={filters.sourceErreur} onChange={handleFilterChange} style={inputStyle} />
        <button onClick={handleApplyFilters} style={{...buttonStyle, backgroundColor: '#007bff', color: 'white'}}>Appliquer Filtres</button>
        <button onClick={handleClearFilters} style={{...buttonStyle, backgroundColor: '#6c757d', color: 'white'}}>Effacer Filtres</button>
      </div>

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={{...thStyle, width: '15%'}}>Timestamp</th>
            <th style={{...thStyle, width: '10%'}}>ID Appel</th>
            <th style={{...thStyle, width: '20%'}}>Source</th>
            <th style={{...thStyle, width: '35%'}}>Message</th>
            <th style={{...thStyle, width: '10%'}}>Trace</th>
            <th style={{...thStyle, width: '10%'}}>Contexte</th>
          </tr>
        </thead>
        <tbody>
          {errorsLog.length > 0 ? errorsLog.map(log => (
            <React.Fragment key={log.id_erreur}>
              <tr>
                <td style={thTdStyle}>{formatDateTime(log.timestamp_erreur)}</td>
                <td style={thTdStyle}>{log.id_appel_fk || 'N/A'}</td>
                <td style={thTdStyle}>{log.source_erreur}</td>
                <td style={thTdStyle}>{log.message_erreur}</td>
                <td style={thTdStyle}>
                  {log.trace_erreur && (
                    <button onClick={() => toggleTrace(log.id_erreur)} style={{...buttonStyle, fontSize:'0.8em', padding:'3px 8px'}}>
                      {expandedTrace === log.id_erreur ? 'Cacher' : 'Voir'}
                    </button>
                  )}
                </td>
                <td style={thTdStyle}>
                  {log.contexte_supplementaire && (
                     <button onClick={() => toggleContext(log.id_erreur)} style={{...buttonStyle, fontSize:'0.8em', padding:'3px 8px'}}>
                       {expandedContext === log.id_erreur ? 'Cacher' : 'Voir'}
                     </button>
                  )}
                </td>
              </tr>
              {expandedTrace === log.id_erreur && log.trace_erreur && (
                <tr><td colSpan="6" style={thTdStyle}><pre style={preStyle}>{log.trace_erreur}</pre></td></tr>
              )}
              {expandedContext === log.id_erreur && log.contexte_supplementaire && (
                 <tr><td colSpan="6" style={thTdStyle}><pre style={preStyle}>{JSON.stringify(JSON.parse(log.contexte_supplementaire), null, 2)}</pre></td></tr>
              )}
            </React.Fragment>
          )) : (
            <tr>
              <td colSpan="6" style={{...thTdStyle, textAlign: 'center'}}>Aucune erreur trouvée pour les critères actuels.</td>
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

export default JournalErreursTable;
