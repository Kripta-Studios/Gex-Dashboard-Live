/**
 * Charts Module (ADMIN ONLY)
 * Specialized chart dispatching and restricted analytical logic.
 * This file overwrites the base createChartPanel from dashboard.js.
 */

/**
 * Create a chart panel (Full Dispatcher - ADMIN VERSION)
 * @param {Object} chartObj - Chart data object
 * @param {number} index - Chart index
 * @returns {HTMLElement} Panel element
 */
createChartPanel = function(chartObj, index) {
    // 1. Dispatch to Fourier (Restricted)
    if (chartObj.type === 'fourier') {
        if (typeof createFourierPanel === 'function') {
            return createFourierPanel(chartObj, index);
        } else {
            console.warn("[Admin] Fourier module not loaded");
            return document.createElement("div");
        }
    }

    // 2. Dispatch to IB (Restricted)
    if (chartObj.type === 'ib') {
        if (typeof createIBPanel === 'function') {
            return createIBPanel(chartObj, index);
        } else {
            console.warn("[Admin] IB module not loaded");
            return document.createElement("div");
        }
    }

    // 3. Fallback to Heatmap (Available in dashboard.js but handled here for consistency)
    return createHeatmapPanel(chartObj, index);
};

console.log("[Admin] Charts dispatcher upgraded.");
