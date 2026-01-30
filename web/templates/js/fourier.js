/**
 * Fourier Panel Module
 * Creates Fourier analysis chart panels using Chart.js
 */

/**
 * Create a Fourier analysis panel
 * @param {Object} chartObj - Chart configuration object
 * @param {number} index - Chart index
 * @returns {HTMLElement} Panel element
 */
function createFourierPanel(chartObj, index) {
    const { data, inputTicker, dateStr } = chartObj;

    const panel = document.createElement("div");
    panel.className = "chart-panel";
    panel.draggable = true;
    panel.dataset.index = index;
    panel.addEventListener("dragstart", handleDragStart);
    panel.addEventListener("dragend", handleDragEnd);

    // Header
    const header = document.createElement("div");
    header.className = "chart-header";
    header.innerHTML = `
    <div class="chart-title-row">
      <div>
        <span class="chart-title" style="color:cyan;">${inputTicker} FOURIER</span>
        <span class="chart-subtitle">${dateStr}</span>
      </div>
      <div>
        <button class="btn-popout" onclick="openDetachedWindow(${index})" title="Pop out">⇱</button>
        <button class="btn-close" onclick="removeChart(${index})">×</button>
      </div>
    </div>
    <div class="chart-stats" style="border-left: 3px solid magenta;">
      <span style="font-size:10px;">Dual Axis: <strong style="color:cyan">Price</strong> vs <strong style="color:magenta">IV FFT</strong></span>
    </div>
  `;
    panel.appendChild(header);

    const canvasContainer = document.createElement("div");
    canvasContainer.style.flex = "1";
    canvasContainer.style.position = "relative";
    canvasContainer.style.minHeight = "0";
    canvasContainer.style.padding = "10px";

    const canvas = document.createElement("canvas");
    canvasContainer.appendChild(canvas);
    panel.appendChild(canvasContainer);

    setTimeout(() => renderFourierChart(canvas, data), 0);

    return panel;
}

/**
 * Render Fourier chart using Chart.js
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} jsonData - Fourier data array
 */
function renderFourierChart(canvas, jsonData) {
    // Filter to market hours
    const filteredData = jsonData.filter(d => {
        const timePart = d.datetime.split(' ')[1];
        return timePart >= "09:20:00" && timePart <= "16:15:00";
    });

    if (filteredData.length === 0) return;

    const labels = filteredData.map(d => {
        const datePart = d.datetime.split(' ')[1];
        return datePart ? datePart.substring(0, 5) : d.datetime;
    });

    const spotFftData = filteredData.map(d => d.spot_fft);
    const ivFftData = filteredData.map(d => d.iv_fft);
    const realSpotData = filteredData.map(d => d.spot);
    const realIvData = filteredData.map(d => d.atm_put_iv);

    // Get turn styles for peaks/valleys
    const getTurnStyles = (dataArr) => {
        const radii = [];
        const colors = [];
        const borders = [];

        for (let i = 0; i < dataArr.length; i++) {
            if (i === 0 || i === dataArr.length - 1) {
                radii.push(0); colors.push('transparent'); borders.push('transparent');
                continue;
            }
            const prev = dataArr[i - 1];
            const curr = dataArr[i];
            const next = dataArr[i + 1];

            if (curr > prev && curr > next) {
                radii.push(4); colors.push('#FF0000'); borders.push('#FFFFFF');
            } else if (curr < prev && curr < next) {
                radii.push(4); colors.push('#00FF00'); borders.push('#FFFFFF');
            } else {
                radii.push(0); colors.push('transparent'); borders.push('transparent');
            }
        }
        return { radii, colors, borders };
    };

    const spotStyles = getTurnStyles(spotFftData);
    const ivStyles = getTurnStyles(ivFftData);

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Real Spot',
                    data: realSpotData,
                    borderColor: 'rgba(255, 255, 255, 0.35)',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    pointRadius: 0,
                    tension: 0,
                    yAxisID: 'y',
                    order: 10
                },
                {
                    label: 'Real IV',
                    data: realIvData,
                    borderColor: 'rgba(255, 0, 255, 0.35)',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    pointRadius: 0,
                    tension: 0,
                    yAxisID: 'y1',
                    order: 19
                },
                {
                    label: 'Fourier Spot',
                    data: spotFftData,
                    borderColor: 'cyan',
                    backgroundColor: 'cyan',
                    borderWidth: 2,
                    yAxisID: 'y',
                    tension: 0.4,
                    pointRadius: spotStyles.radii,
                    pointBackgroundColor: spotStyles.colors,
                    pointBorderColor: spotStyles.borders,
                    pointBorderWidth: 1,
                    pointHitRadius: 10,
                    order: 1
                },
                {
                    label: 'ATM IV (FFT)',
                    data: ivFftData,
                    borderColor: 'magenta',
                    backgroundColor: 'magenta',
                    borderWidth: 2,
                    yAxisID: 'y1',
                    tension: 0.4,
                    pointRadius: ivStyles.radii,
                    pointBackgroundColor: ivStyles.colors,
                    pointBorderColor: ivStyles.borders,
                    pointBorderWidth: 1,
                    pointHitRadius: 10,
                    order: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: 'white' }
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) label += context.parsed.y.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#888', maxTicksLimit: 10 },
                    grid: { color: '#333' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: 'cyan' },
                    grid: { color: '#333' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: 'magenta' },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

/**
 * Add Fourier chart to current tab
 */
function addFourierChartToCurrent(data, ticker, dateStr) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (tab) {
        updateIVTrendFromFourier(ticker, data);
        tab.charts.push({
            type: 'fourier',
            data: data,
            inputTicker: ticker,
            inputExp: 'fourier',
            dateStr: dateStr
        });
    }
}

/**
 * Handle Load Fourier button click
 */
async function handleLoadFourier() {
    const ticker = document.getElementById("ticker").value.toUpperCase();
    const dateVal = document.getElementById("fourier-date").value;
    const dateStr = dateVal.replace(/-/g, "");

    const btn = document.querySelector('button[onclick="handleLoadFourier()"]');
    const originalText = btn.innerText;
    btn.innerText = "⏳";

    const data = await fetchFourierData(ticker, dateStr);

    btn.innerText = originalText;

    if (data) {
        addFourierChartToCurrent(data, ticker, dateStr);
        renderAllCharts();
    } else {
        // Show actual file being searched (with ticker mapping)
        let searchTicker = ticker;
        if (ticker === "/ES") searchTicker = "SPX";
        else if (ticker === "/NQ") searchTicker = "QQQ";
        alert(`No Fourier data found for ${ticker} on ${dateVal}.\nSearched: fourier_data_${searchTicker}_${dateStr}.json`);
    }
}

