/**
 * Data Handlers Module
 * Form handling and chart data loading
 */

/**
 * Get form parameters for chart loading
 * @returns {Object} Ticker, exp, greek
 */
function getParams() {
    const t = document.getElementById("ticker");
    const e = document.getElementById("exp");
    const g = document.getElementById("greek-select");
    return {
        ticker: t.value.toUpperCase(),
        exp: e.value.toLowerCase(),
        greek: g.value,
    };
}

/**
 * Handle Load button click (replaces all charts)
 */
async function handleLoadData() {
    const currentTab = tabs.find((t) => t.id === currentTabId);
    if (!currentTab) return;
    currentTab.charts = [];
    const params = getParams();
    const data = await fetchChartData(params.ticker, params.exp);
    if (data) {
        addChartToCurrent(data, params);
        renderAllCharts();
    }
}

/**
 * Handle Add Chart button click
 */
async function handleAddChart() {
    const params = getParams();
    const btn = document.querySelector(".btn-add");
    btn.innerText = "...";
    const data = await fetchChartData(params.ticker, params.exp);
    btn.innerText = "+";
    if (data) {
        addChartToCurrent(data, params);
        renderAllCharts();
    }
}

/**
 * Add a chart to current tab
 * @param {Object} data - Chart data
 * @param {Object} params - Chart parameters
 */
function addChartToCurrent(data, params) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (tab)
        tab.charts.push({
            data: data,
            greek: params.greek,
            inputTicker: params.ticker,
            inputExp: params.exp,
        });
}
