/**
 * Heatmap Panel Module
 * Creates heatmap chart panels for Greek exposure data
 */

/**
 * Create a heatmap panel for Greek exposure
 * @param {Object} chartObj - Chart configuration object
 * @param {number} index - Chart index
 * @returns {HTMLElement} Panel element
 */
function createHeatmapPanel(chartObj, index) {
    const { data: globalData, greek } = chartObj;

    // Ensure data is synced
    if (tabs[currentTabId] && tabs[currentTabId].charts[index]) {
        tabs[currentTabId].charts[index].data = globalData;
    }

    const raw = globalData.option_data;
    const colStrike = raw.columns.indexOf("strike_price");
    const colMetric = raw.columns.findIndex(
        (c) => c.trim() === `total_${greek}` || c.trim() === greek
    );

    if (colMetric === -1) return document.createElement("div");

    // Aggregate data by strike
    const agg = {};
    raw.data.forEach((r) => {
        const k = parseFloat(r[colStrike]);
        const v = (parseFloat(r[colMetric]) || 0) * 1000000;
        agg[k] = (agg[k] || 0) + v;
    });

    let rows = Object.keys(agg).map((k) => ({
        strike: parseFloat(k),
        value: agg[k],
    }));
    rows.sort((a, b) => b.strike - a.strike);

    const spot = globalData.spot_price || 0;
    const net = rows.reduce((s, i) => s + i.value, 0);

    // Calculate max/min and spot value
    let maxPos = -Infinity, maxPosStrike = 0;
    let maxNeg = Infinity, maxNegStrike = 0;
    let closest = null, minDiff = Infinity, spotVal = 0;

    rows.forEach((d) => {
        if (d.value > maxPos) { maxPos = d.value; maxPosStrike = d.strike; }
        if (d.value < maxNeg) { maxNeg = d.value; maxNegStrike = d.strike; }
        const diff = Math.abs(d.strike - spot);
        if (diff < minDiff) {
            minDiff = diff;
            closest = d.strike;
            spotVal = d.value;
        }
    });

    // --- Time Travel Buffer Logic ---
    const COMPARE_DELAY_MS = 3.5 * 60 * 1000;
    const MAX_BUFFER_MS = 5 * 60 * 1000;

    if (!chartObj.historyBuffer) {
        chartObj.historyBuffer = [];
    }

    // Create snapshot
    const currentStrikesMap = {};
    rows.forEach(r => { currentStrikesMap[r.strike] = r.value; });

    const snapshot = {
        timestamp: Date.now(),
        net: net,
        spotVal: spotVal,
        strikes: currentStrikesMap
    };

    // Add to history
    const lastSnap = chartObj.historyBuffer[chartObj.historyBuffer.length - 1];
    if (!lastSnap || (Date.now() - lastSnap.timestamp > 1000)) {
        chartObj.historyBuffer.push(snapshot);
    }

    // Cleanup old snapshots
    const cutoffTime = Date.now() - MAX_BUFFER_MS;
    if (chartObj.historyBuffer.length > 0 && chartObj.historyBuffer[0].timestamp < cutoffTime) {
        chartObj.historyBuffer = chartObj.historyBuffer.filter(s => s.timestamp > cutoffTime);
    }

    // Find reference snapshot
    const targetTime = Date.now() - COMPARE_DELAY_MS;
    let refSnapshot = chartObj.historyBuffer[0];
    let timeMinDiff = Infinity;

    for (const snap of chartObj.historyBuffer) {
        const diff = Math.abs(snap.timestamp - targetTime);
        if (diff < timeMinDiff) {
            timeMinDiff = diff;
            refSnapshot = snap;
        }
    }

    // Calculate changes
    let netChangeHTML = formatChangePct(net, refSnapshot.net);
    let spotChangeHTML = formatChangePct(spotVal, refSnapshot.spotVal);

    // Calculate strike changes
    const strikeChanges = [];
    rows.forEach((row) => {
        const prevValue = refSnapshot.strikes[row.strike];
        if (prevValue !== undefined && prevValue !== null && prevValue !== 0) {
            const diff = row.value - prevValue;
            const pct = (diff / Math.abs(prevValue)) * 100;
            if (Math.abs(diff) > 1) {
                strikeChanges.push({
                    strike: row.strike,
                    nominalChange: diff,
                    pct: pct,
                    changeHTML: formatChangePct(row.value, prevValue)
                });
            }
        }
    });

    strikeChanges.sort((a, b) => a.nominalChange - b.nominalChange);
    const top5Negative = strikeChanges.slice(0, 5);
    const top5Positive = strikeChanges.slice(-5).reverse();

    const strikesToShow = new Set();
    top5Negative.forEach(item => strikesToShow.add(item.strike));
    top5Positive.forEach(item => strikesToShow.add(item.strike));

    const strikeChangeMap = {};
    strikeChanges.forEach(item => {
        if (strikesToShow.has(item.strike)) {
            strikeChangeMap[item.strike] = item.changeHTML;
        }
    });

    const scalePos = Math.max(Math.abs(maxPos), 1);
    const scaleNeg = Math.max(Math.abs(maxNeg), 1);

    // Create panel
    const panel = document.createElement("div");
    panel.className = "chart-panel";
    panel.draggable = true;
    panel.dataset.index = index;
    panel.addEventListener("dragstart", handleDragStart);
    panel.addEventListener("dragend", handleDragEnd);

    // Header
    const header = document.createElement("div");
    header.className = "chart-header";

    const topRow = document.createElement("div");
    topRow.className = "chart-title-row";
    topRow.innerHTML = `
    <div>
      <span class="chart-title">${globalData.ticker}</span>
      <span class="chart-subtitle">${greek}</span>
    </div>
    <div>
      <button class="btn-popout" onclick="openDetachedWindow(${index})" title="Pop out">⇱</button>
      <button class="btn-close" onclick="removeChart(${index})">×</button>
    </div>
  `;

    const stats = document.createElement("div");
    stats.className = "chart-stats";
    stats.innerHTML = `
    <div>Spot: <span class="stat-val" style="color:white">${spot.toFixed(2)}</span></div>
    <div>MaxC: <span class="stat-val val-pos">${maxPosStrike}</span></div>
    <div>MaxP: <span class="stat-val val-neg">${maxNegStrike}</span></div>
  `;

    header.appendChild(topRow);
    header.appendChild(stats);
    header.innerHTML += generateRegimeHTML(globalData.ticker, greek, spot, net, spotVal, netChangeHTML, spotChangeHTML);
    panel.appendChild(header);

    if (rows.length === 0) {
        const emptyMsg = document.createElement("div");
        emptyMsg.style.flex = "1";
        emptyMsg.style.display = "flex";
        emptyMsg.style.alignItems = "center";
        emptyMsg.style.justifyContent = "center";
        emptyMsg.style.color = "var(--accent-red)";
        emptyMsg.style.fontWeight = "bold";
        emptyMsg.style.fontSize = "12px";
        emptyMsg.innerHTML = `NO DATA FOUND<br><span style="font-size:10px; opacity:0.7; font-weight:400;">${globalData.ticker} / ${chartObj.inputExp}</span>`;
        emptyMsg.style.textAlign = "center";
        panel.appendChild(emptyMsg);
        return panel;
    }

    // Heatmap scroll container
    const scroll = document.createElement("div");
    scroll.className = "heatmap-scroll";

    rows.forEach((row) => {
        const div = document.createElement("div");
        div.className = "grid-row";
        if (row.strike === closest) div.classList.add("spot-row");

        const val = row.value;
        const isPos = val >= 0;
        const intensity = isPos ? Math.abs(val) / scalePos : Math.abs(val) / scaleNeg;

        let bg = "transparent";
        let txtColor = "var(--text-dim)";
        let weight = "400";

        if (Math.abs(val) > 1000) {
            if (isPos) {
                const op = 0.15 + intensity * 0.85;
                if (row.strike === maxPosStrike || intensity > 0.8) {
                    bg = "var(--pos-high)";
                    txtColor = "black";
                    weight = "700";
                } else {
                    bg = `rgba(var(--pos-low-rgb), ${op})`;
                    txtColor = "#ccc";
                }
            } else {
                const op = 0.15 + intensity * 0.85;
                if (row.strike === maxNegStrike) {
                    bg = "var(--neg-high)";
                    txtColor = "black";
                    weight = "700";
                } else {
                    bg = `rgba(var(--neg-low-rgb), ${op})`;
                    txtColor = "#dcd0ff";
                }
            }
        } else {
            txtColor = "#444";
        }

        let labelStyle = "";
        if (row.strike === closest) labelStyle = "color: white; font-weight: 700;";
        else if (row.strike === maxPosStrike) labelStyle = "color: var(--pos-high); font-weight: 700;";
        else if (row.strike === maxNegStrike) labelStyle = "color: var(--neg-high); font-weight: 700;";

        const changeHTML = strikeChangeMap[row.strike] || "";

        div.innerHTML = `
      <div class="y-axis-label" style="${labelStyle}">${row.strike}</div>
      <div class="bar-area">
        <div class="bar-fill" style="background:${bg}"></div>
        <span class="value-text" style="color:${txtColor}; font-weight:${weight}">${formatK(val)}${changeHTML}</span>
        ${row.strike === maxPosStrike ? '<div class="ref-line ref-max-pos"></div>' : ""}
        ${row.strike === maxNegStrike ? '<div class="ref-line ref-max-neg"></div>' : ""}
      </div>
      <div class="y-axis-label"></div>
    `;
        scroll.appendChild(div);
    });

    panel.appendChild(scroll);
    return panel;
}
