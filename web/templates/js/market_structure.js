/** Market Structure renders the same authoritative calculation as KING NODE. */
(function (root) {
    "use strict";
    let renderSequence = 0;

    function escape(value) {
        return String(value ?? "—").replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function fromSnapshot(snapshot) {
        if (snapshot?.schema_version !== "king-node.v2" || snapshot?.quality?.valid !== true ||
            !["live", "last_completed_session"].includes(snapshot.status) ||
            snapshot?.freshness?.stale || !snapshot?.regime?.matrix_key || !snapshot?.regime?.signs ||
            snapshot?.workbook_calculation?.release !== "2026-10-10") {
            throw new Error(snapshot?.error?.code || "Market Structure unavailable: no valid current calculation");
        }
        const regime = snapshot.regime;
        const signs = regime.signs;
        return {
            snapshot,
            structure: {
                name: regime.phenomenon, regime: regime.regime,
                action: regime.action, tilt: regime.tilt, dealersAction: regime.dealers_action,
                dealerIs: regime.dealer_is,
                charmText: signs.charm === "Pos" ? regime.charm_pos : regime.charm_neg,
                supportLevels: regime.support_levels, resistanceLevels: regime.resistance_levels
            },
            conditions: { IV: regime.iv_box, Gamma: signs.gamma, Zomma: signs.zomma,
                Delta: signs.dex, Vex: signs.vex, Vega: signs.vega, Vomma: signs.vomma, Speed: signs.speed },
            ivState: regime.iv_box,
            warning: regime.fragile_positive_gamma ? "FRAGILE POSITIVE GAMMA" : null
        };
    }

    async function runMarketStructureEngine(ticker = "SPX") {
        if (!["SPX", "SPXW"].includes(ticker.toUpperCase())) {
            throw new Error("The KING NODE workbook defines SPX/SPXW only");
        }
        const response = await root.authFetch(`/api/king-node?session=live&_=${Date.now()}`);
        const snapshot = await response.json();
        if (!response.ok) throw new Error(snapshot?.error?.code || "Market Structure unavailable");
        return fromSnapshot(snapshot);
    }

    async function updateMarketStructureUI() {
        if (root.sessionStorage.getItem("gex_user_role") !== "ADMIN") return;
        const panel = root.document.getElementById("market-structure-panel");
        if (!panel) return;
        const sequence = ++renderSequence;
        const get = id => root.document.getElementById(id);
        const setText = (id, text) => { const el = get(id); if (el) el.textContent = text || "—"; };
        // Clear the previous calculation before fetching; an unavailable cycle
        // cannot leave yesterday's dealer action or signs looking current.
        setText("ms-structure-name", "Calculating Market Structure…");
        for (const id of ["ms-dealer-action", "ms-cause-list", "ms-flags-container", "ms-details-container"]) {
            const el = get(id); if (el) el.replaceChildren();
        }
        for (const id of ["ms-tilt-tag", "ms-warning"]) { const el = get(id); if (el) el.style.display = "none"; }
        panel.classList.add("ms-loading");
        try {
            const result = await runMarketStructureEngine("SPX");
            if (sequence !== renderSequence) return;
            const { structure: s, snapshot: model } = result;
            setText("ms-structure-name", s.name);
            setText("ms-dealer-action", s.action);
            setText("ms-tilt-tag", s.tilt);
            get("ms-tilt-tag").style.display = "inline-block";
            const causes = Object.entries(result.conditions).map(([name, value]) =>
                `<div class="ms-cause-item">${escape(name === "Delta" ? "DEX" : name)}: <span class="${value === "Pos" || value === "Low" ? "ms-cause-pos" : "ms-cause-neg"}">${escape(value)}</span></div>`).join("");
            get("ms-cause-list").innerHTML = causes;
            const details = [["Regime", s.regime], ["Dealers", s.dealerIs], ["Dealer action", s.dealersAction],
                ["Charm", s.charmText], ["Support references", s.supportLevels], ["Resistance references", s.resistanceLevels],
                ["Volatility regime", model.regime.box_regime], ["IV direction", model.directions?.atm_iv],
                ["Net GEX", model.totals?.gex?.toLocaleString("en-US")],
                ["Net DEX", model.totals?.dex?.toLocaleString("en-US")],
                ["Net VEX", model.totals?.vex?.toLocaleString("en-US")],
                ["Skew", model.monitor?.skew?.text],
                ["Volatility tension", model.monitor?.vol_tension?.text],
                ["Calculated at", model.generated_at]];
            get("ms-details-container").innerHTML = details.filter(([, value]) => value).map(([label, value]) =>
                `<div class="ms-detail-item"><span class="ms-detail-label">${escape(label)}</span><div class="ms-detail-value">${escape(value)}</div></div>`).join("");
            if (result.warning) { setText("ms-warning", result.warning); get("ms-warning").style.display = "block"; }
        } catch (error) {
            if (sequence !== renderSequence) return;
            setText("ms-structure-name", "MARKET STRUCTURE UNAVAILABLE");
            setText("ms-warning", error.message);
            if (get("ms-warning")) get("ms-warning").style.display = "block";
        } finally {
            if (sequence === renderSequence) panel.classList.remove("ms-loading");
        }
    }

    root.runMarketStructureEngine = runMarketStructureEngine;
    root.updateMarketStructureUI = updateMarketStructureUI;
    if (typeof module !== "undefined" && module.exports) module.exports = { fromSnapshot, escape };
})(typeof window === "undefined" ? globalThis : window);
