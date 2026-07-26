/**
 * Tabs Module
 * Tab management, rendering, and drag-drop
 */

/**
 * Render all tabs in the tab bar
 */
function renderTabs() {
    const container = document.getElementById("tab-container");
    const addBtn = container.querySelector(".new-tab-btn");
    const existingTabs = container.querySelectorAll(".tab");
    existingTabs.forEach((t) => t.remove());

    if (typeof mountKingNodeTab === "function") {
        mountKingNodeTab(container, addBtn);
    }

    tabs.forEach((tab, index) => {
        const tabEl = document.createElement("div");
        tabEl.className = `tab ${tab.id === currentTabId ? "active" : ""}`;

        // Enable Drag and Drop
        tabEl.draggable = true;
        tabEl.dataset.index = index;

        // Click and double-click handlers
        tabEl.onclick = (e) => {
            if (!e.target.classList.contains("tab-close")) switchTab(tab.id);
        };
        tabEl.ondblclick = () => renameTab(tab.id);

        // Drag events
        tabEl.addEventListener('dragstart', handleTabDragStart);
        tabEl.addEventListener('dragover', handleTabDragOver);
        tabEl.addEventListener('drop', handleTabDrop);
        tabEl.addEventListener('dragenter', (e) => e.preventDefault());

        tabEl.innerHTML = `<span>${tab.name}</span>`;

        if (tabs.length > 1) {
            const closeBtn = document.createElement("span");
            closeBtn.className = "tab-close";
            closeBtn.innerHTML = "×";
            closeBtn.onclick = (e) => {
                e.stopPropagation();
                closeTab(tab.id);
            };
            tabEl.appendChild(closeBtn);
        }
        container.insertBefore(tabEl, addBtn);
    });
}

/**
 * Switch to a different tab
 * @param {number} id - Tab ID to switch to
 */
function switchTab(id) {
    if (currentTabId === id) return;
    currentTabId = id;
    renderTabs();
    renderAllCharts();
}

/**
 * Add a new empty tab
 */
function addNewTab() {
    const newId = tabCounter++;
    tabs.push({ id: newId, name: `Page ${tabs.length + 1}`, charts: [] });
    switchTab(newId);
}

/**
 * Close a tab
 * @param {number} id - Tab ID to close
 */
function closeTab(id) {
    if (tabs.length <= 1) return;
    const index = tabs.findIndex((t) => t.id === id);
    if (index === -1) return;
    tabs.splice(index, 1);
    if (id === currentTabId) {
        const nextTab = tabs[index - 1] || tabs[0];
        currentTabId = nextTab.id;
    }
    renderTabs();
    renderAllCharts();
}

/**
 * Rename a tab
 * @param {number} id - Tab ID to rename
 */
function renameTab(id) {
    const tab = tabs.find((t) => t.id === id);
    if (!tab) return;
    const newName = prompt("Rename:", tab.name);
    if (newName && newName.trim() !== "") {
        tab.name = newName.trim();
        renderTabs();
    }
}

/**
 * Get charts for current tab
 * @returns {Array} Current tab's charts
 */
function getCurrentCharts() {
    const tab = tabs.find((t) => t.id === currentTabId);
    return tab ? tab.charts : [];
}

// --- Tab Drag and Drop ---

function handleTabDragStart(e) {
    draggedTabIndex = parseInt(this.dataset.index);
    this.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
}

function handleTabDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleTabDrop(e) {
    e.stopPropagation();
    e.preventDefault();

    const allTabs = document.querySelectorAll('.tab');
    allTabs.forEach(t => t.style.opacity = '1');
    const targetIndex = parseInt(this.dataset.index);

    if (draggedTabIndex !== null && draggedTabIndex !== targetIndex) {
        const movedTab = tabs.splice(draggedTabIndex, 1)[0];
        tabs.splice(targetIndex, 0, movedTab);
        renderTabs();
        saveAllLayouts();
    }

    updateNYTime();
    draggedTabIndex = null;
}
