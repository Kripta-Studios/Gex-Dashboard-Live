/**
 * Market Structure Engine
 * Evaluates options flow and market data to classify into market structures.
 * Data sourced from VIX_AS.xlsx — sheets: "Dealers Action", "By Pairs", "Add Wk 62"
 */

// ─────────────────────────────────────────────────────────────────────────────
//  MARKET STRUCTURES MATRIX
//  Condition fields:
//    IV     : "High" | "Low"
//    Gamma  : "Pos" | "Neg"
//    Zomma  : "Pos" | "Neg"
//    Delta  : "Pos" | "Neg"
//    Vex    : "Pos" | "Neg"
//    Vega   : "Pos" | "Neg"
//    Vomma  : "Pos" | "Neg" | null  (null = wildcard)
//    Speed  : "Pos" | "Neg" | null  (null = wildcard)
//
//  Source sheets (in priority order for extra fields):
//    "Add Wk 62"   – most complete, has Speed column + extra detail
//    "By Pairs"    – subset used for entry / reversal data
//    "Dealers Action" – original base matrix
// ─────────────────────────────────────────────────────────────────────────────
const MARKET_STRUCTURES = [

    // ═══════════════════════════════════════════════════════════════════
    //  HIGH IV STRUCTURES
    // ═══════════════════════════════════════════════════════════════════

    {
        "id": 1,
        "name": "The Waterfall",
        // Source: Dealers Action row 24 / Add Wk 62 row 16
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Forced Selling",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": "5DEMA/15DEMA",
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 2,
        "name": "Mean Reversion",
        // Source: Dealers Action row 25
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 3,
        "name": "The Melt Up",
        // Source: Dealers Action row 26
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": null, "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": "5DEMA/15DEMA",
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 4,
        "name": "The Drag",
        // Source: Dealers Action row 27
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 5,
        "name": "Vol of Vol / Fragile Long Vol",
        // Source: Dealers Action row 28 + By Pairs row 1 + Add Wk 62 row 1
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day (Not clean however; Can have compression characters)",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Choppy H pattern down, Pull backs are entries",
        "flags": { "max_vanna_level": true, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "CCS",
        "entry": "Short Max Vanna",
        "emas": "5DMA/15DMA",
        "approxBouncePts": "40 pts",
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Change in Max Vanna",
        "trendEliminator": "Drains Gamma (Zomma shifts)"
    },
    {
        "id": 6,
        "name": "Liquidation",
        // Source: Dealers Action row 29
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Selling",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 7,
        "name": "Pinned Long Vol",
        // Source: Add Wk 62 row 2
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Transitional",
        "action": "Dealer is Binary. Buys until the pin snaps, then aggressively SELLS.",
        "actionDirection": "BINARY",
        "tilt": "Do not trade",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "N/A",
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 8,
        "name": "Vol-Expansion Pre-Trend",
        // Source: Add Wk 62 row 3
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Fade extremes while gamma exists",
        "flags": { "max_vanna_level": true, "ib_bounce": true, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": "5DEMA/15DEMA",
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Bounce off Max Vanna",
        "trendEliminator": null
    },
    {
        "id": 9,
        "name": "Directionless Chop - Slight Bid",
        // Source: Dealers Action row 36 + Add Wk 62 row 4
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Passive Buyers inside the Pin (Synthetic, flow-driven bid, not a conviction bid)",
        "actionDirection": "CHOP",
        "tilt": "Fade Extremes / Break of gamma flip turns to Bear Trend",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Break of Gamma Flip signals Bear Trend",
        "trendEliminator": null
    },
    {
        "id": 10,
        "name": "Short Bearish Gamma Squeeze",
        // Source: Dealers Action row 37 + Add Wk 62 row 5
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Mechanical Forced Sellers",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": "5DEMA/15DEMA",
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Vol crush can lead to V-shape recovery. When IV prints a lower high while spot prints a lower low — that is the turn.",
        "trendEliminator": null
    },
    {
        "id": 11,
        "name": "Negative Convexity Vol Unwind (Compression Type)",
        // Source: Dealers Action row 42 + Add Wk 62 row 10
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "High Risk - Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 12,
        "name": "Short Gamma Squeeze / Negative Convexity Feedback Loop",
        // Source: Add Wk 62 row 11
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day (Likely Violent)",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": "5DEMA/15DEMA",
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Can lead to V-shape recovery. Usually a major strike (Gamma Wall) or regime shift back to Positive Gamma.",
        "trendEliminator": null
    },
    {
        "id": 13,
        "name": "The Gamma Trap / Crash-to-Melt Vanna (High Vol Pin)",
        // Source: Dealers Action row 45 + Add Wk 62 row 13
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional / Expansion",
        "action": "Binary at open.",
        "actionDirection": "BINARY",
        "tilt": "Do not trade / Scalp Only",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "No",
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },

    // ═══════════════════════════════════════════════════════════════════
    //  LOW IV STRUCTURES
    // ═══════════════════════════════════════════════════════════════════

    {
        "id": 14,
        "name": "The Melt Up (Low IV)",
        // Source: Dealers Action row 30 + By Pairs row 2 + Add Wk 62 row 12
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Momentum, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": "PCS",
        "entry": null,
        "emas": "5DMA/15DMA",
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks",
        "vvixVix": "VIX Down, VVIX Down",
        "reversalSignal": "Change in Max Vanna",
        "trendEliminator": "Short upside calls"
    },
    {
        "id": 15,
        "name": "The Fade",
        // Source: Dealers Action row 31
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 16,
        "name": "V Bottom",
        // Source: Dealers Action row 32
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 17,
        "name": "The Bleed",
        // Source: Dealers Action row 33
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 18,
        "name": "Volatility Mean Reversion Sideways Grind",
        // Source: Dealers Action row 38
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": null },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "SIDEWAYS GRIND",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 19,
        "name": "Volatility Mean Reversion Crush",
        // Source: Dealers Action row 39
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 20,
        "name": "The Ceiling / The Call Pin",
        // Source: Dealers Action row 40 + Add Wk 62 row 8
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Forced Sellers on Rips. Break of Pin on flat IV is a genuine breakout — do not fade otherwise causes snapback.",
        "actionDirection": "SELL / PIN",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Break of Pin on flat IV is genuine breakout",
        "trendEliminator": null
    },
    {
        "id": 21,
        "name": "High Confidence Grind / PIN",
        // Source: Dealers Action row 41 + Add Wk 62 row 9
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Supportive Buyers",
        "actionDirection": "BUY / PIN",
        "tilt": "Fade Extremes / PIN",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 22,
        "name": "Vanna-Fueled Melt Up",
        // Source: Dealers Action row 44 + Add Wk 62 row 12 (Speed=Neg)
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": true },
        "spreads": "PCS",
        "entry": null,
        "emas": "8/20",
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks. Pullbacks can be decent or small.",
        "vvixVix": "VIX Down, VVIX Down",
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 23,
        "name": "Pre-Breakout Convexity Pocket / Gamma Squeeze",
        // Source: Dealers Action row 46
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Compression",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },

    // ═══════════════════════════════════════════════════════════════════
    //  EXTENDED STRUCTURES — sourced from "Add Wk 62"
    // ═══════════════════════════════════════════════════════════════════

    {
        "id": 24,
        "name": "Bear Trend Coiled in a Gamma Pin / Pre-Breakdown Structure",
        // Source: Add Wk 62 row 4 (different Speed from id=9 above)
        // Note: same greek signs as id=9 but Speed explicitly null in original; kept as separate entry
        // for Dealers Action sheet compatibility. Add Wk 62 adds Speed=Neg.
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Selling Pressure in Chop",
        "actionDirection": "CHOP -> SELL",
        "tilt": "Fade Extremes / Break of Gamma Flip turns to Bear Trend",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Break of Gamma Flip",
        "trendEliminator": null
    },
    {
        "id": 25,
        "name": "Short Bearish Gamma Squeeze (Extended)",
        // Source: Add Wk 62 row 5 — Speed=Neg variant
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Mechanical Forced Sellers",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Aggressive Sells",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Vol crush can lead to V-shape recovery. IV lower high + spot lower low = the turn.",
        "trendEliminator": null
    },
    {
        "id": 26,
        "name": "Low IV Positive Gamma Grind (Mean-Reverting Compression)",
        // Source: Add Wk 62 row 6
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes / Mean Reverting",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 27,
        "name": "Compression Regime with Asymmetric Vol Expansion Payoff",
        // Source: Add Wk 62 row 7
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes / Asymmetric Risk-Reward",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 28,
        "name": "Short Gamma Trap / Melt Up",
        // Source: Add Wk 62 row 14
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Chasing / Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "PCS / Long Calls",
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks",
        "vvixVix": "VIX Down, VVIX Down",
        "reversalSignal": "Change in Max Vanna. Max Vanna should be at unrealistic level for confirmation; a shift signals trend reversal.",
        "trendEliminator": "Short upside calls"
    },
    {
        "id": 29,
        "name": "Positive Convexity Vanna-Fueled Melt Up / Pre Gamma Squeeze",
        // Source: Add Wk 62 row 15
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transition to Expansion",
        "action": "Forced Buying",
        "actionDirection": "BUY (Transition)",
        "tilt": "Trend Day (Can act like compression during transition), Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks",
        "vvixVix": "VIX Down, VVIX Down",
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 30,
        "name": "The Waterfall Sell Off",
        // Source: Add Wk 62 row 16
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Forced Selling",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 31,
        "name": "The Mean Reversion Anchor",
        // Source: Add Wk 62 row 17
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "SELL / BUY",
        "tilt": "Fade Extremes / Range Bound High Vol",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 32,
        "name": "Short-Vol Capitulation / The Melt Up",
        // Source: Add Wk 62 row 18
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries / Aggressive Upward Trend",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 33,
        "name": "Orderly Sell Off / Hedged Bear Market",
        // Source: Add Wk 62 row 19
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes / Downward Drift",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 34,
        "name": "Fragile Vanna-Hollow Melt-Up / Fragile Drift",
        // Source: Add Wk 62 row 20
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional — should become Momentum Chaser / Trend Day if IV stays flat or rises",
        "action": "Forced Buying / Lazy Squeeze",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries / Fragile Upside",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 35,
        "name": "Volatility-Capped Slide / The Gamma Trap (in Reverse)",
        // Source: Add Wk 62 row 21
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day (Fading)",
        "action": "Chasing",
        "actionDirection": "Trade in direction of the move",
        "tilt": "Spot Down + VIX Flat: Dealers Sell. Spot Down + VIX Exploding: Dealers Confused/Neutral. Spot Up + VIX Dropping: Dealers Aggressive Buyers.",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 36,
        "name": "Possible Volatility Expansion Engine (If IV Wakes Up)",
        // Source: Add Wk 62 row 22
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "BUY / SELL",
        "tilt": "Fade Extremes / Binary Breakdown-Breakout",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "Straddle / Strangles",
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 37,
        "name": "Orderly Bear Drift / Mean-Reverting Slide",
        // Source: Add Wk 62 row 23
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "Dealer Hedging Downside Moves",
        "actionDirection": "BUY / SELL",
        "tilt": "Drifting Lower",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": "Iron Condors / PCS",
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks",
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 38,
        "name": "Vanna-Fueled Melt Up / Expansion",
        // Source: Add Wk 62 row 24
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },

    // ═══════════════════════════════════════════════════════════════════
    //  HIGH IV — SUPPLEMENTAL (Dealers Action rows not yet captured)
    // ═══════════════════════════════════════════════════════════════════

    {
        "id": 39,
        "name": "Vol Spike with Spot Resilience",
        // Source: Dealers Action row 35
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Trend Day",
        "action": "Supportive Buyers",
        "actionDirection": "BUY",
        "tilt": "Momentum, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    // ═══════════════════════════════════════════════════════════════════
    //  ML DISCOVERED STRUCTURES (gbm_greeks/interaction_matrix.xlsx)
    // ═══════════════════════════════════════════════════════════════════

    // -- Top 5 Bullish Discovered --
    {
        "id": 40,
        "name": "Machine-Driven Short Squeeze",
        // ML: IV=High | Gamma- | Zomma- | Delta+ | Vex+ | Vega+ | Vomma+ | Speed- (Edge: 0.0549)
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Expansion",
        "action": "Aggressive Chasing",
        "actionDirection": "BUY",
        "tilt": "Momentum Breakout, High Probability Upside",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "Long Calls / PCS",
        "entry": null, "emas": "5DMA/15DMA", "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 41,
        "name": "Vanna Convexity Ignition",
        // ML: IV=High | Gamma+ | Zomma+ | Delta+ | Vex- | Vega+ | Vomma+ | Speed+ (Edge: 0.0495)
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": true, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": "Works on Pullbacks", "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 42,
        "name": "Delta-Negative Melt Up",
        // ML: IV=High | Gamma+ | Zomma+ | Delta- | Vex+ | Vega+ | Vomma+ | Speed+ (Edge: 0.0235)
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional / Expansion",
        "action": "Dealer Hedging Upside",
        "actionDirection": "BUY",
        "tilt": "Strong Underlying Bid despite negative delta",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": null,
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 43,
        "name": "High Volatility Grind Up",
        // ML: IV=High | Gamma+ | Zomma+ | Delta+ | Vex+ | Vega+ | Vomma+ | Speed- (Edge: 0.0194, N=1494)
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Supportive Buyers",
        "actionDirection": "BUY",
        "tilt": "Steady Uptrend, Buying Dips",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "PCS",
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 44,
        "name": "Gamma Drain Short Squeeze",
        // ML: IV=High | Gamma- | Zomma+ | Delta+ | Vex- | Vega+ | Vomma+ | Speed+ (Edge: 0.0193, N=3259)
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Forced Covering",
        "actionDirection": "BUY",
        "tilt": "Momentum Chasing",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null, "emas": "5DMA/15DMA", "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": "Vol crush", "trendEliminator": null
    },

    // -- Top 5 Bearish Discovered --
    {
        "id": 45,
        "name": "The Silent Trap / High Probability Breakdown",
        // ML: IV=Low | Gamma- | Zomma- | Delta+ | Vex+ | Vega+ | Vomma+ | Speed+ (Edge: -0.0941)
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional (To Trend Down)",
        "action": "Aggressive Dealer Selling",
        "actionDirection": "SELL",
        "tilt": "High Danger of Violent Breakdown",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "Long Puts / CCS",
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": "VIX Up", "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 46,
        "name": "Negative Convexity Cascade",
        // ML: IV=Low | Gamma- | Zomma+ | Delta+ | Vex+ | Vega+ | Vomma+ | Speed+ (Edge: -0.0695)
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day (Violent Down)",
        "action": "Forced Selling",
        "actionDirection": "SELL",
        "tilt": "Momentum Downside, Do not catch falling knives",
        "flags": { "max_vanna_level": true, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 47,
        "name": "False Breakout Fail",
        // ML: IV=Low | Gamma+ | Zomma+ | Delta+ | Vex- | Vega+ | Vomma+ | Speed- (Edge: -0.0574)
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Dealer Fades Rally",
        "actionDirection": "SELL",
        "tilt": "Fade Upside Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": true },
        "spreads": null,
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 48,
        "name": "High IV Liquidation Failure",
        // ML: IV=High | Gamma+ | Zomma+ | Delta- | Vex- | Vega+ | Vomma+ | Speed+ (Edge: -0.0506)
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Selling Pressure",
        "actionDirection": "SELL",
        "tilt": "Trend Down despite Positive Gamma",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": null,
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 49,
        "name": "Vol-Expansion Downward Slide",
        // ML: IV=Low | Gamma- | Zomma+ | Delta+ | Vex- | Vega+ | Vomma+ | Speed+ (Edge: -0.0463, N=3306)
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression -> Transition",
        "action": "Selling into Rips",
        "actionDirection": "SELL",
        "tilt": "Mean Reverting Downward",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "CCS",
        "entry": null, "emas": null, "approxBouncePts": null,
        "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    }
];


// ─────────────────────────────────────────────────────────────────────────────
//  IV STATE LOGIC
//  Source: "Dealers Action" sheet, rows 1–5
//
//  Rules (in order):
//   1. VIX Current < VIX Open            → LOW
//   2. VIX Current > VIX Prev Close      → HIGH
//   3. Otherwise                         → LOW  (fallback)
//
//  Additional momentum overlay (rows 2–3):
//   - VIX 5MA vs 15MA:  Up → Trend Day regime confirmation
//   - Regime Change threshold: 0.433696 (stored in cell D3)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Determine IV state from VIX levels.
 * @param {number} vixCurrent   - Current VIX spot price
 * @param {number} vixOpen      - VIX opening price for the session
 * @param {number} vixPrevClose - VIX previous session close
 * @returns {"High"|"Low"}
 */

/*
function getIVState(vixCurrent, vixOpen, vixPrevClose) {
    if (vixCurrent !== null && vixOpen !== null && vixPrevClose !== null) {
        if (vixCurrent < vixOpen) return "Low";
        if (vixCurrent > vixPrevClose) return "High";
    }
    return "Low"; // conservative fallback
}
*/
/**
 * Determine IV state aligned with ML training logic (Dynamic Median/Average proxy).
 * @param {number} currentIV    - Current implied volatility (VIX spot or ATM IV)
 * @param {number} dynamicMean  - The dynamic average/median for the session (e.g., EMA20 or Daily Median)
 * @returns {"High"|"Low"}
 */
function getIVState(currentIV, dynamicMean) {
    // Si tenemos ambos datos, evaluamos como el modelo de LightGBM: 
    // ¿Está el IV actual por encima de la tendencia/mediana central?
    if (currentIV !== null && dynamicMean !== null) {
        if (currentIV > dynamicMean) {
            return "High";
        } else {
            return "Low";
        }
    }

    // Fallback de seguridad si faltan datos
    return "Low";
}
/**
 * VIX momentum confirmation (from "Dealers Action" rows 2–3).
 * Returns the momentum label and regime change signal.
 * @param {number} vix5ma  - VIX 5-period moving average
 * @param {number} vix15ma - VIX 15-period moving average
 * @param {number} [regimeChangeThreshold=0.433696]
 * @returns {{ direction: "Up"|"Down"|"Flat", isRegimeChange: boolean }}
 */
function getVIXMomentum(vix5ma, vix15ma, regimeChangeThreshold = 0.433696) {
    if (vix5ma === null || vix15ma === null) return { direction: "Flat", isRegimeChange: false };
    const diff = vix5ma - vix15ma;
    return {
        direction: diff > 0 ? "Up" : diff < 0 ? "Down" : "Flat",
        isRegimeChange: Math.abs(diff) >= regimeChangeThreshold
    };
}


// ─────────────────────────────────────────────────────────────────────────────
//  EMA UTILITIES  (unchanged from original)
// ─────────────────────────────────────────────────────────────────────────────

function calculateEMA(prices, period) {
    if (!prices || prices.length === 0) return null;
    const multiplier = 2 / (period + 1);
    let ema = prices[0];
    for (let i = 1; i < prices.length; i++) {
        ema = (prices[i] - ema) * multiplier + ema;
    }
    return ema;
}

function resampleTo5Min(series1m) {
    if (!series1m || series1m.length === 0) return [];
    const closes = [];
    for (let i = 0; i < series1m.length; i += 5) {
        const endIndex = Math.min(i + 4, series1m.length - 1);
        const c = series1m[endIndex].price ?? series1m[endIndex].close;
        if (c !== undefined && c !== null) closes.push(c);
    }
    return closes;
}


// ─────────────────────────────────────────────────────────────────────────────
//  TECHNICALS FETCH  (unchanged from original, IV state now uses getIVState())
// ─────────────────────────────────────────────────────────────────────────────

async function fetchTechnicals(dateStr) {
    let vixOpen = null, vix9dValue = null, vixEMA20 = null, vixEMA5 = null, vixEMA15 = null, vixPrevClose = null;

    try {
        const vixIB = await fetchIBData("VIX", dateStr);
        if (vixIB?.series?.length > 0) {
            const startMarket = vixIB.series.find(d => d.time >= "09:30");
            vixOpen = startMarket
                ? (startMarket.open ?? startMarket.price)
                : (vixIB.series[0].open ?? vixIB.series[0].price);
            const vix5m = resampleTo5Min(vixIB.series);
            // VIX EMAs — used for IV State (VIX vs its own EMA20) and Momentum (EMA5 vs EMA15)
            vixEMA20 = calculateEMA(vix5m, 20);
            vixEMA5 = calculateEMA(vix5m, 5);
            vixEMA15 = calculateEMA(vix5m, 15);
            vix9dValue = vixIB.series[vixIB.series.length - 1].price;
        }

        // VIX9D — only use for the 9-day VIX value, do NOT overwrite VIX EMAs
        // Previously this was overwriting vixEMA20 with VIX9D's EMA20, causing
        // the IV state to compare VIX spot against VIX9D EMA20 (different instruments).
        const vix9dIB = await fetchIBData("VIX9D", dateStr);
        if (vix9dIB?.series?.length > 0) {
            vix9dValue = vix9dIB.series[vix9dIB.series.length - 1].price;
        }

        const vixLive = await fetchChartData("VIX", "weekly");
        if (vixLive?.prev_close_price !== undefined) vixPrevClose = vixLive.prev_close_price;

    } catch (e) {
        console.warn("Error fetching VIX technicals", e);
    }

    let spotEMA20 = null, spotEMA50 = null;
    try {
        const spxIB = await fetchIBData("SPX", dateStr);
        if (spxIB?.series?.length > 0) {
            const spx5m = resampleTo5Min(spxIB.series);
            spotEMA20 = calculateEMA(spx5m, 20);
            spotEMA50 = calculateEMA(spx5m, 50);
        }
    } catch (e) {
        console.warn("Error fetching SPX technicals", e);
    }

    return { vixOpen, vixPrevClose, vixEMA20, vixEMA5, vixEMA15, vix9dValue, spotEMA20, spotEMA50 };
}


// ─────────────────────────────────────────────────────────────────────────────
//  GREEK FETCH  (unchanged from original)
// ─────────────────────────────────────────────────────────────────────────────

async function fetchNetGreeksLive(ticker) {
    const greeks = ["gamma", "zomma", "delta", "vex", "vega", "vomma", "speed", "charm"];
    const net = {};
    for (const g of greeks) net[g] = 0;

    try {
        const resp = await authFetch('/get_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify([{ ticker, exp: "0dte" }])
        });
        const batchData = await resp.json();

        for (const g of greeks) {
            const dataKey = `${ticker.toUpperCase()}_0dte`;
            if (batchData[dataKey]) {
                const optData = batchData[dataKey].option_data;
                const colMetric = optData.columns.findIndex(c =>
                    c.trim() === `total_${g}` || c.trim() === g);
                const colStrike = optData.columns.findIndex(c =>
                    ["strike_price", "strike"].includes(c.trim().toLowerCase()));

                if (colMetric !== -1) {
                    let sum = 0, maxVal = -Infinity, strikeAtMax = 0;
                    optData.data.forEach(r => {
                        const val = parseFloat(r[colMetric]) || 0;
                        sum += val;
                        if (g === "vanna" && val > maxVal) {
                            maxVal = val;
                            strikeAtMax = parseFloat(r[colStrike]) || 0;
                        }
                    });
                    net[g] = sum;
                    if (g === "vanna") net["max_vanna_strike"] = strikeAtMax;
                }
            }
        }
    } catch (e) {
        console.warn("Error fetching live greeks for MS Engine", e);
    }

    return net;
}


// ─────────────────────────────────────────────────────────────────────────────
//  MAIN ENGINE
// ─────────────────────────────────────────────────────────────────────────────

async function runMarketStructureEngine(ticker = "SPX") {
    const now = new Date();
    const todayStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;

    // 1. Fetch technicals
    const tech = await fetchTechnicals(todayStr);

    // 2. Fetch net greeks
    const netGreeks = await fetchNetGreeksLive(ticker);

    // 3. Layer 1 — IV State (uses Excel logic from "Dealers Action")
    let vixCurrent = tech.vix9dValue;
    try {
        const vixLive = await fetchChartData("VIX", "weekly");
        if (vixLive?.spot_price) vixCurrent = vixLive.spot_price;
    } catch (_) { }

    //const ivState = getIVState(vixCurrent, tech.vixOpen, tech.vixPrevClose);
    const ivState = getIVState(vixCurrent, tech.vixEMA20);

    // 4. VIX Momentum overlay (rows 2–3 of "Dealers Action")
    const vixMomentum = getVIXMomentum(
        tech.vixEMA5,       // proxy for 5MA (calculated from 5m bars)
        tech.vixEMA15,      // NOTE: replace with a true 15MA source if available
        0.15             // regime change threshold from cell D3
    );

    // 5. Build conditions matrix
    const currentConditions = {
        IV: ivState,
        Gamma: netGreeks.gamma >= 0 ? "Pos" : "Neg",
        Zomma: netGreeks.zomma >= 0 ? "Pos" : "Neg",
        Delta: netGreeks.delta >= 0 ? "Pos" : "Neg",
        Vex: netGreeks.vex >= 0 ? "Pos" : "Neg",
        Vega: netGreeks.vega >= 0 ? "Pos" : "Neg",
        Vomma: netGreeks.vomma >= 0 ? "Pos" : "Neg",
        Speed: netGreeks.speed >= 0 ? "Pos" : "Neg"
    };

    // 6. Match structure (null fields are wildcards)
    let matchedStructure = MARKET_STRUCTURES.find(s =>
        s.condition.IV === currentConditions.IV &&
        s.condition.Gamma === currentConditions.Gamma &&
        s.condition.Zomma === currentConditions.Zomma &&
        s.condition.Delta === currentConditions.Delta &&
        s.condition.Vex === currentConditions.Vex &&
        s.condition.Vega === currentConditions.Vega &&
        (s.condition.Vomma === null || s.condition.Vomma === currentConditions.Vomma) &&
        (s.condition.Speed === undefined || s.condition.Speed === null || s.condition.Speed === currentConditions.Speed)
    );

    // 7. Vanna proximity tagging
    let vannaTagging = false;
    if (netGreeks.max_vanna_strike) {
        // realSpotSPX should be provided by the caller context
        const spotPrice = (typeof realSpotSPX !== "undefined") ? realSpotSPX : 0;
        if (spotPrice > 0 && Math.abs(spotPrice - netGreeks.max_vanna_strike) < 6) {
            vannaTagging = true;
        }
    }

    // 8. Fallback if no match
    if (!matchedStructure) {
        matchedStructure = {
            id: 0,
            name: "UNCLASSIFIED STRUCTURE",
            regime: "UNKNOWN",
            action: "Monitor",
            actionDirection: "N/A",
            tilt: "UNKNOWN",
            flags: { max_vanna_level: false, ib_bounce: false, dadu_pinning: false },
            spreads: null, entry: null, emas: null, approxBouncePts: null,
            stochastic: null, vvixVix: null, reversalSignal: null, trendEliminator: null,
            isFallback: true
        };
    }

    // 9. Layer 3 — Spot & VIX9D technical confirmation
    let layer3Warning = null;
    let spotRegime = "Compression";
    if (tech.spotEMA20 !== null && tech.spotEMA50 !== null) {
        if (tech.spotEMA20 > tech.spotEMA50) {
            spotRegime = (tech.vix9dValue !== null && tech.vixEMA20 !== null && tech.vix9dValue > tech.vixEMA20)
                ? "Expansion" : "Compression";
        }
    }

    if ((matchedStructure.regime?.includes("Expansion") || matchedStructure.regime === "Trend Day") &&
        spotRegime === "Compression") {
        layer3Warning = "REGIME MISMATCH - CAUTION";
    }

    return {
        structure: matchedStructure,
        conditions: currentConditions,
        warning: layer3Warning,
        technicals: tech,
        vixMomentum,
        vannaTagging,
        maxVannaStrike: netGreeks.max_vanna_strike,
        netCharm: netGreeks.charm || 0
    };
}


// ─────────────────────────────────────────────────────────────────────────────
//  UI RENDERER  (unchanged logic, extended for new fields)
// ─────────────────────────────────────────────────────────────────────────────

async function updateMarketStructureUI() {
    const role = sessionStorage.getItem("gex_user_role");
    if (role !== "ADMIN") return;

    const parentContainer = document.getElementById("market-structure-panel");
    if (!parentContainer) return;

    parentContainer.classList.add("ms-loading");
    document.getElementById("ms-structure-name").innerHTML = '<div class="loader"></div> Calculating Matrix...';
    document.getElementById("ms-dealer-action").innerText = '';
    document.getElementById("ms-tilt-tag").style.display = 'none';
    document.getElementById("ms-flags-container").innerHTML = '';
    document.getElementById("ms-warning").style.display = 'none';
    const detailsEl = document.getElementById("ms-details-container");
    if (detailsEl) detailsEl.innerHTML = '';

    try {
        const result = await runMarketStructureEngine("SPX");
        parentContainer.classList.remove("ms-loading");

        const struct = result.structure;
        const cond = result.conditions;

        // — Name
        const nameEl = document.getElementById("ms-structure-name");
        nameEl.innerText = struct.name;
        nameEl.style.color = struct.isFallback ? "var(--accent-yellow, #FFD700)" : "white";

        // — Dealer action + direction badge
        const dirColors = {
            'BUY': '#00C853', 'SELL': '#FF1744', 'CHOP': '#FFA726',
            'BINARY': '#AB47BC', 'SIDEWAYS GRIND': '#FFA726',
            'BUY / PIN': '#00C853', 'SELL / PIN': '#FF1744',
            'CHOP -> SELL': '#FF6D00', 'SELL LEAN': '#FF5252',
            'BUY (Transition)': '#69F0AE', 'BUY / SELL': '#42A5F5',
            'Trade in direction of the move': '#FFA726',
            'N/A': '#666'
        };
        const dealerEl = document.getElementById("ms-dealer-action");
        if (struct.actionDirection) {
            const dirColor = dirColors[struct.actionDirection] || '#888';
            dealerEl.innerHTML = `${struct.action} <span style="display:inline-block;margin-left:6px;padding:1px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;background:${dirColor};color:#fff;letter-spacing:0.5px;">${struct.actionDirection}</span>`;
        } else {
            dealerEl.innerText = struct.action;
        }

        // — Tilt tag
        const tiltEl = document.getElementById("ms-tilt-tag");
        tiltEl.innerText = struct.tilt;
        tiltEl.style.display = 'inline-block';
        if (struct.tilt.includes("Momentum") || struct.tilt.includes("Trend Day")) {
            tiltEl.style.background = 'var(--pos-high, #00FF00)'; tiltEl.style.color = '#000';
        } else if (struct.tilt.includes("Fade") || struct.tilt.includes("PIN")) {
            tiltEl.style.background = 'var(--accent-blue, #1E90FF)'; tiltEl.style.color = '#fff';
        } else if (struct.tilt.includes("Do not trade")) {
            tiltEl.style.background = '#FF1744'; tiltEl.style.color = '#fff';
        } else if (struct.tilt.includes("High Risk")) {
            tiltEl.style.background = '#FF6D00'; tiltEl.style.color = '#fff';
        } else if (struct.tilt.includes("Asymmetric") || struct.tilt.includes("Fragile")) {
            tiltEl.style.background = '#AB47BC'; tiltEl.style.color = '#fff';
        } else {
            tiltEl.style.background = 'var(--panel-bg, #2A2A2A)'; tiltEl.style.color = '#fff';
        }

        // — Cause data array
        const causeListEl = document.getElementById("ms-cause-list");
        if (causeListEl) {
            const ivClass = cond.IV === 'High' ? 'ms-cause-high' : 'ms-cause-low';
            let causesHTML = `<div class="ms-cause-item">IV: <span class="${ivClass}">${cond.IV}</span></div>`;
            ['Gamma', 'Zomma', 'Delta', 'Vex', 'Vega', 'Vomma', 'Speed'].forEach(g => {
                const val = cond[g];
                const cls = val === 'Pos' ? 'ms-cause-pos' : 'ms-cause-neg';
                causesHTML += `<div class="ms-cause-item">${g.substring(0, 3)}: <span class="${cls}">${val}</span></div>`;
            });
            if (result.warning) {
                causesHTML += `<div class="ms-cause-item" style="width:100%;color:var(--accent-yellow);margin-top:2px;">Tech: Mismatch</div>`;
            } else {
                causesHTML += `<div class="ms-cause-item" style="width:100%;color:#aaa;margin-top:2px;">Trend Confirmed</div>`;
            }
            // VIX Momentum (from Excel "Dealers Action" rows 2–3)
            if (result.vixMomentum) {
                const mColor = result.vixMomentum.direction === 'Up' ? '#FF5252' : result.vixMomentum.direction === 'Down' ? '#69F0AE' : '#aaa';
                causesHTML += `<div class="ms-cause-item" style="width:100%;color:${mColor};margin-top:2px;">VIX Momentum: ${result.vixMomentum.direction}${result.vixMomentum.isRegimeChange ? ' ⚡ Regime Change' : ''}</div>`;
            }
            causeListEl.innerHTML = causesHTML;
        }

        // — Flags
        const flagsContainer = document.getElementById("ms-flags-container");
        flagsContainer.innerHTML = '';
        if (struct.flags) {
            if (struct.flags.max_vanna_level)
                flagsContainer.innerHTML += `<span class="ms-badge badge-vanna">WATCH: Max Vanna Level</span>`;
            if (struct.flags.ib_bounce)
                flagsContainer.innerHTML += `<span class="ms-badge badge-ib">WATCH: Sup/Res Bounce Level</span>`;
            if (struct.flags.dadu_pinning)
                flagsContainer.innerHTML += `<span class="ms-badge badge-dadu">Dadu Pinning Active</span>`;
        }

        // — Trading details
        const detailsContainer = document.getElementById("ms-details-container");
        if (detailsContainer) {
            let detailsHTML = '';
            if (struct.regime && struct.regime !== 'UNKNOWN') {
                const regimeColor = struct.regime.includes('Trend Day') ? '#00E676' :
                    struct.regime.includes('Compression') ? '#42A5F5' :
                        struct.regime.includes('Transitional') ? '#AB47BC' :
                            struct.regime.includes('Expansion') ? '#FF9100' : '#888';
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">Regime</span><span class="ms-detail-value" style="color:${regimeColor}">${struct.regime}</span></div>`;
            }
            if (struct.spreads && struct.spreads !== 'N/A' && struct.spreads !== 'No')
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">Spreads</span><span class="ms-detail-value">${struct.spreads}</span></div>`;

            // — Net Charm box
            // Positive (+) charm → time decay increases delta for ITM calls/OTM puts → induces SELLING
            // Negative (-) charm → time decay decreases delta for ITM puts/OTM calls → induces BUYING
            const netCharmVal = result.netCharm || 0;
            const isSuppressive = netCharmVal > 0;
            const charmLabel = isSuppressive ? 'SUPPRESSIVE' : 'SUPPORTIVE';
            const charmColor = isSuppressive ? '#FF5252' : '#69F0AE';
            const charmDesc = isSuppressive
                ? 'Time decay induces dealer selling pressure'
                : 'Time decay induces dealer buying pressure';
            detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;border:1px solid ${charmColor}33;border-radius:6px;padding:8px 10px;background:${charmColor}11;">`
                + `<span class="ms-detail-label" style="color:${charmColor};">Net Charm</span>`
                + `<span class="ms-detail-value" style="color:${charmColor};font-weight:700;font-size:0.9rem;">${charmLabel}</span>`
                + `<div style="color:#aaa;font-size:0.65rem;margin-top:3px;">${charmDesc} (${netCharmVal >= 0 ? '+' : ''}${netCharmVal.toFixed(4)})</div>`
                + `</div>`;

            detailsContainer.innerHTML = detailsHTML;
        }

        // — Warning & Vanna Tagging
        const warningEl = document.getElementById("ms-warning");
        if (result.vannaTagging) {
            warningEl.innerHTML = `⚠️ VANNA TAGGED: FRAGILE VOL ZONE (${result.maxVannaStrike})`;
            warningEl.style.background = "#FF1744";
            warningEl.style.color = "white";
            warningEl.style.display = 'block';
        } else if (result.warning) {
            warningEl.innerText = result.warning;
            warningEl.style.background = "rgba(255, 109, 0, 0.2)";
            warningEl.style.color = "var(--accent-yellow)";
            warningEl.style.display = 'block';
        } else {
            warningEl.style.display = 'none';
        }

    } catch (e) {
        console.error("Failed to update Market Structure UI", e);
        parentContainer.classList.remove("ms-loading");
        document.getElementById("ms-structure-name").innerText = "ENGINE ERROR";
    }
}