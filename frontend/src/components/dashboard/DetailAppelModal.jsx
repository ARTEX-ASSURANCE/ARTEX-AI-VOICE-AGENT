import React, { useState, useEffect } from 'react';

const DetailAppelModal = ({ id_appel, onClose }) => {
  const [callDetails, setCallDetails] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id_appel) {
      setIsLoading(false);
      return;
    }

    const fetchCallDetails = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5001';
        const response = await fetch(`${backendUrl}/api/dashboard/calls/${id_appel}`);

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.erreur || `Erreur HTTP: ${response.status}`);
        }
        const data = await response.json();
        if (data.succes) {
          setCallDetails(data.donnees);
        } else {
          throw new Error(data.erreur || "Erreur lors de la récupération des détails de l'appel.");
        }
      } catch (err) {
        setError(err.message);
        setCallDetails(null);
        console.error(`Erreur lors de la récupération des détails pour l'appel ID ${id_appel}:`, err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCallDetails();
  }, [id_appel]);

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      return new Date(isoString).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'medium' });
    } catch (e) { return 'Date invalide'; }
  };

  const formatDuration = (totalSeconds) => {
    if (totalSeconds === null || totalSeconds === undefined) return 'N/A';
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${minutes}m ${seconds}s`;
  };

  const renderJsonParameters = (params) => {
    if (!params) return 'N/A';
    try {
      const parsed = typeof params === 'string' ? JSON.parse(params) : params;
      // Simple display, can be improved
      return <pre style={{whiteSpace: 'pre-wrap', wordBreak: 'break-all', background:'#f9f9f9', padding:'5px', borderRadius:'3px', maxHeight:'100px', overflowY:'auto'}}>{JSON.stringify(parsed, null, 2)}</pre>;
    } catch (e) {
      return String(params); // Show as string if not valid JSON
    }
  };


  // Styles (peuvent être externalisés)
  const modalOverlayStyle = {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  };
  const modalContentStyle = {
    backgroundColor: 'white', padding: '25px', borderRadius: '8px',
    width: '80%', maxWidth: '900px', maxHeight: '85vh', overflowY: 'auto',
    boxShadow: '0 5px 15px rgba(0,0,0,0.3)',
  };
  const sectionTitleStyle = { marginTop: '20px', marginBottom: '10px', fontSize: '1.3em', borderBottom: '1px solid #eee', paddingBottom: '5px', color: '#007bff' };
  const detailItemStyle = { marginBottom: '8px' };
  const labelStyle = { fontWeight: 'bold', marginRight: '8px', color: '#555'};
  const tableStyle = { width: '100%', borderCollapse: 'collapse', fontSize: '0.9em' };
  const thTdStyle = { border: '1px solid #ddd', padding: '8px', textAlign: 'left', verticalAlign: 'top' };
  const thStyle = { ...thTdStyle, backgroundColor: '#f2f2f2', fontWeight: 'bold' };


  if (!id_appel) return null; // Ne rien rendre si aucun ID d'appel n'est sélectionné

  return (
    <div style={modalOverlayStyle} onClick={onClose}> {/* Cliquer hors du contenu ferme la modale */}
      <div style={modalContentStyle} onClick={e => e.stopPropagation()}> {/* Empêcher la fermeture en cliquant sur le contenu */}
        {isLoading && <p>Chargement des détails de l'appel...</p>}
        {error && <p style={{ color: 'red' }}>Erreur: {error}</p>}
        {!isLoading && !error && !callDetails && <p>Aucun détail trouvé pour cet appel.</p>}

        {callDetails && (
          <>
            <h2 style={{marginTop:0, color:'#333', borderBottom:'2px solid #007bff', paddingBottom:'10px'}}>Détails de l'Appel ID: {callDetails.informations_appel?.id_appel}</h2>

            <section>
              <h3 style={sectionTitleStyle}>Informations Générales</h3>
              <p style={detailItemStyle}><span style={labelStyle}>ID LiveKit Room:</span> {callDetails.informations_appel?.id_livekit_room || 'N/A'}</p>
              <p style={detailItemStyle}><span style={labelStyle}>Début:</span> {formatDateTime(callDetails.informations_appel?.timestamp_debut)}</p>
              <p style={detailItemStyle}><span style={labelStyle}>Fin:</span> {formatDateTime(callDetails.informations_appel?.timestamp_fin)}</p>
              <p style={detailItemStyle}><span style={labelStyle}>Durée:</span> {formatDuration(callDetails.informations_appel?.duree_secondes)}</p>
              <p style={detailItemStyle}><span style={labelStyle}>Numéro Appelant:</span> {callDetails.informations_appel?.numero_appelant || 'N/A'}</p>
              <p style={detailItemStyle}><span style={labelStyle}>Adhérent Identifié:</span>
                {callDetails.informations_appel?.id_adherent_contexte
                  ? `${callDetails.informations_appel.prenom || ''} ${callDetails.informations_appel.nom || ''} (ID: ${callDetails.informations_appel.id_adherent_contexte})`
                  : 'Non identifié'}
              </p>
              <p style={detailItemStyle}><span style={labelStyle}>Résumé de l'appel:</span></p>
              <p style={{marginLeft:'10px', fontStyle:'italic', background:'#f9f9f9', padding:'10px', borderRadius:'3px'}}>{callDetails.informations_appel?.resume_appel || 'Non disponible'}</p>

              <h4 style={{...labelStyle, marginTop:'15px'}}>Évaluation de Performance:</h4>
              <p style={detailItemStyle}><span style={labelStyle}>Adhérence aux Instructions:</span> {callDetails.informations_appel?.evaluation_performance_prompt || 'Non évalué'}</p>
              <p style={detailItemStyle}><span style={labelStyle}>Résolution de l'Appel:</span> {callDetails.informations_appel?.evaluation_resolution_appel || 'Non évalué'}</p>
            </section>

            {callDetails.actions_agent && callDetails.actions_agent.length > 0 && (
              <section>
                <h3 style={sectionTitleStyle}>Actions de l'Agent</h3>
                <table style={tableStyle}>
                  <thead><tr><th style={thStyle}>Timestamp</th><th style={thStyle}>Type</th><th style={thStyle}>Outil/Détail</th><th style={thStyle}>Paramètres</th><th style={thStyle}>Résultat/Message</th></tr></thead>
                  <tbody>
                    {callDetails.actions_agent.map(action => (
                      <tr key={action.id_action}>
                        <td style={thTdStyle}>{formatDateTime(action.timestamp_action)}</td>
                        <td style={thTdStyle}>{action.type_action}</td>
                        <td style={thTdStyle}>{action.nom_outil || action.detail_evenement || 'N/A'}</td>
                        <td style={thTdStyle}>{renderJsonParameters(action.parametres_outil)}</td>
                        <td style={thTdStyle}>{action.resultat_outil || action.message_dit || 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            {callDetails.interactions_bd && callDetails.interactions_bd.length > 0 && (
              <section>
                <h3 style={sectionTitleStyle}>Interactions Base de Données</h3>
                <table style={tableStyle}>
                  <thead><tr><th style={thStyle}>Timestamp</th><th style={thStyle}>Type Requête</th><th style={thStyle}>Table Affectée</th><th style={thStyle}>Description</th></tr></thead>
                  <tbody>
                    {callDetails.interactions_bd.map(interaction => (
                      <tr key={interaction.id_interaction_bd}>
                        <td style={thTdStyle}>{formatDateTime(interaction.timestamp_interaction)}</td>
                        <td style={thTdStyle}>{interaction.type_requete}</td>
                        <td style={thTdStyle}>{interaction.table_affectee}</td>
                        <td style={thTdStyle}>{interaction.description_action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            {callDetails.erreurs_appel && callDetails.erreurs_appel.length > 0 && (
              <section>
                <h3 style={sectionTitleStyle}>Erreurs Pendant l'Appel</h3>
                <table style={tableStyle}>
                  <thead><tr><th style={thStyle}>Timestamp</th><th style={thStyle}>Source</th><th style={thStyle}>Message</th></tr></thead>
                  <tbody>
                    {callDetails.erreurs_appel.map(erreur => (
                      <tr key={erreur.id_erreur}>
                        <td style={thTdStyle}>{formatDateTime(erreur.timestamp_erreur)}</td>
                        <td style={thTdStyle}>{erreur.source_erreur}</td>
                        <td style={thTdStyle} title={erreur.trace_erreur || ''}>{erreur.message_erreur}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            <button onClick={onClose} style={{ marginTop: '20px', padding: '10px 15px', backgroundColor:'#6c757d', color:'white', border:'none', borderRadius:'4px', cursor:'pointer' }}>
              Fermer
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default DetailAppelModal;
