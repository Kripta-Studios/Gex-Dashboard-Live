/**
 * Init Module
 * Application initialization and mode handling
 */

/**
 * Initialize the application
 */
async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const mode = urlParams.get('mode');

    // --- Single Chart Detached Mode ---
    if (mode === 'detached') {
        document.body.classList.add('detached-mode');
        const loginScreen = document.getElementById("login-screen");
        if (loginScreen) loginScreen.style.display = "none";
        document.getElementById("app-wrapper").style.display = "flex";

        const ticker = urlParams.get('ticker');
        const theme = urlParams.get('theme');
        const type = urlParams.get('type');

        if (theme) changePalette(theme);

        const wrapper = document.getElementById("charts-wrapper");
        wrapper.innerHTML = "";

        // Fourier/IB charts
        if (type === 'fourier' || type === 'ib') {
            const dateStr = urlParams.get('date');

            const loadSpecial = async () => {
                let data = null;
                if (type === 'fourier') {
                    data = await fetchFourierData(ticker, dateStr);
                } else {
                    data = await fetchIBData(ticker, dateStr);
                }

                if (data) {
                    wrapper.innerHTML = "";
                    const chartConf = {
                        data: data,
                        inputTicker: ticker,
                        dateStr: dateStr,
                        type: type
                    };

                    let panel;
                    if (type === 'fourier') panel = createFourierPanel(chartConf, 0);
                    else panel = createIBPanel(chartConf, 0);

                    wrapper.appendChild(panel);

                    const closeBtn = panel.querySelector('.btn-close');
                    const popBtn = panel.querySelector('.btn-popout');
                    if (closeBtn) closeBtn.style.display = 'none';
                    if (popBtn) popBtn.style.display = 'none';
                } else {
                    wrapper.innerHTML = `<div style="color:red; text-align:center; padding-top:50px;">Data not found for ${type}</div>`;
                }
            };

            loadSpecial();

            const now = new Date();
            const todayStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;

            if (!dateStr || dateStr === 'LIVE' || dateStr === todayStr) {
                setInterval(loadSpecial, 30000);
            }

            return;
        }

        // Heatmap charts
        const exp = urlParams.get('exp');
        const greek = urlParams.get('greek');

        const loadSingle = async () => {
            const data = await fetchChartData(ticker, exp);
            if (data) {
                wrapper.innerHTML = "";
                const panel = createChartPanel({ data, greek, inputTicker: ticker, inputExp: exp }, 0);
                wrapper.appendChild(panel);
                setTimeout(() => alignChartToSpot(panel), 100);
            }
        };
        loadSingle();
        setInterval(loadSingle, 30000);
        return;
    }

    // --- Layout Detached Mode ---
    if (mode === 'detached_layout') {
        document.body.classList.add('detached-layout-mode');
        document.getElementById("login-screen").style.display = "none";
        document.getElementById("app-wrapper").style.display = "flex";

        const theme = urlParams.get('theme');
        if (theme) changePalette(theme);

        const transferId = urlParams.get('transferId');
        const rawConfig = localStorage.getItem(transferId);

        if (!rawConfig) {
            document.getElementById("charts-wrapper").innerHTML = "Error: Layout configuration not found.";
            return;
        }

        const chartsConfig = JSON.parse(rawConfig);
        const wrapper = document.getElementById("charts-wrapper");

        const loadEntireLayout = async () => {
            if (!wrapper.hasChildNodes()) {
                wrapper.innerHTML = '<div style="color:white; margin:auto;">Loading Mixed Layout...</div>';
            }

            const now = new Date();
            const todayStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;

            const promises = chartsConfig.map(async (conf, index) => {
                let data = null;
                const targetDate = (conf.dateStr && conf.dateStr !== 'LIVE') ? conf.dateStr : todayStr;

                try {
                    if (conf.type === 'fourier') {
                        data = await fetchFourierData(conf.ticker, targetDate);
                    } else if (conf.type === 'ib') {
                        data = await fetchIBData(conf.ticker, targetDate);
                    } else {
                        data = await fetchChartData(conf.ticker, conf.exp);
                    }
                } catch (e) {
                    console.error(`Error loading panel ${index}`, e);
                }

                if (data) {
                    const chartObj = {
                        data: data,
                        greek: conf.greek,
                        inputTicker: conf.ticker,
                        inputExp: conf.exp,
                        type: conf.type || 'heatmap',
                        dateStr: targetDate
                    };

                    return createChartPanel(chartObj, index);
                }
                return null;
            });

            const results = await Promise.all(promises);

            wrapper.innerHTML = "";

            results.forEach(panel => {
                if (panel) {
                    const popBtn = panel.querySelector('.btn-popout');
                    if (popBtn) popBtn.style.display = 'none';

                    const closeBtn = panel.querySelector('.btn-close');
                    if (closeBtn) closeBtn.style.display = 'block';

                    wrapper.appendChild(panel);
                }
            });
            setTimeout(() => realignAllCharts(), 100);
        };

        await loadEntireLayout();
        setInterval(loadEntireLayout, 30000);
        return;
    }

    // --- Normal App Mode ---
    const wrapper = document.getElementById("charts-wrapper");
    wrapper.innerHTML = '<div style="color:white; margin:auto; text-align:center;">Loading...</div>';
    const loaded = await loadSavedLayouts();

    if (!loaded) {
        tabs = [{ id: 0, name: "Default", charts: [] }];
        currentTabId = 0;
        tabCounter = 1;
    }

    renderTabs();
    renderAllCharts();
    updateExpSuggestions();
    updateMarketSpots();
    updateNYTime();
    startAutoRefresh();
}

// Initialize Fourier date input on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const dateInput = document.getElementById("fourier-date");
    if (dateInput) dateInput.value = `${yyyy}-${mm}-${dd}`;
});
