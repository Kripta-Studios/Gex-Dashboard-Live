/**
 * Refresh Module
 * Dashboard refresh and data update logic
 */

/**
 * Refresh all charts in the dashboard
 */
async function refreshDashboard() {
    updateMarketSpots();
    updateNYTime();

    if (
        typeof isKingNodeTabActive === "function" &&
        isKingNodeTabActive() &&
        typeof refreshKingNodeDashboard === "function"
    ) {
        await refreshKingNodeDashboard();
        return;
    }

    const currentTab = tabs.find(t => t.id === currentTabId);
    if (!currentTab || !currentTab.charts || currentTab.charts.length === 0) return;

    // Refresh heatmap charts
    const heatmaps = currentTab.charts.filter(c => !c.type || c.type === 'heatmap');

    if (heatmaps.length > 0) {
        const requestList = heatmaps.map(c => ({
            ticker: c.inputTicker,
            exp: c.inputExp,
            time: currentHistoryTimeEST
        }));

        const uniqueRequests = [...new Set(requestList.map(JSON.stringify))].map(JSON.parse);

        try {
            const response = await authFetch('/get_batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(uniqueRequests)
            });

            const batchData = await safeJsonParse(response);
            if (!batchData) throw new Error("Batch response was null or unparseable");
            heatmaps.forEach(chart => {
                const dataKey = `${chart.inputTicker.toUpperCase()}_${chart.inputExp.toLowerCase()}`;
                if (batchData[dataKey]) {
                    chart.data = batchData[dataKey];
                }
            });
        } catch (e) {
            console.error("Batch update failed", e);
        }
    }

    // Refresh Fourier and IB charts
    const specialCharts = currentTab.charts.filter(c => c.type === 'fourier' || c.type === 'ib');

    if (specialCharts.length > 0) {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const todayStr = `${yyyy}${mm}${dd}`;

        let needsRender = false;

        for (let chart of specialCharts) {
            if (chart.dateStr === todayStr) {
                let newData = null;

                if (chart.type === 'fourier') {
                    newData = await fetchFourierData(chart.inputTicker, chart.dateStr);
                } else if (chart.type === 'ib') {
                    newData = await fetchIBData(chart.inputTicker, chart.dateStr);
                }

                if (newData) {
                    chart.data = newData;
                    if (chart.type === 'fourier') updateIVTrendFromFourier(chart.inputTicker, newData);
                    needsRender = true;
                }
            }
        }
    }

    // Sync panel dimensions from DOM before re-rendering
    syncPanelDimensionsFromDOM();

    // Re-render all charts
    renderAllCharts();
    updateNYTime();

    // Update Market Structure Widget
    if (typeof updateMarketStructureUI === 'function') {
        updateMarketStructureUI();
    }
}

/**
 * Sync panel dimensions from DOM to chart objects
 * This preserves user resizing during auto-refresh
 */
function syncPanelDimensionsFromDOM() {
    const container = document.getElementById("charts-wrapper");
    if (!container) return;

    const rows = container.querySelectorAll(".chart-row");
    const tab = tabs.find(t => t.id === currentTabId);
    if (!tab) return;

    rows.forEach((row, rowIndex) => {
        const panels = row.querySelectorAll(".chart-panel");
        panels.forEach(panel => {
            const panelIndex = parseInt(panel.dataset.index);
            if (!isNaN(panelIndex) && tab.charts[panelIndex]) {
                tab.charts[panelIndex].rowIndex = rowIndex;
                tab.charts[panelIndex].panelWidth = panel.offsetWidth;
                tab.charts[panelIndex].panelHeight = panel.offsetHeight;
            }
        });
    });
}

