/**
 * Layout/Persistence Module
 * Save and load dashboard layouts to localStorage
 */

/**
 * Save all layouts to localStorage
 */
function saveAllLayouts() {
    try {
        const themeSelect = document.querySelector("select[onchange*='changePalette']");
        const currentTheme = themeSelect ? themeSelect.value : 'default';

        // Date for comparison
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const todayStr = `${yyyy}${mm}${dd}`;

        // Capture row structure and dimensions from DOM
        const container = document.getElementById("charts-wrapper");
        const rows = container.querySelectorAll(".chart-row");
        const panelRowMap = new Map(); // Map panel index -> { rowIndex, width, height }

        rows.forEach((row, rowIndex) => {
            const panels = row.querySelectorAll(".chart-panel");
            panels.forEach(panel => {
                const panelIndex = parseInt(panel.dataset.index);
                if (!isNaN(panelIndex)) {
                    panelRowMap.set(panelIndex, {
                        rowIndex: rowIndex,
                        width: panel.offsetWidth,
                        height: panel.offsetHeight
                    });
                }
            });
        });

        const cleanTabs = tabs.map((t) => ({
            id: t.id,
            name: t.name,
            charts: t.charts.filter(c => c.inputTicker).map((c, idx) => {
                let dateToSave = null;
                if (c.type === 'fourier' || c.type === 'ib') {
                    if (c.dateStr === todayStr) {
                        dateToSave = "LIVE";
                    } else {
                        dateToSave = c.dateStr;
                    }
                }

                // Get row index and dimensions from current DOM if this tab is active
                let rowIndex = 0;
                let panelWidth = c.panelWidth || null;
                let panelHeight = c.panelHeight || null;

                if (t.id === currentTabId && panelRowMap.has(idx)) {
                    const info = panelRowMap.get(idx);
                    rowIndex = info.rowIndex;
                    panelWidth = info.width;
                    panelHeight = info.height;
                } else {
                    // For non-active tabs, use stored values
                    rowIndex = c.rowIndex || 0;
                }

                return {
                    ticker: c.inputTicker,
                    exp: c.inputExp,
                    greek: c.greek,
                    type: c.type,
                    savedDate: dateToSave,
                    rowIndex: rowIndex,
                    panelWidth: panelWidth,
                    panelHeight: panelHeight
                };
            }),
        }));

        const data = {
            autoRefresh: document.getElementById("auto-refresh")?.checked || false,
            theme: currentTheme,
            tabs: cleanTabs,
        };

        const jsonStr = JSON.stringify(data);
        localStorage.setItem("gex_dashboard_tabs_v1", jsonStr);

        const totalCharts = cleanTabs.reduce((acc, t) => acc + t.charts.length, 0);
        console.log(`[SAVE] Saved ${totalCharts} charts with row structure.`);

        const btn = document.querySelector('button[onclick="saveAllLayouts()"]');
        if (btn) {
            const old = btn.innerText;
            btn.innerText = "SAVED ✓";
            setTimeout(() => (btn.innerText = old), 1000);
        }

    } catch (e) {
        console.error("Save failed:", e);
        alert("Error saving layout. Check console.");
    }
}

/**
 * Load saved layouts from localStorage
 * @returns {Promise<boolean>} True if layouts were loaded
 */
async function loadSavedLayouts() {
    const s = localStorage.getItem("gex_dashboard_tabs_v1");
    if (!s) return false;

    const wrapper = document.getElementById("charts-wrapper");
    wrapper.innerHTML = '<div style="color:var(--accent-blue); margin:auto; text-align:center; font-family:monospace;">RESTORING LAYOUT...</div>';

    try {
        const obj = JSON.parse(s);

        if (obj.autoRefresh !== undefined) {
            const chk = document.getElementById("auto-refresh");
            if (chk) chk.checked = obj.autoRefresh;
        }

        if (obj.theme) {
            const themeSelect = document.querySelector("select[onchange*='changePalette']");
            if (themeSelect) {
                themeSelect.value = obj.theme;
                changePalette(obj.theme);
            }
        }

        if (obj.tabs && Array.isArray(obj.tabs)) {
            tabs = obj.tabs.map((t) => ({ id: t.id, name: t.name, charts: [] }));

            if (tabs.length > 0) {
                tabCounter = Math.max(...tabs.map((t) => t.id)) + 1;
                currentTabId = tabs[0].id;
            } else {
                tabs = [{ id: 0, name: "Default", charts: [] }];
                currentTabId = 0;
            }

            const tabPromises = obj.tabs.map(async (tData) => {
                if (!tData.charts) return;

                const chartPromises = tData.charts.map(async (cConf) => {
                    if (!cConf.ticker) return null;

                    if (!cConf.type) {
                        if (cConf.exp === 'fourier') cConf.type = 'fourier';
                        else if (cConf.exp === 'ib') cConf.type = 'ib';
                        else cConf.type = 'heatmap';
                    }

                    let d = null;
                    let loadedDateStr = null;

                    // Date handling
                    if (cConf.type === 'fourier' || cConf.type === 'ib') {
                        const now = new Date();
                        const yyyy = now.getFullYear();
                        const mm = String(now.getMonth() + 1).padStart(2, '0');
                        const dd = String(now.getDate()).padStart(2, '0');
                        const todayStr = `${yyyy}${mm}${dd}`;

                        if (cConf.savedDate && cConf.savedDate !== "LIVE") {
                            loadedDateStr = cConf.savedDate;
                        } else {
                            loadedDateStr = todayStr;
                        }

                        if (cConf.type === 'fourier') {
                            d = await fetchFourierData(cConf.ticker, loadedDateStr);
                            if (d) updateIVTrendFromFourier(cConf.ticker, d);
                        } else {
                            d = await fetchIBData(cConf.ticker, loadedDateStr);
                        }
                    } else {
                        d = await fetchWithRetry(cConf.ticker, cConf.exp, 1, 0);
                    }

                    if (!d) {
                        console.warn(`[Layout] Skipped ${cConf.ticker} (${cConf.type}). No data.`);
                        d = {
                            ticker: cConf.ticker,
                            spot_price: 0,
                            prev_close_price: 0,
                            option_data: { columns: ["strike_price"], data: [] },
                            analysis: { ib_high: 0, ib_low: 0, ib_range: 0, current_price: 0 },
                            series: []
                        };
                    }

                    return {
                        data: d,
                        greek: cConf.greek,
                        inputTicker: cConf.ticker,
                        inputExp: cConf.exp,
                        type: cConf.type,
                        dateStr: loadedDateStr,
                        rowIndex: cConf.rowIndex || 0,
                        panelWidth: cConf.panelWidth || null,
                        panelHeight: cConf.panelHeight || null
                    };
                });

                const results = await Promise.all(chartPromises);
                const target = tabs.find((x) => x.id === tData.id);
                if (target) {
                    target.charts = results.filter(r => r !== null);
                }
            });

            await Promise.all(tabPromises);
            return true;
        }
    } catch (e) {
        console.error("Error loading layouts:", e);
        wrapper.innerHTML = '<div style="color:red; margin:auto;">Error loading layout.</div>';
    }
    return false;
}

/**
 * Toggle auto refresh
 */
function toggleAutoRefresh() {
    const chk = document.getElementById("auto-refresh");
    const ind = document.getElementById("timer-indicator");
    if (chk.checked) {
        ind.style.display = "block";
        if (!refreshIntervalId)
            refreshIntervalId = setInterval(refreshDashboard, 30000);
    } else {
        ind.style.display = "none";
        if (refreshIntervalId) {
            clearInterval(refreshIntervalId);
            refreshIntervalId = null;
        }
    }
}
