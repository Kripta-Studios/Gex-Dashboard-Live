/**
 * Windows Module
 * Detached windows and popout functionality
 */

/**
 * Open a chart in a detached window
 * @param {number} index - Chart index
 */
function openDetachedWindow(index) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (!tab || !tab.charts[index]) {
        console.error("Chart not found for index:", index);
        return;
    }

    const chart = tab.charts[index];
    const currentTheme = document.body.classList.contains("palette-alt") ? "palette-alt" : "default";

    const params = new URLSearchParams({
        mode: 'detached',
        ticker: chart.inputTicker,
        theme: currentTheme
    });

    if (chart.type === 'fourier' || chart.type === 'ib') {
        params.set('type', chart.type);
        params.set('date', chart.dateStr || "LIVE");
    } else {
        params.set('exp', chart.inputExp || "0dte");
        params.set('greek', chart.greek || "gamma");
    }

    const w = 600;
    const h = 500;
    const left = (screen.width / 2) - (w / 2);
    const top = (screen.height / 2) - (h / 2);

    const url = `${window.location.pathname}?${params.toString()}`;

    window.open(
        url,
        `GEX_${chart.type || 'chart'}_${chart.inputTicker}_${Date.now()}`,
        `width=${w},height=${h},top=${top},left=${left},resizable=yes,scrollbars=yes,status=no`
    );
}

/**
 * Pop out entire layout to new window
 */
function popoutCurrentLayout() {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (!tab || tab.charts.length === 0) {
        alert("Empty layout cannot be popped out.");
        return;
    }

    const layoutConfig = tab.charts.map(c => ({
        ticker: c.inputTicker,
        exp: c.inputExp,
        greek: c.greek,
        type: c.type || 'heatmap',
        dateStr: c.dateStr || 'LIVE'
    }));

    const transferId = 'layout_' + Date.now();
    localStorage.setItem(transferId, JSON.stringify(layoutConfig));

    const currentTheme = document.body.classList.contains("palette-alt") ? "palette-alt" : "default";
    const params = new URLSearchParams({
        mode: 'detached_layout',
        transferId: transferId,
        theme: currentTheme
    });

    const url = `${window.location.pathname}?${params.toString()}`;
    window.open(url, `GEX_LAYOUT_${transferId}`, "width=1200,height=800,resizable=yes,scrollbars=yes");
}

// Window resize handler
window.addEventListener('resize', () => {
    const charts = document.querySelectorAll('canvas');
    charts.forEach(canvas => {
        const chartInstance = Chart.getChart(canvas);
        if (chartInstance) {
            chartInstance.resize();
        }
    });

    if (document.body.classList.contains('detached-mode')) {
        const panel = document.querySelector('.chart-panel');
        if (panel) alignChartToSpot(panel);
    }
});
