/**
 * GEX Dashboard - Main Script Entry Point
 * 
 * This file loads all modular JavaScript files.
 * The modules are loaded in dependency order.
 * 
 * Module Structure:
 * - state.js:      Global state variables
 * - api.js:        Data fetching functions
 * - ui.js:         UI helpers (time, themes, formatting)
 * - tabs.js:       Tab management
 * - dragdrop.js:   Drag and drop for charts
 * - charts.js:     Chart panel creation (dispatcher)
 * - heatmap.js:    Heatmap panel for Greek exposure
 * - fourier.js:    Fourier analysis panels
 * - ib.js:         Initial Balance panels
 * - handlers.js:   Form handlers
 * - history.js:    Time machine / history controls
 * - layout.js:     Save/load layouts
 * - refresh.js:    Dashboard refresh logic
 * - windows.js:    Detached windows
 * - auth.js:       Authentication
 * - init.js:       Application initialization
 * 
 * Usage:
 * Include this file in index.html after all module scripts,
 * or use it as a reference for the correct load order.
 */

// This file serves as documentation for the module structure.
// All modules are loaded via separate <script> tags in index.html.
// The load order is important for proper function resolution.

console.log('[GEX Dashboard] All modules loaded successfully.');
