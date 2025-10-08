let keywordFilterActive = false;
let sortOrder = 'asc'; // 'asc' or 'desc'

// --- Data Fetching and State Management ---

/**
 * Main function to update the view.
 * Gathers all filter criteria, fetches data from the server, and updates the UI.
 */
function updateView() {
    const searchText = document.getElementById('input-busca').value.trim();
    
    // Determine status from the selected button
    const selectedFilterBtn = document.querySelector('.filter-btn.selected[data-filter]');
    const status = selectedFilterBtn ? selectedFilterBtn.dataset.filter : 'all';

    const params = [];

    if (searchText) {
        params.push(`search=${encodeURIComponent(searchText)}`);
    }

    if (status === 'arch' || status === 'notarch') {
        params.push(`status=${status}`);
    }
    if (status === 'amabre') {
        params.push(`amabre=true`);
    }

    // Add the conditional keyword filter
    if (keywordFilterActive) {
        params.push('filter_keywords=true');
    }

    // Always add sort order
    params.push(`sort_order=${sortOrder}`);

    const queryString = params.length > 0 ? `?${params.join('&')}`: '';

    // Show loading indicator
    document.getElementById('protocol-list').innerHTML = '<em>Buscando protocolos...</em>';

    fetch(`/api/protocols${queryString}`)
        .then(response => response.json())
        .then(data => {
            updateTotals(data.totals);
            renderProtocolList(data.protocols);
        })
        .catch(error => {
            console.error('Error fetching protocols:', error);
            document.getElementById('protocol-list').innerHTML = '<em>Erro ao carregar protocolos.</em>';
        });
}

// --- UI Rendering ---

/**
 * Updates the numbers on the filter buttons.
 * @param {object} totals - An object with counts for each category.
 */
function updateTotals(totals) {
    document.getElementById('btn-all').textContent = `Todos (${totals.todos})`;
    document.getElementById('btn-arch').textContent = `Arquivados (+) (${totals.arch})`;
    document.getElementById('btn-notarch').textContent = `Não arquivados (${totals.notarch})`;
    document.getElementById('btn-amabre').textContent = `AMABRE (${totals.amabre})`;
}

/**
 * Clears and rebuilds the list of protocols on the left pane.
 * @param {Array} protocols - The list of protocol objects from the server.
 */
function renderProtocolList(protocols) {
    const listDiv = document.getElementById('protocol-list');
    listDiv.innerHTML = ''; // Clear existing list

    if (protocols.length === 0) {
        listDiv.innerHTML = '<em>Nenhum protocolo encontrado.</em>';
        document.getElementById('detail').innerHTML = '<em>Selecione um protocolo à esquerda...</em>';
        return;
    }

    protocols.forEach(p => {
        const item = document.createElement('div');
        item.className = 'proto-item';
        item.id = `item-${p.id.replace('/', '-')}`;
        item.setAttribute('data-arch', p.has_archivado ? '1' : '0');
        item.onclick = () => showProtocolo(p.id);
        
        let text = `${p.ano}/${p.numero}`;
        if (p.has_archivado) {
            text += ' <span title="Arquivado">+</span>';
        }
        item.innerHTML = text;
        listDiv.appendChild(item);
    });

    // Auto-select the first protocol in the new list
    if (listDiv.firstChild) {
        listDiv.firstChild.click();
    }
}

/**
 * Fetches and displays the detail for a single protocol.
 * @param {string} id - The protocol ID (e.g., "2024/00001").
 */
function showProtocolo(id) {
    const detail = document.getElementById('detail');
    detail.innerHTML = '<em>Carregando protocolo...</em>';
    const search = document.getElementById('input-busca').value.trim();

    fetch(`/protocolo?id=${encodeURIComponent(id)}&search=${encodeURIComponent(search)}`)
        .then(r => r.json())
        .then(data => {
            let metaHtml = '<div class="protocol-meta">';
            if (data.last_update) {
                metaHtml += `<span><strong>Última Atualização:</strong> ${data.last_update}</span>`;
            }
            if (data.arquivado) {
                const statusClass = data.arquivado === 'yes' ? 'archived' : 'not-archived';
                const statusText = data.arquivado === 'yes' ? 'Sim' : 'Não';
                metaHtml += `<span><strong>Arquivado:</strong> <span class="status-${statusClass}">${statusText}</span></span>`;
            }
            metaHtml += '</div>';

            detail.innerHTML = metaHtml + `<pre>${data.html}</pre>`;
            
            // Highlight the selected item in the list
            document.querySelectorAll('.proto-item').forEach(e => e.classList.remove('selected'));
            const el = document.getElementById(`item-${id.replace('/', '-')}`);
            if (el) el.classList.add('selected');
        });
}

// --- Event Handlers ---

/**
 * Handles clicks on the main filter buttons (All, Archived, etc.).
 * @param {string} type - The filter type (e.g., 'all', 'arch').
 */
function filterProtos(type) {
    document.querySelectorAll('.filter-btn[data-filter]').forEach(e => e.classList.remove('selected'));
    const btn = document.getElementById(`btn-${type}`);
    if(btn) btn.classList.add('selected');
    updateView();
}

function exportarProtocolos() {
    const ids = Array.from(document.querySelectorAll('.proto-item'))
        .filter(e => e.style.display !== 'none') // Only visible ones
        .map(e => e.id.replace('item-', '').replace(/-/g, '/'));

    if (ids.length === 0) {
        alert('Nenhum protocolo para exportar!');
        return;
    }

    fetch('/exportar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: ids })
    })
    .then(response => {
        if (!response.ok) throw new Error('Erro ao exportar');
        return response.blob().then(blob => ({ blob, response }));
    })
    .then(({ blob, response }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        const disposition = response.headers.get('Content-Disposition');
        let filename = 'Exportados.txt';
        if (disposition && disposition.includes('filename=')) {
            filename = disposition.split('filename=')[1].replace(/['|"]/g, '');
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    })
    .catch(e => alert('Erro ao exportar: ' + e.message));
}

function removerProtocolo(id) {
    if (!confirm('Tem certeza que deseja remover este protocolo?')) return;
    fetch('/remover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const el = document.getElementById(`item-${id.replace('/', '-')}`);
            if (el) el.remove();
            document.getElementById('detail').innerHTML = '<em>Protocolo removido.</em>';
            updateView(); // Refresh the list and totals
        } else {
            alert('Erro ao remover protocolo.');
        }
    });
}

function removerProtocoloSelecionado() {
    const sel = document.querySelector('.proto-item.selected');
    if (!sel) return;
    const id = sel.id.replace('item-', '').replace(/-/g, '/');
    removerProtocolo(id);
}

// --- Initial Setup ---

window.onload = function () {
    const searchInput = document.getElementById('input-busca');
    const searchBtn = document.getElementById('btn-buscar');
    const sortBtn = document.getElementById('btn-sort');
    const protocolListDiv = document.getElementById('protocol-list');
    const instructionsDiv = document.getElementById('initial-instructions');

    // This function starts the actual data loading process
    function startLoading() {
        // Hide instructions and show the initial empty state for the detail view
        if (instructionsDiv) {
            instructionsDiv.style.display = 'none';
        }
        document.getElementById('detail').innerHTML = '<em>Selecione um protocolo à esquerda...</em>';

        // Show loading message in the protocol list
        protocolListDiv.innerHTML = '<em>Carregando...</em>';

        // Fetch last update time and then load initial data
        fetch('/api/db_last_update')
            .then(response => response.json())
            .then(data => {
                if (data.last_update && data.last_update !== 'Não encontrado') {
                    protocolListDiv.innerHTML = `<em>Carregando banco de dados atualizado em ${data.last_update}</em>`;
                }
                // Wait 2 seconds before loading the data to show the message
                setTimeout(updateView, 2000);
            })
            .catch(error => {
                console.error('Error fetching db update time:', error);
                // Still load data even if fetching time fails
                updateView();
            });
    }

    const startButton = document.getElementById('start-button');

    // Show instructions and wait for the user to click the button
    startButton.addEventListener('click', startLoading);

    function performSearch() {
        // When user searches, reset category filters to 'All'
        document.querySelectorAll('.filter-btn[data-filter]').forEach(e => e.classList.remove('selected'));
        document.getElementById('btn-all').classList.add('selected');
        updateView();
    }

    // Add event listeners for search
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            performSearch();
        }
    });

    sortBtn.addEventListener('click', () => {
        sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
        sortBtn.textContent = sortOrder === 'asc' ? 'A-Z' : 'Z-A';
        updateView();
    });
    
    // Event listeners for filter buttons
    document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
        btn.addEventListener('click', () => filterProtos(btn.dataset.filter));
    });

    const keywordFilterBtn = document.getElementById('btn-keyword-filter');
    keywordFilterBtn.addEventListener('click', () => {
        keywordFilterActive = !keywordFilterActive;
        keywordFilterBtn.classList.toggle('selected', keywordFilterActive);
        updateView();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Delete') removerProtocoloSelecionado();
        if (['ArrowUp', 'ArrowDown'].includes(e.key)) {
            e.preventDefault();
            const items = Array.from(document.querySelectorAll('.proto-item'));
            if (items.length === 0) return;
            const selIndex = items.findIndex(x => x.classList.contains('selected'));
            let nextIndex = selIndex;
            if (e.key === 'ArrowDown') nextIndex = selIndex < items.length - 1 ? selIndex + 1 : 0;
            if (e.key === 'ArrowUp') nextIndex = selIndex > 0 ? selIndex - 1 : items.length - 1;
            if (nextIndex !== selIndex) {
                items[nextIndex].click();
                items[nextIndex].scrollIntoView({ block: 'nearest' });
            }
        }
    });
};