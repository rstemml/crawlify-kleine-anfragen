import { useEffect, useMemo, useRef, useState } from 'react';
import { formatDate, formatNumber } from '../shared/format.js';

const API_BASE = '';

export default function SearchApp() {
  const [conversationId, setConversationId] = useState(null);
  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [searchInput, setSearchInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [results, setResults] = useState([]);
  const [filters, setFilters] = useState({ ressort: '', status: '' });
  const [hasSearched, setHasSearched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const messagesRef = useRef(null);

  useEffect(() => {
    document.title = 'Kleine Anfragen – Semantische Suche';
    loadStats();
  }, []);

  useEffect(() => {
    const container = messagesRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') closeModal();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const filteredResults = useMemo(() => {
    let filtered = results;
    if (filters.ressort) {
      filtered = filtered.filter((r) => r.ressort === filters.ressort);
    }
    if (filters.status) {
      filtered = filtered.filter((r) => r.beratungsstand === filters.status);
    }
    return filtered;
  }, [results, filters]);

  async function loadStats() {
    try {
      const response = await fetch(`${API_BASE}/api/stats`);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  }

  function addMessage(role, content) {
    setMessages((prev) => [...prev, { role, content }]);
  }

  async function search(query) {
    if (isLoading) return;
    setIsLoading(true);
    setHasSearched(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          conversation_id: conversationId
        })
      });

      const data = await response.json();
      setConversationId(data.conversation_id || null);

      if (data.message) {
        addMessage('assistant', data.message);
      }

      setResults(data.results || []);
      setSuggestions(data.refinement_questions || []);
    } catch (error) {
      console.error('Search failed:', error);
      addMessage(
        'assistant',
        'Es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.'
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function loadVorgangDetail(vorgangId) {
    try {
      const response = await fetch(`${API_BASE}/api/vorgang/${vorgangId}`);
      const data = await response.json();
      setDetail(data);
      setIsModalOpen(true);
    } catch (error) {
      console.error('Failed to load detail:', error);
    }
  }

  function handleSearchSubmit(event) {
    event.preventDefault();
    const query = searchInput.trim();
    if (!query) return;
    addMessage('user', query);
    setSearchInput('');
    search(query);
  }

  function handleSuggestionClick(suggestion) {
    let query = suggestion;

    if (suggestion.includes('eingrenzen')) {
      const match = suggestion.match(/'([^']+)'/);
      if (match) {
        setFilters((prev) => ({ ...prev, ressort: match[1] }));
        return;
      }
    }

    if (suggestion.includes('suchen')) {
      const match = suggestion.match(/'([^']+)'/);
      if (match) query = match[1];
    }

    if (suggestion.includes('beantwortete')) {
      setFilters((prev) => ({ ...prev, status: 'Beantwortet' }));
      return;
    }

    if (query) {
      addMessage('user', query);
      setSearchInput('');
      search(query);
    }
  }

  function closeModal() {
    setIsModalOpen(false);
    setDetail(null);
  }

  const resultsCount = results.length;

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <svg
              className="logo-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
            <span className="logo-text">Kleine Anfragen</span>
          </div>
          <div className="header-stats">
            {stats && (
              <>
                <div className="header-stat">
                  <span className="header-stat-value">
                    {formatNumber(stats.total_vorgaenge)}
                  </span>
                  <span>Anfragen</span>
                </div>
                <div className="header-stat">
                  <span className="header-stat-value">
                    {formatNumber(stats.total_drucksachen)}
                  </span>
                  <span>Dokumente</span>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="main-content">
        <div className="search-hero">
          <h1 className="search-hero-title">
            Parlamentarische Anfragen durchsuchen
          </h1>
          <p className="search-hero-subtitle">
            Semantische Suche ueber {stats ? formatNumber(stats.total_vorgaenge) : '...'} Kleine
            Anfragen des Deutschen Bundestages. Stellen Sie Ihre Frage in natuerlicher Sprache.
          </p>

          <form className="search-form" onSubmit={handleSearchSubmit}>
            <input
              type="text"
              className="search-input"
              placeholder="z.B. Klimaschutz, Waffenexporte, Gesundheitspolitik..."
              autoComplete="off"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <button type="submit" className="search-submit" disabled={isLoading}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              Suchen
            </button>
          </form>
        </div>

        {messages.length > 0 && (
          <div className="chat-thread" ref={messagesRef}>
            <div className="chat-messages">
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
                  <div className="message-avatar">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      {message.role === 'user' ? (
                        <>
                          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                          <circle cx="12" cy="7" r="4" />
                        </>
                      ) : (
                        <>
                          <circle cx="12" cy="12" r="10" />
                          <path d="M8 14s1.5 2 4 2 4-2 4-2" />
                          <line x1="9" y1="9" x2="9.01" y2="9" />
                          <line x1="15" y1="9" x2="15.01" y2="9" />
                        </>
                      )}
                    </svg>
                  </div>
                  <div className="message-content">
                    {message.content
                      .split('\n')
                      .filter(Boolean)
                      .map((line, i) => (
                        <p key={`${index}-${i}`}>{line}</p>
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {suggestions.length > 0 && (
          <div className="refinement-suggestions">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                className="refinement-suggestion"
                type="button"
                onClick={() => handleSuggestionClick(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <section className="results-section">
          <div className="results-header">
            <h2 className="results-title">
              {hasSearched ? 'Ergebnisse' : 'Suchergebnisse'}
            </h2>
            {hasSearched ? (
              <p className="results-subtitle">
                <span className="results-count">{resultsCount}</span> relevante
                Anfragen gefunden
              </p>
            ) : (
              <p className="results-subtitle">
                Geben Sie eine Suchanfrage ein, um zu starten
              </p>
            )}
          </div>

          {hasSearched && (
            <div className="results-filters">
              <select
                className="filter-select"
                value={filters.ressort}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, ressort: e.target.value }))
                }
              >
                <option value="">Alle Ressorts</option>
                {(stats?.ressorts || []).map((ressort) => (
                  <option key={ressort.name} value={ressort.name}>
                    {ressort.name} ({ressort.count})
                  </option>
                ))}
              </select>
              <select
                className="filter-select"
                value={filters.status}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, status: e.target.value }))
                }
              >
                <option value="">Alle Status</option>
                <option value="Beantwortet">Beantwortet</option>
                <option value="Noch nicht beantwortet">Noch nicht beantwortet</option>
              </select>
            </div>
          )}

          <div className="results-container">
            {isLoading ? (
              <div className="loading">
                <div className="loading-spinner" />
                <span className="loading-text">Suche laeuft...</span>
              </div>
            ) : !hasSearched ? (
              <div className="empty-state">
                <svg
                  className="empty-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <p>Die semantische Suche versteht natuerliche Sprache</p>
                <p className="empty-hint">
                  Formulieren Sie Ihre Frage, als wuerden Sie einen Experten fragen
                </p>
              </div>
            ) : filteredResults.length === 0 ? (
              <div className="empty-state">
                <svg
                  className="empty-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                <p>Keine Ergebnisse mit diesen Filtern</p>
              </div>
            ) : (
              filteredResults.map((result) => {
                const scoreClass =
                  result.score > 0.7 ? 'high' : result.score > 0.5 ? 'medium' : '';
                const scorePercent = Math.round(result.score * 100);
                const isAnswered = result.beratungsstand === 'Beantwortet';
                const statusClass = isAnswered ? 'answered' : 'pending';
                const statusText = isAnswered ? 'Beantwortet' : 'Offen';
                const tags = (result.schlagworte || []).slice(0, 4);

                return (
                  <div
                    key={result.vorgang_id}
                    className="result-card"
                    role="button"
                    tabIndex={0}
                    onClick={() => loadVorgangDetail(result.vorgang_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') loadVorgangDetail(result.vorgang_id);
                    }}
                  >
                    <div className="result-card-header">
                      <h3 className="result-card-title">
                        {result.titel || 'Ohne Titel'}
                      </h3>
                      <span className={`result-card-score ${scoreClass}`}>
                        {scorePercent}%
                      </span>
                    </div>

                    <div className="result-card-meta">
                      {result.datum && (
                        <span className="result-card-meta-item">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                            <line x1="16" y1="2" x2="16" y2="6" />
                            <line x1="8" y1="2" x2="8" y2="6" />
                            <line x1="3" y1="10" x2="21" y2="10" />
                          </svg>
                          {formatDate(result.datum)}
                        </span>
                      )}
                      {result.ressort && (
                        <span className="result-card-meta-item">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                          </svg>
                          {result.ressort}
                        </span>
                      )}
                    </div>

                    {result.highlight && (
                      <div className="result-card-highlight">{result.highlight}</div>
                    )}

                    {tags.length > 0 && (
                      <div className="result-card-tags">
                        {tags.map((tag) => (
                          <span key={tag} className="result-card-tag">{tag}</span>
                        ))}
                      </div>
                    )}

                    <div className="result-card-status">
                      <span className={`status-badge ${statusClass}`}>{statusText}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </main>

      <footer className="site-footer">
        Daten vom Dokumentations- und Informationssystem des Deutschen Bundestages (DIP)
      </footer>

      <div
        className={`modal-overlay ${isModalOpen ? 'active' : ''}`}
        onClick={(e) => {
          if (e.target.classList.contains('modal-overlay')) closeModal();
        }}
      >
        <div className="modal">
          <button className="modal-close" type="button" onClick={closeModal}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
          <div className="modal-content">
            {detail && (
              <>
                <h2 className="modal-title">{detail.titel || 'Ohne Titel'}</h2>

                <div className="modal-meta">
                  <div className="modal-meta-item">
                    <div className="modal-meta-label">Datum</div>
                    <div className="modal-meta-value">
                      {detail.datum ? formatDate(detail.datum) : '-'}
                    </div>
                  </div>
                  <div className="modal-meta-item">
                    <div className="modal-meta-label">Status</div>
                    <div className="modal-meta-value">
                      {detail.beratungsstand || '-'}
                    </div>
                  </div>
                  <div className="modal-meta-item">
                    <div className="modal-meta-label">Ressort</div>
                    <div className="modal-meta-value">{detail.ressort || '-'}</div>
                  </div>
                  <div className="modal-meta-item">
                    <div className="modal-meta-label">Wahlperiode</div>
                    <div className="modal-meta-value">{detail.legislature || '-'}</div>
                  </div>
                </div>

                <div className="modal-section">
                  <div className="modal-section-title">Initiatoren</div>
                  <p className="modal-text">
                    {detail.initiatoren?.length
                      ? detail.initiatoren.join(', ')
                      : 'Nicht angegeben'}
                  </p>
                </div>

                {detail.abstrakt && (
                  <div className="modal-section">
                    <div className="modal-section-title">Zusammenfassung</div>
                    <p className="modal-text">{detail.abstrakt}</p>
                  </div>
                )}

                {detail.schlagworte?.length > 0 && (
                  <div className="modal-section">
                    <div className="modal-section-title">Schlagworte</div>
                    <div className="result-card-tags">
                      {detail.schlagworte.map((tag) => (
                        <span key={tag} className="result-card-tag">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="modal-section">
                  <div className="modal-section-title">Dokumente</div>
                  <div className="document-list">
                    {detail.drucksachen?.length > 0 ? (
                      detail.drucksachen.map((doc) => (
                        <div
                          key={doc.drucksache_id || doc.dok_url}
                          className="document-item"
                        >
                          <div className="document-info">
                            <div className="document-title">
                              {doc.titel || doc.drucksachetyp || 'Dokument'}
                            </div>
                            <div className="document-meta">
                              {doc.drucksache_nummer || ''}
                              {doc.datum ? ` · ${formatDate(doc.datum)}` : ''}
                            </div>
                          </div>
                          {doc.dok_url && (
                            <a
                              href={doc.dok_url}
                              target="_blank"
                              rel="noreferrer"
                              className="document-link"
                            >
                              PDF
                            </a>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="modal-text">Keine Dokumente verfuegbar</p>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
