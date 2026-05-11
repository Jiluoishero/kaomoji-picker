/* ═══════════════════════════════════════════
   Kaomoji Picker — Frontend Logic
   ═══════════════════════════════════════════ */

// ── State ──
let groups = [];
let currentGroupIndex = 0;
let editMode = false;
let addMode = null;
let addTargetGroup = null;
let currentView = 'main';
let hotkeyRecording = false;
let apiReady = false;

// ── DOM refs ──
const $ = (sel) => document.querySelector(sel);

// ── API helper ──
function api() {
    return window.pywebview && window.pywebview.api;
}

// ── Init: bind events immediately, load data when API ready ──
document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
});

window.addEventListener('pywebviewready', () => {
    apiReady = true;
    loadData();
    loadConfig();
});

// Called from Python via evaluate_js with pre-pushed data
function initFromPython() {
    if (window._initData) {
        groups = window._initData;
        if (currentGroupIndex >= groups.length) currentGroupIndex = 0;
        renderTabs();
        renderSymbols();
    }
    if (window._initConfig) {
        $('#hotkey-text').textContent = formatHotkey(window._initConfig.hotkey || 'ctrl+`');
        $('#toggle-autostart').checked = window._initConfig.auto_start || false;
    }
    apiReady = true;
}
window.initFromPython = initFromPython;

// Fallback: retry if nothing worked after 3s
setTimeout(() => {
    if (groups.length === 0) {
        if (window._initData) { initFromPython(); }
        else if (api()) { apiReady = true; loadData(); loadConfig(); }
    }
}, 3000);

async function loadData() {
    if (!api()) return;
    try {
        groups = await api().get_groups();
        if (currentGroupIndex >= groups.length) currentGroupIndex = 0;
        renderTabs();
        renderSymbols();
    } catch (e) {
        console.error('loadData failed:', e);
    }
}

async function loadConfig() {
    if (!api()) return;
    try {
        const config = await api().get_config();
        $('#hotkey-text').textContent = formatHotkey(config.hotkey || 'ctrl+`');
        $('#toggle-autostart').checked = config.auto_start || false;
    } catch (e) {
        console.error('loadConfig failed:', e);
    }
}

function formatHotkey(hk) {
    return hk.split('+').map(k => {
        k = k.trim();
        if (k.toLowerCase() === 'ctrl') return 'Ctrl';
        if (k.toLowerCase() === 'alt') return 'Alt';
        if (k.toLowerCase() === 'shift') return 'Shift';
        return k.charAt(0).toUpperCase() + k.slice(1);
    }).join(' + ');
}

// ── Bind Events ──
function bindEvents() {
    const app = $('#app');

    $('#btn-close').addEventListener('click', () => {
        if (api()) api().close_panel();
    });

    $('#btn-add').addEventListener('click', toggleAddMode);
    $('#btn-settings').addEventListener('click', () => switchView('settings'));

    $('#btn-add-cancel').addEventListener('click', exitAddMode);
    $('#btn-add-confirm').addEventListener('click', confirmAdd);

    $('#btn-settings-back').addEventListener('click', () => switchView('main'));

    $('#toggle-autostart').addEventListener('change', (e) => {
        if (api()) api().set_auto_start(e.target.checked);
    });

    $('#toggle-editmode').addEventListener('change', (e) => {
        setEditMode(e.target.checked);
    });

    $('#hotkey-btn').addEventListener('click', startHotkeyRecording);
    $('#btn-add-group-edit').addEventListener('click', addNewGroup);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (hotkeyRecording) {
                stopHotkeyRecording();
            } else if (addMode) {
                exitAddMode();
            } else if (api()) {
                api().close_panel();
            }
        }
    });
}

// ═══════════════════════════════════
// View Switching
// ═══════════════════════════════════
function switchView(view) {
    currentView = view;
    const mainView = $('#main-view');
    const settingsView = $('#settings-view');
    mainView.classList.remove('active-view');
    settingsView.classList.remove('active-view');

    if (view === 'main') {
        mainView.classList.add('active-view');
        $('#toggle-editmode').checked = editMode;
    } else {
        settingsView.classList.add('active-view');
    }
}

// ═══════════════════════════════════
// Tab Rendering
// ═══════════════════════════════════
function renderTabs() {
    const tabsScroll = $('#tabs-scroll');
    tabsScroll.innerHTML = '';

    groups.forEach((group, index) => {
        const tab = document.createElement('button');
        tab.className = 'tab';
        tab.textContent = group.name;
        tab.dataset.index = index;

        if (index === currentGroupIndex) tab.classList.add('active');

        if (addMode === 'selecting') {
            tab.classList.add('add-mode-highlight');
        }

        if (editMode) {
            tab.classList.add('edit-mode');
            tab.draggable = true;
            tab.style.position = 'relative';

            const badge = document.createElement('span');
            badge.className = 'tab-delete-badge';
            badge.textContent = '✕';
            badge.addEventListener('click', (e) => {
                e.stopPropagation();
                confirmDeleteGroup(group.name);
            });
            tab.appendChild(badge);

            tab.addEventListener('dragstart', onTabDragStart);
            tab.addEventListener('dragover', onTabDragOver);
            tab.addEventListener('drop', onTabDrop);
            tab.addEventListener('dragend', onTabDragEnd);

            tab.addEventListener('dblclick', (e) => {
                e.stopPropagation();
                startRenameGroup(tab, group.name);
            });
        }

        tab.addEventListener('click', () => {
            if (editMode) return;
            if (addMode === 'selecting') {
                addTargetGroup = group.name;
                addMode = 'input';
                renderTabs();
                showAddInput();
                return;
            }
            currentGroupIndex = index;
            renderTabs();
            renderSymbols();
        });

        if (addMode === 'input' && addTargetGroup === group.name) {
            tab.classList.remove('add-mode-highlight');
            tab.classList.add('add-mode-selected');
        }

        tabsScroll.appendChild(tab);
    });

    $('#btn-add-group-edit').classList.toggle('hidden', !editMode);
}

// ═══════════════════════════════════
// Symbol Grid Rendering
// ═══════════════════════════════════
function renderSymbols() {
    const symbolGrid = $('#symbol-grid');
    symbolGrid.innerHTML = '';

    if (groups.length === 0) {
        symbolGrid.innerHTML = '<div class="empty-state"><span class="empty-state-icon">( ´_ゝ`)</span><span>还没有分组</span></div>';
        return;
    }

    const group = groups[currentGroupIndex];
    if (!group || !group.items || group.items.length === 0) {
        symbolGrid.innerHTML = '<div class="empty-state"><span class="empty-state-icon">(・∀・)</span><span>空的，点 + 添加符号</span></div>';
        return;
    }

    group.items.forEach((item) => {
        const el = document.createElement('div');
        el.className = 'symbol-item';
        el.textContent = ' ' + item.symbol + ' ';

        if (editMode) {
            el.classList.add('edit-mode');
            const badge = document.createElement('span');
            badge.className = 'delete-badge';
            badge.textContent = '✕';
            badge.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteSymbol(group.name, item.symbol, el);
            });
            el.appendChild(badge);
        } else {
            el.addEventListener('click', () => {
                el.style.transform = 'scale(0.94)';
                setTimeout(() => { el.style.transform = ''; }, 80);
                if (api()) api().paste_symbol(item.symbol);
            });
        }

        symbolGrid.appendChild(el);
    });
}

// ═══════════════════════════════════
// Add Mode
// ═══════════════════════════════════
function toggleAddMode() {
    if (addMode) { exitAddMode(); } else { enterAddMode(); }
}

function enterAddMode() {
    addMode = 'selecting';
    addTargetGroup = null;
    $('#btn-add').classList.add('active-btn');
    renderTabs();
}

function showAddInput() {
    const addArea = $('#add-area');
    addArea.classList.remove('collapsed');
    addArea.classList.add('expanded');
    $('#add-textarea').value = '';
    setTimeout(() => $('#add-textarea').focus(), 100);
}

function exitAddMode() {
    addMode = null;
    addTargetGroup = null;
    const addArea = $('#add-area');
    addArea.classList.remove('expanded');
    addArea.classList.add('collapsed');
    $('#add-textarea').value = '';
    $('#btn-add').classList.remove('active-btn');
    renderTabs();
}

async function confirmAdd() {
    const text = $('#add-textarea').value.trim();
    if (!text || !addTargetGroup || !api()) return;
    try {
        await api().add_items(addTargetGroup, text);
        await loadData();
        exitAddMode();
    } catch (e) { console.error('add failed:', e); }
}

// ═══════════════════════════════════
// Edit Mode
// ═══════════════════════════════════
function setEditMode(enabled) {
    editMode = enabled;
    if (!enabled) exitAddMode();
    renderTabs();
    renderSymbols();
}

async function deleteSymbol(groupName, symbol, el) {
    el.style.transition = 'all 0.2s ease';
    el.style.opacity = '0';
    el.style.transform = 'scale(0.7)';
    setTimeout(async () => {
        if (!api()) return;
        try {
            await api().delete_item(groupName, symbol);
            await loadData();
        } catch (e) { console.error('delete failed:', e); }
    }, 200);
}

// ═══════════════════════════════════
// Group Management
// ═══════════════════════════════════
function addNewGroup() {
    const app = $('#app');
    const overlay = document.createElement('div');
    overlay.id = 'confirm-overlay';
    overlay.innerHTML = '<div class="confirm-dialog"><p>新分组名称</p><input type="text" class="tab-rename-input" id="new-group-input" style="width:100%;margin-bottom:14px;padding:8px 10px;font-size:13px" placeholder="输入分组名称…"><div class="confirm-actions"><button class="btn-small btn-ghost" id="confirm-no">取消</button><button class="btn-small btn-accent" id="confirm-yes">创建</button></div></div>';
    app.appendChild(overlay);
    const inp = overlay.querySelector('#new-group-input');
    setTimeout(() => inp.focus(), 50);

    const close = () => overlay.remove();
    const submit = async () => {
        const name = inp.value.trim();
        close();
        if (!name || !api()) return;
        try { await api().add_group(name); await loadData(); }
        catch (e) { console.error('add group failed:', e); }
    };
    overlay.querySelector('#confirm-no').addEventListener('click', close);
    overlay.querySelector('#confirm-yes').addEventListener('click', submit);
    inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submit();
        if (e.key === 'Escape') close();
    });
}

function confirmDeleteGroup(name) {
    const app = $('#app');
    const overlay = document.createElement('div');
    overlay.id = 'confirm-overlay';
    overlay.innerHTML = '<div class="confirm-dialog"><p>确定删除分组「' + name + '」？<br>组内符号将一并删除。</p><div class="confirm-actions"><button class="btn-small btn-ghost" id="confirm-no">取消</button><button class="btn-small btn-danger" id="confirm-yes">删除</button></div></div>';
    app.appendChild(overlay);
    overlay.querySelector('#confirm-no').addEventListener('click', () => overlay.remove());
    overlay.querySelector('#confirm-yes').addEventListener('click', async () => {
        overlay.remove();
        if (!api()) return;
        try { await api().delete_group(name); currentGroupIndex = 0; await loadData(); }
        catch (e) { console.error('delete group failed:', e); }
    });
}

function startRenameGroup(tabEl, oldName) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'tab-rename-input';
    input.value = oldName;
    tabEl.textContent = '';
    tabEl.appendChild(input);
    input.focus();
    input.select();

    const finish = async () => {
        const newName = input.value.trim();
        if (newName && newName !== oldName && api()) {
            try { await api().rename_group(oldName, newName); await loadData(); }
            catch (e) { renderTabs(); }
        } else { renderTabs(); }
    };
    input.addEventListener('blur', finish);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { input.value = oldName; input.blur(); }
    });
}

// ═══════════════════════════════════
// Tab Drag & Drop
// ═══════════════════════════════════
let dragSourceIndex = null;

function onTabDragStart(e) {
    dragSourceIndex = parseInt(e.target.dataset.index);
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragSourceIndex);
}
function onTabDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    $('#tabs-scroll').querySelectorAll('.tab').forEach(t => t.classList.remove('drag-over'));
    e.currentTarget.classList.add('drag-over');
}
function onTabDrop(e) {
    e.preventDefault();
    const targetIndex = parseInt(e.currentTarget.dataset.index);
    if (dragSourceIndex !== null && dragSourceIndex !== targetIndex && api()) {
        const names = groups.map(g => g.name);
        const [moved] = names.splice(dragSourceIndex, 1);
        names.splice(targetIndex, 0, moved);
        api().reorder_groups(names).then(() => { currentGroupIndex = targetIndex; loadData(); });
    }
    $('#tabs-scroll').querySelectorAll('.tab').forEach(t => t.classList.remove('drag-over'));
}
function onTabDragEnd(e) {
    e.target.classList.remove('dragging');
    $('#tabs-scroll').querySelectorAll('.tab').forEach(t => t.classList.remove('drag-over'));
    dragSourceIndex = null;
}

// ═══════════════════════════════════
// Hotkey Recording
// ═══════════════════════════════════
function startHotkeyRecording() {
    hotkeyRecording = true;
    $('#hotkey-btn').classList.add('recording');
    $('#hotkey-text').textContent = '按下新组合键…';

    const handler = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.key === 'Escape') { stopHotkeyRecording(); return; }
        if (['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) return;

        const parts = [];
        if (e.ctrlKey) parts.push('ctrl');
        if (e.altKey) parts.push('alt');
        if (e.shiftKey) parts.push('shift');
        let key = e.key;
        if (key === ' ') key = 'space';
        if (key.length === 1) key = key.toLowerCase();
        parts.push(key);

        const hotkey = parts.join('+');
        if (api()) {
            api().set_hotkey(hotkey).then(() => {
                $('#hotkey-text').textContent = formatHotkey(hotkey);
                stopHotkeyRecording();
            });
        }
    };
    document.addEventListener('keydown', handler, { capture: true });
    $('#hotkey-btn')._handler = handler;
}

function stopHotkeyRecording() {
    hotkeyRecording = false;
    const btn = $('#hotkey-btn');
    btn.classList.remove('recording');
    if (btn._handler) {
        document.removeEventListener('keydown', btn._handler, { capture: true });
        btn._handler = null;
    }
    if (api()) {
        api().get_config().then(config => {
            $('#hotkey-text').textContent = formatHotkey(config.hotkey || 'ctrl+`');
        });
    }
}

// ═══════════════════════════════════
// Panel Show / Hide (called from Python)
// ═══════════════════════════════════
function updateMode(mode) {
    $('#mode-text').textContent = mode === 'pinned' ? '固定📌' : '单次';
    const dot = $('#mode-dot');
    if (dot) dot.className = mode === 'pinned' ? 'pinned' : '';
}

function onPanelShow() {
    const app = $('#app');
    app.classList.remove('panel-hide');
    app.classList.add('panel-show');
    if (currentView !== 'main') switchView('main');
    if (addMode) exitAddMode();
    loadData();
}

function onPanelHide() {
    const app = $('#app');
    app.classList.remove('panel-show');
    app.classList.add('panel-hide');
}

window.updateMode = updateMode;
window.onPanelShow = onPanelShow;
window.onPanelHide = onPanelHide;
