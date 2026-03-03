/**
 * Market Structure Engine
 * Evaluates options flow and market data to classify into 13 distinct Market Structures.
 */

// 13 Market Structures Matrix
const MARKET_STRUCTURES = [
    {
        "id": 1,
        "name": "Vol of Vol / Fragile Long Vol",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Compression Trap",
        "action": "Sell into Rally",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": true, "ib_bounce": false }
    },
    {
        "id": 2,
        "name": "Fragile Stabilisation / The Exhaustive Pin",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg" },
        "regime": "Transitional",
        "action": "Dealer is Binary. Buys until pin snaps, then aggressive SELL.",
        "tilt": "Do not trade",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 3,
        "name": "Vol Spike with Spot Resilience",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Expansion",
        "action": "Supportive Buyers",
        "tilt": "Momentum (Pull backs are entries)",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 4,
        "name": "Directionless Chop - Slight Bid",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Compression",
        "action": "Passive Buyers",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 5,
        "name": "Short Bearish Gamma Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg" },
        "regime": "Expansion",
        "action": "Forced Sellers",
        "tilt": "Momentum (Sell Rallies)",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 6,
        "name": "Volatility Mean Reversion Sideways Grind",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg" },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 7,
        "name": "Volatility Mean Reversion Crush",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 8,
        "name": "The Ceiling / The Call Pin",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Compression",
        "action": "Forced Sellers on Rips",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 9,
        "name": "High Confidence Grind / PIN",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg" },
        "regime": "Compression",
        "action": "Supportive Buyers",
        "tilt": "Fade Extremes / PIN",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 10,
        "name": "Negative Convexity Vol Unwind (Compression Type)",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Compression",
        "action": "Dealer Sells",
        "tilt": "High Risk - Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    },
    {
        "id": 11,
        "name": "Negative Convexity Vol Unwind (Expansion Type)",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Expansion",
        "action": "Dealer Sells",
        "tilt": "Momentum (Pull backs are entries)",
        "flags": { "max_vanna_level": false, "ib_bounce": true }
    },
    {
        "id": 12,
        "name": "Vanna-fueled Melt Up",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Expansion",
        "action": "Forced Buying",
        "tilt": "Momentum (Pull backs are entries)",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": true }
    },
    {
        "id": 13,
        "name": "The Gamma Trap / Crash-to-Melt Vanna",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
        "regime": "Transitional / Expansion",
        "action": "Binary at open",
        "tilt": "Do not trade / Scalp Only",
        "flags": { "max_vanna_level": false, "ib_bounce": false }
    }
];

/**
 * Utility to calculate EMA from an array of prices
 * @param {Array<number>} prices
 * @param {number} period 
 * @returns {number} The current EMA
 */
function calculateEMA(prices, period) {
    if (!prices || prices.length === 0) return null;
    let multiplier = 2 / (period + 1);
    let ema = prices[0]; // SMA for first day

    for (let i = 1; i < prices.length; i++) {
        ema = (prices[i] - ema) * multiplier + ema;
    }
    return ema;
}

/**
 * Convert 1-minute series to 5-minute candles to calculate EMA
 * @param {Array<Object>} series1m - { time: "HH:MM", price: 123 }
 * @returns {Array<number>} Array of closing prices for each 5m candle
 */
function resampleTo5Min(series1m) {
    if (!series1m || series1m.length === 0) return [];

    let closes = [];
    // We assume data is sorted chronologically
    for (let i = 0; i < series1m.length; i += 5) {
        // Find closing price of the 5-min interval
        // take min between (i+4) and length-1
        let endIndex = Math.min(i + 4, series1m.length - 1);
        let c = series1m[endIndex].price || series1m[endIndex].close;
        if (c !== undefined && c !== null) {
            closes.push(c);
        }
    }
    return closes;
}

/**
 * Returns the VIX Open and technicals based on IB data from backend
 * @param {string} dateStr YYYYMMDD
 * @returns {Promise<Object>} Object containing VIX_Open, spotEMA20, spotEMA50, vixEMA20, vix9d
 */
async function fetchTechnicals(dateStr) {
    // 1. Fetch VIX 1min data
    let vixOpen = null;
    let vix9dValue = null;
    let vixEMA20 = null;
    let vixPrevClose = null;

    try {
        const vixIB = await fetchIBData("VIX", dateStr); // In api.js
        if (vixIB && vixIB.series && vixIB.series.length > 0) {
            // Usually starts at 09:30 or first candle in normal hours
            // Find first element with time >= 09:30
            let startMarket = vixIB.series.find(d => d.time >= "09:30");
            if (startMarket) {
                vixOpen = startMarket.open || startMarket.price;
            } else {
                vixOpen = vixIB.series[0].open || vixIB.series[0].price;
            }
            // For VIX9D, we don't have a direct ticker usually unless available in api, 
            // if we don't have VIX9D ticker, we proxy with VIX Spot price for now as an approximation. 
            // Often VIX9D is another ticker. Let's try to fetch /VX or proxy with VIX
            const vix5m = resampleTo5Min(vixIB.series);
            vixEMA20 = calculateEMA(vix5m, 20);
            vix9dValue = vixIB.series[vixIB.series.length - 1].price;
        }

        // Let's get "VIX9D" if there is IB data for it, else just use VIX
        const vix9dIB = await fetchIBData("VIX9D", dateStr);
        if (vix9dIB && vix9dIB.series && vix9dIB.series.length > 0) {
            vix9dValue = vix9dIB.series[vix9dIB.series.length - 1].price;
            // Recalculate VIX9D EMA
            const vix9d_5m = resampleTo5Min(vix9dIB.series);
            vixEMA20 = calculateEMA(vix9d_5m, 20);
        }

        // Get VIX prev close from the main spot endpoint just to be safe
        const vixLive = await fetchChartData("VIX", "weekly");
        if (vixLive && vixLive.prev_close_price !== undefined) {
            vixPrevClose = vixLive.prev_close_price;
        }

    } catch (e) {
        console.warn("Error fetching VIX technicals", e);
    }

    // 2. Fetch SPX 1min data
    let spotEMA20 = null;
    let spotEMA50 = null;
    try {
        const spxIB = await fetchIBData("SPX", dateStr);
        if (spxIB && spxIB.series && spxIB.series.length > 0) {
            const spx5m = resampleTo5Min(spxIB.series);
            spotEMA20 = calculateEMA(spx5m, 20);
            spotEMA50 = calculateEMA(spx5m, 50);
        }
    } catch (e) {
        console.warn("Error fetching SPX technicals", e);
    }

    return {
        vixOpen,
        vixPrevClose,
        vixEMA20,
        vix9dValue,
        spotEMA20,
        spotEMA50
    };
}

/**
 * Aggregate the Net Greeks from the `/get_latest` output or cached tabs
 * @returns {Object} { gamma, zomma, delta, vex, vega, vomma }
 */
async function fetchNetGreeksLive(ticker) {
    // We can use the batch load pattern or fetch them explicitly
    const greeks = ["gamma", "zomma", "delta", "vex", "vega", "vomma"];
    let net = {};

    // Default fallback values
    for (let g of greeks) net[g] = 0;

    try {
        // Just fetch '0dte' for intraday flow, or 'all'? We'll fetch 0dte.
        // If the engine requires total sum across exps, we could fetch 'all'

        let batchReq = greeks.map(g => ({
            ticker: ticker,
            exp: "0dte" // You can adjust this if the engine requires a different expiration
        }));

        const uniqueReqs = [...new Set(batchReq.map(JSON.stringify))].map(JSON.parse);
        const resp = await authFetch('/get_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(uniqueReqs)
        });
        const batchData = await resp.json();

        // Calculate Net for each greek (sum over all strikes)
        for (let g of greeks) {
            const dataKey = `${ticker.toUpperCase()}_0dte`;
            if (batchData[dataKey]) {
                const optData = batchData[dataKey].option_data;
                const colMetric = optData.columns.findIndex(c => c.trim() === `total_${g}` || c.trim() === g);
                if (colMetric !== -1) {
                    let sum = 0;
                    optData.data.forEach(r => {
                        sum += (parseFloat(r[colMetric]) || 0);
                    });
                    net[g] = sum;
                }
            }
        }
    } catch (e) {
        console.warn("Error fetching live greeks for MS Engine", e);
    }

    return net;
}

/**
 * Main function to evaluate the Market Structure
 * @returns {Object} matched structure and any warnings
 */
async function runMarketStructureEngine(ticker = "SPX") {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const todayStr = `${yyyy}${mm}${dd}`;

    // 1. Fetch Technicals
    const tech = await fetchTechnicals(todayStr);

    // 2. Fetch Net Greeks
    const netGreeks = await fetchNetGreeksLive(ticker);

    // 3. Layer 1: Volatility State (The Override)
    let ivState = "LOW";
    // Using current VIX spot vs open and prev close
    let vixCurrent = tech.vix9dValue; // Assuming this maps to current spot contextually or from live SPX / VIX spot
    const vixLive = await fetchChartData("VIX", "weekly");
    if (vixLive && vixLive.spot_price) {
        vixCurrent = vixLive.spot_price;
    }

    if (vixCurrent !== null && tech.vixOpen !== null && tech.vixPrevClose !== null) {
        if (vixCurrent < tech.vixOpen) {
            ivState = "Low";
        } else if (vixCurrent > tech.vixPrevClose) {
            ivState = "High";
        } else {
            ivState = "Low";
        }
    } else {
        ivState = "Low"; // Fallback
    }

    // 4. Layer 2: Matrix Lookup
    // Map net raw numbers to Pos/Neg
    const currentConditions = {
        "IV": ivState === "High" ? "High" : "Low", // Case formatting
        "Gamma": netGreeks.gamma >= 0 ? "Pos" : "Neg",
        "Zomma": netGreeks.zomma >= 0 ? "Pos" : "Neg",
        "Delta": netGreeks.delta >= 0 ? "Pos" : "Neg",
        "Vex": netGreeks.vex >= 0 ? "Pos" : "Neg",
        "Vega": netGreeks.vega >= 0 ? "Pos" : "Neg",
        "Vomma": netGreeks.vomma >= 0 ? "Pos" : "Neg"
    };

    let matchedStructure = MARKET_STRUCTURES.find(s => {
        return (
            s.condition.IV === currentConditions.IV &&
            s.condition.Gamma === currentConditions.Gamma &&
            s.condition.Zomma === currentConditions.Zomma &&
            s.condition.Delta === currentConditions.Delta &&
            s.condition.Vex === currentConditions.Vex &&
            s.condition.Vega === currentConditions.Vega &&
            s.condition.Vomma === currentConditions.Vomma
        );
    });

    if (!matchedStructure) {
        matchedStructure = {
            id: 0,
            name: "UNCLASSIFIED STRUCTURE",
            regime: "UNKNOWN",
            action: "Monitor",
            tilt: "UNKNOWN",
            flags: { max_vanna_level: false, ib_bounce: false, dadu_pinning: false },
            isFallback: true
        };
    }

    // 5. Layer 3: Spot & VIX9D Technical Confirmation
    let layer3Warning = null;
    let spotRegime = "Compression";
    if (tech.spotEMA20 !== null && tech.spotEMA50 !== null) {
        if (tech.spotEMA20 > tech.spotEMA50) {
            // Check VIX9D as well
            if (tech.vix9dValue !== null && tech.vixEMA20 !== null) {
                if (tech.vix9dValue > tech.vixEMA20) {
                    spotRegime = "Expansion";
                } else {
                    spotRegime = "Compression"; // Condition says AND
                }
            } else {
                spotRegime = "Expansion"; // Assume expansion if only Spot EMA satisfied without VIX9D
            }
        } else {
            spotRegime = "Compression";
        }
    }

    // Mismatch check
    if (matchedStructure.regime.includes("Expansion") && spotRegime === "Compression") {
        layer3Warning = "REGIME MISMATCH - CAUTION";
    }

    return {
        structure: matchedStructure,
        conditions: currentConditions,
        warning: layer3Warning,
        technicals: tech
    };
}

/**
 * Update the UI Widget
 */
async function updateMarketStructureUI() {
    // SECURITY CHECK: Only ADMIN role can run the logic
    const role = sessionStorage.getItem("gex_user_role");
    if (role !== "ADMIN") return;

    const parentContainer = document.getElementById("market-structure-panel");
    if (!parentContainer) return;

    // Show loading state
    parentContainer.classList.add("ms-loading");
    document.getElementById("ms-structure-name").innerHTML = '<div class="loader"></div> Calculating Matrix...';
    document.getElementById("ms-dealer-action").innerText = '';
    document.getElementById("ms-tilt-tag").style.display = 'none';
    document.getElementById("ms-flags-container").innerHTML = '';
    document.getElementById("ms-warning").style.display = 'none';

    try {
        const result = await runMarketStructureEngine("SPX");

        parentContainer.classList.remove("ms-loading");

        const struct = result.structure;

        // Title and fallback colors
        const nameEl = document.getElementById("ms-structure-name");
        nameEl.innerText = struct.name;
        if (struct.isFallback) {
            nameEl.style.color = "var(--accent-yellow, #FFD700)";
        } else {
            nameEl.style.color = "white"; // Or theme color
        }

        // Subtitle
        document.getElementById("ms-dealer-action").innerText = struct.action;

        // Tilt tag
        const tiltEl = document.getElementById("ms-tilt-tag");
        tiltEl.innerText = struct.tilt;
        tiltEl.style.display = 'inline-block';
        if (struct.tilt.includes("Momentum")) {
            tiltEl.style.background = 'var(--pos-high, #00FF00)';
            tiltEl.style.color = '#000';
        } else if (struct.tilt.includes("Fade")) {
            tiltEl.style.background = 'var(--accent-blue, #1E90FF)';
            tiltEl.style.color = '#fff';
        } else {
            tiltEl.style.background = 'var(--panel-bg, #2A2A2A)';
            tiltEl.style.color = '#fff';
        }

        // Flags
        const flagsContainer = document.getElementById("ms-flags-container");
        flagsContainer.innerHTML = '';
        if (struct.flags) {
            if (struct.flags.max_vanna_level) {
                flagsContainer.innerHTML += `<span class="ms-badge badge-vanna">WATCH: Max Vanna Level</span>`;
            }
            if (struct.flags.ib_bounce) {
                flagsContainer.innerHTML += `<span class="ms-badge badge-ib">WATCH: IB Bounce Level</span>`;
            }
            if (struct.flags.dadu_pinning) {
                flagsContainer.innerHTML += `<span class="ms-badge badge-dadu">Dadu Pinning Active</span>`;
            }
        }

        // Warning
        const warningEl = document.getElementById("ms-warning");
        if (result.warning) {
            warningEl.innerText = result.warning;
            warningEl.style.display = 'block';
        } else {
            warningEl.style.display = 'none';
        }

    } catch (e) {
        console.error("Failed to update Market Structure UI", e);
        parentContainer.classList.remove("ms-loading");
        document.getElementById("ms-structure-name").innerText = "ENGINE ERROR";
    }
}
