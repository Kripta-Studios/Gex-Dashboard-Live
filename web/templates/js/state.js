/**
 * State Module - Global application state
 * All shared state variables are declared here
 */

// Tab management
let tabs = [{ id: 0, name: "Default", charts: [] }];
let currentTabId = 0;
let tabCounter = 1;

// Refresh management
let refreshIntervalId = null;

// Market data
let realSpotSPX = 0;

// History/Time machine
let historyDebounceTimer = null;
let currentHistoryTimeEST = null;

// IV trend tracking for Vanna coloring
let ivTrendByTicker = {};

// Tab drag and drop
let draggedTabIndex = null;
