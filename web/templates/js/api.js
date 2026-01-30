/**
 * API Module
 * Handles all data fetching from the server
 */

/**
 * Fetch Greek exposure data for a ticker/expiration
 * @param {string} ticker - Ticker symbol (SPX, QQQ, /ES, /NQ, etc.)
 * @param {string} exp - Expiration (0dte, weekly, etc.)
 * @returns {Promise<Object|null>} Chart data or null
 */
async function fetchChartData(ticker, exp) {
    try {
        const ts = new Date().getTime();
        let url = "";

        // Map futures to their underlying for greeks
        // ES or /ES uses SPX greeks, NQ or /NQ uses QQQ greeks
        let greekTicker = ticker;
        const originalTicker = ticker;
        if (ticker === "/ES" || ticker === "ES") {
            greekTicker = "SPX";
        } else if (ticker === "/NQ" || ticker === "NQ") {
            greekTicker = "QQQ";
        }

        // Check mode: LIVE or HISTORY
        if (currentHistoryTimeEST === null) {
            url = `/get_latest?ticker=${greekTicker}&exp=${exp}&_=${ts}`;
        } else {
            url = `/get_history?ticker=${greekTicker}&exp=${exp}&time=${currentHistoryTimeEST}&_=${ts}`;
        }

        const response = await fetch(url);
        if (!response.ok) return null;

        const data = await response.json();
        // Force ticker to be the requested one (e.g. /ES) even if data comes from SPX
        data.ticker = originalTicker;
        data.originalTicker = originalTicker;

        // --- FUTURES HANDLING: FETCH REAL SPOT PRICE & RATIO ---
        // If it is /ES or /NQ, we try to fetch the IB data file to get the real futures price
        // This allows us to show the real Futures Spot and convert strikes (for NQ)
        if (originalTicker === "/ES" || originalTicker === "/NQ" || originalTicker === "ES" || originalTicker === "NQ") {
            try {
                // Determine date string. If live, use today. If history, parse from `currentHistoryTimeEST`
                let dateStr = "";
                if (currentHistoryTimeEST) {
                    // format is usually YYYYMMDD_HHMMSS or similar
                    dateStr = currentHistoryTimeEST.split('_')[0];
                } else {
                    const now = new Date();
                    const y = now.getFullYear();
                    const m = String(now.getMonth() + 1).padStart(2, '0');
                    const d = String(now.getDate()).padStart(2, '0');
                    dateStr = `${y}${m}${d}`;
                }

                const cleanTicker = originalTicker.replace(/\//g, '');
                const ibUrl = `/ib_charts/ib_data_${cleanTicker}_${dateStr}.json?_=${ts}`; // Use same timestamp to bust cache

                const ibResp = await fetch(ibUrl);
                if (ibResp.ok) {
                    const ibData = await ibResp.json();
                    if (ibData && ibData.analysis && ibData.analysis.current_price) {
                        const futureSpot = ibData.analysis.current_price;
                        data.futureSpot = futureSpot; // Inject future spot

                        // For NQ (mapped to QQQ), calculate ratio to convert strikes
                        if (greekTicker === "QQQ" && data.spot_price) {
                            // Priority: Use NDX Spot if available (analysis.underlying_spot)
                            // Fallback: Use NQ Spot (futureSpot)
                            const numerator = ibData.analysis.underlying_spot || futureSpot;
                            data.conversionRatio = numerator / data.spot_price;
                        }
                    }
                }
            } catch (err) {
                console.warn("[FUTURES] Could not fetch IB data for conversion", err);
            }
        }

        return data;
    } catch (e) {
        console.error(e);
        return null;
    }
}

/**
 * Fetch Fourier analysis data
 * @param {string} ticker - Ticker symbol
 * @param {string} dateStr - Date in YYYYMMDD format
 * @returns {Promise<Object|null>} Fourier data or null
 */
async function fetchFourierData(ticker, dateStr) {
    try {
        const ts = new Date().getTime();
        // Clean ticker for file path (remove slashes)
        // /ES -> ES, /NQ -> NQ
        const fourierTicker = ticker.replace(/\//g, '');

        const url = `/fourier/fourier_data_${fourierTicker}_${dateStr}.json?_=${ts}`;
        const response = await fetch(url);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        console.error("Fourier Fetch Error:", e);
        return null;
    }
}

/**
 * Fetch Initial Balance data
 * @param {string} ticker - Ticker symbol
 * @param {string} dateStr - Date in YYYYMMDD format
 * @returns {Promise<Object|null>} IB data or null
 */
async function fetchIBData(ticker, dateStr) {
    try {
        const ts = new Date().getTime();
        // Clean ticker for file path (remove slashes like ib_service.py does)
        // /ES -> ES, /NQ -> NQ
        const cleanTicker = ticker.replace(/\//g, '');
        const url = `/ib_charts/ib_data_${cleanTicker}_${dateStr}.json?_=${ts}`;
        const response = await fetch(url);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        return null;
    }
}

/**
 * Fetch with retry for unreliable data
 * @param {string} ticker - Ticker symbol
 * @param {string} exp - Expiration
 * @param {number} maxRetries - Max retry attempts
 * @param {number} delay - Delay between retries in ms
 * @returns {Promise<Object|null>} Data or null
 */
async function fetchWithRetry(ticker, exp, maxRetries = 10, delay = 500) {
    for (let i = 0; i < maxRetries; i++) {
        const data = await fetchChartData(ticker, exp);
        if (data && data.option_data && data.option_data.data && data.option_data.data.length > 0) {
            return data;
        }
        console.log(`[Retry ${i + 1}/${maxRetries}] Waiting for data: ${ticker} ${exp}...`);
        await new Promise(resolve => setTimeout(resolve, delay));
    }
    return null;
}

/**
 * Update market spot prices (SPX, VIX)
 */
async function updateMarketSpots() {
    const spx = await fetchChartData("SPX", "0dte");
    if (spx && spx.spot_price) realSpotSPX = spx.spot_price;
    updateEl("spot-spx", "change-spx", spx);

    const vix = await fetchChartData("VIX", "weekly");
    updateEl("spot-vix", "change-vix", vix);
}

/**
 * Update a market price element
 * @param {string} idP - Price element ID
 * @param {string} idC - Change element ID
 * @param {Object} d - Data object
 */
function updateEl(idP, idC, d) {
    if (d && d.spot_price) {
        const p = d.spot_price;
        const prev = d.prev_close_price;
        document.getElementById(idP).innerText = p.toFixed(2);
        if (prev) {
            const diff = p - prev;
            const pct = (diff / prev) * 100;
            const el = document.getElementById(idC);
            el.innerText = `(${diff >= 0 ? "+" : ""}${diff.toFixed(2)}, ${pct.toFixed(2)}%)`;
            el.className = `market-change ${diff > 0.01 ? "change-pos" : diff < -0.01 ? "change-neg" : "change-flat"}`;
        }
    }
}
