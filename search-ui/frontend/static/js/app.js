/**
 * Kleine Anfragen Search UI
 * Interactive semantic search for German parliamentary questions
 */

const API_BASE = '';  // Same origin

// State
let conversationId = null;
let currentResults = [];
let isLoading = false;

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSubmit = document.getElementById('chat-submit');
const refinementSuggestions = document.getElementById('refinement-suggestions');
const resultsHeader = document.getElementById('results-header');
const resultsContainer = document.getElementById('results-container');
const resultsFilters = document.getElementById('results-filters');
const headerStats = document.getElementById('header-stats');
const modalOverlay = document.getElementById('modal-overlay');
const modalContent = document.getElementById('modal-content');
const modalClose = document.getElementById('modal-close');
const filterRessort = document.getElementById('filter-ressort');
const filterStatus = document.getElementById('filter-status');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
});

function setupEventListeners() {
    // Chat form submission
    chatForm.addEventListener('submit', handleChatSubmit);

    // Modal close
    modalClose.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) closeModal();
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // Filter changes
    filterRessort.addEventListener('change', applyFilters);
    filterStatus.addEventListener('change', applyFilters);
}

// === API Functions ===

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const stats = await response.json();

        headerStats.innerHTML = `
            <div class="header-stat">
                <span class="header-stat-value">${stats.total_vorgaenge.toLocaleString()}</span>
                <span>Anfragen</span>
            </div>
            <div class="header-stat">
                <span class="header-stat-value">${stats.total_drucksachen.toLocaleString()}</span>
                <span>Dokumente</span>
            </div>
        `;

        // Populate ressort filter
        stats.ressorts.forEach(r => {
            const option = document.createElement('option');
            option.value = r.name;
            option.textContent = `${r.name} (${r.count})`;
            filterRessort.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function search(query, filters = null) {
    if (isLoading) return;

    isLoading = true;
    chatSubmit.disabled = true;
    showLoading();

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
        conversationId = data.conversation_id;

        // Add assistant message
        addMessage('assistant', data.message);

        // Update results
        if (data.results) {
            currentResults = data.results;
            renderResults(data.results);
        }

        // Update suggestions
        if (data.refinement_questions) {
            renderSuggestions(data.refinement_questions);
        }
    } catch (error) {
        console.error('Search failed:', error);
        addMessage('assistant', 'Es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.');
    } finally {
        isLoading = false;
        chatSubmit.disabled = false;
    }
}

async function loadVorgangDetail(vorgangId) {
    try {
        const response = await fetch(`${API_BASE}/api/vorgang/${vorgangId}`);
        const data = await response.json();
        showDetailModal(data);
    } catch (error) {
        console.error('Failed to load detail:', error);
    }
}

// === Event Handlers ===

function handleChatSubmit(e) {
    e.preventDefault();

    const query = chatInput.value.trim();
    if (!query) return;

    // Add user message
    addMessage('user', query);
    chatInput.value = '';

    // Perform search
    search(query);
}

function handleSuggestionClick(suggestion) {
    // Extract the search term from suggestion
    let query = suggestion;

    // If it's a question, convert to search
    if (suggestion.includes('eingrenzen')) {
        const match = suggestion.match(/'([^']+)'/);
        if (match) {
            filterRessort.value = match[1];
            applyFilters();
            return;
        }
    }

    if (suggestion.includes('suchen')) {
        const match = suggestion.match(/'([^']+)'/);
        if (match) {
            query = match[1];
        }
    }

    if (suggestion.includes('beantwortete')) {
        filterStatus.value = 'Beantwortet';
        applyFilters();
        return;
    }

    // Add as user message and search
    chatInput.value = query;
    handleChatSubmit(new Event('submit'));
}

function applyFilters() {
    if (!currentResults.length) return;

    const ressort = filterRessort.value;
    const status = filterStatus.value;

    let filtered = currentResults;

    if (ressort) {
        filtered = filtered.filter(r => r.ressort === ressort);
    }

    if (status) {
        filtered = filtered.filter(r => r.beratungsstand === status);
    }

    renderResults(filtered, false);
}

// === Rendering Functions ===

function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatarIcon = role === 'user'
        ? '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
        : '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>';

    messageDiv.innerHTML = `
        <div class="message-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                ${avatarIcon}
            </svg>
        </div>
        <div class="message-content">
            <p>${escapeHtml(content)}</p>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderResults(results, updateHeader = true) {
    if (updateHeader) {
        resultsHeader.innerHTML = `
            <h2>Suchergebnisse</h2>
            <p class="results-subtitle">
                <span class="results-count">${results.length}</span> relevante Anfragen gefunden
            </p>
        `;
        resultsFilters.style.display = 'flex';
    }

    if (!results.length) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <p>Keine Ergebnisse mit diesen Filtern</p>
            </div>
        `;
        return;
    }

    resultsContainer.innerHTML = results.map((result, index) => {
        const scoreClass = result.score > 0.7 ? 'high' : result.score > 0.5 ? 'medium' : '';
        const scorePercent = Math.round(result.score * 100);

        const isAnswered = result.beratungsstand === 'Beantwortet';
        const statusClass = isAnswered ? 'answered' : 'pending';
        const statusText = isAnswered ? 'Beantwortet' : 'Offen';

        const tags = (result.schlagworte || []).slice(0, 4);

        return `
            <div class="result-card" onclick="loadVorgangDetail('${result.vorgang_id}')">
                <div class="result-card-header">
                    <h3 class="result-card-title">${escapeHtml(result.titel || 'Ohne Titel')}</h3>
                    <span class="result-card-score ${scoreClass}">${scorePercent}%</span>
                </div>

                <div class="result-card-meta">
                    ${result.datum ? `
                        <span class="result-card-meta-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                                <line x1="16" y1="2" x2="16" y2="6"/>
                                <line x1="8" y1="2" x2="8" y2="6"/>
                                <line x1="3" y1="10" x2="21" y2="10"/>
                            </svg>
                            ${formatDate(result.datum)}
                        </span>
                    ` : ''}
                    ${result.ressort ? `
                        <span class="result-card-meta-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                            </svg>
                            ${escapeHtml(result.ressort)}
                        </span>
                    ` : ''}
                </div>

                ${result.highlight ? `
                    <div class="result-card-highlight">
                        ${escapeHtml(result.highlight)}
                    </div>
                ` : ''}

                ${tags.length ? `
                    <div class="result-card-tags">
                        ${tags.map(tag => `<span class="result-card-tag">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                ` : ''}

                <div class="result-card-status">
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderSuggestions(suggestions) {
    if (!suggestions || !suggestions.length) {
        refinementSuggestions.innerHTML = '';
        return;
    }

    refinementSuggestions.innerHTML = suggestions.map(s => `
        <button class="refinement-suggestion" onclick="handleSuggestionClick('${escapeHtml(s)}')">${escapeHtml(s)}</button>
    `).join('');
}

function showLoading() {
    resultsContainer.innerHTML = `
        <div class="loading">
            <div class="loading-spinner"></div>
        </div>
    `;
}

function showDetailModal(data) {
    const initiatorenText = data.initiatoren
        ? data.initiatoren.join(', ')
        : 'Nicht angegeben';

    const schlagworteHtml = data.schlagworte
        ? data.schlagworte.map(s => `<span class="result-card-tag">${escapeHtml(s)}</span>`).join('')
        : '';

    const drucksachenHtml = data.drucksachen && data.drucksachen.length
        ? data.drucksachen.map(d => `
            <div class="document-item">
                <div class="document-info">
                    <div class="document-title">${escapeHtml(d.titel || d.drucksachetyp || 'Dokument')}</div>
                    <div class="document-meta">
                        ${d.drucksache_nummer || ''} ${d.datum ? `| ${formatDate(d.datum)}` : ''}
                    </div>
                </div>
                ${d.dok_url ? `<a href="${d.dok_url}" target="_blank" class="document-link">PDF</a>` : ''}
            </div>
        `).join('')
        : '<p class="modal-text">Keine Dokumente verfuegbar</p>';

    modalContent.innerHTML = `
        <h2 class="modal-title">${escapeHtml(data.titel || 'Ohne Titel')}</h2>

        <div class="modal-meta">
            <div class="modal-meta-item">
                <div class="modal-meta-label">Datum</div>
                <div class="modal-meta-value">${data.datum ? formatDate(data.datum) : '-'}</div>
            </div>
            <div class="modal-meta-item">
                <div class="modal-meta-label">Status</div>
                <div class="modal-meta-value">${data.beratungsstand || '-'}</div>
            </div>
            <div class="modal-meta-item">
                <div class="modal-meta-label">Ressort</div>
                <div class="modal-meta-value">${data.ressort || '-'}</div>
            </div>
            <div class="modal-meta-item">
                <div class="modal-meta-label">Wahlperiode</div>
                <div class="modal-meta-value">${data.legislature || '-'}</div>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Initiatoren</div>
            <p class="modal-text">${escapeHtml(initiatorenText)}</p>
        </div>

        ${data.abstrakt ? `
            <div class="modal-section">
                <div class="modal-section-title">Zusammenfassung</div>
                <p class="modal-text">${escapeHtml(data.abstrakt)}</p>
            </div>
        ` : ''}

        ${schlagworteHtml ? `
            <div class="modal-section">
                <div class="modal-section-title">Schlagworte</div>
                <div class="result-card-tags">${schlagworteHtml}</div>
            </div>
        ` : ''}

        <div class="modal-section">
            <div class="modal-section-title">Dokumente</div>
            <div class="document-list">
                ${drucksachenHtml}
            </div>
        </div>
    `;

    modalOverlay.classList.add('active');
}

function closeModal() {
    modalOverlay.classList.remove('active');
}

// === Utility Functions ===

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('de-DE', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    } catch {
        return dateStr;
    }
}
