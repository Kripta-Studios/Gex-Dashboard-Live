/**
 * Charts Module
 * Chart creation, rendering, and panel management
 */

/**
 * Render all charts in the current tab
 */
function renderAllCharts() {
    const wrapper = document.getElementById("charts-wrapper");
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
 * @param {HTMLElement} panel - Chart panel element
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
 * Create a chart panel (dispatcher)
 * @param {Object} chartObj - Chart data object
 * @param {number} index - Chart index
 * @returns {HTMLElement} Panel element
 */
function createChartPanel(chartObj, index) {
    // Dispatch to specific panel creators
    if (chartObj.type === 'fourier') return createFourierPanel(chartObj, index);
    if (chartObj.type === 'ib') return createIBPanel(chartObj, index);
    return createHeatmapPanel(chartObj, index);
}

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
            regimeColorVar = "--pos-high";
            behaviorText = `MM BUYING (IV ${ivTrend.toUpperCase()}) → Support`;
        } else if (mmSelling) {
            regimeColorVar = "--neg-high";
            behaviorText = `MM SELLING (IV ${ivTrend.toUpperCase()}) → Pressure`;
        } else {
            regimeColorVar = isLocalPos ? "--pos-high" : "--neg-high";
            behaviorText = isLocalPos ? "IV Drop = Buying | IV Spike = Selling." : "IV Drop = Selling | IV Spike = Buying.";
        }
        biasText = `IV: ${ivTrend.toUpperCase()}`;
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
    } else {
        regimeText = isLocalPos ? "LOCAL POS" : "LOCAL NEG";
        behaviorText = "Standard hedging mechanics apply.";
        regimeColorVar = isLocalPos ? "--pos-high" : "--neg-high";
        biasText = `Net: ${formatK(netValue)}`;
    }

    const borderColor = `var(${regimeColorVar})`;
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
    console.log(`[IV Trend] ${ticker}: ${ivTrendByTicker[ticker]} (change: ${change.toFixed(4)})`);
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
