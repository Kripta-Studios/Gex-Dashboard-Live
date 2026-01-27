/**
 * Authentication Module
 * Handles login, session management, and access control
 */

// Hash constants for authentication
const TARGET_EMAIL_HASH = "0f089be93d18d31f8ac42fc84ecd206bea41ffbde1df2a11dc1de1637822dcb7";
const TARGET_PASS_HASH = "9b068d00dba617e0e84667d11ac6eb934e8ca73f4102195095eeff8ccd3359e1";

/**
 * Generate SHA-256 hash of a string
 * @param {string} message - String to hash
 * @returns {Promise<string>} Hex-encoded hash
 */
async function sha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

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
            errorDiv.innerText = "Invalid credentials.";
            btn.innerText = "AUTHENTICATE";
        }
    } catch (e) {
        console.error(e);
        errorDiv.innerText = "Server connection failed.";
        btn.innerText = "AUTHENTICATE";
    }
}

/**
 * Grant access to the application
 * @param {string} role - User role (ADMIN, USER)
 */
function grantAccess(role) {
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app-wrapper").style.display = "flex";

    // Admin-only: Show IB button
    if (role === 'ADMIN') {
        const ibBtn = document.getElementById("btn-ib");
        if (ibBtn) ibBtn.style.display = "inline-block";
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
 * Check existing session on page load
 */
function checkSession() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = sessionStorage.getItem("gex_auth_token");
    const role = sessionStorage.getItem("gex_user_role");

    // Valid token or detached mode (assumes valid session)
    if (token || urlParams.get('mode') === 'detached') {
        sessionStorage.setItem("gex_auth_token", "valid");
        grantAccess(role);
    }
}

// Initialize session check after DOM is fully loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkSession);
} else {
    // DOM already loaded, but wait a tick for other scripts
    setTimeout(checkSession, 0);
}

// Enter key login handler
document.getElementById("login-pass")?.addEventListener("keypress", function (e) {
    if (e.key === "Enter") checkLogin();
});
