/**
 * KING NODE admin workspace.
 *
 * Financial calculations live in modules/king_node_engine.py.  This module is
 * deliberately a renderer for the authenticated /api/king-node contract.
 */
(function attachKingNode(root) {
    "use strict";

    const TAB_ID = "__king_node__";
    const SCHEMA_VERSION = "king-node.v2";
    let renderSequence = 0;

    function finite(value) {
        const parsed =
            typeof value === "number"
                ? value
                : typeof value === "string" && value.trim() !== ""
                  ? Number(value)
                  : NaN;
        return Number.isFinite(parsed) ? parsed : null;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function text(value, fallback = "—") {
        if (value === null || value === undefined || value === "") {
            return fallback;
        }
        return escapeHtml(value);
    }

    function formatNumber(value, decimals = 2) {
        const parsed = finite(value);
        if (parsed === null) return "—";
        return parsed.toLocaleString("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    }

    function formatPrice(value) {
        return formatNumber(value, 1);
    }

    function formatExposure(value) {
        const parsed = finite(value);
        if (parsed === null) return "—";
        const absolute = Math.abs(parsed);
        let divisor = 1;
        let suffix = "";
        if (absolute >= 1e9) {
            divisor = 1e9;
            suffix = "B";
        } else if (absolute >= 1e6) {
            divisor = 1e6;
            suffix = "M";
        } else if (absolute >= 1e3) {
            divisor = 1e3;
            suffix = "K";
        }
        const scaled = parsed / divisor;
        const sign = scaled > 0 ? "+" : "";
        return `${sign}${scaled.toLocaleString("en-US", {
            minimumFractionDigits: absolute >= 1e6 ? 2 : 1,
            maximumFractionDigits: absolute >= 1e6 ? 2 : 1,
        })}${suffix}`;
    }

    function formatRawGamma(value) {
        const parsed = finite(value);
        if (parsed === null) return "—";
        return parsed.toLocaleString("en-US", {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3,
        });
    }

    function formatPercent(value, decimals = 2) {
        const parsed = finite(value);
        if (parsed === null) return "—";
        return `${parsed > 0 ? "+" : ""}${parsed.toFixed(decimals)}%`;
    }

    function tone(value) {
        const parsed = finite(value);
        if (parsed === null || parsed === 0) return "neutral";
        return parsed > 0 ? "positive" : "negative";
    }

    function directionTone(direction) {
        if (direction === "Up") return "negative";
        if (direction === "Down") return "positive";
        return "neutral";
    }

    function ageText(seconds) {
        const parsed = finite(seconds);
        if (parsed === null) return "age unknown";
        if (parsed < 60) return `${Math.round(parsed)}s old`;
        if (parsed < 3600) return `${Math.round(parsed / 60)}m old`;
        return `${(parsed / 3600).toFixed(1)}h old`;
    }

    function timeText(value) {
        if (!value) return "—";
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return text(value);
        return escapeHtml(
            parsed.toLocaleString("en-GB", {
                timeZone: "America/New_York",
                hour12: false,
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            })
        );
    }

    function qualityErrorText(error) {
        if (typeof error === "string") return error;

        if (error && typeof error === "object") {
            return [
                error.code,
                error.component ? `component=${error.component}` : null,
                error.retryable === true ? "retryable" : null,
            ]
                .filter(Boolean)
                .join(" · ");
        }

        return "Unknown KING NODE error";
    }

    function normaliseSnapshot(data) {
        if (!data || typeof data !== "object") {
            throw new Error("KING NODE returned an empty response.");
        }

        if (data.schema_version !== SCHEMA_VERSION) {
            throw new Error(
                `Unsupported KING NODE schema: ${data.schema_version || "missing"}`
            );
        }

        const errors = Array.isArray(data.quality?.errors)
            ? data.quality.errors.map(qualityErrorText)
            : [];

        const acceptedStatus = new Set(["live", "last_completed_session"]);

        if (
            !acceptedStatus.has(data.status) ||
            data.quality?.valid !== true ||
            !Array.isArray(data.rows) ||
            data.rows.length === 0
        ) {
            throw new Error(
                errors.join(" · ") ||
                    data.error?.code ||
                    data.message ||
                    "The backend failed closed without a valid strike surface."
            );
        }

        return data;
    }

    function statusClass(model) {
        if (
            model.status === "live" &&
            model.quality?.valid === true &&
            !model.freshness?.stale
        ) {
            return "positive";
        }

        if (
            model.status === "unavailable" ||
            model.quality?.valid === false
        ) {
            return "negative";
        }

        return "warning";
    }

    function statusLabel(model) {
        if (model.status === "last_completed_session") {
            return "LAST COMPLETED";
        }

        if (model.freshness?.stale) {
            return "STALE";
        }

        return String(
            model.quality?.grade ||
                model.status ||
                "UNKNOWN"
        ).toUpperCase();
    }

    function metricCard(label, value, hint, formatter = formatExposure) {
        return `
            <article class="kn-metric ${tone(value)}">
                <div class="kn-metric-label">${escapeHtml(label)}</div>
                <div class="kn-metric-value">${formatter(value)}</div>
                <div class="kn-metric-hint">${escapeHtml(hint)}</div>
            </article>
        `;
    }

    function nodeCard(label, node, spot, formatter = formatExposure) {
        const strike = finite(node?.strike);
        const value = finite(node?.value);
        if (strike === null) {
            return `
                <article class="kn-level-card neutral">
                    <span>${escapeHtml(label)}</span>
                    <strong>—</strong>
                    <small>Not present in the validated window</small>
                </article>
            `;
        }
        const distance = strike - spot;
        return `
            <article class="kn-level-card ${tone(value)}">
                <span>${escapeHtml(label)}</span>
                <strong>${formatPrice(strike)}</strong>
                <small>${formatter(value)} · ${distance >= 0 ? "+" : ""}${distance.toFixed(1)} pts</small>
            </article>
        `;
    }

    function indexItem(model, name) {
        const full = model.provenance?.indices?.[name];
        const compact = model.inputs?.indices?.[name];

        return {
            value: full?.value ?? compact?.value ?? null,
            status:
                full?.mode ??
                full?.status ??
                compact?.provenance ??
                "unavailable",
            age_seconds:
                full?.inputs_age_seconds ??
                full?.age_seconds ??
                null,
            provider:
                full?.provider ??
                full?.source ??
                model.provenance?.provider ??
                "unknown",
            quality:
                full?.quality ??
                compact?.quality ??
                null,
        };
    }

    function indexCard(label, item, direction) {
        const value = finite(item?.value);

        const qualityValid =
            item?.quality && typeof item.quality === "object"
                ? item.quality.valid !== false
                : item?.quality !== "unavailable";

        const available =
            value !== null &&
            item?.status !== "unavailable" &&
            qualityValid;

        return `
            <article class="kn-index-card ${available ? "" : "is-degraded"}">
                <div>
                    <span>${escapeHtml(label)}</span>
                    <strong>${value === null ? "—" : formatNumber(value, 2)}</strong>
                </div>
                <div class="kn-index-meta">
                    <b class="${directionTone(direction)}">${text(direction, "Flat")}</b>
                    <small>${text(item?.status, "missing")} · ${ageText(item?.age_seconds)} · ${text(item?.provider)}</small>
                </div>
            </article>
        `;
    }

    function namedLevelRows(items, side) {
        const levels = Array.isArray(items) ? items : [];
        if (!levels.length) {
            return `<div class="kn-empty">No ${escapeHtml(side)} level passed the data gate.</div>`;
        }
        return levels
            .map((item, index) => {
                const score = finite(item.score);
                const confluence = finite(item.confluence);
                const backers = Array.isArray(item.backers)
                    ? item.backers.join(" · ")
                    : "";
                return `
                    <div class="kn-ranked-level">
                        <b>${escapeHtml(side.slice(0, 1).toUpperCase())}${index + 1}</b>
                        <strong>${formatPrice(item.strike)}</strong>
                        <span>${item.distance >= 0 ? "+" : ""}${formatNumber(item.distance, 1)} pts</span>
                        <small>${score === null ? "locked carry" : `score ${score.toFixed(2)}`} · confl ${confluence ?? "—"}${backers ? ` · ${escapeHtml(backers)}` : ""}</small>
                    </div>
                `;
            })
            .join("");
    }

    function wallRows(items, label) {
        const walls = Array.isArray(items) ? items : [];
        if (!walls.length) return '<div class="kn-empty">No qualifying wall.</div>';
        return walls
            .map(
                (wall, index) => `
                    <div class="kn-wall">
                        <b>${escapeHtml(label)} ${index + 1}</b>
                        <strong>${formatPrice(wall.strike)}</strong>
                        <span>${formatExposure(wall.gamma_gross)} gross Γ · ${formatExposure(wall.gex)} GEX</span>
                    </div>
                `
            )
            .join("");
    }

    function warningPanel(model) {
        const warnings = Array.isArray(model.quality?.warnings)
            ? [...model.quality.warnings]
            : [];

        if (model.freshness?.stale) {
            warnings.unshift(
                `Oldest input is ${ageText(
                    model.freshness.oldest_age_seconds
                )}; limit ${ageText(
                    model.freshness.max_age_seconds
                )}.`
            );
        }

        if (!warnings.length) {
            return `
                <div class="kn-gate-ok">
                    All configured source, coverage, freshness and reference gates passed.
                </div>
            `;
        }

        return `
            <ul class="kn-warning-list">
                ${warnings
                    .map(
                        (warning) =>
                            `<li>${escapeHtml(warning)}</li>`
                    )
                    .join("")}
            </ul>
        `;
    }

    function tableRows(model) {
        const spot = finite(model.inputs?.underlying?.spot) || 0;
        const rawNode = finite(model.levels?.raw_gamma?.strike);
        const kingNode = finite(model.levels?.king_gamma?.strike);
        const maxGex = finite(model.levels?.max_gex?.strike);
        const minGex = finite(model.levels?.min_gex?.strike);
        const zeroGamma = finite(model.levels?.zero_gamma?.strike);
        const gammaFlip = finite(model.levels?.gamma_flip);
        const maxAbsoluteGex = Math.max(
            1,
            ...model.rows.map((row) => Math.abs(finite(row.gex) || 0))
        );
        const nearestSpot = model.rows.reduce(
            (best, row) =>
                !best ||
                Math.abs(row.strike - spot) < Math.abs(best.strike - spot)
                    ? row
                    : best,
            null
        )?.strike;

        return model.rows
            .map((row) => {
                const strike = finite(row.strike);
                const markers = [];
                if (strike === rawNode) markers.push("RAW");
                if (strike === kingNode) markers.push("KING");
                if (strike === maxGex) markers.push("MAX");
                if (strike === minGex) markers.push("MIN");
                if (strike === zeroGamma) markers.push("ZG");
                if (strike === gammaFlip) markers.push("FLIP");
                const classes = [
                    strike === nearestSpot ? "is-spot" : "",
                    strike === rawNode || strike === kingNode ? "is-node" : "",
                ]
                    .filter(Boolean)
                    .join(" ");
                const bar = ((Math.abs(finite(row.gex) || 0) / maxAbsoluteGex) * 100).toFixed(1);
                return `
                    <tr class="${classes}">
                        <td class="kn-strike">${formatPrice(strike)}${markers.length ? `<small>${markers.join("·")}</small>` : ""}</td>
                        <td>${formatRawGamma(row.raw_gamma)}</td>
                        <td>${formatExposure(row.gamma_gross)}</td>
                        <td class="${tone(row.gex)}">
                            <div class="kn-gex-cell" style="--kn-bar:${bar}%">
                                <span>${formatExposure(row.gex)}</span><i></i>
                            </div>
                        </td>
                        <td class="${tone(row.zomma)}">${formatExposure(row.zomma)}</td>
                        <td class="${tone(row.dex)}">${formatExposure(row.dex)}</td>
                        <td class="${tone(row.vex)}">${formatExposure(row.vex)}</td>
                        <td class="${tone(row.vomma)}">${formatExposure(row.vomma)}</td>
                        <td class="${tone(row.vega)}">${formatExposure(row.vega)}</td>
                        <td class="${tone(row.speed)}">${formatExposure(row.speed)}</td>
                    </tr>
                `;
            })
            .join("");
    }

    function renderModel(model) {
        const underlying = model.inputs?.underlying || {};
        const expiration = model.inputs?.expiration || {};

        const spot = finite(underlying.spot) || 0;
        const previousClose = finite(underlying.previous_close);

        const spotChangePct =
            previousClose !== null && previousClose !== 0
                ? ((spot - previousClose) / previousClose) * 100
                : null;

        const timeToExpiryYears =
            finite(expiration.time_to_expiry_years);

        const dteHours =
            timeToExpiryYears === null
                ? null
                : timeToExpiryYears * 365 * 24;

        const regime = model.regime || {};
        const signs = regime.signs || {};

        const indexSource = {
            vix: indexItem(model, "vix"),
            vvix: indexItem(model, "vvix"),
            vix1d: indexItem(model, "vix1d"),
        };

        const gex = model.monitor?.gex || {};
        const skew = model.monitor?.skew || {};
        const atmIv = finite(skew.atm_iv);
        const vomma = model.monitor?.vomma || {};
        const tension = model.monitor?.vol_tension || {};
        const extremes = model.monitor?.vix1d_extremes || {};
        const zeroGamma = model.levels?.zero_gamma;

        const generatedTimestamp =
            new Date(model.generated_at).getTime();

        const generatedAge =
            finite(model.freshness?.oldest_age_seconds) ??
            (Number.isFinite(generatedTimestamp)
                ? Math.max(
                      0,
                      (Date.now() - generatedTimestamp) / 1000
                  )
                : null);

        return `
            <section class="king-node-shell">
                <header class="kn-header">
                    <div>
                        <div class="kn-eyebrow">KING NODE · PORTABLE V5 ENGINE</div>
                        <h1>Dealer structure, volatility state & locked levels</h1>
                        <p>Snapshot ${timeText(model.generated_at)} ET · ${ageText(generatedAge)} · ${model.quality?.strike_count || model.rows.length}/${model.quality?.expected_strike_count || 47} strikes · smooth ${model.quality?.smooth_depth || 1}/3</p>
                    </div>
                    <div class="kn-header-actions">
                        <span class="kn-status ${statusClass(model)}">${escapeHtml(statusLabel(model))}</span>
                        <button id="kn-refresh-btn" type="button">REFRESH</button>
                    </div>
                </header>

                <div class="kn-contract-note">
                    <strong>Authoritative calculation:</strong>
                    backend <code>${SCHEMA_VERSION}</code> using the validated ThetaData v3 SPXW option surface.
                    Raw gamma is <code>(Γcall × OIcall) + (Γput × OIput)</code> per strike.
                    VIX is derived from VIX-option underlying observations; VIX1D and VVIX are reconstructed from authorised option NBBO inputs.
                    No stale or unavailable input is silently substituted.
                </div>

                <div class="kn-hero-grid kn-hero-grid-wide">
                    <article class="kn-spot-card">
                        <span>SPX SPOT</span>
                        <strong>${formatPrice(spot)}</strong>
                        <small class="${tone(spotChangePct)}">${formatPercent(spotChangePct)} vs previous close · DTE ${formatNumber(dteHours, 2)}h</small>
                    </article>
                    <article class="kn-regime-card ${signs.gamma === "Pos" ? "positive" : "negative"}">
                        <span>DEALER REGIME</span>
                        <strong>${text(regime.regime)}</strong>
                        <small>${text(regime.action)} · ${text(regime.tilt)}</small>
                    </article>
                    <article class="kn-spot-card">
                        <span>VOL TENSION</span>
                        <strong>${text(tension.label)}</strong>
                        <small>${text(tension.expectation)}${finite(tension.ratio) === null ? "" : ` · V1D/VIX ${formatNumber(tension.ratio, 2)}`}</small>
                    </article>
                    <article class="kn-spot-card">
                        <span>RAW GAMMA LEVEL</span>
                        <strong>${formatPrice(model.levels?.raw_gamma?.strike)}</strong>
                        <small>${formatRawGamma(model.levels?.raw_gamma?.value)} Γ×OI · exact per-leg multiplication</small>
                    </article>
                    <article class="kn-spot-card">
                        <span>ZERO GAMMA / FLIP</span>
                        <strong>${formatPrice(zeroGamma?.strike)} <em>/</em> ${formatPrice(model.levels?.gamma_flip)}</strong>
                        <small>ZG interpolated ${formatPrice(zeroGamma?.interpolated_strike)} · daemon ${formatPrice(model.levels?.daemon_zero_gamma)}</small>
                    </article>
                </div>

                <div class="kn-index-grid">
                    ${indexCard("VIX", indexSource.vix, model.directions?.vix)}
                    ${indexCard("VVIX", indexSource.vvix, model.directions?.vvix)}
                    ${indexCard("VIX1D", indexSource.vix1d, model.directions?.vix1d)}
                    ${indexCard(
                        "ATM CALL IV",
                        {
                            value:
                                atmIv === null
                                    ? null
                                    : atmIv * 100,
                            status:
                                atmIv === null
                                    ? "unavailable"
                                    : "derived_from_option_surface",
                            age_seconds:
                                model.freshness?.oldest_age_seconds,
                            provider:
                                model.provenance?.provider,
                            quality: {
                                valid: atmIv !== null,
                            },
                        },
                        model.directions?.atm_iv
                    )}
                </div>

                <div class="kn-level-grid kn-level-grid-six">
                    ${nodeCard("RAW GAMMA", model.levels?.raw_gamma, spot, formatRawGamma)}
                    ${nodeCard("KING GROSS GAMMA", model.levels?.king_gamma, spot)}
                    ${nodeCard("MAX GEX", model.levels?.max_gex, spot)}
                    ${nodeCard("MIN GEX", model.levels?.min_gex, spot)}
                    ${nodeCard(
                        "GAMMA FLIP",
                        { strike: model.levels?.gamma_flip, value: null },
                        spot
                    )}
                    ${nodeCard(
                        "ZERO GAMMA",
                        { strike: zeroGamma?.strike, value: null },
                        spot
                    )}
                </div>

                <div class="kn-metrics-grid kn-metrics-grid-wide">
                    ${metricCard("RAW Γ", model.totals?.raw_gamma, "Σ per-leg Γ×OI", formatRawGamma)}
                    ${metricCard("GROSS Γ", model.totals?.gamma_gross, "Workbook column B")}
                    ${metricCard("NET GEX", model.totals?.gex, `${text(gex.sign)} · ${formatExposure(gex.per_15_minutes)}/15m`)}
                    ${metricCard("DEX", model.totals?.dex, `sign ${text(signs.dex)}`)}
                    ${metricCard("VEX", model.totals?.vex, `sign ${text(signs.vex)}`)}
                    ${metricCard("ZOMMA", model.totals?.zomma, `sign ${text(signs.zomma)}`)}
                    ${metricCard("VOMMA", model.totals?.vomma, text(vomma.status))}
                    ${metricCard("VEGA", model.totals?.vega, `sign ${text(signs.vega)}`)}
                    ${metricCard("SPEED", model.totals?.speed, `sign ${text(signs.speed)}`)}
                    ${metricCard("CHARM", model.totals?.charm, `sign ${text(signs.charm)}`)}
                </div>

                <div class="kn-structure-grid">
                    <article class="kn-panel">
                        <div class="kn-panel-header"><span>LOCKED RESISTANCES</span><small>3-cycle hysteresis · six slots</small></div>
                        <div class="kn-ranked-list">${namedLevelRows(model.levels?.resistances, "resistance")}</div>
                    </article>
                    <article class="kn-panel">
                        <div class="kn-panel-header"><span>LOCKED SUPPORTS</span><small>3-cycle hysteresis · six slots</small></div>
                        <div class="kn-ranked-list">${namedLevelRows(model.levels?.supports, "support")}</div>
                    </article>
                    <article class="kn-panel">
                        <div class="kn-panel-header"><span>CALL WALLS</span><small>top gross gamma where net GEX &gt; 0</small></div>
                        <div class="kn-wall-list">${wallRows(model.levels?.call_walls, "CALL")}</div>
                    </article>
                    <article class="kn-panel">
                        <div class="kn-panel-header"><span>PUT WALLS</span><small>top gross gamma where net GEX &lt; 0</small></div>
                        <div class="kn-wall-list">${wallRows(model.levels?.put_walls, "PUT")}</div>
                    </article>
                </div>

                <div class="kn-main-grid">
                    <article class="kn-panel kn-table-panel">
                        <div class="kn-panel-header">
                            <div>
                                <span>47-STRIKE KING NODE PROFILE</span>
                                <small>A:I workbook profile plus raw Γ×OI</small>
                            </div>
                            <span>${model.rows.length} rows</span>
                        </div>
                        <div class="kn-table-scroll">
                            <table class="kn-table">
                                <thead>
                                    <tr>
                                        <th>Strike</th>
                                        <th>Raw Γ×OI</th>
                                        <th>Gross Γ</th>
                                        <th>GEX</th>
                                        <th>Zomma</th>
                                        <th>DEX</th>
                                        <th>VEX</th>
                                        <th>Vomma</th>
                                        <th>Vega</th>
                                        <th>Speed</th>
                                    </tr>
                                </thead>
                                <tbody>${tableRows(model)}</tbody>
                            </table>
                        </div>
                    </article>

                    <aside class="kn-side-stack">
                        <article class="kn-panel kn-readout">
                            <div class="kn-panel-header"><span>MATRIX & BOX CONTRACT</span><small>${text(regime.reference_mode)}</small></div>
                            <div class="kn-readout-row"><span>Phenomenon</span><strong>${text(regime.phenomenon)}</strong></div>
                            <div class="kn-readout-row"><span>Dealer is</span><strong>${text(regime.dealer_is)}</strong></div>
                            <div class="kn-readout-row"><span>Dealer action</span><strong>${text(regime.dealers_action)}</strong></div>
                            <div class="kn-readout-row"><span>Action / tilt</span><strong>${text(regime.action)} · ${text(regime.tilt)}</strong></div>
                            <div class="kn-readout-row"><span>IV class / intensity / DTE boost</span><strong>${text(regime.iv_raw)} → ${text(regime.iv_box)} · ${formatNumber(regime.iv_intensity, 2)}× · ${formatNumber(regime.dte_boost, 2)}×</strong></div>
                            <div class="kn-readout-row"><span>Matrix key</span><code>${text(regime.matrix_key)}</code></div>
                            <div class="kn-readout-row"><span>Box key</span><code>${text(regime.box_key)}</code></div>
                        </article>

                        <article class="kn-panel kn-readout">
                            <div class="kn-panel-header"><span>LIVE MONITORS</span></div>
                            <div class="kn-readout-row"><span>Net GEX trajectory</span><strong>${formatExposure(gex.per_15_minutes)}/15m · ${text(gex.sign)} · ${finite(gex.flip_age_minutes) === null ? "no session flip" : `flipped ${formatNumber(gex.flip_age_minutes, 0)}m ago`}</strong></div>
                            <div class="kn-readout-row"><span>Vomma near spot</span><strong>${text(vomma.status)} · ref ${formatExposure(vomma.reference)}</strong></div>
                            <div class="kn-readout-row"><span>Put / call skew</span><strong>${formatNumber(skew.put_skew_vol_points, 2)}vp ${text(skew.put_direction)} · ${formatNumber(skew.call_skew_vol_points, 2)}vp ${text(skew.call_direction)} · RR ${formatNumber(skew.risk_reversal_vol_points, 2)}vp</strong></div>
                            <div class="kn-readout-row"><span>VIX1D session</span><strong>Lo ${formatNumber(extremes.session_low, 2)} · Hi ${formatNumber(extremes.session_high, 2)} · ${extremes.vol_bottom ? "VOL BOTTOM" : extremes.vol_top ? "VOL TOP" : "no extreme flag"}</strong></div>
                        </article>

                        <article class="kn-panel kn-readout">
                            <div class="kn-panel-header"><span>DATA & REFERENCE GATES</span></div>
                            ${warningPanel(model)}
                            <div class="kn-source-line">
                                <span>Provider</span>
                                <strong>${text(model.provenance?.provider)} ${text(model.provenance?.api_version)}</strong>
                                <small>Options ${text(model.provenance?.entitlements?.options)} · Index ${text(model.provenance?.entitlements?.index)} · Rate ${text(model.provenance?.entitlements?.rate)}</small>
                                <small>MDDS ${text(model.provenance?.readiness?.mdds)} · FPSS ${text(model.provenance?.readiness?.fpss)}</small>
                            </div>
                            <div class="kn-source-line">
                                <span>Coverage</span>
                                <strong>raw Γ ${formatPercent((model.quality?.raw_gamma_coverage || 0) * 100, 1)} · profile ${formatPercent((model.quality?.profile_coverage || 0) * 100, 1)}</strong>
                                <small>Endpoint is ADMIN-only and Cache-Control: no-store.</small>
                            </div>
                        </article>
                    </aside>
                </div>
            </section>
        `;
    }

    function renderError(error) {
        const retryable = error?.retryable === true;

        const title = retryable
            ? "KING NODE UNAVAILABLE"
            : "KING NODE FAILED CLOSED";

        const explanation = retryable
            ? "No valid live snapshot is currently available. The service will retry automatically."
            : "No stale surface or unauthorised volatility input was substituted.";

        return `
            <section class="king-node-shell">
                <div class="kn-error">
                    <span>${title}</span>
                    <strong>${escapeHtml(
                        error?.message ||
                            String(error)
                    )}</strong>
                    <p>${explanation}</p>
                    <button id="kn-refresh-btn" type="button">TRY AGAIN</button>
                </div>
            </section>
        `;
    }

    function bindRefreshButton() {
        const button = document.getElementById("kn-refresh-btn");
        if (button) {
            button.addEventListener("click", refreshKingNodeDashboard);
        }
    }

    async function fetchKingNodeSnapshot() {
        const response = await authFetch(
            `/api/king-node?_=${Date.now()}`
        );

        const data = await safeJsonParse(response);

        if (!response.ok) {
            const apiError = data?.error;
            const code = apiError?.code;

            const error = new Error(
                code
                    ? [
                          code,
                          apiError.component
                              ? `component=${apiError.component}`
                              : null,
                          apiError.retryable === true
                              ? "retryable"
                              : null,
                      ]
                          .filter(Boolean)
                          .join(" · ")
                    : data?.message ||
                      `KING NODE API returned HTTP ${response.status}.`
            );

            error.code = code;
            error.retryable =
                apiError?.retryable === true;
            error.httpStatus = response.status;

            throw error;
        }

        return normaliseSnapshot(data);
    }

    async function renderKingNodeDashboard() {
        const wrapper = document.getElementById("charts-wrapper");
        if (!wrapper) return;
        const sequence = ++renderSequence;
        wrapper.scrollLeft = 0;
        wrapper.innerHTML = `
            <section class="king-node-shell">
                <div class="kn-loading"><span></span>Loading validated KING NODE snapshot…</div>
            </section>
        `;
        try {
            const model = await fetchKingNodeSnapshot();
            if (sequence !== renderSequence || !isKingNodeTabActive()) return;
            wrapper.innerHTML = renderModel(model);
        } catch (error) {
            if (sequence !== renderSequence || !isKingNodeTabActive()) return;
            wrapper.innerHTML = renderError(error);
        }
        bindRefreshButton();
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
        SCHEMA_VERSION,
        escapeHtml,
        formatExposure,
        formatRawGamma,
        normaliseSnapshot,
        renderModel,
    });
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
