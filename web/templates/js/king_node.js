/**
 * King Node Web
 *
 * A deterministic web translation of the exposure table maintained by the
 * legacy King Node workbook. It consumes the same authenticated SPX/SPXW 0DTE
 * Tastytrade snapshot as the rest of this dashboard. It does not read, mutate,
 * or execute the Excel workbook.
 */
(function initializeKingNodeWeb(root) {
    "use strict";

    if (root.KingNodeWeb) return;

    const TAB_ID = "__king_node__";
    const STRIKES_EACH_SIDE = 23;
    const WINDOW_SIZE = STRIKES_EACH_SIDE * 2 + 1;
    const BILLION = 1e9;
    const METRICS = [
        ["gamma", "GEX"],
        ["delta", "DEX"],
        ["vanna", "VEX"],
        ["zomma", "ZOMMA"],
        ["vomma", "VOMMA"],
        ["vega", "VEGA"],
        ["speed", "SPEED"],
    ];
    const SOURCE_FIELDS = [
        "total_gamma",
        "total_delta",
        "total_vanna",
        "total_zomma",
        "total_vomma",
        "total_vega",
        "total_speed",
        "total_charm",
        "total_dgex",
        "call_gex",
        "put_gex",
    ];

    let renderSequence = 0;
    let gexHistory = [];

    function finiteNumber(value, fallback = 0) {
        const number = Number(value);
        return Number.isFinite(number) ? number : fallback;
    }

    function nullableNumber(value) {
        if (value === null || value === undefined || value === "") return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function rowsFromSplit(optionData) {
        if (
            !optionData ||
            !Array.isArray(optionData.columns) ||
            !Array.isArray(optionData.data)
        ) {
            return [];
        }

        return optionData.data.map((values) => {
            const row = {};
            optionData.columns.forEach((column, index) => {
                row[column] = values[index];
            });
            return row;
        });
    }

    function aggregateByStrike(rawRows) {
        const grouped = new Map();

        rawRows.forEach((row) => {
            const strike = nullableNumber(row.strike_price);
            if (strike === null || strike <= 0) return;

            if (!grouped.has(strike)) {
                const initial = {
                    strike,
                    callIvSum: 0,
                    callIvCount: 0,
                    putIvSum: 0,
                    putIvCount: 0,
                    rawCallGamma: 0,
                    rawPutGamma: 0,
                    rawGammaCount: 0,
                };
                SOURCE_FIELDS.forEach((field) => {
                    initial[field] = 0;
                    initial[`${field}Count`] = 0;
                });
                grouped.set(strike, initial);
            }

            const target = grouped.get(strike);
            SOURCE_FIELDS.forEach((field) => {
                const value = nullableNumber(row[field]);
                if (value !== null) {
                    target[field] += value;
                    target[`${field}Count`] += 1;
                }
            });

            const callGamma = nullableNumber(row.call_gamma);
            const putGamma = nullableNumber(row.put_gamma);
            const callOpenInterest = nullableNumber(row.call_open_int);
            const putOpenInterest = nullableNumber(row.put_open_int);
            if (
                callGamma !== null &&
                putGamma !== null &&
                callOpenInterest !== null &&
                putOpenInterest !== null
            ) {
                target.rawCallGamma += callGamma * callOpenInterest;
                target.rawPutGamma += putGamma * putOpenInterest;
                target.rawGammaCount += 1;
            }

            const callIv = nullableNumber(row.call_iv);
            if (callIv !== null && callIv > 0) {
                target.callIvSum += callIv;
                target.callIvCount += 1;
            }
            const putIv = nullableNumber(row.put_iv);
            if (putIv !== null && putIv > 0) {
                target.putIvSum += putIv;
                target.putIvCount += 1;
            }
        });

        return [...grouped.values()]
            .map((row) => {
                const exposure = (field) =>
                    row[`${field}Count`] > 0 ? row[field] : null;
                const callGex = exposure("call_gex");
                const putGex = exposure("put_gex");
                const rawGamma =
                    row.rawGammaCount > 0
                        ? row.rawCallGamma + row.rawPutGamma
                        : null;
                return {
                    strike: row.strike,
                    rawGamma,
                    rawCallGamma:
                        row.rawGammaCount > 0 ? row.rawCallGamma : null,
                    rawPutGamma:
                        row.rawGammaCount > 0 ? row.rawPutGamma : null,
                    gammaGross:
                        callGex !== null && putGex !== null
                            ? (Math.abs(callGex) + Math.abs(putGex)) / BILLION
                            : null,
                    gamma: exposure("total_gamma"),
                    delta: exposure("total_delta"),
                    vanna: exposure("total_vanna"),
                    zomma: exposure("total_zomma"),
                    vomma: exposure("total_vomma"),
                    vega: exposure("total_vega"),
                    speed: exposure("total_speed"),
                    charm: exposure("total_charm"),
                    dgex: exposure("total_dgex"),
                    callIv:
                        row.callIvCount > 0
                            ? row.callIvSum / row.callIvCount
                            : null,
                    putIv:
                        row.putIvCount > 0
                            ? row.putIvSum / row.putIvCount
                            : null,
                };
            })
            .sort((left, right) => left.strike - right.strike);
    }

    function selectStrikeWindow(rows, spot) {
        if (rows.length <= WINDOW_SIZE) return rows.slice();

        let centerIndex = 0;
        let centerDistance = Infinity;
        rows.forEach((row, index) => {
            const distance = Math.abs(row.strike - spot);
            if (distance < centerDistance) {
                centerDistance = distance;
                centerIndex = index;
            }
        });

        let start = Math.max(0, centerIndex - STRIKES_EACH_SIDE);
        let end = start + WINDOW_SIZE;
        if (end > rows.length) {
            end = rows.length;
            start = Math.max(0, end - WINDOW_SIZE);
        }
        return rows.slice(start, end);
    }

    function nearestRow(rows, target, predicate = () => true) {
        let best = null;
        let distance = Infinity;
        rows.forEach((row) => {
            if (!predicate(row)) return;
            const candidateDistance = Math.abs(row.strike - target);
            if (candidateDistance < distance) {
                best = row;
                distance = candidateDistance;
            }
        });
        return best;
    }

    function strongestNode(
        rows,
        predicate = () => true,
        metric = "gamma"
    ) {
        let best = null;
        rows.forEach((row) => {
            if (!predicate(row) || !Number.isFinite(row[metric])) return;
            if (
                !best ||
                Math.abs(row[metric]) > Math.abs(best[metric])
            ) {
                best = row;
            }
        });
        return best;
    }

    function average(values) {
        const valid = values.filter((value) => Number.isFinite(value));
        if (valid.length === 0) return null;
        return valid.reduce((sum, value) => sum + value, 0) / valid.length;
    }

    function buildKingNodeModel(data, vixSpot = null) {
        const spot = nullableNumber(data && data.spot_price);
        if (spot === null || spot <= 0) {
            throw new Error("SPX spot is missing from the Tastytrade snapshot.");
        }

        const aggregatedRows = aggregateByStrike(
            rowsFromSplit(data && data.option_data)
        );
        if (aggregatedRows.length === 0) {
            throw new Error("The SPX 0DTE option surface is empty.");
        }

        const rows = selectStrikeWindow(aggregatedRows, spot);
        const gammaCoverage = rows.filter((row) =>
            Number.isFinite(row.gamma)
        ).length;
        if (gammaCoverage < 5) {
            throw new Error(
                "Fewer than five strikes contain valid GEX values."
            );
        }
        const rawGammaCoverage = rows.filter((row) =>
            Number.isFinite(row.rawGamma)
        ).length;
        if (rawGammaCoverage < 5) {
            throw new Error(
                "Fewer than five strikes contain call/put gamma and open interest for raw gamma."
            );
        }

        const totals = {};
        METRICS.forEach(([key]) => {
            totals[key] = rows.reduce(
                (sum, row) => sum + finiteNumber(row[key]),
                0
            );
        });
        totals.gammaGross = rows.reduce(
            (sum, row) => sum + finiteNumber(row.gammaGross),
            0
        );
        totals.charm = rows.reduce(
            (sum, row) => sum + finiteNumber(row.charm),
            0
        );
        totals.dgex = rows.reduce(
            (sum, row) => sum + finiteNumber(row.dgex),
            0
        );
        totals.rawGamma = rows.reduce(
            (sum, row) => sum + finiteNumber(row.rawGamma),
            0
        );

        const atm = nearestRow(rows, spot);
        const putWing = nearestRow(
            rows,
            spot * 0.98,
            (row) => row.putIv !== null
        );
        const callWing = nearestRow(
            rows,
            spot * 1.02,
            (row) => row.callIv !== null
        );
        const atmIv = atm
            ? average([atm.callIv, atm.putIv])
            : null;
        const riskReversal =
            putWing && callWing
                ? (callWing.callIv - putWing.putIv) * 100
                : null;

        const requiredCells = rows.length * (METRICS.length + 1);
        const presentCells = rows.reduce(
            (count, row) =>
                count +
                METRICS.filter(([key]) => Number.isFinite(row[key])).length +
                (Number.isFinite(row.rawGamma) ? 1 : 0),
            0
        );
        const completeness =
            requiredCells > 0 ? presentCells / requiredCells : 0;
        const coverage = Math.min(rows.length / WINDOW_SIZE, 1);
        const lowerNode = strongestNode(rows, (row) => row.strike < spot);
        const upperNode = strongestNode(rows, (row) => row.strike > spot);
        const gammaNode = strongestNode(rows);
        const rawGammaNode = strongestNode(
            rows,
            () => true,
            "rawGamma"
        );
        const zeroGammaRaw = nullableNumber(data.zerogamma);
        const zeroGamma =
            zeroGammaRaw !== null && zeroGammaRaw > 0 ? zeroGammaRaw : null;
        const previousClose = nullableNumber(data.prev_close_price);

        return {
            ticker: "SPX",
            expiration: "0DTE / SPXW",
            spot,
            previousClose,
            spotChange:
                previousClose && previousClose > 0
                    ? ((spot - previousClose) / previousClose) * 100
                    : null,
            vixSpot: nullableNumber(vixSpot),
            asOf: data.today_ddt_string || "Latest daemon snapshot",
            rows,
            totals,
            atmIv,
            riskReversal,
            gammaNode,
            rawGammaNode,
            lowerNode,
            upperNode,
            zeroGamma,
            coverage,
            completeness,
            quality:
                coverage >= 0.95 && completeness >= 0.99
                    ? "COMPLETE"
                    : "PARTIAL",
            regime:
                totals.gamma >= 0
                    ? "POSITIVE GAMMA"
                    : "NEGATIVE GAMMA",
            behavior:
                totals.gamma >= 0
                    ? "Stabilizing / mean-reverting dealer hedge pressure"
                    : "Accelerating / trend-reinforcing dealer hedge pressure",
            dealerBias:
                totals.delta >= 0 ? "NET LONG DELTA" : "NET SHORT DELTA",
        };
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function formatSigned(value, decimals = 3) {
        if (!Number.isFinite(value)) return "—";
        const sign = value > 0 ? "+" : "";
        return `${sign}${value.toFixed(decimals)}B`;
    }

    function formatRawGamma(value, decimals = 3) {
        if (!Number.isFinite(value)) return "—";
        return value.toLocaleString("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    }

    function formatPrice(value) {
        if (!Number.isFinite(value)) return "—";
        return value.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function formatPercent(value, decimals = 2) {
        if (!Number.isFinite(value)) return "—";
        const sign = value > 0 ? "+" : "";
        return `${sign}${value.toFixed(decimals)}%`;
    }

    function toneFor(value) {
        if (!Number.isFinite(value) || value === 0) return "neutral";
        return value > 0 ? "positive" : "negative";
    }

    function updateGexHistory(model) {
        const now = Date.now();
        const last = gexHistory[gexHistory.length - 1];
        if (!last || last.asOf !== model.asOf) {
            gexHistory.push({
                timestamp: now,
                asOf: model.asOf,
                value: model.totals.gamma,
            });
        }
        const cutoff = now - 46 * 60 * 1000;
        gexHistory = gexHistory.filter((point) => point.timestamp >= cutoff);

        if (gexHistory.length < 2) {
            return {
                text: "GEX slope building from live web snapshots",
                tone: "neutral",
            };
        }

        const first = gexHistory[0];
        const lastPoint = gexHistory[gexHistory.length - 1];
        const elapsedMinutes = Math.max(
            (lastPoint.timestamp - first.timestamp) / 60000,
            0.5
        );
        const per15 =
            ((lastPoint.value - first.value) / elapsedMinutes) * 15;
        const arrow = per15 > 0 ? "▲" : per15 < 0 ? "▼" : "▬";
        return {
            text: `GEX slope ${arrow} ${formatSigned(per15)} / 15m`,
            tone: toneFor(per15),
        };
    }

    function metricCard(label, value, hint, formatter = formatSigned) {
        return `
            <article class="kn-metric ${toneFor(value)}">
                <div class="kn-metric-label">${label}</div>
                <div class="kn-metric-value">${formatter(value)}</div>
                <div class="kn-metric-hint">${hint}</div>
            </article>
        `;
    }

    function levelCard(
        label,
        row,
        spot,
        metric = "gamma",
        metricLabel = "GEX",
        formatter = formatSigned
    ) {
        if (!row) {
            return `
                <article class="kn-level-card">
                    <span>${label}</span>
                    <strong>—</strong>
                    <small>No qualifying strike</small>
                </article>
            `;
        }
        const distance = row.strike - spot;
        const value = row[metric];
        return `
            <article class="kn-level-card ${toneFor(value)}">
                <span>${label}</span>
                <strong>${formatPrice(row.strike)}</strong>
                <small>${formatter(value)} ${metricLabel} · ${distance >= 0 ? "+" : ""}${distance.toFixed(1)} pts</small>
            </article>
        `;
    }

    function exposureTable(model) {
        const maxAbsGamma = Math.max(
            ...model.rows.map((row) => Math.abs(row.gamma)),
            0.000001
        );
        const nearest = nearestRow(model.rows, model.spot);

        return model.rows
            .slice()
            .reverse()
            .map((row) => {
                const width = Math.max(
                    2,
                    (Math.abs(row.gamma) / maxAbsGamma) * 100
                );
                const classes = [
                    row === nearest ? "is-spot" : "",
                    row === model.gammaNode ? "is-node" : "",
                ]
                    .filter(Boolean)
                    .join(" ");
                return `
                    <tr class="${classes}">
                        <td class="kn-strike">${formatPrice(row.strike)}</td>
                        <td>${formatRawGamma(row.rawGamma)}</td>
                        <td>${formatSigned(row.gammaGross)}</td>
                        <td class="${toneFor(row.gamma)}">
                            <div class="kn-gex-cell">
                                <span>${formatSigned(row.gamma)}</span>
                                <i class="${toneFor(row.gamma)}" style="--kn-bar:${width.toFixed(1)}%"></i>
                            </div>
                        </td>
                        <td class="${toneFor(row.delta)}">${formatSigned(row.delta)}</td>
                        <td class="${toneFor(row.vanna)}">${formatSigned(row.vanna)}</td>
                        <td class="${toneFor(row.zomma)}">${formatSigned(row.zomma)}</td>
                        <td class="${toneFor(row.vomma)}">${formatSigned(row.vomma)}</td>
                        <td class="${toneFor(row.vega)}">${formatSigned(row.vega)}</td>
                        <td class="${toneFor(row.speed)}">${formatSigned(row.speed)}</td>
                    </tr>
                `;
            })
            .join("");
    }

    function renderModel(model) {
        const slope = updateGexHistory(model);
        const qualityTone =
            model.quality === "COMPLETE" ? "positive" : "warning";
        const regimeTone = toneFor(model.totals.gamma);
        const skewText = Number.isFinite(model.riskReversal)
            ? `${model.riskReversal.toFixed(2)} vol pts (2% call − 2% put)`
            : "Insufficient wing IV coverage";

        return `
            <section class="king-node-shell">
                <header class="kn-header">
                    <div>
                        <div class="kn-eyebrow">KING NODE · WEB TRANSLATION</div>
                        <h1>SPX / SPXW 0DTE Exposure Engine</h1>
                        <p>Tastytrade option surface · 47-strike window · ${escapeHtml(model.asOf)}</p>
                    </div>
                    <div class="kn-header-actions">
                        <span class="kn-status ${qualityTone}">${model.quality}</span>
                        <button id="kn-refresh-btn" type="button">REFRESH</button>
                    </div>
                </header>

                <div class="kn-contract-note">
                    <strong>Data contract:</strong> live Tastytrade SPX/SPXW chain and the dashboard daemon's
                    exposure formulas. This is not a cell-for-cell execution of the Excel workbook.
                    Raw gamma is calculated directly as (call gamma × call OI) + (put gamma × put OI)
                    at every strike. VIX1D and VVIX are not synthesized from incomplete persisted inputs.
                </div>

                <div class="kn-hero-grid">
                    <article class="kn-spot-card">
                        <span>SPX SPOT</span>
                        <strong>${formatPrice(model.spot)}</strong>
                        <small class="${toneFor(model.spotChange)}">${formatPercent(model.spotChange)} vs previous close</small>
                    </article>
                    <article class="kn-regime-card ${regimeTone}">
                        <span>DEALER REGIME</span>
                        <strong>${model.regime}</strong>
                        <small>${model.behavior}</small>
                    </article>
                    <article class="kn-spot-card">
                        <span>ZERO GAMMA</span>
                        <strong>${formatPrice(model.zeroGamma)}</strong>
                        <small>${model.zeroGamma ? `${(model.spot - model.zeroGamma).toFixed(1)} pts from spot` : "No valid profile crossing"}</small>
                    </article>
                    <article class="kn-spot-card">
                        <span>VIX / ATM IV</span>
                        <strong>${model.vixSpot === null ? "—" : model.vixSpot.toFixed(2)} <em>/</em> ${model.atmIv === null ? "—" : (model.atmIv * 100).toFixed(2) + "%"}</strong>
                        <small>VVIX — · VIX1D — · no proxy substitution</small>
                    </article>
                </div>

                <div class="kn-level-grid">
                    ${levelCard("LOWER GAMMA NODE", model.lowerNode, model.spot)}
                    ${levelCard("KING GAMMA NODE", model.gammaNode, model.spot)}
                    ${levelCard("UPPER GAMMA NODE", model.upperNode, model.spot)}
                    ${levelCard(
                        "RAW GAMMA LEVEL",
                        model.rawGammaNode,
                        model.spot,
                        "rawGamma",
                        "Γ×OI",
                        formatRawGamma
                    )}
                </div>

                <div class="kn-metrics-grid">
                    ${metricCard(
                        "RAW GAMMA",
                        model.totals.rawGamma,
                        "Σ[(Γcall × OIcall) + (Γput × OIput)]",
                        formatRawGamma
                    )}
                    ${metricCard("GEX", model.totals.gamma, `Gross ${formatSigned(model.totals.gammaGross)}`)}
                    ${metricCard("DEX", model.totals.delta, model.dealerBias)}
                    ${metricCard("VEX", model.totals.vanna, "Vanna exposure")}
                    ${metricCard("ZOMMA", model.totals.zomma, "Gamma / volatility convexity")}
                    ${metricCard("VOMMA", model.totals.vomma, "Vega convexity")}
                    ${metricCard("VEGA", model.totals.vega, "Volatility sensitivity")}
                    ${metricCard("SPEED", model.totals.speed, "Gamma / spot convexity")}
                </div>

                <div class="kn-main-grid">
                    <article class="kn-panel kn-table-panel">
                        <div class="kn-panel-header">
                            <div>
                                <span>EXPOSURE LADDER</span>
                                <small>Workbook-equivalent columns · daemon values scaled by 10⁹</small>
                            </div>
                            <span>${model.rows.length}/${WINDOW_SIZE} strikes</span>
                        </div>
                        <div class="kn-table-scroll">
                            <table class="kn-table">
                                <thead>
                                    <tr>
                                        <th>Strike</th>
                                        <th>Raw Γ×OI</th>
                                        <th>Gamma gross</th>
                                        <th>GEX</th>
                                        <th>DEX</th>
                                        <th>VEX</th>
                                        <th>Zomma</th>
                                        <th>Vomma</th>
                                        <th>Vega</th>
                                        <th>Speed</th>
                                    </tr>
                                </thead>
                                <tbody>${exposureTable(model)}</tbody>
                            </table>
                        </div>
                    </article>

                    <aside class="kn-side-stack">
                        <article class="kn-panel kn-readout">
                            <div class="kn-panel-header"><span>LIVE READOUT</span></div>
                            <div class="kn-readout-row">
                                <span>GEX trajectory</span>
                                <strong class="${slope.tone}">${slope.text}</strong>
                            </div>
                            <div class="kn-readout-row">
                                <span>Delta posture</span>
                                <strong class="${toneFor(model.totals.delta)}">${model.dealerBias}</strong>
                            </div>
                            <div class="kn-readout-row">
                                <span>Risk reversal</span>
                                <strong>${skewText}</strong>
                            </div>
                            <div class="kn-readout-row">
                                <span>Surface coverage</span>
                                <strong>${(model.coverage * 100).toFixed(1)}% window · ${(model.completeness * 100).toFixed(1)}% metrics</strong>
                            </div>
                        </article>

                        <article class="kn-panel kn-method">
                            <div class="kn-panel-header"><span>VOLATILITY INDEX DATA GATE</span></div>
                            <div class="kn-readout-row">
                                <span>VIX</span>
                                <strong>${model.vixSpot === null ? "UNAVAILABLE — no observed index value" : "OBSERVED — index value, not reconstructed"}</strong>
                            </div>
                            <div class="kn-readout-row">
                                <span>VIX1D</span>
                                <strong class="warning">CURRENT FEED BLOCKED — ThetaData Standard can supply the missing 0DTE/next-term NBBO; capture and CMT engine are not wired</strong>
                            </div>
                            <div class="kn-readout-row">
                                <span>VVIX</span>
                                <strong class="warning">CURRENT FEED BLOCKED — ThetaData Standard can supply both eligible VIX monthly terms; capture and CMT engine are not wired</strong>
                            </div>
                        </article>

                        <article class="kn-panel kn-method">
                            <div class="kn-panel-header"><span>METHOD & LIMITS</span></div>
                            <ul>
                                <li>Uses the nearest 23 strikes on each side of SPX spot, matching the 47-strike King Node window.</li>
                                <li>Aggregates the daemon's OI-derived SPX/SPXW exposure values by strike.</li>
                                <li>Raw gamma uses each side's own streamed gamma and open interest; it is not dollar-scaled GEX.</li>
                                <li>The strongest absolute GEX strike is labelled the King Gamma Node; this is descriptive, not a trade signal.</li>
                                <li>ThetaData availability is a source capability, not a computed index value; the current web response remains fail-closed.</li>
                                <li>Workbook lock/hysteresis state and IBKR-only prints remain outside this web data contract.</li>
                            </ul>
                        </article>
                    </aside>
                </div>
            </section>
        `;
    }

    function renderError(message) {
        return `
            <section class="king-node-shell">
                <div class="kn-error">
                    <span>KING NODE DATA UNAVAILABLE</span>
                    <strong>${escapeHtml(message)}</strong>
                    <p>The tab failed closed; no stale or synthetic surface was substituted.</p>
                    <button id="kn-refresh-btn" type="button">TRY AGAIN</button>
                </div>
            </section>
        `;
    }

    function readVixFromMonitor() {
        const element =
            typeof document !== "undefined"
                ? document.getElementById("spot-vix")
                : null;
        if (!element) return null;
        const cleaned = element.textContent.replace(/,/g, "").trim();
        return nullableNumber(cleaned);
    }

    function bindRefreshButton() {
        const button = document.getElementById("kn-refresh-btn");
        if (button) {
            button.addEventListener("click", () => {
                refreshKingNodeDashboard();
            });
        }
    }

    async function fetchKingNodeSnapshot() {
        const timestamp = Date.now();
        const response = await authFetch(
            `/get_latest?ticker=SPX&exp=0dte&_=${timestamp}`
        );
        if (!response.ok) return null;
        return safeJsonParse(response);
    }

    async function renderKingNodeDashboard() {
        const wrapper = document.getElementById("charts-wrapper");
        if (!wrapper) return;

        const sequence = ++renderSequence;
        wrapper.scrollLeft = 0;
        wrapper.innerHTML = `
            <section class="king-node-shell">
                <div class="kn-loading">
                    <span></span>
                    Loading the latest SPX/SPXW 0DTE surface…
                </div>
            </section>
        `;

        try {
            const data = await fetchKingNodeSnapshot();
            if (sequence !== renderSequence || !isKingNodeTabActive()) return;
            if (!data) {
                throw new Error("No authenticated SPX 0DTE snapshot is available.");
            }

            const model = buildKingNodeModel(data, readVixFromMonitor());
            wrapper.innerHTML = renderModel(model);
            bindRefreshButton();
        } catch (error) {
            if (sequence !== renderSequence || !isKingNodeTabActive()) return;
            wrapper.innerHTML = renderError(
                error && error.message ? error.message : String(error)
            );
            bindRefreshButton();
        }
    }

    async function refreshKingNodeDashboard() {
        if (!isKingNodeTabActive()) return;
        await renderKingNodeDashboard();
    }

    function isKingNodeAvailable() {
        return (
            typeof sessionStorage !== "undefined" &&
            sessionStorage.getItem("gex_user_role") === "ADMIN"
        );
    }

    function isKingNodeTabActive() {
        return (
            typeof currentTabId !== "undefined" &&
            currentTabId === TAB_ID
        );
    }

    function setKingNodeViewActive(active) {
        if (typeof document === "undefined") return;
        document.body.classList.toggle("king-node-active", Boolean(active));
    }

    function mountKingNodeTab(container, addButton) {
        if (!isKingNodeAvailable()) return;

        const tab = document.createElement("div");
        tab.className = `tab king-node-tab ${
            isKingNodeTabActive() ? "active" : ""
        }`;
        tab.dataset.kingNode = "true";
        tab.innerHTML = "<span>KING NODE</span><b>LIVE</b>";
        tab.addEventListener("click", () => {
            if (typeof switchTab === "function") switchTab(TAB_ID);
        });
        container.insertBefore(tab, addButton);
    }

    root.KingNodeWeb = Object.freeze({
        TAB_ID,
        WINDOW_SIZE,
        rowsFromSplit,
        aggregateByStrike,
        selectStrikeWindow,
        buildKingNodeModel,
    });
    root.buildKingNodeModel = buildKingNodeModel;
    root.isKingNodeAvailable = isKingNodeAvailable;
    root.isKingNodeTabActive = isKingNodeTabActive;
    root.setKingNodeViewActive = setKingNodeViewActive;
    root.mountKingNodeTab = mountKingNodeTab;
    root.renderKingNodeDashboard = renderKingNodeDashboard;
    root.refreshKingNodeDashboard = refreshKingNodeDashboard;

    if (
        typeof document !== "undefined" &&
        isKingNodeAvailable() &&
        typeof root.renderTabs === "function"
    ) {
        root.renderTabs();
    }
})(typeof window !== "undefined" ? window : globalThis);
