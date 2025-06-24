import React from 'react';
import './InsightsPanel.css';

/**
 * Un composant pour afficher joliment le prompt envoyé au LLM.
 * @param {{ prompt: string }} props
 */
const FormattedPrompt = ({ prompt }) => {
  if (!prompt) {
    // Texte pour l'utilisateur, déjà en français.
    return <pre className="prompt-content">En attente de la prochaine action...</pre>;
  }
  return <pre className="prompt-content">{prompt}</pre>;
};

/**
 * Le panneau d'informations qui affiche les données en temps réel de l'agent.
 * @param {{ insights: object, duration: number }} props
 */
const InsightsPanel = ({ insights, duration }) => {
  // Définir des valeurs par défaut pour éviter les erreurs si les données ne sont pas encore arrivées
  const { kpis = {}, reasoning = {} } = insights;

  // Formate la durée de secondes en MM:SS
  const formatDuration = (totalSeconds) => {
    const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const seconds = (totalSeconds % 60).toString().padStart(2, '0');
    return `${minutes}:${seconds}`;
  };

  return (
    <aside className="insights-panel">
      <div className="panel-header">
        {/* Texte pour l'utilisateur, déjà en français */}
        <h2>Informations de l'Agent</h2>
      </div>
      <div className="panel-content">
        <div className="insight-card">
          <h3 className="card-title">
            {/* Texte pour l'utilisateur, déjà en français */}
            Durée de l'Appel
          </h3>
          <p className="duration-text">{formatDuration(duration)}</p>
        </div>

        <div className="insight-card">
          <h3 className="card-title">
            {/* Texte pour l'utilisateur, déjà en français */}
            Indicateurs de Performance (KPIs)
          </h3>
          <p className="kpi-text">
            {/* Texte pour l'utilisateur, déjà en français */}
            Appels Connectés: {kpis.call_started || 0}
          </p>
          {/* Vous pouvez ajouter d'autres KPIs ici au fur et à mesure que l'agent les envoie */}
        </div>

        <div className="insight-card">
          <h3 className="card-title">
            {/* Texte pour l'utilisateur, déjà en français */}
            Raisonnement de l'Agent
          </h3>
          <div className="reasoning-content">
            {/* Texte pour l'utilisateur, déjà en français */}
            <p><strong>Dernière Action:</strong></p>
            <p className="search-results-text">
              {/* Texte pour l'utilisateur, déjà en français */}
              {reasoning.search_results || "En attente d'une interaction..."}
            </p>
            {/* Texte pour l'utilisateur, déjà en français */}
            <p><strong>Prompt envoyé au Modèle:</strong></p>
            <FormattedPrompt prompt={reasoning.prompt} />
          </div>
        </div>
      </div>
    </aside>
  );
};

export default InsightsPanel;