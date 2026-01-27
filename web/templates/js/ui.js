/**
 * UI Module
 * User interface functions: time display, themes, modes
 */

/**
 * Toggle Zen mode (hide controls)
 */
function toggleZenMode() {
    document.body.classList.toggle("zen-active");
    setTimeout(() => {
        const panels = document.querySelectorAll(".chart-panel");
        panels.forEach((panel) => alignChartToSpot(panel));
    }, 200);
}

/**
 * Change color palette
 * @param {string} theme - Theme name (default, palette-alt)
 */
function changePalette(theme) {
    document.body.classList.remove("palette-alt");
    if (theme !== "default") document.body.classList.add(theme);
}

/**
 * Take a screenshot of the charts
 */
function takeSnapshot() {
    const el = document.getElementById("charts-wrapper");

    html2canvas(el, {
        backgroundColor: "#050505",
        scale: 2,
    }).then((canvas) => {
        const link = document.createElement("a");
        link.download = `GEX-Snapshot-${new Date().toLocaleTimeString()}.png`;
        link.href = canvas.toDataURL();
        link.click();
    });
}

/**
 * Update NY time display
 */
function updateNYTime() {
    const nyEl = document.getElementById("ny-time");
    const dataEl = document.getElementById("last-data-time");

    // NY Clock
    if (nyEl) {
        nyEl.innerText = new Date().toLocaleString("en-US", {
            timeZone: "America/New_York",
            hour: "2-digit", minute: "2-digit", hour12: false
        });
    }

    // Find time from current tab
    const currentTab = tabs.find(t => t.id === currentTabId);
    if (!currentTab || !currentTab.charts || currentTab.charts.length === 0) {
        if (dataEl) dataEl.innerText = "--:--";
        return;
    }

    let latestVal = -1;
    let latestStr = "--:--";

    currentTab.charts.forEach(chart => {
        let timeStr = null;

        // Priority 1: today_ddt_string (Heatmaps)
        if (chart.data && chart.data.today_ddt_string) {
            const match = chart.data.today_ddt_string.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
            if (match) {
                let hours = parseInt(match[1]);
                const minutes = match[2];
                const ampm = match[3].toUpperCase();
                if (ampm === "PM" && hours !== 12) hours += 12;
                if (ampm === "AM" && hours === 12) hours = 0;
                timeStr = hours.toString().padStart(2, "0") + ":" + minutes;
            }
        }
        // Priority 2: Fourier - array with datetime
        else if (chart.data && Array.isArray(chart.data) && chart.data.length > 0) {
            const last = chart.data[chart.data.length - 1];
            if (last.datetime) {
                const timePart = last.datetime.split(' ')[1];
                if (timePart) {
                    timeStr = timePart.substring(0, 5);
                }
            }
        }
        // Priority 3: IB Charts - series array
        if (chart.data && chart.data.series && chart.data.series.length > 0) {
            const last = chart.data.series[chart.data.series.length - 1];
            timeStr = last.time || (last.datetime ? last.datetime.split(' ')[1] : null);
        }

        if (timeStr) {
            const clean = timeStr.trim().substring(0, 5);
            const val = parseInt(clean.replace(':', ''));
            if (!isNaN(val) && val > latestVal) {
                latestVal = val;
                latestStr = clean;
            }
        }
    });

    // Update data time display
    if (dataEl) {
        if (currentHistoryTimeEST !== null) {
            dataEl.innerText = latestStr + " (H)";
            dataEl.style.color = "var(--accent-red)";
        } else {
            dataEl.innerText = latestStr;
            dataEl.style.color = "";
        }
    }
}

/**
 * Update expiration suggestions based on ticker
 */
function updateExpSuggestions() {
    const t = document.getElementById("ticker").value.toUpperCase();
    const l = document.getElementById("exp-list");
    l.innerHTML = "";
    const opts = t === "SPX" ? ["0dte", "1dte", "weekly"]
        : t === "SPY" || t === "QQQ" ? ["0dte", "weekly"]
            : ["weekly"];
    opts.forEach((o) => {
        const el = document.createElement("option");
        el.value = o;
        l.appendChild(el);
    });
}

/**
 * Format percentage change with color
 * @param {number} current - Current value
 * @param {number} previous - Previous value
 * @returns {string} HTML span with formatted percentage
 */
function formatChangePct(current, previous) {
    if (previous === null || previous === undefined || previous === 0) return "";

    const diff = current - previous;
    const pct = (diff / Math.abs(previous)) * 100;

    let colorStyle = "var(--text-dim)";
    let sign = "";

    if (pct > 0.001) {
        colorStyle = "var(--accent-green)";
        sign = "+";
    } else if (pct < -0.001) {
        colorStyle = "var(--accent-red)";
        sign = "";
    }

    return `<span style="color:${colorStyle}; font-size: 10px; font-weight: normal; margin-left: 4px;">(${sign}${pct.toFixed(2)}%)</span>`;
}

/**
 * Format large numbers with K suffix
 * @param {number} n - Number to format
 * @returns {string} Formatted string
 */
function formatK(n) {
    if (Math.abs(n) < 1) return "0";
    return parseInt(n).toLocaleString('en-US') + "k";
}

// Escape key handler for Zen mode
document.addEventListener('keydown', function (e) {
    if (e.key === "Escape" || e.keyCode === 27) {
        if (document.body.classList.contains("zen-active")) {
            toggleZenMode();
        }
    }
});

// Update time every second
setInterval(updateNYTime, 1000);
