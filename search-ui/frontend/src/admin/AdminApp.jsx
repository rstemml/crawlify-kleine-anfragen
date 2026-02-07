import { useCallback, useEffect, useMemo, useState } from 'react';
import { formatNumber, formatShortDate } from '../shared/format.js';

const API_BASE = '';

export default function AdminApp() {
  const [adminToken, setAdminToken] = useState(null);
  const [loginError, setLoginError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  const [overview, setOverview] = useState(null);

  const [vorgaengeSearch, setVorgaengeSearch] = useState('');
  const [vorgaengeRessort, setVorgaengeRessort] = useState('');
  const [vorgaengeStatus, setVorgaengeStatus] = useState('');
  const [vorgaengePage, setVorgaengePage] = useState(1);
  const [vorgaengeSortBy, setVorgaengeSortBy] = useState('datum');
  const [vorgaengeSortOrder, setVorgaengeSortOrder] = useState('desc');
  const [vorgaengeData, setVorgaengeData] = useState({ items: [], total: 0, pages: 0, limit: 50, offset: 0 });

  const [drucksachenPage, setDrucksachenPage] = useState(1);
  const [drucksachenVorgangId, setDrucksachenVorgangId] = useState('');
  const [drucksachenData, setDrucksachenData] = useState({ items: [], total: 0, pages: 0, limit: 50, offset: 0 });

  const [sqlQuery, setSqlQuery] = useState('');
  const [sqlResult, setSqlResult] = useState({ status: 'idle' });

  const [textModal, setTextModal] = useState({ open: false, title: '', content: '' });

  useEffect(() => {
    document.title = 'Admin - Kleine Anfragen';
    const stored = sessionStorage.getItem('adminToken');
    if (stored) {
      setAdminToken(stored);
    }
  }, []);

  const username = useMemo(() => {
    if (!adminToken) return '';
    try {
      const payload = JSON.parse(atob(adminToken.split('.')[1]));
      return payload.sub || '';
    } catch {
      return '';
    }
  }, [adminToken]);

  function handleExpiredToken() {
    sessionStorage.removeItem('adminToken');
    setAdminToken(null);
    setLoginError('Sitzung abgelaufen, bitte erneut anmelden');
  }

  const fetchWithAuth = useCallback(
    async (url, options = {}) => {
      const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${adminToken}`
        }
      });
      if (response.status === 401) {
        handleExpiredToken();
      }
      return response;
    },
    [adminToken]
  );

  const loadOverview = useCallback(async () => {
    try {
      const response = await fetchWithAuth('/api/admin/overview');
      if (!response.ok) return;
      const data = await response.json();
      setOverview(data);
    } catch (error) {
      console.error('Failed to load overview:', error);
    }
  }, [fetchWithAuth]);

  const loadVorgaenge = useCallback(async () => {
    const params = new URLSearchParams({
      limit: '50',
      offset: String((vorgaengePage - 1) * 50),
      sort_by: vorgaengeSortBy,
      sort_order: vorgaengeSortOrder
    });

    if (vorgaengeSearch) params.append('search', vorgaengeSearch);
    if (vorgaengeRessort) params.append('ressort', vorgaengeRessort);
    if (vorgaengeStatus) params.append('status', vorgaengeStatus);

    try {
      const response = await fetchWithAuth(`/api/admin/vorgaenge?${params}`);
      if (!response.ok) return;
      const data = await response.json();
      setVorgaengeData(data);
    } catch (error) {
      console.error('Failed to load vorgaenge:', error);
    }
  }, [
    fetchWithAuth,
    vorgaengePage,
    vorgaengeSortBy,
    vorgaengeSortOrder,
    vorgaengeSearch,
    vorgaengeRessort,
    vorgaengeStatus
  ]);

  const loadDrucksachen = useCallback(async () => {
    const params = new URLSearchParams({
      limit: '50',
      offset: String((drucksachenPage - 1) * 50)
    });

    if (drucksachenVorgangId) params.append('vorgang_id', drucksachenVorgangId);

    try {
      const response = await fetchWithAuth(`/api/admin/drucksachen?${params}`);
      if (!response.ok) return;
      const data = await response.json();
      setDrucksachenData(data);
    } catch (error) {
      console.error('Failed to load drucksachen:', error);
    }
  }, [fetchWithAuth, drucksachenPage, drucksachenVorgangId]);

  useEffect(() => {
    if (!adminToken) return;
    if (activeTab === 'overview') loadOverview();
  }, [adminToken, activeTab, loadOverview]);

  useEffect(() => {
    if (!adminToken || activeTab !== 'vorgaenge') return;
    const debounceId = setTimeout(() => {
      loadVorgaenge();
    }, 300);
    return () => clearTimeout(debounceId);
  }, [
    adminToken,
    activeTab,
    loadVorgaenge,
    vorgaengeSearch,
    vorgaengeRessort,
    vorgaengeStatus,
    vorgaengePage,
    vorgaengeSortBy,
    vorgaengeSortOrder
  ]);

  useEffect(() => {
    if (!adminToken || activeTab !== 'drucksachen') return;
    const debounceId = setTimeout(() => {
      loadDrucksachen();
    }, 300);
    return () => clearTimeout(debounceId);
  }, [adminToken, activeTab, loadDrucksachen, drucksachenPage, drucksachenVorgangId]);

  async function handleLogin(event) {
    event.preventDefault();
    setLoginError('');

    const usernameInput = event.target.elements.username.value;
    const passwordInput = event.target.elements.password.value;

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: usernameInput, password: passwordInput })
      });

      if (response.ok) {
        const data = await response.json();
        sessionStorage.setItem('adminToken', data.access_token);
        setAdminToken(data.access_token);
        setActiveTab('overview');
      } else {
        setLoginError('Ungueltige Anmeldedaten');
      }
    } catch (error) {
      setLoginError('Verbindungsfehler');
    }
  }

  function handleLogout() {
    sessionStorage.removeItem('adminToken');
    setAdminToken(null);
    setLoginError('');
    setActiveTab('overview');
  }

  function handleSort(sortBy) {
    setVorgaengePage(1);
    if (vorgaengeSortBy === sortBy) {
      setVorgaengeSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'));
    } else {
      setVorgaengeSortBy(sortBy);
      setVorgaengeSortOrder('desc');
    }
  }

  function handleTabChange(tab) {
    setActiveTab(tab);
  }

  function viewVorgangDrucksachen(vorgangId) {
    setActiveTab('drucksachen');
    setDrucksachenVorgangId(vorgangId);
    setDrucksachenPage(1);
  }

  async function viewText(drucksacheId) {
    try {
      const response = await fetchWithAuth(`/api/admin/drucksache-text/${drucksacheId}`);
      if (!response.ok) return;
      const data = await response.json();
      setTextModal({
        open: true,
        title: `Volltext - ${drucksacheId}`,
        content: data.volltext || 'Kein Text verfuegbar'
      });
    } catch (error) {
      console.error('Failed to load text:', error);
    }
  }

  function closeTextModal() {
    setTextModal({ open: false, title: '', content: '' });
  }

  async function executeSQL() {
    const query = sqlQuery.trim();
    if (!query) return;

    setSqlResult({ status: 'loading' });

    try {
      const response = await fetchWithAuth(
        `/api/admin/query?query=${encodeURIComponent(query)}&limit=100`,
        { method: 'POST' }
      );
      const data = await response.json();

      if (data.error) {
        setSqlResult({ status: 'error', message: data.error });
        return;
      }

      if (!data.rows || !data.rows.length) {
        setSqlResult({ status: 'empty' });
        return;
      }

      setSqlResult({
        status: 'success',
        columns: data.columns,
        rows: data.rows,
        count: data.count
      });
    } catch (error) {
      setSqlResult({ status: 'error', message: error.message });
    }
  }

  const ressortOptions = overview?.by_ressort || [];
  const statusOptions = overview?.by_status || [];

  if (!adminToken) {
    return (
      <div className="login-overlay">
        <div className="login-modal">
          <div className="login-header">
            <svg className="login-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <h2>Admin Login</h2>
          </div>
          <form className="login-form" onSubmit={handleLogin}>
            <div className="form-group">
              <label htmlFor="username">Benutzername</label>
              <input type="text" id="username" name="username" required autoComplete="username" />
            </div>
            <div className="form-group">
              <label htmlFor="password">Passwort</label>
              <input type="password" id="password" name="password" required autoComplete="current-password" />
            </div>
            <div className="login-error">{loginError}</div>
            <button type="submit" className="login-button">Anmelden</button>
          </form>
        </div>
      </div>
    );
  }

  const renderBarChart = (data, labelKey, valueKey) => {
    if (!data || !data.length) {
      return <p style={{ color: 'var(--text-muted)' }}>Keine Daten</p>;
    }

    const maxValue = Math.max(...data.map((item) => item[valueKey]));

    return data.map((item) => {
      const percent = (item[valueKey] / maxValue) * 100;
      return (
        <div className="bar-item" key={`${labelKey}-${item[labelKey]}`}>
          <span className="bar-label" title={item[labelKey]}>
            {item[labelKey]}
          </span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${percent}%` }}></div>
          </div>
          <span className="bar-value">{formatNumber(item[valueKey])}</span>
        </div>
      );
    });
  };

  const renderPagination = (data, onPageChange) => {
    const currentPage = Math.floor(data.offset / data.limit) + 1;
    const totalPages = data.pages;

    if (!totalPages || totalPages <= 1) {
      return null;
    }

    const pages = [];
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
      pages.push(1);
      if (startPage > 2) pages.push('...');
    }

    for (let i = startPage; i <= endPage; i += 1) {
      pages.push(i);
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) pages.push('...');
      pages.push(totalPages);
    }

    return (
      <div className="pagination">
        <button
          className="page-button"
          disabled={currentPage === 1}
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
        >
          &laquo; Zurueck
        </button>
        {pages.map((page, index) =>
          page === '...' ? (
            <span key={`dots-${index}`} className="page-info">
              ...
            </span>
          ) : (
            <button
              key={`page-${page}`}
              className={`page-button ${page === currentPage ? 'active' : ''}`}
              type="button"
              onClick={() => onPageChange(page)}
            >
              {page}
            </button>
          )
        )}
        <span className="page-info">{formatNumber(data.total)} Eintraege</span>
        <button
          className="page-button"
          disabled={currentPage === totalPages}
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
        >
          Weiter &raquo;
        </button>
      </div>
    );
  };

  return (
    <div className="admin-app">
      <header className="admin-header">
        <div className="header-left">
          <a href="/" className="back-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Zurueck zur Suche
          </a>
          <h1>Admin Dashboard</h1>
        </div>
        <div className="header-right">
          <span className="admin-user">{username}</span>
          <button className="logout-button" type="button" onClick={handleLogout}>
            Abmelden
          </button>
        </div>
      </header>

      <nav className="admin-nav">
        <button
          className={`nav-tab ${activeTab === 'overview' ? 'active' : ''}`}
          type="button"
          onClick={() => handleTabChange('overview')}
        >
          Uebersicht
        </button>
        <button
          className={`nav-tab ${activeTab === 'vorgaenge' ? 'active' : ''}`}
          type="button"
          onClick={() => handleTabChange('vorgaenge')}
        >
          Vorgaenge
        </button>
        <button
          className={`nav-tab ${activeTab === 'drucksachen' ? 'active' : ''}`}
          type="button"
          onClick={() => handleTabChange('drucksachen')}
        >
          Drucksachen
        </button>
        <button
          className={`nav-tab ${activeTab === 'sql' ? 'active' : ''}`}
          type="button"
          onClick={() => handleTabChange('sql')}
        >
          SQL Query
        </button>
      </nav>

      <main className="admin-content">
        <section className={`tab-content ${activeTab === 'overview' ? 'active' : ''}`}>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-label">Vorgaenge Gesamt</div>
              <div className="stat-card-value">
                {formatNumber(overview?.vorgaenge_total || 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Drucksachen Gesamt</div>
              <div className="stat-card-value">
                {formatNumber(overview?.drucksachen_total || 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Mit Embeddings</div>
              <div className="stat-card-value success">
                {formatNumber(overview?.with_embeddings || 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Ohne Embeddings</div>
              <div className="stat-card-value warning">
                {formatNumber(overview?.without_embeddings || 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Texte Gesamt</div>
              <div className="stat-card-value">
                {formatNumber(overview?.drucksache_texts_total || 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Mit Volltext</div>
              <div className="stat-card-value success">
                {formatNumber(overview?.text_coverage?.with_text || 0)}
              </div>
            </div>
          </div>

          <div className="charts-grid">
            <div className="chart-card">
              <h3>Nach Ressort</h3>
              <div className="bar-chart">
                {renderBarChart((overview?.by_ressort || []).slice(0, 8), 'name', 'count')}
              </div>
            </div>
            <div className="chart-card">
              <h3>Nach Status</h3>
              <div className="bar-chart">
                {renderBarChart(overview?.by_status || [], 'name', 'count')}
              </div>
            </div>
            <div className="chart-card">
              <h3>Nach Jahr</h3>
              <div className="bar-chart">
                {renderBarChart((overview?.by_year || []).slice(0, 10), 'year', 'count')}
              </div>
            </div>
            <div className="chart-card">
              <h3>Drucksache Typen</h3>
              <div className="bar-chart">
                {renderBarChart((overview?.drucksache_types || []).slice(0, 6), 'type', 'count')}
              </div>
            </div>
          </div>

          <div className="recent-section">
            <h3>Zuletzt aktualisiert</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Titel</th>
                  <th>Datum</th>
                  <th>Aktualisiert</th>
                </tr>
              </thead>
              <tbody>
                {(overview?.recent_vorgaenge || []).map((item) => (
                  <tr key={item.vorgang_id}>
                    <td>{item.vorgang_id}</td>
                    <td className="title-cell" title={item.titel || ''}>
                      {item.titel || '-'}
                    </td>
                    <td>{formatShortDate(item.datum)}</td>
                    <td>{formatShortDate(item.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className={`tab-content ${activeTab === 'vorgaenge' ? 'active' : ''}`}>
          <div className="toolbar">
            <input
              type="text"
              className="search-input"
              placeholder="Suchen..."
              value={vorgaengeSearch}
              onChange={(event) => {
                setVorgaengeSearch(event.target.value);
                setVorgaengePage(1);
              }}
            />
            <select
              className="filter-select"
              value={vorgaengeRessort}
              onChange={(event) => {
                setVorgaengeRessort(event.target.value);
                setVorgaengePage(1);
              }}
            >
              <option value="">Alle Ressorts</option>
              {ressortOptions.map((option) => (
                <option key={option.name} value={option.name}>
                  {option.name} ({option.count})
                </option>
              ))}
            </select>
            <select
              className="filter-select"
              value={vorgaengeStatus}
              onChange={(event) => {
                setVorgaengeStatus(event.target.value);
                setVorgaengePage(1);
              }}
            >
              <option value="">Alle Status</option>
              {statusOptions.map((option) => (
                <option key={option.name} value={option.name}>
                  {option.name} ({option.count})
                </option>
              ))}
            </select>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  {[
                    { label: 'ID', key: 'vorgang_id' },
                    { label: 'Titel', key: 'titel' },
                    { label: 'Datum', key: 'datum' },
                    { label: 'Ressort', key: 'ressort' },
                    { label: 'Status', key: 'beratungsstand' }
                  ].map((header) => {
                    const isSorted = vorgaengeSortBy === header.key;
                    const isAsc = isSorted && vorgaengeSortOrder === 'asc';
                    return (
                      <th
                        key={header.key}
                        className={`sortable ${isSorted ? 'sorted' : ''} ${isAsc ? 'asc' : ''}`}
                        onClick={() => handleSort(header.key)}
                      >
                        {header.label}
                      </th>
                    );
                  })}
                  <th>Embedding</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {vorgaengeData.items.map((item) => (
                  <tr key={item.vorgang_id}>
                    <td>{item.vorgang_id}</td>
                    <td className="title-cell" title={item.titel || ''}>
                      {item.titel || '-'}
                    </td>
                    <td>{formatShortDate(item.datum)}</td>
                    <td>{item.ressort || '-'}</td>
                    <td>
                      <span
                        className={`badge ${item.beratungsstand === 'Beantwortet' ? 'success' : 'warning'}`}
                      >
                        {item.beratungsstand || '-'}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${item.embedding_version ? 'success' : 'neutral'}`}>
                        {item.embedding_version ? 'Ja' : 'Nein'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="action-button"
                        type="button"
                        onClick={() => viewVorgangDrucksachen(item.vorgang_id)}
                      >
                        Dokumente
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {renderPagination(vorgaengeData, (page) => setVorgaengePage(page))}
        </section>

        <section className={`tab-content ${activeTab === 'drucksachen' ? 'active' : ''}`}>
          <div className="toolbar">
            <input
              type="text"
              className="search-input"
              placeholder="Vorgang ID filtern..."
              value={drucksachenVorgangId}
              onChange={(event) => {
                setDrucksachenVorgangId(event.target.value);
                setDrucksachenPage(1);
              }}
            />
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Vorgang ID</th>
                  <th>Titel</th>
                  <th>Typ</th>
                  <th>Nummer</th>
                  <th>Datum</th>
                  <th>Text</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {drucksachenData.items.map((item) => (
                  <tr key={item.drucksache_id}>
                    <td>{item.drucksache_id}</td>
                    <td>{item.vorgang_id}</td>
                    <td className="title-cell" title={item.titel || ''}>
                      {item.titel || '-'}
                    </td>
                    <td>{item.drucksachetyp || '-'}</td>
                    <td>{item.drucksache_nummer || '-'}</td>
                    <td>{formatShortDate(item.datum)}</td>
                    <td>
                      <span className={`badge ${item.has_text ? 'success' : 'neutral'}`}>
                        {item.has_text ? `${(item.text_length / 1000).toFixed(1)}k` : 'Nein'}
                      </span>
                    </td>
                    <td>
                      {item.dok_url ? (
                        <a href={item.dok_url} target="_blank" rel="noreferrer" className="action-button">
                          PDF
                        </a>
                      ) : null}
                      {item.has_text ? (
                        <button className="action-button" type="button" onClick={() => viewText(item.drucksache_id)}>
                          Text
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {renderPagination(drucksachenData, (page) => setDrucksachenPage(page))}
        </section>

        <section className={`tab-content ${activeTab === 'sql' ? 'active' : ''}`}>
          <div className="sql-editor">
            <label htmlFor="sql-input">SQL Query (nur SELECT)</label>
            <textarea
              id="sql-input"
              placeholder="SELECT * FROM vorgang LIMIT 10"
              value={sqlQuery}
              onChange={(event) => setSqlQuery(event.target.value)}
            ></textarea>
            <button className="execute-button" type="button" onClick={executeSQL}>
              Ausfuehren
            </button>
          </div>

          <div className="sql-result">
            {sqlResult.status === 'idle' ? (
              <p className="sql-hint">
                Verfuegbare Tabellen: <code>vorgang</code>, <code>drucksache</code>,{' '}
                <code>drucksache_text</code>
              </p>
            ) : null}
            {sqlResult.status === 'loading' ? <p>Ausfuehren...</p> : null}
            {sqlResult.status === 'error' ? (
              <div className="sql-error">{sqlResult.message}</div>
            ) : null}
            {sqlResult.status === 'empty' ? <p>Keine Ergebnisse</p> : null}
            {sqlResult.status === 'success' ? (
              <>
                <p style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>
                  {formatNumber(sqlResult.count)} Ergebnisse
                </p>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {sqlResult.columns.map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sqlResult.rows.map((row, rowIndex) => (
                        <tr key={`row-${rowIndex}`}>
                          {row.map((cell, cellIndex) => (
                            <td key={`cell-${rowIndex}-${cellIndex}`}>{String(cell ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </div>
        </section>
      </main>

      <div
        className={`modal-overlay ${textModal.open ? 'active' : ''}`}
        onClick={(event) => {
          if (event.target.classList.contains('modal-overlay')) closeTextModal();
        }}
      >
        <div className="modal text-modal">
          <div className="modal-header">
            <h3>{textModal.title}</h3>
            <button className="modal-close" type="button" onClick={closeTextModal}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
          <div className="modal-body">
            <pre>{textModal.content}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
