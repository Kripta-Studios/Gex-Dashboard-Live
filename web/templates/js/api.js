/**
 * API Module
 * Handles all data fetching from the server
 */

/**
 * Handle unauthorized response — clear session and show login
 */
function handleUnauthorized() {
    sessionStorage.removeItem("gex_auth_token");
    sessionStorage.removeItem("gex_user_role");
    const loginScreen = document.getElementById("login-screen");
    const appWrapper = document.getElementById("app-wrapper");
    if (loginScreen) loginScreen.style.display = "";
    if (appWrapper) appWrapper.style.display = "none";
}

/**
 * Authenticated fetch wrapper
 * Injects Bearer token and handles 401 auto-logout
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options (method, body, etc.)
 * @returns {Promise<Response>} Fetch response
 */
async function authFetch(url, options = {}) {
    const token = sessionStorage.getItem("gex_auth_token");
    if (!options.headers) options.headers = {};
    if (token) options.headers["Authorization"] = `Bearer ${token}`;

    const response = await fetch(url, options);

    if (response.status === 401) {
        handleUnauthorized();
    }

    return response;
}

/**
 * Safely parse JSON that might contain Python's NaN, Infinity, True, False, None
 * Handles all positions: after colons, in arrays, nested objects, etc.
 * @param {Response} response
 */
async function safeJsonParse(response) {
    const text = await response.text();
    if (!text) return null;
    // Replace Python/JS non-standard tokens with JSON-safe equivalents.
    // Word-boundary patterns avoid corrupting string values that contain
    // these as substrings (e.g. "NaNometer", "Infinity pool").
    const sanitized = text
        .replace(/\bTrue\b/g, 'true')       // Python bool → JSON bool
        .replace(/\bFalse\b/g, 'false')
        .replace(/\bNone\b/g, 'null')        // Python None → JSON null
        .replace(/\bNaN\b/g, 'null')         // NaN anywhere → null
        .replace(/-Infinity\b/g, 'null')     // -Infinity before +Infinity
        .replace(/\bInfinity\b/g, 'null');   // +Infinity → null
    try {
        return JSON.parse(sanitized);
    } catch (e) {
        console.error("Parse error on sanitized JSON:", e);
        return null;
    }
}

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

        const response = await authFetch(url);
        if (!response.ok) return null;

        const data = await safeJsonParse(response);
        // Guard: parse can return null if server sends malformed/truncated JSON
        if (!data) {
            console.warn(`[fetchChartData] Null data after parse for ${greekTicker} ${exp}`);
            return null;
        }
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

                const ibResp = await authFetch(ibUrl);
                if (ibResp.ok) {
                    const ibData = await safeJsonParse(ibResp);
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
        const response = await authFetch(url);
        if (!response.ok) return null;
        return await safeJsonParse(response);
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
        const response = await authFetch(url);
        if (!response.ok) return null;
        return await safeJsonParse(response);
    } catch (e) {
        return null;
    }
}

/**
 * Fetch IB data with retry - waits for server to finish generating file
 * @param {string} ticker - Ticker symbol
 * @param {string} dateStr - Date in YYYYMMDD format
 * @param {number} maxRetries - Max retry attempts
 * @param {number} delay - Delay between retries in ms
 * @returns {Promise<Object|null>} Complete IB data or null
 */
async function fetchIBDataWithRetry(ticker, dateStr, maxRetries = 5, delay = 2000) {
    for (let i = 0; i < maxRetries; i++) {
        const data = await fetchIBData(ticker, dateStr);
        // Check if data is complete (has analysis with required fields)
        if (data && data.analysis && data.analysis.ib_range !== undefined) {
            return data;
        }
        console.log(`[IB Retry ${i + 1}/${maxRetries}] Waiting for complete IB data: ${ticker} ${dateStr}...`);
        await new Promise(resolve => setTimeout(resolve, delay));
    }
    return null;
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