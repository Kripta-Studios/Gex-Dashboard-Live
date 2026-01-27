/**
 * History/Time Machine Module
 * Controls for viewing historical data
 */

/**
 * Get current time in EST as minutes from midnight
 * @returns {number} Minutes since midnight EST
 */
function getCurrentESTMinutes() {
    const now = new Date();
    const estString = now.toLocaleString("en-US", { timeZone: "America/New_York", hour12: false });
    const timePart = estString.split(", ")[1];
    const [h, m] = timePart.split(":").map(Number);
    return (h * 60) + m;
}

/**
 * Scrub through history time (visual update only)
 * @param {number} val - Slider value (0-100)
 */
function scrubHistory(val) {
    const label = document.getElementById("history-time");
    const slider = document.getElementById("history-slider");

    const START_MINUTES = 3 * 60;   // 03:00 EST
    const CLOSE_MINUTES = 16 * 60;  // 16:00 EST

    const currentEstMinutes = getCurrentESTMinutes();
    const effectiveEndMinutes = Math.min(currentEstMinutes, CLOSE_MINUTES);

    if (currentEstMinutes < START_MINUTES) {
        label.innerText = "PRE-MARKET";
        return;
    }

    // Live mode
    if (val >= 99) {
        label.innerText = "LIVE";
        label.style.color = "var(--accent-green)";
        currentHistoryTimeEST = null;
        return;
    }

    // History mode
    const range = effectiveEndMinutes - START_MINUTES;
    const pct = val / 100;
    const targetMinutes = Math.floor(START_MINUTES + (range * pct));

    const h = Math.floor(targetMinutes / 60);
    const m = targetMinutes % 60;

    const timeStr = h.toString().padStart(2, "0") + ":" + m.toString().padStart(2, "0");
    const apiTimeStr = h.toString().padStart(2, "0") + m.toString().padStart(2, "0");

    label.innerText = timeStr + " EST";
    label.style.color = "var(--accent-red)";

    currentHistoryTimeEST = apiTimeStr;
}

/**
 * Load historical data at selected time
 */
function loadHistoryNow() {
    const btn = document.getElementById("btn-history-load");

    stopAutoRefresh();

    const originalText = "GO";
    btn.innerText = "⌛";
    btn.disabled = true;

    refreshDashboard()
        .then(() => {
            btn.innerText = originalText;
            btn.disabled = false;
            updateNYTime();
        })
        .catch((error) => {
            console.error("Load failed:", error);
            btn.innerText = "❌";
            setTimeout(() => {
                btn.innerText = originalText;
                btn.disabled = false;
            }, 2000);
        });
}

/**
 * Switch to live mode
 */
function goLive() {
    const slider = document.getElementById("history-slider");

    slider.value = 100;
    scrubHistory(100);

    console.log("Switching to LIVE mode...");
    refreshDashboard();

    startAutoRefresh();
}

/**
 * Start auto-refresh interval
 */
function startAutoRefresh() {
    stopAutoRefresh();

    if (currentHistoryTimeEST === null) {
        refreshIntervalId = setInterval(() => {
            if (currentHistoryTimeEST === null) {
                refreshDashboard();
            }
        }, 20000);
        console.log("Auto-refresh STARTED (LIVE mode)");
    }
}

/**
 * Stop auto-refresh interval
 */
function stopAutoRefresh() {
    if (refreshIntervalId !== null) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
        console.log("Auto-refresh STOPPED (History mode)");
    }
}
