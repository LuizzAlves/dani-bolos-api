/* ============================================================
   DANI BOLOS — PAINEL ADMINISTRATIVO — LÓGICA
   Todas as chamadas usam a API real. Nenhum dado mockado.
   ============================================================ */

// ============================================================
// API CLIENT
// ============================================================
const API = {
    base: '/admin',
    get token() { return sessionStorage.getItem('admin_token') || ''; },
    set token(t) { sessionStorage.setItem('admin_token', t); },

    async fetch(path, opts = {}) {
        const url = this.base + path;
        const headers = { 'X-Admin-Token': this.token, 'Content-Type': 'application/json', ...(opts.headers || {}) };
        try {
            const res = await fetch(url, { ...opts, headers });
            if (res.status === 403) { this.logout(); throw new Error('Token inválido'); }
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || body.message || `Erro ${res.status}`);
            }
            return res.json();
        } catch (e) {
            if (e.message === 'Token inválido') throw e;
            console.error('API error:', e);
            throw e;
        }
    },

    get(path) { return this.fetch(path); },
    post(path, data) { return this.fetch(path, { method: 'POST', body: JSON.stringify(data) }); },
    patch(path, data) { return this.fetch(path, { method: 'PATCH', body: JSON.stringify(data) }); },

    logout() {
        sessionStorage.removeItem('admin_token');
        document.getElementById('login-overlay').classList.add('visible');
        document.body.classList.add('locked');
    },

    // Endpoints
    getDashboard() { return this.get('/dashboard/stats'); },
    getOrders(q) { return this.get('/orders' + (q ? '?' + q : '')); },
    getOrder(id) { return this.get('/orders/' + id); },
    createOrder(d) { return this.post('/orders', d); },
    updateStatus(id, s) { return this.patch('/orders/' + id + '/status', { new_status: s }); },
    getCalendar(y, m) { return this.get('/calendar?year=' + y + '&month=' + m); },
    updateDay(d, data) { return this.patch('/calendar/' + d, data); },
    getAlerts() { return this.get('/alerts'); },
    resolveAlert(id) { return this.patch('/alerts/' + id + '/resolve', {}); },
    getCatalog() { return this.get('/catalog'); },
    updateCatalogItem(t, id, d) { return this.patch('/catalog/' + t + '/' + id, { data: d }); },
    createCatalogItem(t, d) { return this.post('/catalog/' + t, d); },
    deleteCatalogItem(t, id) { return this.fetch('/catalog/' + t + '/' + id, { method: 'DELETE' }); },
    getReadyCakes() { return this.get('/ready-cakes'); },
    createReadyCake(d) { return this.post('/ready-cakes', d); },
    updateReadyCake(id, d) { return this.patch('/ready-cakes/' + id, d); },
    deleteReadyCake(id) { return this.fetch('/ready-cakes/' + id, { method: 'DELETE' }); },
    getSettings() { return this.get('/settings'); },
    saveSettings(d) { return this.patch('/settings', { settings: d }); },
};

// ============================================================
// STATE
// ============================================================
let calY, calM, selDay = null;
let calendarData = null;
let catalogCache = null;
let historyCache = [];

const MN = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
const DL = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
const STATUS_LABELS = {
    AGUARDANDO_CONFIRMACAO: 'Aguardando',
    CONFIRMADO: 'Confirmado',
    EM_PRODUCAO: 'Em Produção',
    PRONTO: 'Pronto',
    ENTREGUE: 'Entregue',
    FINALIZADO: 'Finalizado',
    CANCELADO: 'Cancelado',
};
const STATUS_FLOW = {
    AGUARDANDO_CONFIRMACAO: ['CONFIRMADO', 'CANCELADO'],
    CONFIRMADO: ['EM_PRODUCAO', 'CANCELADO'],
    EM_PRODUCAO: ['PRONTO', 'CANCELADO'],
    PRONTO: ['ENTREGUE'],
    ENTREGUE: ['FINALIZADO'],
};

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    calY = now.getFullYear();
    calM = now.getMonth();

    initLogin();
    initTabs();
    initSidebar();
    initDate();
    initDrawer();
    initKanbanFilters();
    initHistoryFilters();

    if (API.token) {
        tryAuth();
    } else {
        API.logout();
    }
});

// ============================================================
// LOGIN
// ============================================================
function initLogin() {
    const overlay = document.getElementById('login-overlay');
    const btn = document.getElementById('login-btn');
    const input = document.getElementById('login-token');
    const errEl = document.getElementById('login-error');

    btn.addEventListener('click', async () => {
        const token = input.value.trim();
        if (!token) { errEl.textContent = 'Informe o token'; return; }
        API.token = token;
        errEl.textContent = '';
        btn.disabled = true;
        btn.textContent = 'Verificando...';
        try {
            await API.getDashboard();
            overlay.classList.remove('visible');
            document.body.classList.remove('locked');
            loadAll();
        } catch {
            errEl.textContent = 'Token inválido ou API indisponível';
            sessionStorage.removeItem('admin_token');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Entrar';
        }
    });

    input.addEventListener('keydown', e => { if (e.key === 'Enter') btn.click(); });
    document.getElementById('header-logout')?.addEventListener('click', () => API.logout());
}

async function tryAuth() {
    try {
        await API.getDashboard();
        document.getElementById('login-overlay').classList.remove('visible');
        document.body.classList.remove('locked');
        loadAll();
    } catch {
        API.logout();
    }
}

function loadAll() {
    loadDashboard();
    loadKanban();
    loadCalendar();
    loadHistory();
    loadCatalogForForm();
    loadAlerts();
    loadCatalogTab('tamanhos');
    initCatalogTabs();
    loadSettings();
    loadReadyCakes();
    startPolling();
}

// ============================================================
// TABS
// ============================================================
function initTabs() {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            const panel = document.getElementById('tab-' + tab);
            if (panel) { void panel.offsetWidth; panel.classList.add('active'); }
            closeSidebar();
        });
    });
}

function initSidebar() {
    document.getElementById('sidebar-toggle').addEventListener('click', () => {
        const sidebar = document.getElementById('sidebar');
        const isOpen = sidebar.classList.toggle('open');
        document.getElementById('sidebar-backdrop')?.classList.toggle('visible', isOpen);
        document.body.classList.toggle('sidebar-visible', isOpen);
    });
    document.getElementById('sidebar-backdrop')?.addEventListener('click', closeSidebar);
}

function closeSidebar() {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebar-backdrop')?.classList.remove('visible');
    document.body.classList.remove('sidebar-visible');
}

function initDate() {
    const d = new Date();
    document.getElementById('header-date').textContent = d.toLocaleDateString('pt-BR', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
}

// ============================================================
// POLLING (alertas + kanban badge a cada 60s)
// ============================================================
let pollTimer = null;
function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        try {
            const data = await API.getDashboard();
            updateBadges(data);
        } catch { /* ignore */ }
    }, 60000);
}

function updateBadges(stats) {
    const alertBadge = document.getElementById('badge-alertas');
    if (stats.alert_count > 0) {
        alertBadge.textContent = stats.alert_count;
        alertBadge.style.display = '';
    } else {
        alertBadge.style.display = 'none';
    }
    const pedBadge = document.getElementById('badge-pedidos');
    if (stats.aguardando_count > 0) {
        pedBadge.textContent = stats.aguardando_count;
        pedBadge.style.display = '';
    } else {
        pedBadge.style.display = 'none';
    }
}

// ============================================================
// DASHBOARD / AGENDA
// ============================================================
async function loadDashboard() {
    try {
        const s = await API.getDashboard();
        document.getElementById('m-hoje').textContent = s.today_count;
        document.getElementById('m-aguardando').textContent = s.aguardando_count;
        document.getElementById('m-faturamento').textContent = 'R$ ' + Number(s.faturamento_semanal).toLocaleString('pt-BR', { minimumFractionDigits: 0 });
        document.getElementById('m-amanha').textContent = s.tomorrow_count;
        updateBadges(s);
    } catch (e) {
        console.error('loadDashboard:', e);
    }
}

// ============================================================
// CALENDAR
// ============================================================
async function loadCalendar() {
    try {
        calendarData = await API.getCalendar(calY, calM + 1);
        renderCal();
        initCalendarNav();
    } catch (e) {
        console.error('loadCalendar:', e);
        renderCal();
        initCalendarNav();
    }
}

function initCalendarNav() {
    // Remove old listeners by cloning
    ['cal-prev', 'cal-next', 'cap-minus', 'cap-plus', 'btn-block-day', 'btn-save-day-message'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.replaceWith(el.cloneNode(true));
    });

    document.getElementById('cal-prev').addEventListener('click', () => { calM--; if(calM<0){calM=11;calY--;} loadCalendar(); });
    document.getElementById('cal-next').addEventListener('click', () => { calM++; if(calM>11){calM=0;calY++;} loadCalendar(); });

    document.getElementById('cap-minus').addEventListener('click', () => adjustCapacity(-1));
    document.getElementById('cap-plus').addEventListener('click', () => adjustCapacity(1));
    document.getElementById('btn-block-day').addEventListener('click', toggleBlockDay);
    document.getElementById('btn-save-day-message').addEventListener('click', saveDayMessage);
}

function renderCal() {
    const g = document.getElementById('calendar-grid');
    g.innerHTML = '';
    document.getElementById('cal-month-label').textContent = MN[calM] + ' ' + calY;

    DL.forEach(l => { const e=document.createElement('div'); e.className='cal-day-label'; e.textContent=l; g.appendChild(e); });

    const first = new Date(calY, calM, 1).getDay();
    const days = new Date(calY, calM+1, 0).getDate();
    const now = new Date();

    // Build day map from API data
    const dayMap = {};
    if (calendarData?.days) {
        calendarData.days.forEach(d => { dayMap[d.date] = d; });
    }

    for(let i=0;i<first;i++){ const e=document.createElement('div'); e.className='cal-day empty'; g.appendChild(e); }

    for(let d=1;d<=days;d++){
        const e=document.createElement('div'); e.className='cal-day';
        const ds = calY + '-' + String(calM+1).padStart(2,'0') + '-' + String(d).padStart(2,'0');
        const av = dayMap[ds];
        if(now.getFullYear()===calY && now.getMonth()===calM && now.getDate()===d) e.classList.add('today');
        if(selDay===ds) e.classList.add('selected');
        if(av?.blocked) e.classList.add('blocked');

        let h = '<span>' + d + '</span>';
        if(av && !av.blocked) {
            const cnt = av.order_count ?? 0;
            const max = av.max_orders || 5;
            const p = cnt / max;
            const c = p >= 1 ? 'full' : p >= 0.6 ? 'warning' : cnt > 0 ? 'available' : '';
            if (cnt > 0 || max !== 5) {
                h += '<span class="cal-slots ' + c + '">' + cnt + '/' + max + '</span>';
            }
        }
        e.innerHTML = h;
        e.addEventListener('click', () => { selDay = ds; renderCal(); loadDayDetail(ds, d); });
        g.appendChild(e);
    }
}

async function loadDayDetail(ds, dn) {
    const dayInfo = calendarData?.days?.find(d => d.date === ds) || { max_orders: 5, confirmed_orders: 0, order_count: 0, blocked: false };

    document.getElementById('day-detail-title').textContent = dn + ' de ' + MN[calM];

    const max = dayInfo.max_orders || 5;
    const cnt = dayInfo.order_count ?? 0;
    document.getElementById('cap-value').textContent = max;
    const pct = max > 0 ? (cnt / max) * 100 : 0;
    const bar = document.getElementById('capacity-bar');
    bar.style.width = Math.min(pct, 100) + '%';
    bar.style.background = pct >= 100 ? 'var(--red)' : pct >= 60 ? 'linear-gradient(90deg,var(--amber),#f59e0b)' : 'linear-gradient(90deg,var(--green),var(--teal))';
    document.getElementById('capacity-text').textContent = cnt + ' / ' + max + ' pedidos';

    const blockBtn = document.getElementById('btn-block-day');
    blockBtn.textContent = dayInfo.blocked ? 'Desbloquear' : 'Bloquear';

    const msgInput = document.getElementById('day-block-message');
    const msgStatus = document.getElementById('day-message-status');
    if (msgInput) msgInput.value = dayInfo.block_reason || '';
    if (msgStatus) {
        msgStatus.textContent = dayInfo.blocked ? 'Dia bloqueado' : 'Opcional';
        msgStatus.classList.toggle('is-blocked', !!dayInfo.blocked);
    }

    // Load orders for this day
    try {
        const orders = await API.getOrders('pickup_date=' + ds);
        const list = document.getElementById('day-orders-list');
        if (!orders.length) {
            list.innerHTML = '<p class="empty-state">Nenhum pedido neste dia</p>';
            return;
        }
        list.innerHTML = orders.map(o => `
            <div class="day-order-card" data-id="${o.id}">
                <div class="day-order-card__top">
                    <strong>${o.client_name || 'Sem nome'}</strong>
                    <span>${o.order_number ? '#' + o.order_number : ''}</span>
                </div>
                <div class="day-order-card__meta">
                    <span>${o.pickup_time || 'Horario pendente'}</span>
                    <span class="prod-status prod-status--${o.status?.toLowerCase()}">${STATUS_LABELS[o.status] || o.status}</span>
                </div>
                <div class="day-order-card__desc">${o.size_description || 'Tamanho pendente'}${o.dough ? ' · ' + o.dough : ''}</div>
                <div class="day-order-card__fillings">${[o.filling_1, o.filling_2].filter(Boolean).join(' + ') || 'Recheio pendente'}</div>
            </div>`).join('');

        list.querySelectorAll('.day-order-card').forEach(el => {
            el.addEventListener('click', () => openOrderDrawer(el.dataset.id));
        });
    } catch (e) {
        console.error('loadDayDetail orders:', e);
        document.getElementById('day-orders-list').innerHTML = '<p class="empty-state">Erro ao carregar pedidos</p>';
    }
}

async function adjustCapacity(delta) {
    if (!selDay) return;
    const cur = parseInt(document.getElementById('cap-value').textContent) || 5;
    const next = Math.max(1, cur + delta);
    try {
        await API.updateDay(selDay, { max_orders: next });
        await loadCalendar();
        const dn = parseInt(selDay.split('-')[2]);
        loadDayDetail(selDay, dn);
        showToast('Capacidade atualizada', 'success');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function saveDayMessage() {
    if (!selDay) return;
    const message = (document.getElementById('day-block-message')?.value || '').trim();
    try {
        await API.updateDay(selDay, { block_reason: message });
        await loadCalendar();
        const dn = parseInt(selDay.split('-')[2]);
        loadDayDetail(selDay, dn);
        showToast('Mensagem do dia salva', 'success');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function toggleBlockDay() {
    if (!selDay) return;
    const dayInfo = calendarData?.days?.find(d => d.date === selDay);
    const isBlocked = dayInfo?.blocked || false;
    const message = (document.getElementById('day-block-message')?.value || '').trim();

    try {
        await API.updateDay(selDay, {
            blocked: !isBlocked,
            block_reason: message || dayInfo?.block_reason || (!isBlocked ? 'Bloqueado pelo painel' : '')
        });
        await loadCalendar();
        const dn = parseInt(selDay.split('-')[2]);
        loadDayDetail(selDay, dn);
        showToast(isBlocked ? 'Dia desbloqueado' : 'Dia bloqueado', 'success');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ============================================================
// KANBAN
// ============================================================
let allOrdersCache = [];

function initKanbanFilters() {
    const sInp = document.getElementById('kanban-search-input');
    if (sInp) {
        sInp.addEventListener('input', () => filterKanban());
    }

    document.querySelectorAll('.k-filter').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.k-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterKanban();
        });
    });
}

function filterKanban() {
    const term = (document.getElementById('kanban-search-input')?.value || '').toLowerCase();
    const activeFilter = document.querySelector('.k-filter.active')?.dataset.filter || 'all';
    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];

    now.setDate(now.getDate() + 1);
    const tomorrowStr = now.toISOString().split('T')[0];

    // Reset now for week start
    const wNow = new Date();
    const wDay = wNow.getDay();
    const wStart = new Date(wNow); wStart.setDate(wNow.getDate() - wDay);
    const wEnd = new Date(wStart); wEnd.setDate(wStart.getDate() + 6);
    const wStartStr = wStart.toISOString().split('T')[0];
    const wEndStr = wEnd.toISOString().split('T')[0];

    document.querySelectorAll('.kanban-card').forEach(card => {
        const txt = card.textContent.toLowerCase();
        const isLate = card.classList.contains('is-late');
        const d = card.dataset.date; // we'll add this in card creation

        let matchTerm = !term || txt.includes(term);
        let matchF = true;

        if (activeFilter === 'today') matchF = d === todayStr;
        else if (activeFilter === 'tomorrow') matchF = d === tomorrowStr;
        else if (activeFilter === 'week') matchF = d >= wStartStr && d <= wEndStr;
        else if (activeFilter === 'late') matchF = isLate;

        card.style.display = (matchTerm && matchF) ? 'block' : 'none';
    });
}

function updateKanbanSummary(orders) {
    const todayStr = new Date().toISOString().split('T')[0];
    let tHoje = 0, vProd = 0, entHoje = 0, atrasos = 0;

    orders.forEach(o => {
        const pd = o.pickup_date;
        if (pd === todayStr && !['CANCELADO', 'RASCUNHO'].includes(o.status)) tHoje++;
        if (['CONFIRMADO', 'EM_PRODUCAO'].includes(o.status)) vProd += parseFloat(o.total_value || 0);
        if (pd === todayStr && ['ENTREGUE', 'FINALIZADO'].includes(o.status)) entHoje++;
        if (pd && pd < todayStr && !['ENTREGUE', 'FINALIZADO', 'CANCELADO', 'RASCUNHO'].includes(o.status)) atrasos++;
    });

    const fHoje = document.getElementById('ks-total-hoje');
    if(fHoje) fHoje.textContent = tHoje;
    const fVProd = document.getElementById('ks-valor-producao');
    if(fVProd) fVProd.textContent = 'R$ ' + vProd.toFixed(2).replace('.', ',');
    const fEnt = document.getElementById('ks-entregues');
    if(fEnt) fEnt.textContent = entHoje;
    const fAtr = document.getElementById('ks-atrasados');
    if(fAtr) fAtr.textContent = atrasos;
}

async function loadKanban() {
    const map = {
        AGUARDANDO_CONFIRMACAO: 'kanban-aguardando',
        CONFIRMADO: 'kanban-producao',
        EM_PRODUCAO: 'kanban-producao',
        PRONTO: 'kanban-pronto',
        ENTREGUE: 'kanban-entregue',
        FINALIZADO: 'kanban-entregue',
    };
    const columns = ['kanban-aguardando', 'kanban-producao', 'kanban-pronto', 'kanban-entregue'];
    columns.forEach(id => { const c=document.getElementById(id); if(c) c.innerHTML = '<div class="kanban-loading">Carregando...</div>'; });

    try {
        const orders = await API.getOrders();
        allOrdersCache = orders;
        updateKanbanSummary(orders);

        columns.forEach(id => { const c=document.getElementById(id); if(c) c.innerHTML = ''; });

        const todayStr = new Date().toISOString().split('T')[0];
        const now2 = new Date(); now2.setDate(now2.getDate() + 1);
        const tomStr = now2.toISOString().split('T')[0];

        orders.forEach(o => {
            const cid = map[o.status]; if (!cid) return;
            const container = document.getElementById(cid);
            if(!container) return;

            const card = document.createElement('div');
            card.className = 'kanban-card';
            card.draggable = true;
            card.dataset.id = o.id;
            card.dataset.date = o.pickup_date || '';

            const phoneClean = (o.client_phone || '').replace(/\D/g, '');
            const isLate = o.pickup_date && o.pickup_date < todayStr && !['ENTREGUE', 'FINALIZADO'].includes(o.status);

            if (isLate) card.classList.add('is-late');
            else if (o.pickup_date === todayStr) card.classList.add('is-today');
            else if (o.pickup_date === tomStr) card.classList.add('is-tomorrow');

            // Action button
            let actionBtn = '';
            if (o.status === 'AGUARDANDO_CONFIRMACAO') {
                actionBtn = `<button class="btn-main-action" data-status="CONFIRMADO" data-id="${o.id}">Confirmar</button>`;
            } else if (o.status === 'CONFIRMADO') {
                actionBtn = `<button class="btn-main-action" data-status="EM_PRODUCAO" data-id="${o.id}">Em Produção</button>`;
            } else if (o.status === 'EM_PRODUCAO') {
                actionBtn = `<button class="btn-main-action btn-main-action--pronto" data-status="PRONTO" data-id="${o.id}">Pronto</button>`;
            } else if (o.status === 'PRONTO') {
                actionBtn = `<button class="btn-main-action btn-main-action--entregue" data-status="ENTREGUE" data-id="${o.id}">Entregue</button>`;
            }

            card.innerHTML = `
                <div class="kcard-header">
                    <span class="kcard-number">#${o.order_number || '—'}</span>
                    ${isLate ? '<span class="kcard-badge-late">Atrasado</span>' : ''}
                </div>
                <div class="kcard-client">${o.client_name || 'Sem nome'}</div>
                <div class="kcard-details">
                    <span>${o.size_description || ''} · ${o.dough || ''}</span>
                    <span>${o.filling_1 || ''}${o.filling_2 ? ' + ' + o.filling_2 : ''}</span>
                </div>
                <div class="kcard-date">📅 ${fmtDate(o.pickup_date)} às ${o.pickup_time || '—'}</div>
                <div class="kcard-header" style="margin-top: 6px; margin-bottom: 0;">
                    <span class="kcard-value">${o.total_value ? 'R$ ' + Number(o.total_value).toFixed(2).replace('.', ',') : '—'}</span>
                </div>
                <div class="kcard-actions">
                    ${actionBtn}
                    ${phoneClean && !actionBtn ? '<a href="https://wa.me/' + phoneClean + '" target="_blank" class="btn-whatsapp" title="Abrir WhatsApp"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.019-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 01-4.243-1.216l-.256-.16-2.867.852.852-2.867-.16-.256A8 8 0 1120 12a8 8 0 01-8 8z"/></svg></a>' : ''}
                    <button class="btn-detail" title="Ver detalhes" data-id="${o.id}">•••</button>
                </div>`;

            // Setup events
            card.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', o.id);
                card.classList.add('dragging');
            });
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                document.querySelectorAll('.kanban-column').forEach(col => col.classList.remove('drag-over'));
            });

            card.querySelector('.btn-main-action')?.addEventListener('click', async (e) => {
                e.stopPropagation();
                const ns = e.target.dataset.status;
                try {
                    await API.updateStatus(o.id, ns);
                    showToast('Status atualizado para ' + STATUS_LABELS[ns], 'success');
                    loadKanban(); loadDashboard(); loadHistory();
                } catch(err) { showToast('Erro: ' + err.message, 'error'); }
            });

            card.querySelector('.btn-detail')?.addEventListener('click', (e) => { e.stopPropagation(); openOrderDrawer(o.id); });
            card.addEventListener('click', () => openOrderDrawer(o.id));
            container.appendChild(card);
        });

        // Setup drop zones
        document.querySelectorAll('.kanban-column').forEach(col => {
            col.addEventListener('dragover', e => { e.preventDefault(); col.querySelector('.kanban-cards').classList.add('drag-over'); });
            col.addEventListener('dragleave', e => { col.querySelector('.kanban-cards').classList.remove('drag-over'); });
            col.addEventListener('drop', async e => {
                e.preventDefault();
                col.querySelector('.kanban-cards').classList.remove('drag-over');
                const id = e.dataTransfer.getData('text/plain');
                const targetStatus = col.dataset.status;
                if(id && targetStatus) {
                    try {
                        await API.updateStatus(id, targetStatus);
                        showToast('Movido para ' + STATUS_LABELS[targetStatus], 'success');
                        loadKanban(); loadDashboard(); loadHistory();
                    } catch(err) { showToast('Erro: ' + err.message, 'error'); }
                }
            });
        });

        // Update counts
        columns.forEach(cid => {
            const el = document.getElementById(cid);
            if (!el) return;
            const n = el.children.length;
            const countEl = document.getElementById('kc-' + cid.replace('kanban-', ''));
            if (countEl) countEl.textContent = n;
        });

        filterKanban();

    } catch (e) {
        columns.forEach(id => { const c=document.getElementById(id); if(c) c.innerHTML = '<div class="kanban-empty">Erro ao carregar</div>'; });
        console.error('loadKanban:', e);
    }
}

function fmtDate(s) {
    if (!s) return '—';
    const [y, m, d] = s.split('-');
    return d + '/' + m;
}

function fmtFullDate(s) {
    if (!s) return '---';
    const [y, m, d] = s.split('-');
    return d + '/' + m + '/' + y;
}

// ============================================================
// HISTORICO
// ============================================================
function initHistoryFilters() {
    document.getElementById('history-search-input')?.addEventListener('input', renderHistory);
    document.getElementById('history-status-filter')?.addEventListener('change', renderHistory);
    document.getElementById('history-refresh')?.addEventListener('click', loadHistory);
}

async function loadHistory() {
    const list = document.getElementById('history-list');
    if (list) list.innerHTML = '<div class="kanban-loading">Carregando historico...</div>';

    try {
        const orders = await API.getOrders('status=FINALIZADO,CANCELADO');
        historyCache = orders.sort((a, b) => {
            const ad = a.pickup_date || a.created_at || '';
            const bd = b.pickup_date || b.created_at || '';
            if (bd !== ad) return bd.localeCompare(ad);
            return (b.order_number || 0) - (a.order_number || 0);
        });
        updateHistorySummary(historyCache);
        renderHistory();
    } catch (e) {
        console.error('loadHistory:', e);
        if (list) list.innerHTML = '<div class="kanban-empty">Erro ao carregar historico</div>';
    }
}

function updateHistorySummary(orders) {
    const finalizados = orders.filter(o => o.status === 'FINALIZADO');
    const cancelados = orders.filter(o => o.status === 'CANCELADO');
    const valor = finalizados.reduce((sum, o) => sum + parseFloat(o.total_value || 0), 0);

    const fEl = document.getElementById('hist-finalizados');
    const cEl = document.getElementById('hist-cancelados');
    const vEl = document.getElementById('hist-valor');
    if (fEl) fEl.textContent = finalizados.length;
    if (cEl) cEl.textContent = cancelados.length;
    if (vEl) vEl.textContent = 'R$ ' + valor.toFixed(2).replace('.', ',');
}

function renderHistory() {
    const list = document.getElementById('history-list');
    if (!list) return;

    const term = (document.getElementById('history-search-input')?.value || '').toLowerCase();
    const status = document.getElementById('history-status-filter')?.value || 'all';
    const filtered = historyCache.filter(o => {
        const haystack = [
            o.order_number, o.client_name, o.client_phone, o.size_description,
            o.dough, o.filling_1, o.filling_2, o.status
        ].filter(Boolean).join(' ').toLowerCase();
        const matchesTerm = !term || haystack.includes(term);
        const matchesStatus = status === 'all' || o.status === status;
        return matchesTerm && matchesStatus;
    });

    if (!filtered.length) {
        list.innerHTML = '<div class="empty-state"><p>Nenhum pedido encontrado no historico</p></div>';
        return;
    }

    list.innerHTML = filtered.map(o => {
        const statusClass = (o.status || '').toLowerCase();
        const statusLabel = STATUS_LABELS[o.status] || o.status || '---';
        const total = o.total_value ? 'R$ ' + Number(o.total_value).toFixed(2).replace('.', ',') : '---';
        return `
            <div class="history-card history-card--${statusClass}" data-id="${o.id}">
                <div class="history-card__top">
                    <div>
                        <strong>#${o.order_number || '---'}</strong>
                        <span>${o.client_name || 'Sem nome'}</span>
                    </div>
                    <span class="history-status history-status--${statusClass}">${statusLabel}</span>
                </div>
                <div class="history-card__meta">
                    <span>${fmtFullDate(o.pickup_date)} as ${o.pickup_time || '---'}</span>
                    <span>${o.client_phone || ''}</span>
                </div>
                <div class="history-card__details">
                    <span>${o.size_description || 'Tamanho pendente'}${o.dough ? ' · ' + o.dough : ''}</span>
                    <span>${[o.filling_1, o.filling_2].filter(Boolean).join(' + ') || 'Recheio pendente'}</span>
                </div>
                <div class="history-card__footer">
                    <span>${total}</span>
                    <button class="btn-detail history-detail" data-id="${o.id}">Detalhes</button>
                </div>
            </div>`;
    }).join('');

    list.querySelectorAll('.history-card').forEach(card => {
        card.addEventListener('click', () => openOrderDrawer(card.dataset.id));
    });
    list.querySelectorAll('.history-detail').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            openOrderDrawer(btn.dataset.id);
        });
    });
}

// ============================================================
// DRAWER
// ============================================================
function initDrawer() {
    document.getElementById('drawer-close').addEventListener('click', closeDrawer);
    document.getElementById('drawer-overlay').addEventListener('click', e => { if(e.target === e.currentTarget) closeDrawer(); });
}

async function openOrderDrawer(orderId) {
    try {
        const o = await API.getOrder(orderId);
        document.getElementById('drawer-title').textContent = 'Pedido #' + (o.order_number || '—');

        const phoneClean = (o.client_phone || '').replace(/\D/g, '');
        const waLink = phoneClean ? `<a href="https://wa.me/${phoneClean}" target="_blank" class="btn btn--whatsapp btn--sm">📱 WhatsApp</a>` : '';

        document.getElementById('drawer-body').innerHTML = [
            ['👤 Cliente', o.client_name || '—'],
            ['📱 Telefone', (o.client_phone || '—') + ' ' + waLink],
            ['🎂 Tamanho', o.size_description || '—'],
            ['🔲 Formato', o.shape || '—'],
            ['🍞 Massa', o.dough || '—'],
            ['🥄 Recheio 1', o.filling_1 || '—'],
            ['🥄 Recheio 2', o.filling_2 || '—'],
            ['✨ Finalização', o.finish || '—'],
            ['➕ Adicionais', o.extras?.length ? o.extras.join(', ') : 'Nenhum'],
            ['📅 Data', fmtDate(o.pickup_date) + ' às ' + (o.pickup_time || '—')],
            ['📝 Observações', o.notes || 'Nenhuma'],
        ].map(([l,v]) => `<div class="modal-detail-row"><span class="modal-detail-label">${l}</span><span class="modal-detail-value">${v}</span></div>`).join('')
        + `<div class="modal-detail-row" style="margin-top:10px;padding-top:12px;border-top:1px solid var(--border)"><span class="modal-detail-label" style="font-size:1rem;font-weight:700">💰 Total</span><span class="modal-detail-value" style="font-size:1.1rem;font-weight:700;color:var(--green)">${o.total_value ? 'R$ ' + Number(o.total_value).toFixed(2).replace('.', ',') : '—'}</span></div>`;

        // Footer buttons based on status
        const footer = document.getElementById('drawer-footer');
        const nextStatuses = STATUS_FLOW[o.status] || [];
        footer.innerHTML = nextStatuses.map(ns => {
            const cls = ns === 'CANCELADO' ? 'btn--danger' : 'btn--primary';
            const icon = ns === 'CANCELADO' ? '❌' : '✅';
            return `<button class="btn ${cls} btn--sm" data-status="${ns}">${icon} ${STATUS_LABELS[ns] || ns}</button>`;
        }).join('');

        footer.querySelectorAll('button[data-status]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const ns = btn.dataset.status;
                try {
                    await API.updateStatus(o.id, ns);
                    showToast('Status atualizado: ' + (STATUS_LABELS[ns] || ns), 'success');
                    closeDrawer();
                    loadKanban();
                    loadDashboard();
                    loadHistory();
                } catch (e) { showToast('Erro: ' + e.message, 'error'); }
            });
        });

        document.getElementById('drawer-overlay').classList.add('visible');
    } catch (e) {
        showToast('Erro ao abrir pedido: ' + e.message, 'error');
    }
}

function closeDrawer() { document.getElementById('drawer-overlay').classList.remove('visible'); }

// ============================================================
// NEW ORDER FORM
// ============================================================
async function loadCatalogForForm() {
    try {
        catalogCache = await API.getCatalog();
        populateSelects();
    } catch (e) {
        console.error('loadCatalogForForm:', e);
    }

    document.getElementById('new-order-form').addEventListener('submit', handleNewOrder);
}

function populateSelects() {
    const c = catalogCache;
    if (!c) return;

    // Sizes
    const sizeEl = document.getElementById('no-size');
    sizeEl.innerHTML = '<option value="">Selecione...</option>';
    c.sizes.filter(s => s.active).forEach(s => {
        sizeEl.innerHTML += `<option value="${s.id}" data-shape="${s.shape}" data-pw="${s.price_white}" data-pc="${s.price_chocolate}">${s.description} (${s.servings} fatias)</option>`;
    });

    // Fillings
    const f1 = document.getElementById('no-filling1');
    const f2 = document.getElementById('no-filling2');
    f1.innerHTML = '<option value="">Selecione...</option>';
    f2.innerHTML = '<option value="">Selecione...</option>';
    c.fillings.filter(f => f.available).forEach(f => {
        const opt = `<option value="${f.id}">${f.name}</option>`;
        f1.innerHTML += opt;
        f2.innerHTML += opt;
    });

    // Finishes
    const finEl = document.getElementById('no-finish');
    finEl.innerHTML = '<option value="">Selecione...</option>';
    c.finishes.filter(f => f.active).forEach(f => {
        finEl.innerHTML += `<option value="${f.id}">${f.name}${f.has_extra_cost ? ' 💰' : ''}</option>`;
    });

    // Extras
    const extEl = document.getElementById('no-extras');
    extEl.innerHTML = '';
    c.extras.filter(e => e.active).forEach(e => {
        extEl.innerHTML += `<option value="${e.id}">${e.name} (R$ ${Number(e.price_per_layer).toFixed(2).replace('.', ',')})</option>`;
    });

    // Time slots
    const timeEl = document.getElementById('no-time');
    timeEl.innerHTML = '<option value="">Selecione...</option>';
    c.time_slots.filter(t => t.available).forEach(t => {
        timeEl.innerHTML += `<option value="${t.slot_time}">${t.label}</option>`;
    });

    // Auto-fill shape based on size
    sizeEl.addEventListener('change', () => {
        const opt = sizeEl.selectedOptions[0];
        if (opt?.dataset.shape) {
            // Store shape for submission
            sizeEl.dataset.selectedShape = opt.dataset.shape;
        }
    });
}

async function handleNewOrder(e) {
    e.preventDefault();
    const form = e.target;
    const sizeEl = document.getElementById('no-size');

    const data = {
        client_name: document.getElementById('no-client-name').value.trim(),
        client_phone: document.getElementById('no-client-phone').value.trim(),
        size_id: sizeEl.value ? parseInt(sizeEl.value) : null,
        shape: sizeEl.dataset.selectedShape || null,
        dough: document.getElementById('no-dough').value || null,
        filling_1_id: document.getElementById('no-filling1').value ? parseInt(document.getElementById('no-filling1').value) : null,
        filling_2_id: document.getElementById('no-filling2').value ? parseInt(document.getElementById('no-filling2').value) : null,
        finish_id: document.getElementById('no-finish').value ? parseInt(document.getElementById('no-finish').value) : null,
        pickup_date: document.getElementById('no-date').value || null,
        pickup_time: document.getElementById('no-time').value || null,
        total_value: document.getElementById('no-value').value ? parseFloat(document.getElementById('no-value').value) : null,
        notes: document.getElementById('no-notes').value.trim() || null,
        filling_count: 2,
    };

    // Extras
    const extSel = document.getElementById('no-extras');
    const extras = [];
    for (const opt of extSel.selectedOptions) {
        if (opt.value) extras.push({ extra_id: parseInt(opt.value), layers: 1 });
    }
    if (extras.length) data.extras = extras;

    try {
        const res = await API.createOrder(data);
        showToast('Pedido #' + res.order_number + ' criado! ✅', 'success');
        form.reset();
        loadKanban();
        loadDashboard();

        // Offer to go to kanban
        setTimeout(() => {
            document.querySelector('[data-tab="pedidos"]')?.click();
        }, 1500);
    } catch (e) {
        showToast('Erro ao criar pedido: ' + e.message, 'error');
    }
}

// ============================================================
// ALERTS
// ============================================================
async function loadAlerts() {
    try {
        const data = await API.getAlerts();
        const list = document.getElementById('alerts-list');

        if (!data.alerts.length) {
            list.innerHTML = '<div class="empty-state"><span class="empty-icon">✅</span><p>Nenhum alerta pendente</p></div>';
            return;
        }

        list.innerHTML = data.alerts.map(a => {
            const phoneClean = (a.client_phone || '').replace(/\D/g, '');
            const typeLabels = {
                HUMAN_REQUESTED: '🙋 Ajuda Humana',
                STUCK_CLIENT: '🔒 Cliente Travado',
                CUSTOM_FILLING: '🎨 Recheio Personalizado',
                INTERPRETATION_ERROR: '❓ Erro de Interpretação',
                FLOW_ERROR: '⚠️ Erro no Fluxo',
                MAX_FALLBACK: '🔄 Máximo de Tentativas',
                READY_CAKE_INTEREST: '🎂 Interesse Pronta Entrega',
            };
            return `
            <div class="alert-item" data-id="${a.id}">
                <div class="alert-header">
                    <span class="alert-type">${typeLabels[a.alert_type] || a.alert_type}</span>
                    <span class="alert-time">${fmtDateTime(a.created_at)}</span>
                </div>
                <h4 class="alert-title">${a.title}</h4>
                ${a.description ? '<p class="alert-desc">' + a.description + '</p>' : ''}
                <div class="alert-meta">
                    ${a.client_name ? '<span>👤 ' + a.client_name + '</span>' : ''}
                    ${a.client_phone ? '<span>📱 ' + a.client_phone + '</span>' : ''}
                </div>
                ${a.last_message ? '<div class="alert-message">💬 "' + truncate(a.last_message, 120) + '"</div>' : ''}
                <div class="alert-actions">
                    ${phoneClean ? '<a href="https://wa.me/' + phoneClean + '" target="_blank" class="btn btn--whatsapp btn--sm">📱 Atender Cliente</a>' : ''}
                    <button class="btn btn--outline btn--sm alert-resolve-btn" data-id="${a.id}">✅ Resolvido</button>
                </div>
            </div>`;
        }).join('');

        list.querySelectorAll('.alert-resolve-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                try {
                    await API.resolveAlert(btn.dataset.id);
                    showToast('Alerta resolvido', 'success');
                    loadAlerts();
                    loadDashboard();
                } catch (e) { showToast('Erro: ' + e.message, 'error'); }
            });
        });
    } catch (e) {
        console.error('loadAlerts:', e);
    }
}

function fmtDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('pt-BR', { day:'2-digit', month:'2-digit' }) + ' ' + d.toLocaleTimeString('pt-BR', { hour:'2-digit', minute:'2-digit' });
}

function truncate(s, n) { return s.length > n ? s.slice(0, n) + '…' : s; }

// ============================================================
// CATALOG TAB (Config)
// ============================================================
function initCatalogTabs() {
    document.querySelectorAll('.catalog-tab').forEach(t => {
        t.addEventListener('click', () => {
            document.querySelectorAll('.catalog-tab').forEach(x => x.classList.remove('active'));
            t.classList.add('active');
            loadCatalogTab(t.dataset.catalog);
        });
    });
}

async function loadCatalogTab(type) {
    if (type === 'geral') { renderGeneralSettings(); return; }
    if (type === 'horarios') { renderServiceHours(); return; }

    const c = document.getElementById('catalog-content');
    if (!catalogCache) {
        try { catalogCache = await API.getCatalog(); } catch { c.innerHTML = '<p class="p-4">Erro ao carregar catálogo</p>'; return; }
    }

    const r = {
        tamanhos: renderSizes,
        recheios: renderFillings,
        adicionais: renderExtras,
        finalizacoes: renderFinishes,
        docinhos: renderSweets,
    };
    if (r[type]) c.innerHTML = r[type]();
    bindCatalogToggles(type);
}

function tog(on) { return '<label class="toggle"><input type="checkbox" ' + (on ? 'checked' : '') + '><span class="toggle-slider"></span></label>'; }
function inputNum(val, cls, step='0.01') { return `<input type="number" step="${step}" class="inline-edit ${cls}" value="${val}" style="width: 80px; padding: 4px; border: 1px solid var(--border); border-radius: 4px; text-align: right;">`; }

function renderSizes() {
    let html = `
    <div style="padding: 16px; border-bottom: 1px solid var(--border);">
        <button class="btn btn--primary btn--sm" onclick="toggleAddForm('sizes')">➕ Novo Tamanho</button>
        <div id="form-add-sizes" style="display:none; margin-top:12px; padding:16px; border:1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg);">
            <h3 style="font-size:0.9rem; margin-bottom:10px;">Adicionar Novo Tamanho</h3>
            <form id="form-new-size" onsubmit="event.preventDefault(); submitNewCatalogItem('sizes', this);" style="display:grid; gap:10px;">
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <div style="flex:1; min-width:150px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Descrição *</label><input type="text" name="description" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:80px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Peso (kg) *</label><input type="number" step="0.001" name="weight_kg" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:70px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Fatias *</label><input type="number" name="servings" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:120px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Forma *</label><select name="shape" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"><option value="REDONDA">REDONDA</option><option value="RETANGULAR">RETANGULAR</option></select></div>
                </div>
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <div style="flex:1;"><label style="font-size:0.75rem; color:var(--text-secondary);">Preço Massa Branca *</label><input type="number" step="0.01" name="price_white" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="flex:1;"><label style="font-size:0.75rem; color:var(--text-secondary);">Preço Massa Chocolate *</label><input type="number" step="0.01" name="price_chocolate" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                </div>
                <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:5px;">
                    <button type="button" class="btn btn--outline btn--sm" onclick="toggleAddForm('sizes')">Cancelar</button>
                    <button type="submit" class="btn btn--primary btn--sm">Salvar</button>
                </div>
            </form>
        </div>
    </div>
    `;

    if (!catalogCache?.sizes?.length) {
        return html + '<p class="p-4">Nenhum tamanho cadastrado</p>';
    }

    return html + '<table class="catalog-table"><thead><tr><th>#</th><th>Descrição</th><th>Peso</th><th>Fatias</th><th>Forma</th><th>Branca (R$)</th><th>Chocolate (R$)</th><th>Ativo</th><th>Ações</th></tr></thead><tbody>' +
        catalogCache.sizes.map(s => `<tr data-id="${s.id}"><td>${s.id}</td><td>${s.description}</td><td>${s.weight_kg} kg</td><td>${s.servings}</td><td>${s.shape || ''}</td><td>${inputNum(Number(s.price_white).toFixed(2), 'edit-pw')}</td><td>${inputNum(Number(s.price_chocolate).toFixed(2), 'edit-pc')}</td><td>${tog(s.active)}</td><td><button class="btn btn--danger btn--sm" style="padding:4px 8px;" onclick="deleteCatalogItemClick('sizes', ${s.id}, '${s.description.replace(/'/g, "\\'")}')">🗑️</button></td></tr>`).join('') +
        '</tbody></table>';
}

function renderFillings() {
    let html = `
    <div style="padding: 16px; border-bottom: 1px solid var(--border);">
        <button class="btn btn--primary btn--sm" onclick="toggleAddForm('fillings')">➕ Novo Recheio</button>
        <div id="form-add-fillings" style="display:none; margin-top:12px; padding:16px; border:1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg);">
            <h3 style="font-size:0.9rem; margin-bottom:10px;">Adicionar Novo Recheio</h3>
            <form id="form-new-filling" onsubmit="event.preventDefault(); submitNewCatalogItem('fillings', this);" style="display:grid; gap:10px;">
                <div><label style="font-size:0.75rem; color:var(--text-secondary);">Nome *</label><input type="text" name="name" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:5px;">
                    <button type="button" class="btn btn--outline btn--sm" onclick="toggleAddForm('fillings')">Cancelar</button>
                    <button type="submit" class="btn btn--primary btn--sm">Salvar</button>
                </div>
            </form>
        </div>
    </div>
    `;

    if (!catalogCache?.fillings?.length) {
        return html + '<p class="p-4">Nenhum recheio cadastrado</p>';
    }

    return html + '<table class="catalog-table"><thead><tr><th>#</th><th>Nome</th><th>Disponível</th><th>Ações</th></tr></thead><tbody>' +
        catalogCache.fillings.map(f => `<tr data-id="${f.id}"><td>${f.id}</td><td>${f.name}</td><td>${tog(f.available)}</td><td><button class="btn btn--danger btn--sm" style="padding:4px 8px;" onclick="deleteCatalogItemClick('fillings', ${f.id}, '${f.name.replace(/'/g, "\\'")}')">🗑️</button></td></tr>`).join('') +
        '</tbody></table>';
}

function renderExtras() {
    let html = `
    <div style="padding: 16px; border-bottom: 1px solid var(--border);">
        <button class="btn btn--primary btn--sm" onclick="toggleAddForm('extras')">➕ Novo Adicional</button>
        <div id="form-add-extras" style="display:none; margin-top:12px; padding:16px; border:1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg);">
            <h3 style="font-size:0.9rem; margin-bottom:10px;">Adicionar Novo Adicional</h3>
            <form id="form-new-extra" onsubmit="event.preventDefault(); submitNewCatalogItem('extras', this);" style="display:grid; gap:10px;">
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <div style="flex:1; min-width:150px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Nome *</label><input type="text" name="name" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:100px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Preço/Camada *</label><input type="number" step="0.01" name="price_per_layer" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <label style="font-size:0.85rem; color:var(--text-secondary); display:flex; align-items:center; gap:6px;"><input type="checkbox" name="requires_approval"> Exige aprovação manual?</label>
                </div>
                <div><label style="font-size:0.75rem; color:var(--text-secondary);">Descrição</label><input type="text" name="description" style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:5px;">
                    <button type="button" class="btn btn--outline btn--sm" onclick="toggleAddForm('extras')">Cancelar</button>
                    <button type="submit" class="btn btn--primary btn--sm">Salvar</button>
                </div>
            </form>
        </div>
    </div>
    `;

    if (!catalogCache?.extras?.length) {
        return html + '<p class="p-4">Nenhum adicional cadastrado</p>';
    }

    return html + '<table class="catalog-table"><thead><tr><th>#</th><th>Nome</th><th>R$/Camada</th><th>Aprovação</th><th>Ativo</th><th>Ações</th></tr></thead><tbody>' +
        catalogCache.extras.map(e => `<tr data-id="${e.id}"><td>${e.id}</td><td>${e.name}</td><td>${inputNum(Number(e.price_per_layer).toFixed(2), 'edit-ppl')}</td><td><label><input type="checkbox" class="edit-req" ${e.requires_approval ? 'checked' : ''}> Sim</label></td><td>${tog(e.active)}</td><td><button class="btn btn--danger btn--sm" style="padding:4px 8px;" onclick="deleteCatalogItemClick('extras', ${e.id}, '${e.name.replace(/'/g, "\\'")}')">🗑️</button></td></tr>`).join('') +
        '</tbody></table>';
}

function renderFinishes() {
    let html = `
    <div style="padding: 16px; border-bottom: 1px solid var(--border);">
        <button class="btn btn--primary btn--sm" onclick="toggleAddForm('finishes')">➕ Nova Finalização</button>
        <div id="form-add-finishes" style="display:none; margin-top:12px; padding:16px; border:1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg);">
            <h3 style="font-size:0.9rem; margin-bottom:10px;">Adicionar Nova Finalização</h3>
            <form id="form-new-finish" onsubmit="event.preventDefault(); submitNewCatalogItem('finishes', this);" style="display:grid; gap:10px;">
                <div><label style="font-size:0.75rem; color:var(--text-secondary);">Nome *</label><input type="text" name="name" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                <div style="display:flex; gap:15px; flex-wrap:wrap;">
                    <label style="font-size:0.85rem; color:var(--text-secondary); display:flex; align-items:center; gap:6px;"><input type="checkbox" name="has_extra_cost"> Tem custo extra?</label>
                    <label style="font-size:0.85rem; color:var(--text-secondary); display:flex; align-items:center; gap:6px;"><input type="checkbox" name="requires_approval"> Exige aprovação manual?</label>
                </div>
                <div><label style="font-size:0.75rem; color:var(--text-secondary);">Descrição</label><input type="text" name="description" style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:5px;">
                    <button type="button" class="btn btn--outline btn--sm" onclick="toggleAddForm('finishes')">Cancelar</button>
                    <button type="submit" class="btn btn--primary btn--sm">Salvar</button>
                </div>
            </form>
        </div>
    </div>
    `;

    if (!catalogCache?.finishes?.length) {
        return html + '<p class="p-4">Nenhuma finalização cadastrada</p>';
    }

    return html + '<table class="catalog-table"><thead><tr><th>#</th><th>Nome</th><th>Custo Extra</th><th>Aprovação</th><th>Ativa</th><th>Ações</th></tr></thead><tbody>' +
        catalogCache.finishes.map(f => `<tr data-id="${f.id}"><td>${f.id}</td><td>${f.name}</td><td><label><input type="checkbox" class="edit-cost" ${f.has_extra_cost ? 'checked' : ''}> Sim</label></td><td><label><input type="checkbox" class="edit-req" ${f.requires_approval ? 'checked' : ''}> Sim</label></td><td>${tog(f.active)}</td><td><button class="btn btn--danger btn--sm" style="padding:4px 8px;" onclick="deleteCatalogItemClick('finishes', ${f.id}, '${f.name.replace(/'/g, "\\'")}')">🗑️</button></td></tr>`).join('') +
        '</tbody></table>';
}

function renderSweets() {
    let html = `
    <div style="padding: 16px; border-bottom: 1px solid var(--border);">
        <button class="btn btn--primary btn--sm" onclick="toggleAddForm('sweets')">➕ Novo Docinho</button>
        <div id="form-add-sweets" style="display:none; margin-top:12px; padding:16px; border:1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg);">
            <h3 style="font-size:0.9rem; margin-bottom:10px;">Adicionar Novo Docinho</h3>
            <form id="form-new-sweet" onsubmit="event.preventDefault(); submitNewCatalogItem('sweets', this);" style="display:grid; gap:10px;">
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <div style="flex:1; min-width:150px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Nome *</label><input type="text" name="name" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:80px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Qtd/Cento *</label><input type="number" name="unit_quantity" value="100" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:90px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Preço *</label><input type="number" step="0.01" name="price" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                    <div style="width:80px;"><label style="font-size:0.75rem; color:var(--text-secondary);">Mínimo *</label><input type="number" name="min_order_qty" value="50" required style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                </div>
                <div><label style="font-size:0.75rem; color:var(--text-secondary);">Descrição</label><input type="text" name="description" style="width:100%; padding:6px; border:1px solid var(--border); border-radius:4px;"></div>
                <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:5px;">
                    <button type="button" class="btn btn--outline btn--sm" onclick="toggleAddForm('sweets')">Cancelar</button>
                    <button type="submit" class="btn btn--primary btn--sm">Salvar</button>
                </div>
            </form>
        </div>
    </div>
    `;

    if (!catalogCache?.sweets?.length) {
        return html + '<p class="p-4">Nenhum docinho cadastrado</p>';
    }

    return html + '<table class="catalog-table"><thead><tr><th>#</th><th>Nome</th><th>Qtd</th><th>Preço (R$)</th><th>Mín.</th><th>Ativo</th><th>Ações</th></tr></thead><tbody>' +
        catalogCache.sweets.map(s => `<tr data-id="${s.id}"><td>${s.id}</td><td>${s.name}</td><td>${s.unit_quantity} un</td><td>${inputNum(Number(s.price).toFixed(2), 'edit-price')}</td><td>${s.min_order_qty} un</td><td>${tog(s.active)}</td><td><button class="btn btn--danger btn--sm" style="padding:4px 8px;" onclick="deleteCatalogItemClick('sweets', ${s.id}, '${s.name.replace(/'/g, "\\'")}')">🗑️</button></td></tr>`).join('') +
        '</tbody></table>';
}

function bindCatalogToggles(type) {
    const c = document.getElementById('catalog-content');
    const fieldMap = {
        tamanhos: 'active', recheios: 'available', adicionais: 'active', finalizacoes: 'active', docinhos: 'active',
    };
    const apiType = {
        tamanhos: 'sizes', recheios: 'fillings', adicionais: 'extras', finalizacoes: 'finishes', docinhos: 'sweets',
    };

    const updateItem = async (el, id, data, name, successMsg) => {
        try {
            await API.updateCatalogItem(apiType[type], id, data);
            showToast(successMsg || `"${name}" atualizado`, 'success');
            catalogCache = null;
        } catch (err) {
            showToast('Erro: ' + err.message, 'error');
            if (el.type === 'checkbox') el.checked = !el.checked;
        }
    };

    c.querySelectorAll('.toggle input').forEach(toggle => {
        toggle.addEventListener('change', (e) => {
            const tr = e.target.closest('tr');
            const id = tr?.dataset.id;
            const name = tr?.querySelector('td:nth-child(2)')?.textContent || '';
            updateItem(e.target, id, { [fieldMap[type]]: e.target.checked }, name, `"${name}" ${e.target.checked ? 'ativado' : 'desativado'}`);
        });
    });

    // Inputs (preços, etc)
    c.querySelectorAll('.inline-edit, .edit-req, .edit-cost').forEach(inp => {
        inp.addEventListener('change', (e) => {
            const tr = e.target.closest('tr');
            const id = tr?.dataset.id;
            const name = tr?.querySelector('td:nth-child(2)')?.textContent || '';
            const data = {};

            if (e.target.classList.contains('edit-pw')) data.price_white = parseFloat(e.target.value);
            if (e.target.classList.contains('edit-pc')) data.price_chocolate = parseFloat(e.target.value);
            if (e.target.classList.contains('edit-ppl')) data.price_per_layer = parseFloat(e.target.value);
            if (e.target.classList.contains('edit-price')) data.price = parseFloat(e.target.value);
            if (e.target.classList.contains('edit-req')) data.requires_approval = e.target.checked;
            if (e.target.classList.contains('edit-cost')) data.has_extra_cost = e.target.checked;

            updateItem(e.target, id, data, name);
        });
    });
}

// ============================================================
// SERVICE HOURS SETTINGS
// ============================================================
async function renderServiceHours() {
    const c = document.getElementById('catalog-content');
    let settings = {};
    try { settings = (await API.getSettings()).settings; } catch { /* use defaults */ }

    const defaultHours = {
        "0": {isOpen: true, openTime: "06:00", closeTime: "20:00"},
        "1": {isOpen: true, openTime: "06:00", closeTime: "20:00"},
        "2": {isOpen: true, openTime: "06:00", closeTime: "20:00"},
        "3": {isOpen: true, openTime: "06:00", closeTime: "20:00"},
        "4": {isOpen: true, openTime: "06:00", closeTime: "20:00"},
        "5": {isOpen: true, openTime: "07:00", closeTime: "18:00"},
        "6": {isOpen: true, openTime: "09:00", closeTime: "12:00"}
    };

    const hours = settings.service_hours || defaultHours;
    const days = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

    let html = `
    <div class="config-grid" style="padding: 22px;">
        <div class="card card--full">
            <h2>📅 Horários de Serviço (por dia da semana)</h2>
            <table class="catalog-table">
                <thead>
                    <tr>
                        <th>Dia</th>
                        <th>Aberto?</th>
                        <th>Abertura</th>
                        <th>Fechamento</th>
                    </tr>
                </thead>
                <tbody id="service-hours-body">
    `;

    for (let i = 0; i < 7; i++) {
        const daySet = hours[i] || {isOpen: false, openTime: "00:00", closeTime: "00:00"};
        html += `
            <tr data-day="${i}">
                <td>${days[i]}</td>
                <td>${tog(daySet.isOpen)}</td>
                <td><input type="time" class="inline-edit sh-open" value="${daySet.openTime}"></td>
                <td><input type="time" class="inline-edit sh-close" value="${daySet.closeTime}"></td>
            </tr>
        `;
    }

    html += `
                </tbody>
            </table>
            <div style="margin-top: 20px;">
                <button class="btn btn--primary" id="btn-save-service-hours">Salvar Horários</button>
            </div>
        </div>
    </div>`;

    c.innerHTML = html;

    document.getElementById('btn-save-service-hours').addEventListener('click', async () => {
        const trs = document.querySelectorAll('#service-hours-body tr');
        const newHours = {};
        trs.forEach(tr => {
            const day = tr.dataset.day;
            const isOpen = tr.querySelector('.toggle input').checked;
            const openTime = tr.querySelector('.sh-open').value;
            const closeTime = tr.querySelector('.sh-close').value;
            newHours[day] = {isOpen, openTime, closeTime};
        });
        try {
            await API.saveSettings({ service_hours: newHours });
            showToast('Horários salvos! ✅', 'success');
        } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    });
}

// ============================================================
// GENERAL SETTINGS (sub-tab "Geral" within Config)
// ============================================================
async function renderGeneralSettings() {
    const c = document.getElementById('catalog-content');
    let settings = {};
    try { settings = (await API.getSettings()).settings; } catch { /* use defaults */ }

    c.innerHTML = `
    <div class="config-grid" style="padding: 22px;">
        <div class="card">
            <h2>🏪 Confeitaria</h2>
            <div class="cfg-field"><label>Nome</label><input type="text" id="cfg-shop-name" value="${settings.shop_name || 'Dani Bolos'}"></div>
            <div class="cfg-field"><label>Telefone / WhatsApp</label><input type="text" id="cfg-shop-phone" value="${settings.shop_phone || ''}"></div>
            <div class="cfg-row">
                <div class="cfg-field"><label>Abre às</label><input type="time" id="cfg-open" value="${settings.opening_time || '08:00'}"></div>
                <div class="cfg-field"><label>Fecha às</label><input type="time" id="cfg-close" value="${settings.closing_time || '18:00'}"></div>
            </div>
            <div class="cfg-field"><label>Máx. pedidos/dia (padrão)</label><input type="number" id="cfg-max-orders" value="${settings.max_orders_default || 5}" min="1" max="50"></div>
        </div>
        <div class="card">
            <h2>🤖 Bot</h2>
            <div class="cfg-field"><label>Timeout conversa (min)</label><input type="number" id="cfg-timeout" value="${settings.timeout_minutes || 120}" min="10"></div>
            <div class="cfg-field"><label>Máx. fallbacks antes de pausar</label><input type="number" id="cfg-fallback" value="${settings.max_fallback_count || 3}" min="1"></div>
        </div>
        <div class="card card--full">
            <h2>📢 Mensagens e Avisos</h2>
            <div class="cfg-field"><label>Aviso Sazonal (início da conversa)</label><textarea rows="2" id="cfg-seasonal" placeholder="Ex: 🎄 Agenda de Natal aberta!">${settings.seasonal_message || ''}</textarea></div>
            <div class="cfg-field"><label>Mensagem de Limite Atingido (quando um dia lota)</label><textarea rows="2" id="cfg-limit-message" placeholder="Ex: Infelizmente já atingimos o limite de encomendas para esta data. Por favor, escolha outro dia.">${settings.limit_reached_message || ''}</textarea></div>
            <button class="btn btn--primary" id="btn-save-general">Salvar Configurações</button>
        </div>
    </div>`;

    document.getElementById('btn-save-general').addEventListener('click', saveGeneralSettings);
}

async function saveGeneralSettings() {
    const data = {
        shop_name: document.getElementById('cfg-shop-name').value,
        shop_phone: document.getElementById('cfg-shop-phone').value,
        opening_time: document.getElementById('cfg-open').value,
        closing_time: document.getElementById('cfg-close').value,
        max_orders_default: parseInt(document.getElementById('cfg-max-orders').value) || 5,
        timeout_minutes: parseInt(document.getElementById('cfg-timeout').value) || 120,
        max_fallback_count: parseInt(document.getElementById('cfg-fallback').value) || 3,
        seasonal_message: document.getElementById('cfg-seasonal').value,
        limit_reached_message: document.getElementById('cfg-limit-message').value,
    };
    try {
        await API.saveSettings(data);
        showToast('Configurações salvas! ✅', 'success');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ============================================================
// SETTINGS — Flow toggles
// ============================================================
async function loadSettings() {
    try {
        const data = await API.getSettings();
        const s = data.settings;
        document.getElementById('cfg-bot-active').checked = s.bot_active !== false;
        document.getElementById('cfg-orders-paused').checked = s.orders_paused !== true;
    } catch { /* use defaults */ }

    document.getElementById('cfg-bot-active').addEventListener('change', async (e) => {
        try {
            await API.saveSettings({ bot_active: e.target.checked });
            showToast(e.target.checked ? 'Bot ativado' : 'Bot pausado', e.target.checked ? 'success' : 'info');
        } catch (err) { e.target.checked = !e.target.checked; showToast('Erro', 'error'); }
    });

    document.getElementById('cfg-orders-paused').addEventListener('change', async (e) => {
        try {
            await API.saveSettings({ orders_paused: !e.target.checked });
            showToast(e.target.checked ? 'Pedidos ativos' : 'Pedidos pausados', e.target.checked ? 'success' : 'info');
        } catch (err) { e.target.checked = !e.target.checked; showToast('Erro', 'error'); }
    });
}


// ============================================================
// READY CAKES (PRONTA ENTREGA)
// ============================================================

async function loadReadyCakes() {
    const list = document.getElementById('ready-cakes-list');
    if (!list) return;

    list.innerHTML = '<div class="kanban-loading" style="grid-column: 1 / -1;">Carregando bolos prontos...</div>';

    try {
        const cakes = await API.getReadyCakes();
        if (!cakes.length) {
            list.innerHTML = '<div class="empty-state" style="grid-column: 1 / -1;"><span class="empty-icon">🍰</span><p>Nenhum bolo pronto cadastrado para hoje.</p></div>';
            return;
        }

        list.innerHTML = cakes.map(c => {
            const priceStr = c.price ? 'R$ ' + Number(c.price).toFixed(2).replace('.', ',') : 'Sob consulta';
            const descStr = c.description ? `<p style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 12px; line-height: 1.4;">${c.description}</p>` : '';
            
            return `
            <div class="card" style="display: flex; flex-direction: column; justify-content: space-between; border-left: 4px solid ${c.available ? 'var(--green)' : 'var(--text-muted)'}; opacity: ${c.available ? 1 : 0.7};">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <h3 style="font-size: 1rem; font-weight: 600; color: var(--text);">${c.flavor}</h3>
                        <span style="font-size: 0.9rem; font-weight: 700; color: var(--green);">${priceStr}</span>
                    </div>
                    ${descStr}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 12px; border-top: 1px solid var(--border); margin-top: 12px;">
                    <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-secondary);">Disponível?</span>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <label class="toggle">
                            <input type="checkbox" ${c.available ? 'checked' : ''} onchange="toggleReadyCakeAvailability(${c.id}, this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                        <button class="btn btn--danger btn--sm" style="padding: 4px 8px; margin-left: 10px;" onclick="deleteReadyCakeClick(${c.id}, '${c.flavor.replace(/'/g, "\\'")}')">🗑️</button>
                    </div>
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('loadReadyCakes:', e);
        list.innerHTML = '<div class="kanban-empty" style="grid-column: 1 / -1;">Erro ao carregar bolos prontos</div>';
    }
}

window.submitReadyCakeForm = async function(form) {
    const flavor = document.getElementById('rc-flavor').value.trim();
    const priceVal = document.getElementById('rc-price').value;
    const description = document.getElementById('rc-description').value.trim() || null;
    const price = priceVal ? parseFloat(priceVal) : null;

    try {
        await API.createReadyCake({ flavor, price, description });
        showToast('Bolo pronto adicionado! 🎂', 'success');
        form.reset();
        loadReadyCakes();
    } catch (err) {
        showToast('Erro ao criar bolo pronto: ' + err.message, 'error');
    }
};

window.toggleReadyCakeAvailability = async function(id, available) {
    try {
        await API.updateReadyCake(id, { available });
        showToast(available ? 'Bolo marcado como disponível' : 'Bolo marcado como reservado/indisponível', 'success');
        loadReadyCakes();
    } catch (e) {
        showToast('Erro ao atualizar disponibilidade: ' + e.message, 'error');
        loadReadyCakes();
    }
};

window.deleteReadyCakeClick = async function(id, flavor) {
    if (!confirm(`Tem certeza que deseja excluir o bolo pronto "${flavor}"?`)) return;
    try {
        await API.deleteReadyCake(id);
        showToast('Bolo pronto removido! 🗑️', 'success');
        loadReadyCakes();
    } catch (e) {
        showToast('Erro ao remover bolo pronto: ' + e.message, 'error');
    }
};

// Global Helpers for Catalog CRUD
window.toggleAddForm = function(type) {
    const el = document.getElementById('form-add-' + type);
    if (el) {
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }
};

window.submitNewCatalogItem = async function(type, form) {
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => {
        if (value === 'on') data[key] = true;
        else {
            if (['weight_kg', 'servings', 'price_white', 'price_chocolate', 'price_per_layer', 'price', 'unit_quantity', 'min_order_qty'].includes(key)) {
                data[key] = value.includes('.') || value.includes(',') ? parseFloat(value.replace(',', '.')) : parseInt(value);
            } else {
                data[key] = value;
            }
        }
    });

    if (form.elements['requires_approval'] && !data['requires_approval']) data['requires_approval'] = false;
    if (form.elements['has_extra_cost'] && !data['has_extra_cost']) data['has_extra_cost'] = false;

    const apiTypeMap = {
        tamanhos: 'sizes', recheios: 'fillings', adicionais: 'extras', finalizacoes: 'finishes', docinhos: 'sweets',
        sizes: 'sizes', fillings: 'fillings', extras: 'extras', finishes: 'finishes', sweets: 'sweets'
    };

    try {
        await API.createCatalogItem(apiTypeMap[type], data);
        showToast('Item adicionado com sucesso! ✅', 'success');
        form.reset();
        window.toggleAddForm(type);
        catalogCache = null;
        const currentActiveTab = document.querySelector('.catalog-tab.active')?.dataset.catalog;
        if (currentActiveTab) loadCatalogTab(currentActiveTab);
        loadCatalogForForm();
    } catch (e) {
        showToast('Erro ao criar item: ' + e.message, 'error');
    }
};

window.deleteCatalogItemClick = async function(type, id, label) {
    if (!confirm(`Tem certeza que deseja excluir "${label}"?`)) return;

    const apiTypeMap = {
        tamanhos: 'sizes', recheios: 'fillings', adicionais: 'extras', finalizacoes: 'finishes', docinhos: 'sweets',
        sizes: 'sizes', fillings: 'fillings', extras: 'extras', finishes: 'finishes', sweets: 'sweets'
    };

    try {
        await API.deleteCatalogItem(apiTypeMap[type], id);
        showToast('Item removido com sucesso! 🗑️', 'success');
        catalogCache = null;
        const currentActiveTab = document.querySelector('.catalog-tab.active')?.dataset.catalog;
        if (currentActiveTab) loadCatalogTab(currentActiveTab);
        loadCatalogForForm();
    } catch (e) {
        showToast('Erro ao remover item: ' + e.message, 'error');
    }
};


// ============================================================
// TOAST
// ============================================================
function showToast(msg, type='info') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = 'toast toast--' + type;
    const icons = {success:'✅', error:'❌', info:'ℹ️'};
    t.innerHTML = '<span>' + (icons[type]||'') + '</span><span>' + msg + '</span>';
    c.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(30px)'; t.style.transition='all 0.3s'; setTimeout(()=>t.remove(),300); }, 3500);
}
