/**
 * Dashboard Module (Public)
 * Core rendering and shared UI logic for both Users and Admins
 */

/**
 * Render all charts in the current tab
 */
function renderAllCharts() {
    const wrapper = document.getElementById("charts-wrapper");
    if (!wrapper) return;
    wrapper.scrollLeft = 0;
    const activeCharts = getCurrentCharts();
    wrapper.innerHTML = "";
    if (activeCharts.length === 0) {
        wrapper.innerHTML = '<div style="width:100%; text-align:center; padding-top:100px; color:var(--text-dim);">Empty Layout</div>';
        return;
    }

    // Group charts by rowIndex
    const rowsMap = new Map();
    activeCharts.forEach((chartObj, index) => {
        const rowIndex = chartObj.rowIndex || 0;
        if (!rowsMap.has(rowIndex)) {
            rowsMap.set(rowIndex, []);
        }
        rowsMap.get(rowIndex).push({ chartObj, index });
    });

    // Sort row indices and create rows
    const sortedRowIndices = [...rowsMap.keys()].sort((a, b) => a - b);

    sortedRowIndices.forEach(rowIndex => {
        const row = document.createElement("div");
        row.className = "chart-row";
        row.addEventListener("dragover", handleRowDragOver);
        wrapper.appendChild(row);

        rowsMap.get(rowIndex).forEach(({ chartObj, index }) => {
            const panel = createChartPanel(chartObj, index);

            // Apply saved dimensions if available
            if (chartObj.panelWidth) {
                panel.style.width = chartObj.panelWidth + 'px';
            }
            if (chartObj.panelHeight) {
                panel.style.height = chartObj.panelHeight + 'px';
            }

            row.appendChild(panel);
            setTimeout(() => alignChartToSpot(panel), 50);
        });
    });
}

/**
 * Align chart scroll to spot price row
 */
function alignChartToSpot(panel) {
    const spot = panel.querySelector(".spot-row");
    const scrollContainer = panel.querySelector(".heatmap-scroll");

    if (spot && scrollContainer) {
        const spotTop = spot.offsetTop;
        const containerTop = scrollContainer.offsetTop;
        const positionInList = spotTop - containerTop;
        const containerHeight = scrollContainer.clientHeight;
        const rowHeight = spot.clientHeight;
        scrollContainer.scrollTop = positionInList - containerHeight / 2 + rowHeight / 2;
    }
}

/**
 * Realign all charts to spot
 */
function realignAllCharts() {
    const panels = document.querySelectorAll(".chart-panel");
    panels.forEach((panel) => {
        alignChartToSpot(panel);
    });
}

/**
 * Remove a chart from current tab
 * @param {number} index - Chart index
 */
function removeChart(index) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (tab) {
        tab.charts.splice(index, 1);
        renderAllCharts();
    }
}

/**
 * Base Chart Panel Dispatcher (Public version - Heatmaps only)
 * Overwritten by charts.js for Admins to include Fourier/IB
 */
let createChartPanel = function(chartObj, index) {
    return createHeatmapPanel(chartObj, index);
};

/**
 * Generate Greek regime analysis HTML
 */
function generateRegimeHTML(ticker, greek, spot, netValue, spotStrikeValue, netChangeHTML = "", spotChangeHTML = "") {
    let regimeText = "", behaviorText = "", biasText = "", regimeColorVar = "--text-dim";
    const isLocalPos = spotStrikeValue >= 0;
    const isNetPos = netValue >= 0;

    const isAligned = isLocalPos === isNetPos;
    const alignmentText = isAligned ? "CONVERGENT" : "DIVERGENT";
    const alignmentColor = isAligned ? "var(--accent-green)" : "var(--accent-red)";

    if (greek === "gamma" || greek === "dgex") {
        if (isLocalPos) {
            regimeText = "POSITIVE (STICKY)";
            behaviorText = "Dealer sells strength / buys weakness. Low Volatility.";
            regimeColorVar = "--pos-high";
        } else {
            regimeText = "NEGATIVE (ACCEL)";
            behaviorText = "Dealer buys strength / sells weakness. High Volatility.";
            regimeColorVar = "--neg-high";
        }
        biasText = isNetPos ? "Bullish Exposure" : "Bearish Exposure";
    } else if (greek === "delta") {
        if (isNetPos) {
            regimeText = "NET LONG";
            behaviorText = "Dealers are Long. Market needs to sell to hedge.";
            regimeColorVar = "--pos-high";
        } else {
            regimeText = "NET SHORT";
            behaviorText = "Dealers are Short. Market needs to buy to hedge.";
            regimeColorVar = "--neg-high";
        }
        biasText = isLocalPos ? "Local Support" : "Local Resistance";
    } else if (greek === "vanna") {
        const ivTrend = ivTrendByTicker[ticker] || 'neutral';
        const ivRising = ivTrend === 'rising';
        const ivFalling = ivTrend === 'falling';
        let mmBuying = (isLocalPos && ivFalling) || (!isLocalPos && ivRising);
        let mmSelling = (isLocalPos && ivRising) || (!isLocalPos && ivFalling);
        regimeText = isLocalPos ? "POS VANNA" : "NEG VANNA";
        if (mmBuying) {
            regimeColorVar = null; // will use inline color
            behaviorText = `SUPPORTIVE — Dealers BUYING (IV ${ivTrend.toUpperCase()})`;
        } else if (mmSelling) {
            regimeColorVar = null; // will use inline color
            behaviorText = `SUPPRESSIVE — Dealers SELLING (IV ${ivTrend.toUpperCase()})`;
        } else {
            regimeColorVar = null;
            behaviorText = isLocalPos ? "IV Drop = Supportive (BUY) | IV Spike = Suppressive (SELL)" : "IV Drop = Suppressive (SELL) | IV Spike = Supportive (BUY)";
        }
        biasText = `IV: ${ivTrend.toUpperCase()}`;
    } else if (greek === "vega") {
        regimeText = isNetPos ? "LONG VEGA" : "SHORT VEGA";
        behaviorText = isNetPos ? "Profits from Volatility expansion. MM need to buy dips." : "Profits from Volatility crush. MM need to sell rips.";
        regimeColorVar = isNetPos ? "--pos-high" : "--neg-high";
        biasText = "Vol Sensitivity";
    } else if (greek === "vomma") {
        regimeText = isLocalPos ? "POS VOMMA" : "NEG VOMMA";
        behaviorText = isLocalPos ? "Vega increases as Vol rises. Tail risk acceleration." : "Vega decreases as Vol rises. Volatility stabilization.";
        regimeColorVar = isLocalPos ? "--pos-high" : "--neg-high";
        biasText = "Vol Convexity";
    } else if (greek === "zomma") {
        if (isLocalPos) {
            regimeText = "POS ZOMMA";
            behaviorText = "Gamma increases as Vol drops (Stabilizing).";
            regimeColorVar = "--pos-high";
        } else {
            regimeText = "NEG ZOMMA";
            behaviorText = "Gamma increases as Vol rises (Destabilizing).";
            regimeColorVar = "--neg-high";
        }
        biasText = "Gamma convexity";
    } else if (greek === "speed") {
        if (isLocalPos) {
            regimeText = "POS SPEED";
            behaviorText = "Gamma increases as Spot rises. Momentum reinforcing.";
            regimeColorVar = "--pos-high";
        } else {
            regimeText = "NEG SPEED";
            behaviorText = "Gamma decreases as Spot rises. Stabilizing / Exhaustion.";
            regimeColorVar = "--neg-high";
        }
        biasText = "Gamma sensitivity";
    } else if (greek === "charm") {
        // Negative charm → time decay induces dealer BUYING → Supportive
        // Positive charm → time decay induces dealer SELLING → Suppressive
        const isCharmSupportive = isLocalPos ? false : true; // negative local = supportive
        regimeText = isCharmSupportive ? "SUPPORTIVE CHARM" : "SUPPRESSIVE CHARM";
        behaviorText = isCharmSupportive
            ? "SUPPORTIVE — Time decay induces dealer BUYING"
            : "SUPPRESSIVE — Time decay induces dealer SELLING";
        regimeColorVar = null;
        biasText = isNetPos ? "Net Positive" : "Net Negative";
    } else {
        regimeText = isLocalPos ? "LOCAL POS" : "LOCAL NEG";
        behaviorText = "Standard hedging mechanics apply.";
        regimeColorVar = isLocalPos ? "--pos-high" : "--neg-high";
        biasText = `Net: ${formatK(netValue)}`;
    }

    let borderColor;
    if (regimeColorVar === null) {
        // Vanna Supportive/Suppressive — use direct flow colors
        if (behaviorText.includes('SUPPORTIVE')) {
            borderColor = '#00BCD4';
        } else if (behaviorText.includes('SUPPRESSIVE')) {
            borderColor = '#FFB300';
        } else {
            borderColor = 'var(--text-dim)';
        }
    } else {
        borderColor = `var(${regimeColorVar})`;
    }
    const formattedSpot = spot.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    return `
    <div class="regime-wrapper" style="border-left-color: ${borderColor};">
      <div class="regime-header-toggle" onclick="this.parentElement.classList.toggle('active')">
        <span style="color: ${borderColor};">${greek.toUpperCase()} ANALYSIS</span>
        <span class="regime-toggle-icon">▼</span>
      </div>
      <div class="regime-content">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; margin-bottom: 8px;">
          <div>
            <div style="font-size: 9px; color: var(--text-dim); text-transform: uppercase;">Current Spot</div>
            <div style="font-size: 13px; font-weight: 700; color: white;">${formattedSpot}</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 9px; color: var(--text-dim); text-transform: uppercase;">Net Exposure</div>
            <div style="font-size: 13px; font-weight: 700; color: var(${isNetPos ? "--pos-high" : "--neg-high"});">
              ${formatK(netValue)} ${netChangeHTML}
            </div>
          </div>
          <div>
            <div style="font-size: 9px; color: var(--text-dim); text-transform: uppercase;">Local Strike Exp</div>
            <div style="font-size: 13px; font-weight: 700; color: var(${isLocalPos ? "--pos-high" : "--neg-high"});">
              ${formatK(spotStrikeValue)} ${spotChangeHTML}
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 9px; color: var(--text-dim); text-transform: uppercase;">Structure</div>
            <div style="font-size: 11px; font-weight: 700; color: ${alignmentColor}; letter-spacing: 0.5px;">${alignmentText}</div>
          </div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <div style="display: flex; justify-content: space-between;">
            <span style="color: var(--text-dim);">Regime:</span>
            <span style="font-weight: 700; color: ${borderColor};">${regimeText}</span>
          </div>
          <div style="font-size: 10px; color: #ccc; font-style: italic; margin: 2px 0;">
            "${behaviorText}"
          </div>
          <div style="display: flex; justify-content: space-between; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 4px; margin-top: 2px;">
            <span style="color: var(--text-dim);">Market Bias:</span>
            <span style="font-weight: 700; color: white;">${biasText}</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Update IV trend from Fourier data
 */
function updateIVTrendFromFourier(ticker, fourierData) {
    if (!fourierData || !Array.isArray(fourierData) || fourierData.length < 5) {
        ivTrendByTicker[ticker] = 'neutral';
        return;
    }
    const recentPoints = fourierData.slice(-10);
    const ivValues = recentPoints.map(d => d.iv_fft).filter(v => v !== null && v !== undefined);
    if (ivValues.length < 3) {
        ivTrendByTicker[ticker] = 'neutral';
        return;
    }
    const midpoint = Math.floor(ivValues.length / 2);
    const firstHalfAvg = ivValues.slice(0, midpoint).reduce((a, b) => a + b, 0) / midpoint;
    const secondHalfAvg = ivValues.slice(midpoint).reduce((a, b) => a + b, 0) / (ivValues.length - midpoint);
    const change = secondHalfAvg - firstHalfAvg;
    if (change > 0.001) {
        ivTrendByTicker[ticker] = 'rising';
    } else if (change < -0.001) {
        ivTrendByTicker[ticker] = 'falling';
    } else {
        ivTrendByTicker[ticker] = 'neutral';
    }
}
