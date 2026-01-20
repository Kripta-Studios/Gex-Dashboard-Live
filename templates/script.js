let tabs = [{ id: 0, name: "Default", charts: [] }];
let currentTabId = 0;
let tabCounter = 1;
let refreshIntervalId = null;
let realSpotSPX = 0; 
let historyDebounceTimer = null;
let currentHistoryTimeEST = null;
// --- AUTHENTICATION & LOGIN ---
const TARGET_EMAIL_HASH =
  "0f089be93d18d31f8ac42fc84ecd206bea41ffbde1df2a11dc1de1637822dcb7";
const TARGET_PASS_HASH =
  "9b068d00dba617e0e84667d11ac6eb934e8ca73f4102195095eeff8ccd3359e1";

async function sha256(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hashHex;
}

// --- AUTHENTICATION (SERVER SIDE) ---

async function checkLogin() {
  const emailInput = document.getElementById("login-email").value.trim();
  const passInput = document.getElementById("login-pass").value;
  const errorDiv = document.getElementById("login-error");
  const btn = document.querySelector(".login-btn");

  errorDiv.innerText = "";
  btn.innerText = "VERIFYING...";

  try {
    // Enviamos credenciales al servidor Python
    const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailInput, password: passInput })
    });

    const data = await response.json();

    if (response.ok && data.status === "ok") {
        // Login Exitoso
        sessionStorage.setItem("gex_auth_token", data.token);
        sessionStorage.setItem("gex_user_role", data.role);
        grantAccess(data.role);
    } else {
        errorDiv.innerText = "Invalid credentials.";
        btn.innerText = "AUTHENTICATE";
    }
  } catch (e) {
    console.error(e);
    errorDiv.innerText = "Server connection failed.";
    btn.innerText = "AUTHENTICATE";
  }
}

function grantAccess(role) {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app-wrapper").style.display = "flex";
  
  // LOGICA ADMIN: Mostrar botón IB
  if (role === 'ADMIN') {
      const ibBtn = document.getElementById("btn-ib");
      if(ibBtn) ibBtn.style.display = "inline-block";
  }

  init();
}

// Checkeo de sesión al recargar (simple)
(function checkSession() {
    const token = sessionStorage.getItem("gex_auth_token");
    const role = sessionStorage.getItem("gex_user_role");
    if (token) {
        grantAccess(role);
    }
})();

document
  .getElementById("login-pass")
  .addEventListener("keypress", function (e) {
    if (e.key === "Enter") checkLogin();
  });


(function checkSession() {
  const urlParams = new URLSearchParams(window.location.search);
  // Si tenemos token válido O si estamos en modo detached (asumimos que viene de una sesión válida)
  if (sessionStorage.getItem("gex_auth_token") === "valid" || urlParams.get('mode') === 'detached') {
    // Aseguramos el token en la nueva ventana por si acaso
    sessionStorage.setItem("gex_auth_token", "valid");
    grantAccess();
  }
})();

async function init() {
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');

  // En script.js -> dentro de async function init()
  
    // --- CASO 1: SINGLE CHART DETACHED ---
    if (mode === 'detached') {
        document.body.classList.add('detached-mode');
        const loginScreen = document.getElementById("login-screen");
        if(loginScreen) loginScreen.style.display = "none";
        document.getElementById("app-wrapper").style.display = "flex";
        
        const ticker = urlParams.get('ticker');
        const theme = urlParams.get('theme');
        const type = urlParams.get('type'); // Nuevo parámetro
  
        if (theme) changePalette(theme);
        
        const wrapper = document.getElementById("charts-wrapper");
        wrapper.innerHTML = ""; // Limpiar loading
  
        // A. Lógica para FOURIER / IB
        if (type === 'fourier' || type === 'ib') {
            const dateStr = urlParams.get('date');
            
            const loadSpecial = async () => {
                let data = null;
                // Decidir qué fetch usar
                if (type === 'fourier') {
                    data = await fetchFourierData(ticker, dateStr);
                } else {
                    data = await fetchIBData(ticker, dateStr);
                }
  
                if (data) {
                    wrapper.innerHTML = "";
                    
                    // Crear objeto de configuración compatible
                    const chartConf = { 
                        data: data, 
                        inputTicker: ticker, 
                        dateStr: dateStr,
                        type: type
                    };
  
                    // Renderizar usando las funciones existentes
                    let panel;
                    if (type === 'fourier') panel = createFourierPanel(chartConf, 0);
                    else panel = createIBPanel(chartConf, 0);
  
                    wrapper.appendChild(panel);
                    
                    // Ocultar controles innecesarios en modo detached
                    const closeBtn = panel.querySelector('.btn-close');
                    const popBtn = panel.querySelector('.btn-popout');
                    if(closeBtn) closeBtn.style.display = 'none';
                    if(popBtn) popBtn.style.display = 'none';
                } else {
                     wrapper.innerHTML = `<div style="color:red; text-align:center; padding-top:50px;">Data not found for ${type}</div>`;
                }
            };
  
			loadSpecial();

          // OPTIMIZACIÓN: Solo activar auto-refresh si es "LIVE" o la fecha de hoy
          // Calculamos fecha de hoy formato YYYYMMDD
          const now = new Date();
          const todayStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
          
          // Si el parámetro 'date' en la URL es 'LIVE' o coincide con hoy, activamos el loop
          if (!dateStr || dateStr === 'LIVE' || dateStr === todayStr) {
              setInterval(loadSpecial, 30000);
          }
          
          return;

        }
  
        // B. Lógica existente para HEATMAPS (tu código anterior)
        const exp = urlParams.get('exp');
        const greek = urlParams.get('greek');
        
        const loadSingle = async () => {
            const data = await fetchChartData(ticker, exp);
            if (data) {
                wrapper.innerHTML = "";
                const panel = createChartPanel({ data, greek, inputTicker: ticker, inputExp: exp }, 0);
                wrapper.appendChild(panel);
                setTimeout(() => alignChartToSpot(panel), 100);
            }
        };
        loadSingle();
        setInterval(loadSingle, 30000);
        return; 
    }

   // --- CASO 2: LAYOUT COMPLETO DETACHED (MEJORADO PARA MIXED CHARTS) ---
  if (mode === 'detached_layout') {
      document.body.classList.add('detached-layout-mode');
      
      document.getElementById("login-screen").style.display = "none";
      document.getElementById("app-wrapper").style.display = "flex";

      const theme = urlParams.get('theme');
      if (theme) changePalette(theme);

      const transferId = urlParams.get('transferId');
      const rawConfig = localStorage.getItem(transferId);
      
      if (!rawConfig) {
          document.getElementById("charts-wrapper").innerHTML = "Error: Layout configuration not found.";
          return;
      }

      const chartsConfig = JSON.parse(rawConfig);
      const wrapper = document.getElementById("charts-wrapper");

      // Función inteligente para cargar datos según el tipo
      const loadEntireLayout = async () => {
          if (!wrapper.hasChildNodes()) {
               wrapper.innerHTML = '<div style="color:white; margin:auto;">Loading Mixed Layout...</div>';
          }

          // Calcular fecha de hoy para Fourier/IB si están en modo LIVE
          const now = new Date();
          const todayStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;

          // Buscamos datos en paralelo, respetando el tipo de cada gráfico
          const promises = chartsConfig.map(async (conf, index) => {
              
              let data = null;
              // Normalizamos la fecha: si es LIVE o null, usamos hoy.
              const targetDate = (conf.dateStr && conf.dateStr !== 'LIVE') ? conf.dateStr : todayStr;

              try {
                  // A. LOGICA PARA FOURIER
                  if (conf.type === 'fourier') {
                      data = await fetchFourierData(conf.ticker, targetDate);
                  } 
                  // B. LOGICA PARA IB LEVELS
                  else if (conf.type === 'ib') {
                      data = await fetchIBData(conf.ticker, targetDate);
                  } 
                  // C. LOGICA PARA HEATMAPS (TABLAS)
                  else {
                      // Usamos fetchWithRetry si existe, si no fetchChartData simple
                      // Asumimos que es 'heatmap' si no tiene type
                      data = await fetchChartData(conf.ticker, conf.exp);
                  }
              } catch (e) {
                  console.error(`Error loading panel ${index}`, e);
              }

              if (data) {
                  // Reconstruimos el objeto chart completo
                  const chartObj = {
                      data: data,
                      greek: conf.greek,
                      inputTicker: conf.ticker,
                      inputExp: conf.exp,
                      type: conf.type || 'heatmap',
                      dateStr: targetDate
                  };

                  // createChartPanel actúa como despachador (Dispatcher)
                  // Llamará a createFourierPanel o createIBPanel internamente si el type coincide
                  return createChartPanel(chartObj, index);
              }
              return null;
          });

          const results = await Promise.all(promises);
          
          wrapper.innerHTML = ""; // Limpiamos contenedor
          
 	 results.forEach(panel => {
    if (panel) {
        // En lugar de ocultar TODO, solo ocultamos el popout (para evitar popouts infinitos)
        const popBtn = panel.querySelector('.btn-popout');
        if(popBtn) popBtn.style.display = 'none';
        
        // MANTENEMOS el botón de cierre (X) para que el usuario pueda limpiar la vista
        const closeBtn = panel.querySelector('.btn-close');
        if(closeBtn) closeBtn.style.display = 'block'; 

        wrapper.appendChild(panel);
    }
});
          setTimeout(() => realignAllCharts(), 100);
      };

      await loadEntireLayout();

      // Auto-refresh cada 60s
      setInterval(loadEntireLayout, 30000);
      
      return;
  
  }

  // --- CASO 3: APP NORMAL ---
  // El código de siempre...
  const wrapper = document.getElementById("charts-wrapper");
  wrapper.innerHTML = '<div style="color:white; margin:auto; text-align:center;">Loading...</div>';
  const loaded = await loadSavedLayouts();
  // ... etc ...
  if (!loaded) {
    tabs = [{ id: 0, name: "Default", charts: [] }];
    currentTabId = 0;
    tabCounter = 1;
  }
  renderTabs();
  renderAllCharts();
  updateExpSuggestions();
  updateMarketSpots();
  updateNYTime();
  toggleAutoRefresh();
}

// --- HISTORY LOGIC ---

/**
 * Obtiene los minutos totales del día actual en hora EST (Nueva York).
 * Ejemplo: 03:00 AM = 180 minutos.
 */
function getCurrentESTMinutes() {
    const now = new Date();
    // Convertir la fecha actual a string en zona horaria America/New_York
    const estString = now.toLocaleString("en-US", { timeZone: "America/New_York", hour12: false });
    // Parsear la hora devuelta (M/D/YYYY, HH:MM:SS)
    const timePart = estString.split(", ")[1];
    const [h, m] = timePart.split(":").map(Number);
    return (h * 60) + m;
}

// --- EN SCRIPT.JS ---

// 1. Modificamos scrubHistory para que NO cargue datos, solo actualice el texto visualmente
function scrubHistory(val) {
    const label = document.getElementById("history-time");
    const slider = document.getElementById("history-slider");
    
    // Rango de Mercado en Minutos
    const START_MINUTES = 3 * 60;      // 03:00 EST
    const CLOSE_MINUTES = 16 * 60;     // 16:00 EST
    
    const currentEstMinutes = getCurrentESTMinutes();
    const effectiveEndMinutes = Math.min(currentEstMinutes, CLOSE_MINUTES);

    if (currentEstMinutes < START_MINUTES) {
        label.innerText = "PRE-MARKET";
        return;
    }

    // Si es LIVE (100%)
    if (val >= 99) {
        label.innerText = "LIVE"; // Indicamos que está listo para ir a Live
        label.style.color = "var(--accent-green)";
        currentHistoryTimeEST = null; // Preparamos el estado para Live
        // IMPORTANTE: Aquí YA NO llamamos a refreshDashboard() automáticamente
        return;
    }

    // Si es HISTORIA
    const range = effectiveEndMinutes - START_MINUTES;
    const pct = val / 100; 
    const targetMinutes = Math.floor(START_MINUTES + (range * pct));
    
    const h = Math.floor(targetMinutes / 60);
    const m = targetMinutes % 60;
    
    // Formato Visual
    const timeStr = h.toString().padStart(2, "0") + ":" + m.toString().padStart(2, "0");
    // Formato API
    const apiTimeStr = h.toString().padStart(2, "0") + m.toString().padStart(2, "0");

    label.innerText = timeStr + " EST";
    label.style.color = "var(--accent-red)";
    
    // Actualizamos la variable global, pero NO refrescamos
    currentHistoryTimeEST = apiTimeStr;
}

// 2. Nueva función para el botón que ejecutará la carga
// --- En script.js ---

function loadHistoryNow() {
    const btn = document.getElementById("btn-history-load");
    
    // Guardamos texto original
    const originalText = "GO"; 
    btn.innerText = "⌛";
    btn.disabled = true; // Evitar doble click

    refreshDashboard()
        .then(() => {
            // Si todo va bien
            btn.innerText = originalText;
            btn.disabled = false;
        })
        .catch((error) => {
            // SI HAY ERROR (Aquí atrapamos el "cuelgue")
            console.error("Load failed:", error);
            btn.innerText = "❌"; // Aviso visual de error
            setTimeout(() => {
                btn.innerText = originalText;
                btn.disabled = false;
            }, 2000);
        });
}

function goLive() {
    const slider = document.getElementById("history-slider");
    
    // 1. Mover visualmente el slider al final
    slider.value = 100; 
    
    // 2. Actualizar el texto y poner la variable interna en modo LIVE (null)
    scrubHistory(100);  

    // 3. ¡LO IMPORTANTE! Forzar la llamada al servidor inmediatamente
    // (Esto es lo que faltaba)
    console.log("Switching to LIVE mode...");
    refreshDashboard();
}
// --- MODIFIED DATA FETCHING ---

async function fetchChartData(ticker, exp) {
  try {
    const ts = new Date().getTime();
    let url = "";

    // CHECK MODE: LIVE OR HISTORY?
    if (currentHistoryTimeEST === null) {
        // Live Mode
        url = `/get_latest?ticker=${ticker}&exp=${exp}&_=${ts}`;
    } else {
        // History Mode
        url = `/get_history?ticker=${ticker}&exp=${exp}&time=${currentHistoryTimeEST}&_=${ts}`;
    }

    const response = await fetch(url);
    if (!response.ok) {
        // If history not found, silently fail or return null
        // console.warn("Data not available for this time");
        return null; 
    }
    
    const data = await response.json();
    if (!data.ticker || data.ticker === "undefined") data.ticker = ticker;
    
    // Visual Indicator: If history, dim the charts slightly or show an icon?
    // For now, the red time label is enough.
    
    return data;
  } catch (e) {
    console.error(e);
    return null;
  }
}

// ... (Rest of code: renderAllCharts, etc. remains same) ...

// --- NEW FEATURES LOGIC ---

// 1. ZEN MODE
function toggleZenMode() {
  document.body.classList.toggle("zen-active");
  setTimeout(() => {
    const panels = document.querySelectorAll(".chart-panel");
    panels.forEach((panel) => alignChartToSpot(panel));
  }, 200);
}

// 2. PALETTES
function changePalette(theme) {
  document.body.classList.remove("palette-alt");
  if (theme !== "default") document.body.classList.add(theme);
}

// 3. SNAPSHOT
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

// --- TABS ---
function renderTabs() {
  const container = document.getElementById("tab-container");
  const addBtn = container.querySelector(".new-tab-btn");
  const existingTabs = container.querySelectorAll(".tab");
  existingTabs.forEach((t) => t.remove());

  tabs.forEach((tab, index) => {
    const tabEl = document.createElement("div");
    tabEl.className = `tab ${tab.id === currentTabId ? "active" : ""}`;
    
    // Habilitar Drag and Drop
    tabEl.draggable = true;
    tabEl.dataset.index = index;

    // Eventos de click y doble click existentes
    tabEl.onclick = (e) => {
      if (!e.target.classList.contains("tab-close")) switchTab(tab.id);
    };
    tabEl.ondblclick = () => renameTab(tab.id);
    
    // --- NUEVOS EVENTOS DE ARRASTRE ---
    tabEl.addEventListener('dragstart', handleTabDragStart);
    tabEl.addEventListener('dragover', handleTabDragOver);
    tabEl.addEventListener('drop', handleTabDrop);
    tabEl.addEventListener('dragenter', (e) => e.preventDefault());

    tabEl.innerHTML = `<span>${tab.name}</span>`;

    if (tabs.length > 1) {
      const closeBtn = document.createElement("span");
      closeBtn.className = "tab-close";
      closeBtn.innerHTML = "×";
      closeBtn.onclick = (e) => {
        e.stopPropagation();
        closeTab(tab.id);
      };
      tabEl.appendChild(closeBtn);
    }
    container.insertBefore(tabEl, addBtn);
  });
}

function switchTab(id) {
  if (currentTabId === id) return;
  currentTabId = id;
  renderTabs();
  renderAllCharts();
}

function addNewTab() {
  const newId = tabCounter++;
  tabs.push({ id: newId, name: `Page ${tabs.length + 1}`, charts: [] });
  switchTab(newId);
}

function closeTab(id) {
  if (tabs.length <= 1) return;
  const index = tabs.findIndex((t) => t.id === id);
  if (index === -1) return;
  tabs.splice(index, 1);
  if (id === currentTabId) {
    const nextTab = tabs[index - 1] || tabs[0];
    currentTabId = nextTab.id;
  }
  renderTabs();
  renderAllCharts();
}

function renameTab(id) {
  const tab = tabs.find((t) => t.id === id);
  if (!tab) return;
  const newName = prompt("Rename:", tab.name);
  if (newName && newName.trim() !== "") {
    tab.name = newName.trim();
    renderTabs();
  }
}

function getCurrentCharts() {
  const tab = tabs.find((t) => t.id === currentTabId);
  return tab ? tab.charts : [];
}

// --- DRAG & DROP ---
function handleDragStart(e) {
  e.dataTransfer.effectAllowed = "move";
  this.classList.add("dragging");
}

function handleDragEnd(e) {
    this.classList.remove("dragging");
    
    // Si estamos en una ventana independiente, no intentamos hacer lógica de "sacar fuera"
    const isDetached = document.body.classList.contains('detached-mode') || 
                       document.body.classList.contains('detached-layout-mode');

    if (!isDetached) {
        // Lógica original de sacar ventana fuera (solo para la ventana principal)
        const mouseX = e.screenX;
        const mouseY = e.screenY;
        const margin = 50; 
        if (mouseX < window.screenX - margin || mouseX > (window.screenX + window.outerWidth) + margin) {
            const index = parseInt(this.dataset.index);
            const tab = tabs.find((t) => t.id === currentTabId);
            if (tab && tab.charts[index]) openDetachedWindow(index);
            return;
        }
    }

    // --- REORDENAMIENTO SEGURO ---
    const container = document.getElementById("charts-wrapper");
    const panels = container.querySelectorAll(".chart-panel");
    
    // Si es una ventana de Layout Detached, necesitamos reconstruir la lista local
    if (document.body.classList.contains('detached-layout-mode')) {
        // En el modo detached_layout, no usamos la variable global 'tabs' de la misma forma.
        // Simplemente dejamos que el DOM se mantenga como está tras el drop.
        // Opcional: podrías actualizar un array local si quisieras que el auto-refresh respete el nuevo orden.
        console.log("Reordenado en vista local");
        return; 
    }

    // Lógica normal para la App principal
    const tab = tabs.find((t) => t.id === currentTabId);
    if (!tab) return;
    const newChartOrder = [];
    panels.forEach((panel) => {
        const originalIndex = parseInt(panel.dataset.index);
        if (!isNaN(originalIndex) && tab.charts[originalIndex])
            newChartOrder.push(tab.charts[originalIndex]);
    });
    tab.charts = newChartOrder;
    renderAllCharts();
}

// Volvemos a usar 'x' (Horizontal)
function getDragAfterElement(container, x) {
  const draggableElements = [
    ...container.querySelectorAll(".chart-panel:not(.dragging)"),
  ];

  return draggableElements.reduce(
    (closest, child) => {
      const box = child.getBoundingClientRect();
      // Calculamos distancia horizontal (Eje X)
      const offset = x - box.left - box.width / 2;
      
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    },
    { offset: Number.NEGATIVE_INFINITY }
  ).element;
}

// Actualizamos el evento para pasar clientX
function handleWrapperDragOver(e) {
  e.preventDefault();
  const container = document.getElementById("charts-wrapper");
  // Pasamos e.clientX (Horizontal)
  const afterElement = getDragAfterElement(container, e.clientX);
  const draggable = document.querySelector(".dragging");
  if (draggable) {
    if (afterElement == null) container.appendChild(draggable);
    else container.insertBefore(draggable, afterElement);
  }
}

// --- DATA ---
function getParams() {
  const t = document.getElementById("ticker");
  const e = document.getElementById("exp");
  const g = document.getElementById("greek-select");
  return {
    ticker: t.value.toUpperCase(),
    exp: e.value.toLowerCase(),
    greek: g.value,
  };
}

async function handleLoadData() {
  const currentTab = tabs.find((t) => t.id === currentTabId);
  if (!currentTab) return;
  currentTab.charts = [];
  const params = getParams();
  const data = await fetchChartData(params.ticker, params.exp);
  if (data) {
    addChartToCurrent(data, params);
    renderAllCharts();
  }
}

async function handleAddChart() {
  const params = getParams();
  const btn = document.querySelector(".btn-add");
  btn.innerText = "...";
  const data = await fetchChartData(params.ticker, params.exp);
  btn.innerText = "+";
  if (data) {
    addChartToCurrent(data, params);
    renderAllCharts();
  }
}

function addChartToCurrent(data, params) {
  const tab = tabs.find((t) => t.id === currentTabId);
  if (tab)
    tab.charts.push({
      data: data,
      greek: params.greek,
      inputTicker: params.ticker,
      inputExp: params.exp,
    });
}

function removeChart(index) {
  const tab = tabs.find((t) => t.id === currentTabId);
  if (tab) {
    tab.charts.splice(index, 1);
    renderAllCharts();
  }
}

// --- RENDERING ---
function renderAllCharts() {
  const wrapper = document.getElementById("charts-wrapper");
  wrapper.scrollLeft = 0;
  const activeCharts = getCurrentCharts();
  wrapper.innerHTML = "";
  if (activeCharts.length === 0) {
    wrapper.innerHTML =
      '<div style="width:100%; text-align:center; padding-top:100px; color:var(--text-dim);">Empty Layout</div>';
    return;
  }
  activeCharts.forEach((chartObj, index) => {
    const panel = createChartPanel(chartObj, index);
    wrapper.appendChild(panel);
    setTimeout(() => alignChartToSpot(panel), 50);
  });
}

function generateRegimeHTML(ticker, greek, spot, netValue, spotStrikeValue) {
  let regimeText = "",
    behaviorText = "",
    biasText = "",
    regimeColorVar = "--text-dim";
  const isLocalPos = spotStrikeValue >= 0;
  const isNetPos = netValue >= 0;

  const isAligned = isLocalPos === isNetPos;
  const alignmentText = isAligned ? "CONVERGENT" : "DIVERGENT";
  const alignmentColor = isAligned
    ? "var(--accent-green)"
    : "var(--accent-red)";

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
    if (isLocalPos) {
      regimeText = "POS VANNA";
      behaviorText = "IV Drop = Buying | IV Spike = Selling.";
      regimeColorVar = "--pos-high";
    } else {
      regimeText = "NEG VANNA";
      behaviorText = "IV Drop = Selling | IV Spike = Buying.";
      regimeColorVar = "--neg-high";
    }
    biasText = "Vol Impact";
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
                            <div style="font-size: 13px; font-weight: 700; color: white;">${spot.toFixed(
                              2
                            )}</div>
                        </div>

                        <div style="text-align: right;">
                            <div style="font-size: 9px; color: var(--text-dim); text-transform: uppercase;">Net Exposure</div>
                            <div style="font-size: 13px; font-weight: 700; color: var(${
                              isNetPos ? "--pos-high" : "--neg-high"
                            });">${formatK(netValue)}</div>
                        </div>

                        <div>
                            <div style="font-size: 9px; color: var(--text-dim); text-transform: uppercase;">Local Strike Exp</div>
                            <div style="font-size: 13px; font-weight: 700; color: var(${
                              isLocalPos ? "--pos-high" : "--neg-high"
                            });">${formatK(spotStrikeValue)}</div>
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

function createChartPanel(chartObj, index) {
  const { data: globalData, greek } = chartObj;
  if (tabs[currentTabId] && tabs[currentTabId].charts[index]) {
      tabs[currentTabId].charts[index].data = globalData; // <--- AÑADIR ESTA LÍNEA
  }
  const raw = globalData.option_data;
  const colStrike = raw.columns.indexOf("strike_price");
  const colMetric = raw.columns.findIndex(
    (c) => c.trim() === `total_${greek}` || c.trim() === greek
  );

  if (colMetric === -1) return document.createElement("div");

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

  let maxPos = -Infinity,
    maxPosStrike = 0;
  let maxNeg = Infinity,
    maxNegStrike = 0;
  let closest = null,
    minDiff = Infinity,
    spotVal = 0;

  rows.forEach((d) => {
    if (d.value > maxPos) {
      maxPos = d.value;
      maxPosStrike = d.strike;
    }
    if (d.value < maxNeg) {
      maxNeg = d.value;
      maxNegStrike = d.strike;
    }
    const diff = Math.abs(d.strike - spot);
    if (diff < minDiff) {
      minDiff = diff;
      closest = d.strike;
      spotVal = d.value;
    }
  });

  const scalePos = Math.max(Math.abs(maxPos), 1);
  const scaleNeg = Math.max(Math.abs(maxNeg), 1);

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
            <div>Spot: <span class="stat-val" style="color:white">${spot.toFixed(
              2
            )}</span></div>
            <div>MaxC: <span class="stat-val val-pos">${maxPosStrike}</span></div>
            <div>MaxP: <span class="stat-val val-neg">${maxNegStrike}</span></div>
        `;

  header.appendChild(topRow);
  header.appendChild(stats);
  header.innerHTML += generateRegimeHTML(
    globalData.ticker,
    greek,
    spot,
    net,
    spotVal
  );
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
  // Heatmap Scroll
  const scroll = document.createElement("div");
  scroll.className = "heatmap-scroll";

  rows.forEach((row) => {
    const div = document.createElement("div");
    div.className = "grid-row";
    if (row.strike === closest) div.classList.add("spot-row");

    const val = row.value;
    const isPos = val >= 0;
    const intensity = isPos
      ? Math.abs(val) / scalePos
      : Math.abs(val) / scaleNeg;

    // --- LÓGICA DE COLOR (HEATMAP) ---
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
    else if (row.strike === maxPosStrike)
      labelStyle = "color: var(--pos-high); font-weight: 700;";
    else if (row.strike === maxNegStrike)
      labelStyle = "color: var(--neg-high); font-weight: 700;";

    div.innerHTML = `
                <div class="y-axis-label" style="${labelStyle}">${
      row.strike
    }</div>
                <div class="bar-area">
                    <div class="bar-fill" style="background:${bg}"></div>
                    <span class="value-text" style="color:${txtColor}; font-weight:${weight}">${formatK(
      val
    )}</span>
                    ${
                      row.strike === maxPosStrike
                        ? '<div class="ref-line ref-max-pos"></div>'
                        : ""
                    }
                    ${
                      row.strike === maxNegStrike
                        ? '<div class="ref-line ref-max-neg"></div>'
                        : ""
                    }
                </div>
                <div class="y-axis-label"></div>
            `;
    scroll.appendChild(div);
  });

  panel.appendChild(scroll);
  return panel;
}

function alignChartToSpot(panel) {
  const spot = panel.querySelector(".spot-row");
  const scrollContainer = panel.querySelector(".heatmap-scroll");

  if (spot && scrollContainer) {
    // 1. Obtenemos la posición del spot respecto al panel
    const spotTop = spot.offsetTop;
    // 2. Obtenemos donde empieza la lista (para restar la altura del header)
    const containerTop = scrollContainer.offsetTop;

    // 3. Posición real dentro de la lista scrolleable
    const positionInList = spotTop - containerTop;

    const containerHeight = scrollContainer.clientHeight;
    const rowHeight = spot.clientHeight;

    // 4. Aplicamos el scroll para centrar
    scrollContainer.scrollTop =
      positionInList - containerHeight / 2 + rowHeight / 2;
  }
}

function formatK(n) {
  return Math.abs(n) < 1 ? "0" : n.toFixed(0) + "k";
}

// --- SYSTEM ---
function toggleAutoRefresh() {
  const chk = document.getElementById("auto-refresh");
  const ind = document.getElementById("timer-indicator");
  if (chk.checked) {
    ind.style.display = "block";
    if (!refreshIntervalId)
      refreshIntervalId = setInterval(refreshDashboard, 30000);
  } else {
    ind.style.display = "none";
    if (refreshIntervalId) {
      clearInterval(refreshIntervalId);
      refreshIntervalId = null;
    }
  }
}

async function refreshDashboard() {
    // 1. Recolectar qué necesitamos
    const currentTab = tabs.find(t => t.id === currentTabId);
    if (!currentTab || currentTab.charts.length === 0) return;

    const requestList = currentTab.charts.map(c => ({
        ticker: c.inputTicker,
        exp: c.inputExp
    }));

    // Eliminar duplicados para no pedir lo mismo 2 veces
    const uniqueRequests = [...new Set(requestList.map(JSON.stringify))].map(JSON.parse);

    try {
        // 2. Hacer UNA sola petición POST
        const response = await fetch('/get_batch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(uniqueRequests)
        });
        
        const batchData = await response.json(); // Devuelve objeto { "SPX_0dte": {...}, "QQQ_weekly": {...} }

        // 3. Distribuir datos a los gráficos
        currentTab.charts.forEach(chart => {
            const key = `${chart.inputTicker}_${chart.inputExp}`; // Asegúrate de que coincida con la clave del servidor
            // Nota: En servidor usé Upper_Lower (SPX_0dte), ajusta aquí si es necesario
            const dataKey = `${chart.inputTicker.toUpperCase()}_${chart.inputExp.toLowerCase()}`;
            
            if (batchData[dataKey]) {
                chart.data = batchData[dataKey];
            }
        });

		updateMarketSpots();
        updateNYTime();
        renderAllCharts(); // Renderizar todo de golpe
        
    } catch (e) {
        console.error("Batch update failed", e);
    }
}


// --- SUSTITUIR EN SCRIPT.JS ---

// --- NUEVA FUNCIÓN HELPER ---
async function fetchWithRetry(ticker, exp, maxRetries = 10, delay = 500) {
    for (let i = 0; i < maxRetries; i++) {
        // Intentamos pedir los datos
        const data = await fetchChartData(ticker, exp);
        
        // Si hay datos válidos, los devolvemos inmediatamente
        if (data && data.option_data && data.option_data.data && data.option_data.data.length > 0) {
            return data;
        }
        
        // Si llegamos aquí, falló. Esperamos antes de reintentar.
        console.log(`[Retry ${i+1}/${maxRetries}] Waiting for data: ${ticker} ${exp}...`);
        await new Promise(resolve => setTimeout(resolve, delay));
    }
    return null; // Si tras 10 intentos sigue fallando, nos rendimos
}

function saveAllLayouts() {
  try {
      const themeSelect = document.querySelector("select[onchange*='changePalette']");
      const currentTheme = themeSelect ? themeSelect.value : 'default';
      
      // Fecha de HOY para comparar
      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, '0');
      const dd = String(now.getDate()).padStart(2, '0');
      const todayStr = `${yyyy}${mm}${dd}`;

      const cleanTabs = tabs.map((t) => ({
        id: t.id,
        name: t.name,
        charts: t.charts.filter(c => c.inputTicker).map((c) => {
          
          // Lógica de fecha inteligente
          let dateToSave = null;
          if (c.type === 'fourier' || c.type === 'ib') {
              // Si la fecha del gráfico es HOY, guardamos "LIVE" para que mañana se actualice.
              // Si es una fecha antigua, la guardamos tal cual.
              if (c.dateStr === todayStr) {
                  dateToSave = "LIVE";
              } else {
                  dateToSave = c.dateStr;
              }
          }

          return {
            ticker: c.inputTicker,
            exp: c.inputExp,
            greek: c.greek,
            type: c.type,
            savedDate: dateToSave // <--- CAMPO NUEVO
          };
        }),
      }));

      const data = {
        autoRefresh: document.getElementById("auto-refresh").checked,
        theme: currentTheme,
        tabs: cleanTabs,
      };

      const jsonStr = JSON.stringify(data);
      localStorage.setItem("gex_dashboard_tabs_v1", jsonStr);

      const totalCharts = cleanTabs.reduce((acc, t) => acc + t.charts.length, 0);
      console.log(`[SAVE] Saved ${totalCharts} charts.`);
      
      const btn = document.querySelector('button[onclick="saveAllLayouts()"]');
      if(btn) {
          const old = btn.innerText;
          btn.innerText = "SAVED ✓";
          setTimeout(() => (btn.innerText = old), 1000);
      }
      
  } catch (e) {
      console.error("Save failed:", e);
      alert("Error saving layout. Check console.");
  }
}

async function loadSavedLayouts() {
  const s = localStorage.getItem("gex_dashboard_tabs_v1");
  if (!s) return false;
  
  const wrapper = document.getElementById("charts-wrapper");
  wrapper.innerHTML = '<div style="color:var(--accent-blue); margin:auto; text-align:center; font-family:monospace;">RESTORING LAYOUT...</div>';

  try {
    const obj = JSON.parse(s);

    if (obj.autoRefresh !== undefined) {
        const chk = document.getElementById("auto-refresh");
        if(chk) chk.checked = obj.autoRefresh;
    }

    if (obj.theme) {
        const themeSelect = document.querySelector("select[onchange*='changePalette']");
        if (themeSelect) {
            themeSelect.value = obj.theme;
            changePalette(obj.theme);
        }
    }
    
    if (obj.tabs && Array.isArray(obj.tabs)) {
      tabs = obj.tabs.map((t) => ({ id: t.id, name: t.name, charts: [] }));
      
      if (tabs.length > 0) {
          tabCounter = Math.max(...tabs.map((t) => t.id)) + 1;
          currentTabId = tabs[0].id;
      } else {
          tabs = [{ id: 0, name: "Default", charts: [] }];
          currentTabId = 0;
      }

      const tabPromises = obj.tabs.map(async (tData) => {
        if (!tData.charts) return;

        const chartPromises = tData.charts.map(async (cConf) => {
          if (!cConf.ticker) return null;

          if (!cConf.type) {
              if (cConf.exp === 'fourier') cConf.type = 'fourier';
              else if (cConf.exp === 'ib') cConf.type = 'ib';
              else cConf.type = 'heatmap';
          }

          let d = null;
          let loadedDateStr = null; // Para guardar qué fecha cargamos

          // --- GESTIÓN DE FECHAS ---
          if (cConf.type === 'fourier' || cConf.type === 'ib') {
              // Calcular hoy local
              const now = new Date();
              const yyyy = now.getFullYear();
              const mm = String(now.getMonth() + 1).padStart(2, '0');
              const dd = String(now.getDate()).padStart(2, '0');
              const todayStr = `${yyyy}${mm}${dd}`;

              // Decidir fecha objetivo
              if (cConf.savedDate && cConf.savedDate !== "LIVE") {
                  loadedDateStr = cConf.savedDate; // Fecha histórica fija
              } else {
                  loadedDateStr = todayStr; // "LIVE" o por defecto -> Hoy
              }

              // Cargar datos
              if (cConf.type === 'fourier') {
                  d = await fetchFourierData(cConf.ticker, loadedDateStr);
              } else {
                  d = await fetchIBData(cConf.ticker, loadedDateStr);
              }
          } 
          else {
              // Heatmaps normales
              d = await fetchWithRetry(cConf.ticker, cConf.exp, 1, 0);
          }
          
          if (!d) {
              console.warn(`[Layout] Skipped ${cConf.ticker} (${cConf.type}). No data.`);
               d = {
                  ticker: cConf.ticker,
                  spot_price: 0,
                  prev_close_price: 0,
                  option_data: { columns: ["strike_price"], data: [] },
                  analysis: { ib_high:0, ib_low:0, ib_range:0, current_price:0 }, 
                  series: [] 
              };
          }

          return {
              data: d,
              greek: cConf.greek,
              inputTicker: cConf.ticker,
              inputExp: cConf.exp,
              type: cConf.type,
              dateStr: loadedDateStr // <--- IMPORTANTE: Restauramos la fecha en el objeto vivo
          };
        });

        const results = await Promise.all(chartPromises);
        const target = tabs.find((x) => x.id === tData.id);
        if (target) {
            target.charts = results.filter(r => r !== null);
        }
      });

      await Promise.all(tabPromises);
      return true;
    }
  } catch (e) {
    console.error("Error loading layouts:", e);
    wrapper.innerHTML = '<div style="color:red; margin:auto;">Error loading layout.</div>';
  }
  return false;
}

async function updateMarketSpots() {
  const spx = await fetchChartData("SPX", "0dte");
  if (spx && spx.spot_price) realSpotSPX = spx.spot_price; // Save for simulator
  updateEl("spot-spx", "change-spx", spx);

  const vix = await fetchChartData("VIX", "weekly");
  updateEl("spot-vix", "change-vix", vix);
}

function updateEl(idP, idC, d) {
  if (d && d.spot_price) {
    const p = d.spot_price;
    const prev = d.prev_close_price;
    document.getElementById(idP).innerText = p.toFixed(2);
    if (prev) {
      const diff = p - prev;
      const pct = (diff / prev) * 100;
      const el = document.getElementById(idC);
      el.innerText = `(${diff >= 0 ? "+" : ""}${diff.toFixed(2)}, ${pct.toFixed(
        2
      )}%)`;
      el.className = `market-change ${
        diff > 0.01 ? "change-pos" : diff < -0.01 ? "change-neg" : "change-flat"
      }`;
    }
  }
}

function updateNYTime() {
    const nyEl = document.getElementById("ny-time");
    const dataEl = document.getElementById("last-data-time");

    // 1. Reloj NY (Sin segundos)
    if (nyEl) {
        nyEl.innerText = new Date().toLocaleString("en-US", {
            timeZone: "America/New_York",
            hour: "2-digit", minute: "2-digit", hour12: false
        });
    }

    // 2. Buscar hora en la pestaña actual
    const currentTab = tabs.find(t => t.id === currentTabId);
    if (!currentTab || !currentTab.charts || currentTab.charts.length === 0) {
        if (dataEl) dataEl.innerText = "--:--";
        return;
    }

    let latestVal = -1;
    let latestStr = "--:--";

    currentTab.charts.forEach(chart => {
        let timeStr = null;
        
        // Prioridad 1: Campo timestamp (Tablas Heatmap)
        if (chart.data && chart.data.timestamp) {
            timeStr = chart.data.timestamp;
        } 
        // Prioridad 2: Series de tiempo (Fourier / IB)
        else if (chart.data && chart.data.series && chart.data.series.length > 0) {
            const last = chart.data.series[chart.data.series.length - 1];
            timeStr = last.time || (last.datetime ? last.datetime.split(' ')[1] : null);
        }

        if (timeStr) {
            const clean = timeStr.trim().substring(0, 5); // Cortar a HH:MM
            const val = parseInt(clean.replace(':', ''));
            if (!isNaN(val) && val > latestVal) {
                latestVal = val;
                latestStr = clean;
            }
        }
    });

    if (dataEl) dataEl.innerText = latestStr;
}
function updateExpSuggestions() {
  const t = document.getElementById("ticker").value.toUpperCase();
  const l = document.getElementById("exp-list");
  l.innerHTML = "";
  const opts =
    t === "SPX"
      ? ["0dte", "1dte", "weekly"]
      : t === "SPY" || t === "QQQ"
      ? ["0dte", "weekly"]
      : ["weekly"];
  opts.forEach((o) => {
    const el = document.createElement("option");
    el.value = o;
    l.appendChild(el);
  });
}
document.addEventListener('keydown', function(e) {
    if (e.key === "Escape" || e.keyCode === 27) {
        if (document.body.classList.contains("zen-active")) {
            toggleZenMode();
        }
    }
});
/**
 * Busca todos los paneles de gráficos activos y los vuelve a centrar 
 * en el precio Spot actual.
 */
function realignAllCharts() {
  const panels = document.querySelectorAll(".chart-panel");
  panels.forEach((panel) => {
    alignChartToSpot(panel);
  });
}

// En script.js - Reemplazar la función existente

function openDetachedWindow(index) {
  // 1. Buscamos el gráfico en los datos actuales
  const tab = tabs.find((t) => t.id === currentTabId);
  if (!tab || !tab.charts[index]) {
      console.error("Chart not found for index:", index);
      return;
  }

  const chart = tab.charts[index];
  
  // 2. Detectamos el tema actual
  const currentTheme = document.body.classList.contains("palette-alt") ? "palette-alt" : "default";

  // 3. Construimos los parámetros base
  const params = new URLSearchParams({
    mode: 'detached',
    ticker: chart.inputTicker,
    theme: currentTheme
  });

  // 4. Lógica específica según el TIPO de gráfico
  if (chart.type === 'fourier' || chart.type === 'ib') {
      // Para Fourier/IB pasamos el tipo y la fecha específica
      params.set('type', chart.type);
      params.set('date', chart.dateStr || "LIVE"); 
  } else {
      // Para Heatmaps normales
      params.set('exp', chart.inputExp || "0dte");
      params.set('greek', chart.greek || "gamma");
  }

  // 5. Configuración de la ventana
  const w = 600; // Un poco más ancho para gráficos de líneas
  const h = 500;
  const left = (screen.width / 2) - (w / 2);
  const top = (screen.height / 2) - (h / 2);

  const url = `${window.location.pathname}?${params.toString()}`;

  window.open(
    url,
    `GEX_${chart.type || 'chart'}_${chart.inputTicker}_${Date.now()}`, 
    `width=${w},height=${h},top=${top},left=${left},resizable=yes,scrollbars=yes,status=no`
  );
}

function popoutCurrentLayout() {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (!tab || tab.charts.length === 0) {
        alert("Empty layout cannot be popped out.");
        return;
    }

    // 1. Extraemos la configuración COMPLETA (incluyendo tipo y fecha)
    const layoutConfig = tab.charts.map(c => ({
        ticker: c.inputTicker,
        exp: c.inputExp,
        greek: c.greek,
        type: c.type || 'heatmap', // Guardamos el tipo (ib, fourier, heatmap)
        dateStr: c.dateStr || 'LIVE' // Guardamos la fecha si existe
    }));

    // 2. Generamos ID única
    const transferId = 'layout_' + Date.now();
    
    // 3. Guardamos en LocalStorage
    localStorage.setItem(transferId, JSON.stringify(layoutConfig));

    // 4. Preparamos parámetros
    const currentTheme = document.body.classList.contains("palette-alt") ? "palette-alt" : "default";
    const params = new URLSearchParams({
        mode: 'detached_layout',
        transferId: transferId,
        theme: currentTheme
    });

    // 5. Abrir ventana ancha
    const url = `${window.location.pathname}?${params.toString()}`;
    window.open(url, `GEX_LAYOUT_${transferId}`, "width=1200,height=800,resizable=yes,scrollbars=yes");
}

// --- FOURIER CHART LOGIC ---

// 1. Inicializar fecha al cargar la página
document.addEventListener("DOMContentLoaded", () => {
    const today = new Date();
    // Formato YYYY-MM-DD para el input type="date"
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const dateInput = document.getElementById("fourier-date");
    if(dateInput) dateInput.value = `${yyyy}-${mm}-${dd}`;
});

// Busca esta función y reemplázala por completo
async function handleLoadFourier() {
    const ticker = document.getElementById("ticker").value.toUpperCase();
    const dateVal = document.getElementById("fourier-date").value; // YYYY-MM-DD
    
    // Convertir YYYY-MM-DD a YYYYMMDD para la API
    const dateStr = dateVal.replace(/-/g, "");
    
    const btn = document.querySelector('button[onclick="handleLoadFourier()"]');
    const originalText = btn.innerText;
    btn.innerText = "⏳";

    // CORRECCIÓN AQUÍ: Pasamos 'ticker' como primer argumento
    const data = await fetchFourierData(ticker, dateStr);
    
    btn.innerText = originalText;

    if (data) {
        addFourierChartToCurrent(data, ticker, dateStr);
        renderAllCharts();
    } else {
        alert(`No Fourier data found for ${ticker} on ${dateVal}.\nEnsure the server has generated: fourier_data_${ticker}_${dateStr}.json`);
    }
}

// Busca esta función y reemplázala por completo
async function fetchFourierData(ticker, dateStr) {
    try {
        const ts = new Date().getTime();
        // Construimos la URL correcta coincidiendo con el Python: fourier_data_{TICKER}_{YYYYMMDD}.json
        const url = `/fourier/fourier_data_${ticker}_${dateStr}.json?_=${ts}`;
        
        const response = await fetch(url);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        console.error("Fourier Fetch Error:", e);
        return null;
    }
}

function addFourierChartToCurrent(data, ticker, dateStr) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (tab) {
        tab.charts.push({
            type: 'fourier', // Marcamos el tipo para diferenciarlo de los Heatmaps
            data: data,
            inputTicker: ticker,
            inputExp: 'fourier', // Identificador especial
            dateStr: dateStr
        });
    }
}

// MODIFICAR LA FUNCIÓN createChartPanel PARA SOPORTAR FOURIER
// (Reemplaza o modifica tu función existente createChartPanel con esta lógica)

const originalCreateChartPanel = createChartPanel; // Guardamos referencia si quieres mantener la vieja lógica separada

// Modificar el despachador de paneles
createChartPanel = function(chartObj, index) {
    if (chartObj.type === 'fourier') return createFourierPanel(chartObj, index);
    if (chartObj.type === 'ib') return createIBPanel(chartObj, index); // <--- ESTO
    return originalCreateChartPanel(chartObj, index);
};

// En script.js

function createIBPanel(chartObj, index) {
    const { data, inputTicker, dateStr } = chartObj;
    
    const panel = document.createElement("div");
    panel.className = "chart-panel";
    panel.draggable = true;
    panel.dataset.index = index;
    panel.addEventListener("dragstart", handleDragStart);
    panel.addEventListener("dragend", handleDragEnd);

    // Header IB Estilizado CON BOTÓN POPOUT
    const header = document.createElement("div");
    header.className = "chart-header";
    header.innerHTML = `
        <div class="chart-title-row">
            <div>
                <span class="chart-title" style="color:#FFD700;">${inputTicker} IB & LEVELS</span>
                <span class="chart-subtitle">${dateStr}</span>
            </div>
            <div>
                <button class="btn-popout" onclick="openDetachedWindow(${index})" title="Pop out">⇱</button>
                <button class="btn-close" onclick="removeChart(${index})">×</button>
            </div>
        </div>
        <div class="chart-stats" style="border-left: 3px solid #FFD700; display:flex; gap:10px;">
            <span style="font-size:10px;">Range: <strong style="color:white">${data.analysis.ib_range.toFixed(2)}</strong></span>
            <span style="font-size:10px;">High: ${data.analysis.ib_high.toFixed(2)}</span>
            <span style="font-size:10px;">Low: ${data.analysis.ib_low.toFixed(2)}</span>
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

    // Pequeño delay para asegurar que el DOM está listo para Chart.js
    setTimeout(() => renderIBChartJs(canvas, data), 0);

    return panel;
}

function createFourierPanel(chartObj, index) {
    const { data, inputTicker, dateStr } = chartObj;
    
    const panel = document.createElement("div");
    panel.className = "chart-panel";
    panel.draggable = true;
    panel.dataset.index = index;
    panel.addEventListener("dragstart", handleDragStart);
    panel.addEventListener("dragend", handleDragEnd);

    // Header CON BOTÓN POPOUT
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

    setTimeout(() => renderChartJs(canvas, data), 0);

    return panel;
}


function renderChartJs(canvas, jsonData) {
    // --- 1. FILTRO HORARIO (Igual que IB: 03:00 - 16:15) ---
    const filteredData = jsonData.filter(d => {
        const timePart = d.datetime.split(' ')[1]; 
        return timePart >= "03:00:00" && timePart <= "16:15:00";
    });

    if (filteredData.length === 0) return;

    // --- 2. PREPARAR DATOS ---
    const labels = filteredData.map(d => {
        const datePart = d.datetime.split(' ')[1]; 
        return datePart ? datePart.substring(0, 5) : d.datetime;
    });
    const spotData = filteredData.map(d => d.spot_fft);
    const ivData = filteredData.map(d => d.iv_fft);

    // --- 3. LÓGICA PARA DETECTAR GIROS (DOTS) ---
    // Retorna arrays de estilos para cada punto del gráfico
    const getTurnStyles = (dataArr) => {
        const radii = [];
        const colors = [];
        const borders = [];

        for (let i = 0; i < dataArr.length; i++) {
            // Ignoramos el primer y último punto porque no tienen vecinos completos
            if (i === 0 || i === dataArr.length - 1) {
                radii.push(0);
                colors.push('transparent');
                borders.push('transparent');
                continue;
            }

            const prev = dataArr[i - 1];
            const curr = dataArr[i];
            const next = dataArr[i + 1];

            // PICO (Va de arriba a abajo) -> ROJO
            if (curr > prev && curr > next) {
                radii.push(4);          // Tamaño del punto
                colors.push('#FF0000'); // Rojo
                borders.push('#FFFFFF'); // Borde blanco para contraste
            }
            // VALLE (Va de abajo a arriba) -> VERDE
            else if (curr < prev && curr < next) {
                radii.push(4);          // Tamaño del punto
                colors.push('#00FF00'); // Verde Lime
                borders.push('#FFFFFF'); // Borde blanco
            }
            // SIN CAMBIO DE DIRECCIÓN -> OCULTO
            else {
                radii.push(0);
                colors.push('transparent');
                borders.push('transparent');
            }
        }
        return { radii, colors, borders };
    };

    // Calculamos estilos para ambas líneas
    const spotStyles = getTurnStyles(spotData);
    const ivStyles = getTurnStyles(ivData);

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Spot Price',
                    data: spotData,
                    borderColor: 'cyan',
                    backgroundColor: 'cyan',
                    borderWidth: 2,
                    yAxisID: 'y',
                    tension: 0.4,
                    // --- ESTILOS DINÁMICOS SPOT ---
                    pointRadius: spotStyles.radii,
                    pointBackgroundColor: spotStyles.colors,
                    pointBorderColor: spotStyles.borders,
                    pointBorderWidth: 1,
                    pointHitRadius: 10 // Facilita el hover aunque el punto sea pequeño
                },
                {
                    label: 'ATM IV',
                    data: ivData,
                    borderColor: 'magenta',
                    backgroundColor: 'magenta',
                    borderWidth: 2,
                    yAxisID: 'y1',
                    tension: 0.4,
                    // --- ESTILOS DINÁMICOS IV ---
                    pointRadius: ivStyles.radii,
                    pointBackgroundColor: ivStyles.colors,
                    pointBorderColor: ivStyles.borders,
                    pointBorderWidth: 1,
                    pointHitRadius: 10
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
                legend: { labels: { color: 'white' } },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false
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
// 4. ACTUALIZAR refreshDashboard PARA RECARGAR FOURIER
// (Modifica tu función refreshDashboard existente o añade esto dentro)

const originalRefreshDashboard = refreshDashboard;

// Busca la parte donde sobreescribes refreshDashboard y actualiza el bucle for
refreshDashboard = async function() {
    // 1. Ejecutar la lógica normal (Heatmaps - Batch Update)
    await originalRefreshDashboard();

    const currentTab = tabs.find(t => t.id === currentTabId);
    if (!currentTab) return;

    // 2. Lógica extra para Fourier y IB
    const specialCharts = currentTab.charts.filter(c => c.type === 'fourier' || c.type === 'ib');
    
    if (specialCharts.length > 0) {
        // Calcular fecha de HOY "YYYYMMDD"
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const todayStr = `${yyyy}${mm}${dd}`;

        let needsRender = false;

        for (let chart of specialCharts) {
            // SOLO recargamos si la fecha del gráfico coincide con HOY
            if (chart.dateStr === todayStr) {
                let newData = null;
                
                if (chart.type === 'fourier') {
                    newData = await fetchFourierData(chart.inputTicker, chart.dateStr);
                } else if (chart.type === 'ib') {
                    newData = await fetchIBData(chart.inputTicker, chart.dateStr);
                }
                
                if (newData) {
                    chart.data = newData;
                    needsRender = true;
                }
            }
        }
        
        // Si hubo cambios, repintamos todo (necesario porque Chart.js usa Canvas)
        if (needsRender) {
            renderAllCharts();
        }
    }
};
// --- LÓGICA EXCLUSIVA IB ---

async function handleLoadIB() {
    const ticker = document.getElementById("ticker").value.toUpperCase();
    const dateVal = document.getElementById("fourier-date").value; 
    const dateStr = dateVal.replace(/-/g, "");
    
    const btn = document.getElementById("btn-ib");
    const originalText = btn.innerText;
    btn.innerText = "⏳";

    const data = await fetchIBData(ticker, dateStr);
    
    btn.innerText = originalText;

    if (data) {
        addIBChartToCurrent(data, ticker, dateStr);
        renderAllCharts();
    } else {
        alert(`No IB Levels data found for ${ticker}.`);
    }
}

async function fetchIBData(ticker, dateStr) {
    try {
        const ts = new Date().getTime();
        const url = `/ib_charts/ib_data_${ticker}_${dateStr}.json?_=${ts}`;
        const response = await fetch(url);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) { return null; }
}

function addIBChartToCurrent(data, ticker, dateStr) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (tab) {
        tab.charts.push({
            type: 'ib',
            data: data,
            inputTicker: ticker,
            inputExp: 'ib',
            dateStr: dateStr
        });
    }
}

// --- FUNCIÓN DE DIBUJADO PARA IB CHART (FALTANTE) ---
function renderIBChartJs(canvas, jsonData) {
    // --- 1. FILTRO HORARIO (08:00 - 16:15) ---
    // Filtramos los datos brutos antes de procesarlos.
    // El formato de 'd.time' es "HH:MM", así que la comparación de texto funciona.
    const rawSeries = jsonData.series || [];
    const series = rawSeries.filter(d => d.time >= "09:20" && d.time <= "16:15");
    
    // Si después de filtrar no queda nada (o no había datos), salimos
    if (series.length === 0) return;

    const labels = series.map(d => d.time); // Eje X
    const priceData = series.map(d => d.price); // Eje Y
    
    // 2. Extraer niveles clave (High, Low, etc)
    const ibHigh = jsonData.analysis.ib_high;
    const ibLow = jsonData.analysis.ib_low;
    const currentPrice = jsonData.analysis.current_price;
    const ibRange = jsonData.analysis.ib_range;

    const datasets = [];

    // --- A. LÍNEA DE PRECIO ---
    datasets.push({
        label: 'Price',
        data: priceData,
        borderColor: '#00F0FF',
        backgroundColor: '#00F0FF',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
        order: 1
    });

    // Helper para líneas horizontales (se adapta automáticamente al nuevo largo de 'labels')
    const makeHLine = (val, color, label, borderDash = [5, 5]) => ({
        label: label,
        data: labels.map(() => val), 
        borderColor: color,
        borderWidth: 1,
        borderDash: borderDash,
        pointRadius: 0,
        fill: false,
        order: 10
    });

    // --- B. LÍNEAS IB ---
    datasets.push(makeHLine(ibHigh, 'rgba(255,255,255,0.7)', 'IB High'));
    datasets.push(makeHLine(ibLow, 'rgba(255,255,255,0.7)', 'IB Low'));

    // --- C. FIBONACCI ---
    const fibColors = ['#FFD700', '#FF8C00', '#FF4500'];
    const ibMid = (ibHigh + ibLow) / 2; // Calculamos el punto medio

    // Determinamos qué extensiones mostrar basándonos en el punto medio
    if (currentPrice >= ibMid) {
        // Si el precio está por encima del Midpoint, mostrar extensiones superiores
        [1.272, 1.618, 2.0].forEach((ext, i) => {
            const val = ibLow + (ibRange * ext);
            datasets.push(makeHLine(val, fibColors[i], `Fib ${ext}`, [2, 2]));
        });
    } else {
        // Si el precio está por debajo del Midpoint, mostrar extensiones inferiores
        [-0.272, -0.618, -1.0].forEach((ext, i) => {
            const val = ibLow + (ibRange * ext);
            datasets.push(makeHLine(val, fibColors[i], `Fib ${ext}`, [2, 2]));
        });
    }

    // --- D. GREEKS ---
    const greekColors = {
        'max_gamma': '#00FF00', 'min_gamma': '#FF0000', 
        'max_dgex': '#00FFFF', 'min_dgex': '#FFA500',
        'min_vanna': '#9400D3'
    };
    
    if (jsonData.levels) {
        Object.keys(jsonData.levels).forEach(k => {
            if (greekColors[k]) {
                const label = k.replace('_', ' ').toUpperCase();
                datasets.push(makeHLine(jsonData.levels[k], greekColors[k], label, [10, 5]));
            }
        });
    }

    // 3. Renderizar
    new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'nearest',
                intersect: true,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
		    displayColors: false,
                    callbacks: {
			title: function(context) {
				return context[0].dataset.label;
			},
                        label: function(context) {
                    		return `Price: ${context.parsed.y.toFixed(2)}`;
                	}
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#666', maxTicksLimit: 10 },
                    grid: { color: '#222' }
                },
                y: {
                    position: 'right',
                    ticks: { color: '#888' },
                    grid: { color: '#222' }
                }
            }
        }
    });
}

window.addEventListener('resize', () => {
    // Si hay gráficos de Chart.js, los forzamos a actualizar su tamaño
    const charts = document.querySelectorAll('canvas');
    charts.forEach(canvas => {
        const chartInstance = Chart.getChart(canvas);
        if (chartInstance) {
            chartInstance.resize();
        }
    });
    
    // Si es modo heatmap, realineamos al spot
    if (document.body.classList.contains('detached-mode')) {
        const panel = document.querySelector('.chart-panel');
        if (panel) alignChartToSpot(panel);
    }
});

let draggedTabIndex = null;

function handleTabDragStart(e) {
  draggedTabIndex = parseInt(this.dataset.index);
  this.style.opacity = '0.5';
  e.dataTransfer.effectAllowed = 'move';
}

function handleTabDragOver(e) {
  e.preventDefault(); // Necesario para permitir el drop
  e.dataTransfer.dropEffect = 'move';
  return false;
}

function handleTabDrop(e) {
  e.stopPropagation();
  e.preventDefault();

  // Restaurar opacidad de todas las pestañas
  const allTabs = document.querySelectorAll('.tab');
  allTabs.forEach(t => t.style.opacity = '1');  
  const targetIndex = parseInt(this.dataset.index);
  
  if (draggedTabIndex !== null && draggedTabIndex !== targetIndex) {
    // Reordenar el array global de pestañas
    const movedTab = tabs.splice(draggedTabIndex, 1)[0];
    tabs.splice(targetIndex, 0, movedTab);
    
    // Guardar el nuevo orden y refrescar la UI
    renderTabs();
    saveAllLayouts(); // Opcional: para que el orden persista al recargar
  }
  
  updateNYTime();
  draggedTabIndex = null;
}

setInterval(updateNYTime, 1000);
