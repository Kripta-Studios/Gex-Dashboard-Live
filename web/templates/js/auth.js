/**
 * Authentication Module
 * Handles login, session management, and access control
 */

/**
 * Server-side authentication check
 */
async function checkLogin() {
    const emailInput = document.getElementById("login-email").value.trim();
    const passInput = document.getElementById("login-pass").value;
    const errorDiv = document.getElementById("login-error");
    const btn = document.querySelector(".login-btn");

    errorDiv.innerText = "";
    btn.innerText = "VERIFYING...";

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: emailInput, password: passInput })
        });

        const data = await response.json();

        if (response.ok && data.status === "ok") {
            sessionStorage.setItem("gex_auth_token", data.token);
            sessionStorage.setItem("gex_user_role", data.role);
            grantAccess(data.role);
        } else {
            errorDiv.innerText = data.message || "Invalid credentials.";
            btn.innerText = "AUTHENTICATE";
        }
    } catch (e) {
        console.error(e);
        errorDiv.innerText = "Server connection failed.";
        btn.innerText = "AUTHENTICATE";
    }
}

/**
 * Toggle Market Structure Panel Visibility
 */
function toggleMarketStructurePanel() {
    const role = sessionStorage.getItem("gex_user_role");
    if (role !== "ADMIN") return;

    const msPanel = document.getElementById("market-structure-panel");
    if (msPanel) {
        if (msPanel.style.display === "none") {
            msPanel.style.display = "flex";
            if (typeof updateMarketStructureUI === 'function') {
                updateMarketStructureUI();
            }
        } else {
            msPanel.style.display = "none";
        }
    }
}

/**
 * Grant access to the application
 * @param {string} role - User role (ADMIN, USER)
 */
function grantAccess(role) {
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app-wrapper").style.display = "flex";

    // Admin-only: Show IB, MS Engine, and Chart buttons
    if (role === 'ADMIN') {
        const msBtn = document.getElementById("btn-toggle-ms");
        if (msBtn) msBtn.style.display = "inline-block";
        const msPanel = document.getElementById("market-structure-panel");
        if (msPanel) msPanel.style.display = "flex";

        const chartBtn = document.getElementById("btn-chart");
        if (chartBtn) chartBtn.style.display = "inline-block";

        const ibBtn = document.getElementById("btn-ib");
        if (ibBtn) ibBtn.style.display = "inline-block";

        // Load restrictive admin scripts dynamically
        loadAdminScripts();
    } else {
        const msBtn = document.getElementById("btn-toggle-ms");
        if (msBtn) msBtn.style.display = "none";
        const msPanel = document.getElementById("market-structure-panel");
        if (msPanel) msPanel.style.display = "none";

        const chartBtn = document.getElementById("btn-chart");
        if (chartBtn) chartBtn.style.display = "none";

        const ibBtn = document.getElementById("btn-ib");
        if (ibBtn) ibBtn.style.display = "none";
    }

    // Call init only if it's defined (script.js must be loaded first)
    if (typeof init === 'function') {
        init();
    } else {
        // Wait for init to become available
        const waitForInit = setInterval(() => {
            if (typeof init === 'function') {
                clearInterval(waitForInit);
                init();
            }
        }, 50);
        // Timeout after 5 seconds
        setTimeout(() => clearInterval(waitForInit), 5000);
    }
}

/**
 * Check existing session on page load via server-side verification
 */
async function checkSession() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = sessionStorage.getItem("gex_auth_token");
    const role = sessionStorage.getItem("gex_user_role");

    // Detached mode bypass (for development/embedding)
    if (urlParams.get('mode') === 'detached') {
        sessionStorage.setItem("gex_auth_token", "detached");
        grantAccess(role || "USER");
        return;
    }

    // No stored token → stay on login screen
    if (!token) return;

    // Verify token with server
    try {
        const response = await fetch('/verify_token', {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            // Update role in case it changed
            sessionStorage.setItem("gex_user_role", data.role);
            grantAccess(data.role);
        } else {
            // Token is invalid/expired → clear and show login
            sessionStorage.removeItem("gex_auth_token");
            sessionStorage.removeItem("gex_user_role");
        }
    } catch (e) {
        // Server unreachable → let user try anyway with cached role
        console.warn("Could not verify token with server:", e);
        if (role) {
            grantAccess(role);
        }
    }
}

// Initialize session check after DOM is fully loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkSession);
} else {
    // DOM already loaded, but wait a tick for other scripts
    setTimeout(checkSession, 0);
}

/**
 * Dynamically load restricted admin scripts using authenticated fetch
 */
async function loadAdminScripts() {
    const role = sessionStorage.getItem("gex_user_role");
    if (role !== "ADMIN") return;

    const scripts = ["js/fourier.js", "js/ib.js", "js/charts.js", "js/market_structure.js"];
    const token = sessionStorage.getItem("gex_auth_token");

    console.log("[Auth] Loading specialized admin modules...");

    for (const path of scripts) {
        try {
            const resp = await fetch(`/${path}`, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (resp.ok) {
                const code = await resp.text();
                const scriptEl = document.createElement("script");
                scriptEl.textContent = code;
                scriptEl.dataset.path = path;
                document.head.appendChild(scriptEl);
                console.log(`[Auth] Injected: ${path}`);
            } else {
                console.error(`[Auth] Failed to load admin script: ${path} (Status: ${resp.status})`);
            }
        } catch (e) {
            console.error(`[Auth] Error loading ${path}:`, e);
        }
    }
}

// Enter key login handler
document.getElementById("login-pass")?.addEventListener("keypress", function (e) {
    if (e.key === "Enter") checkLogin();
});
