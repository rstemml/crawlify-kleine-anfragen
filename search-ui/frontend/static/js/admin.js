/**
 * Admin Dashboard for Kleine Anfragen
 */

const API_BASE = '';

// State
let authCredentials = null;
let vorgaengeState = { page: 1, sortBy: 'datum', sortOrder: 'desc' };
let drucksachenState = { page: 1 };

// DOM Elements
const loginOverlay = document.getElementById('login-overlay');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const adminApp = document.getElementById('admin-app');
const adminUser = document.getElementById('admin-user');
const logoutButton = document.getElementById('logout-button');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check for stored credentials
    const stored = sessionStorage.getItem('adminAuth');
    if (stored) {
        authCredentials = stored;
        showAdminApp();
    }

    setupEventListeners();
});

function setupEventListeners() {
    // Login form
    loginForm.addEventListener('submit', handleLogin);

    // Logout
    logoutButton.addEventListener('click', handleLogout);

    // Tab navigation
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Vorgaenge filters
    document.getElementById('vorgang-search').addEventListener('input', debounce(loadVorgaenge, 300));
    document.getElementById('vorgang-ressort').addEventListener('change', loadVorgaenge);
    document.getElementById('vorgang-status').addEventListener('change', loadVorgaenge);

    // Vorgaenge sorting
    document.querySelectorAll('#vorgaenge-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const sortBy = th.dataset.sort;
            if (vorgaengeState.sortBy === sortBy) {
                vorgaengeState.sortOrder = vorgaengeState.sortOrder === 'desc' ? 'asc' : 'desc';
            } else {
                vorgaengeState.sortBy = sortBy;
                vorgaengeState.sortOrder = 'desc';
            }
            vorgaengeState.page = 1;
            loadVorgaenge();
        });
    });

    // Drucksachen filter
    document.getElementById('drucksache-vorgang').addEventListener('input', debounce(loadDrucksachen, 300));

    // SQL execute
    document.getElementById('sql-execute').addEventListener('click', executeSQL);

    // Text modal close
    document.getElementById('text-modal-close').addEventListener('click', closeTextModal);
    document.getElementById('text-modal-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'text-modal-overlay') closeTextModal();
    });
}

// === Authentication ===

async function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    authCredentials = btoa(`${username}:${password}`);

    try {
        const response = await fetchWithAuth('/api/admin/overview');
        if (response.ok) {
            sessionStorage.setItem('adminAuth', authCredentials);
            showAdminApp();
        } else {
            loginError.textContent = 'Ungueltige Anmeldedaten';
            authCredentials = null;
        }
    } catch (error) {
        loginError.textContent = 'Verbindungsfehler';
        authCredentials = null;
    }
}

function handleLogout() {
    authCredentials = null;
    sessionStorage.removeItem('adminAuth');
    loginOverlay.style.display = 'flex';
    adminApp.style.display = 'none';
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    loginError.textContent = '';
}

async function fetchWithAuth(url, options = {}) {
    return fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Basic ${authCredentials}`
        }
    });
}

// === App Display ===

async function showAdminApp() {
    loginOverlay.style.display = 'none';
    adminApp.style.display = 'flex';

    // Decode username for display
    const decoded = atob(authCredentials);
    const username = decoded.split(':')[0];
    adminUser.textContent = username;

    // Load initial data
    await loadOverview();
}

function switchTab(tabId) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(`tab-${tabId}`).classList.add('active');

    // Load tab data
    if (tabId === 'overview') loadOverview();
    else if (tabId === 'vorgaenge') loadVorgaenge();
    else if (tabId === 'drucksachen') loadDrucksachen();
}

// === Overview Tab ===

async function loadOverview() {
    try {
        const response = await fetchWithAuth('/api/admin/overview');
        const data = await response.json();

        renderStats(data);
        renderCharts(data);
        renderRecentTable(data.recent_vorgaenge);
        populateFilters(data);
    } catch (error) {
        console.error('Failed to load overview:', error);
    }
}

function renderStats(data) {
    const grid = document.getElementById('stats-grid');
    grid.innerHTML = `
        <div class="stat-card">
            <div class="stat-card-label">Vorgaenge Gesamt</div>
            <div class="stat-card-value">${data.vorgaenge_total.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <div class="stat-card-label">Drucksachen Gesamt</div>
            <div class="stat-card-value">${data.drucksachen_total.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <div class="stat-card-label">Mit Embeddings</div>
            <div class="stat-card-value success">${data.with_embeddings.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <div class="stat-card-label">Ohne Embeddings</div>
            <div class="stat-card-value warning">${data.without_embeddings.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <div class="stat-card-label">Texte Gesamt</div>
            <div class="stat-card-value">${data.drucksache_texts_total.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <div class="stat-card-label">Mit Volltext</div>
            <div class="stat-card-value success">${data.text_coverage.with_text.toLocaleString()}</div>
        </div>
    `;
}

function renderCharts(data) {
    renderBarChart('chart-ressort', data.by_ressort.slice(0, 8), 'name', 'count');
    renderBarChart('chart-status', data.by_status, 'name', 'count');
    renderBarChart('chart-year', data.by_year.slice(0, 10), 'year', 'count');
    renderBarChart('chart-types', data.drucksache_types.slice(0, 6), 'type', 'count');
}

function renderBarChart(containerId, data, labelKey, valueKey) {
    const container = document.getElementById(containerId);
    if (!data || !data.length) {
        container.innerHTML = '<p style="color: var(--text-muted);">Keine Daten</p>';
        return;
    }

    const maxValue = Math.max(...data.map(d => d[valueKey]));

    container.innerHTML = data.map(item => {
        const percent = (item[valueKey] / maxValue) * 100;
        return `
            <div class="bar-item">
                <span class="bar-label" title="${item[labelKey]}">${item[labelKey]}</span>
                <div class="bar-track">
                    <div class="bar-fill" style="width: ${percent}%"></div>
                </div>
                <span class="bar-value">${item[valueKey].toLocaleString()}</span>
            </div>
        `;
    }).join('');
}

function renderRecentTable(items) {
    const tbody = document.querySelector('#recent-table tbody');
    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${item.vorgang_id}</td>
            <td class="title-cell" title="${escapeHtml(item.titel || '')}">${escapeHtml(item.titel || '-')}</td>
            <td>${formatDate(item.datum)}</td>
            <td>${formatDate(item.updated_at)}</td>
        </tr>
    `).join('');
}

function populateFilters(data) {
    // Ressort filter
    const ressortSelect = document.getElementById('vorgang-ressort');
    const currentRessort = ressortSelect.value;
    ressortSelect.innerHTML = '<option value="">Alle Ressorts</option>';
    data.by_ressort.forEach(r => {
        const option = document.createElement('option');
        option.value = r.name;
        option.textContent = `${r.name} (${r.count})`;
        ressortSelect.appendChild(option);
    });
    ressortSelect.value = currentRessort;

    // Status filter
    const statusSelect = document.getElementById('vorgang-status');
    const currentStatus = statusSelect.value;
    statusSelect.innerHTML = '<option value="">Alle Status</option>';
    data.by_status.forEach(s => {
        const option = document.createElement('option');
        option.value = s.name;
        option.textContent = `${s.name} (${s.count})`;
        statusSelect.appendChild(option);
    });
    statusSelect.value = currentStatus;
}

// === Vorgaenge Tab ===

async function loadVorgaenge() {
    const search = document.getElementById('vorgang-search').value;
    const ressort = document.getElementById('vorgang-ressort').value;
    const status = document.getElementById('vorgang-status').value;

    const params = new URLSearchParams({
        limit: 50,
        offset: (vorgaengeState.page - 1) * 50,
        sort_by: vorgaengeState.sortBy,
        sort_order: vorgaengeState.sortOrder
    });

    if (search) params.append('search', search);
    if (ressort) params.append('ressort', ressort);
    if (status) params.append('status', status);

    try {
        const response = await fetchWithAuth(`/api/admin/vorgaenge?${params}`);
        const data = await response.json();
        renderVorgaengeTable(data);
        renderPagination('vorgaenge-pagination', data, (page) => {
            vorgaengeState.page = page;
            loadVorgaenge();
        });
        updateSortIndicators();
    } catch (error) {
        console.error('Failed to load vorgaenge:', error);
    }
}

function renderVorgaengeTable(data) {
    const tbody = document.querySelector('#vorgaenge-table tbody');
    tbody.innerHTML = data.items.map(item => `
        <tr>
            <td>${item.vorgang_id}</td>
            <td class="title-cell" title="${escapeHtml(item.titel || '')}">${escapeHtml(item.titel || '-')}</td>
            <td>${formatDate(item.datum)}</td>
            <td>${escapeHtml(item.ressort || '-')}</td>
            <td>
                <span class="badge ${item.beratungsstand === 'Beantwortet' ? 'success' : 'warning'}">
                    ${escapeHtml(item.beratungsstand || '-')}
                </span>
            </td>
            <td>
                <span class="badge ${item.embedding_version ? 'success' : 'neutral'}">
                    ${item.embedding_version ? 'Ja' : 'Nein'}
                </span>
            </td>
            <td>
                <button class="action-button" onclick="viewVorgangDrucksachen('${item.vorgang_id}')">
                    Dokumente
                </button>
            </td>
        </tr>
    `).join('');
}

function updateSortIndicators() {
    document.querySelectorAll('#vorgaenge-table th.sortable').forEach(th => {
        th.classList.remove('sorted', 'asc');
        if (th.dataset.sort === vorgaengeState.sortBy) {
            th.classList.add('sorted');
            if (vorgaengeState.sortOrder === 'asc') {
                th.classList.add('asc');
            }
        }
    });
}

function viewVorgangDrucksachen(vorgangId) {
    document.getElementById('drucksache-vorgang').value = vorgangId;
    switchTab('drucksachen');
    loadDrucksachen();
}

// === Drucksachen Tab ===

async function loadDrucksachen() {
    const vorgangId = document.getElementById('drucksache-vorgang').value;

    const params = new URLSearchParams({
        limit: 50,
        offset: (drucksachenState.page - 1) * 50
    });

    if (vorgangId) params.append('vorgang_id', vorgangId);

    try {
        const response = await fetchWithAuth(`/api/admin/drucksachen?${params}`);
        const data = await response.json();
        renderDrucksachenTable(data);
        renderPagination('drucksachen-pagination', data, (page) => {
            drucksachenState.page = page;
            loadDrucksachen();
        });
    } catch (error) {
        console.error('Failed to load drucksachen:', error);
    }
}

function renderDrucksachenTable(data) {
    const tbody = document.querySelector('#drucksachen-table tbody');
    tbody.innerHTML = data.items.map(item => `
        <tr>
            <td>${item.drucksache_id}</td>
            <td>${item.vorgang_id}</td>
            <td class="title-cell" title="${escapeHtml(item.titel || '')}">${escapeHtml(item.titel || '-')}</td>
            <td>${escapeHtml(item.drucksachetyp || '-')}</td>
            <td>${escapeHtml(item.drucksache_nummer || '-')}</td>
            <td>${formatDate(item.datum)}</td>
            <td>
                <span class="badge ${item.has_text ? 'success' : 'neutral'}">
                    ${item.has_text ? `${(item.text_length / 1000).toFixed(1)}k` : 'Nein'}
                </span>
            </td>
            <td>
                ${item.dok_url ? `<a href="${item.dok_url}" target="_blank" class="action-button">PDF</a>` : ''}
                ${item.has_text ? `<button class="action-button" onclick="viewText('${item.drucksache_id}')">Text</button>` : ''}
            </td>
        </tr>
    `).join('');
}

async function viewText(drucksacheId) {
    try {
        const response = await fetchWithAuth(`/api/admin/drucksache-text/${drucksacheId}`);
        const data = await response.json();

        document.getElementById('text-modal-title').textContent = `Volltext - ${drucksacheId}`;
        document.getElementById('text-modal-content').textContent = data.volltext || 'Kein Text verfuegbar';
        document.getElementById('text-modal-overlay').classList.add('active');
    } catch (error) {
        console.error('Failed to load text:', error);
    }
}

function closeTextModal() {
    document.getElementById('text-modal-overlay').classList.remove('active');
}

// === SQL Tab ===

async function executeSQL() {
    const query = document.getElementById('sql-input').value.trim();
    if (!query) return;

    const resultDiv = document.getElementById('sql-result');
    resultDiv.innerHTML = '<p>Ausfuehren...</p>';

    try {
        const response = await fetchWithAuth(`/api/admin/query?query=${encodeURIComponent(query)}&limit=100`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.error) {
            resultDiv.innerHTML = `<div class="sql-error">${escapeHtml(data.error)}</div>`;
            return;
        }

        if (!data.rows || !data.rows.length) {
            resultDiv.innerHTML = '<p>Keine Ergebnisse</p>';
            return;
        }

        resultDiv.innerHTML = `
            <p style="margin-bottom: 12px; color: var(--text-secondary);">${data.count} Ergebnisse</p>
            <div class="table-container">
                <table class="data-table">
                    <thead>
                        <tr>
                            ${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${data.rows.map(row => `
                            <tr>
                                ${row.map(cell => `<td>${escapeHtml(String(cell ?? ''))}</td>`).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        resultDiv.innerHTML = `<div class="sql-error">Fehler: ${escapeHtml(error.message)}</div>`;
    }
}

// === Pagination ===

function renderPagination(containerId, data, onPageChange) {
    const container = document.getElementById(containerId);
    const currentPage = Math.floor(data.offset / data.limit) + 1;
    const totalPages = data.pages;

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = `
        <button class="page-button" ${currentPage === 1 ? 'disabled' : ''} onclick="arguments[0].stopPropagation()">
            &laquo; Zurueck
        </button>
    `;

    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        html += `<button class="page-button">1</button>`;
        if (startPage > 2) html += `<span class="page-info">...</span>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-button ${i === currentPage ? 'active' : ''}">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span class="page-info">...</span>`;
        html += `<button class="page-button">${totalPages}</button>`;
    }

    html += `
        <span class="page-info">${data.total.toLocaleString()} Eintraege</span>
        <button class="page-button" ${currentPage === totalPages ? 'disabled' : ''}>
            Weiter &raquo;
        </button>
    `;

    container.innerHTML = html;

    // Event listeners
    const buttons = container.querySelectorAll('.page-button');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.textContent.trim();
            if (text.includes('Zurueck') && currentPage > 1) {
                onPageChange(currentPage - 1);
            } else if (text.includes('Weiter') && currentPage < totalPages) {
                onPageChange(currentPage + 1);
            } else if (!isNaN(parseInt(text))) {
                onPageChange(parseInt(text));
            }
        });
    });
}

// === Utilities ===

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('de-DE');
    } catch {
        return dateStr;
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
