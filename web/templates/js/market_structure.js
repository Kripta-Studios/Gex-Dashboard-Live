/**
 * Market Structure Engine
 * Evaluates options flow and market data to classify into 13 distinct Market Structures.
 */

// 23 Market Structures Matrix
const MARKET_STRUCTURES = [
    // ═══════════════════════════════════════════════════════════════════
    //  HIGH IV STRUCTURES
    // ═══════════════════════════════════════════════════════════════════
    {
        "id": 1,
        "name": "The Waterfall",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Selling",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": "5DEMA/15DEMA", "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 2,
        "name": "Mean Reversion",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 3,
        "name": "The Melt Up",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": null, "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": "5DEMA/15DEMA", "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 4,
        "name": "The Drag",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 5,
        "name": "Vol of Vol / Fragile Long Vol",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Trend Day",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Momentum, Pull backs are entries",
        "flags": { "max_vanna_level": true, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "CCS", "entry": "Short Max Vanna", "emas": "8/20", "approxBouncePts": "40 pts", "stochastic": null, "vvixVix": null, "reversalSignal": "Change in Max Vanna", "trendEliminator": null
    },
    {
        "id": 6,
        "name": "Liquidation",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Selling",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 7,
        "name": "Pinned long vol",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Transitional",
        "action": "Dealer is Binary. Buys until the pin snaps, then aggressively SELLS.",
        "actionDirection": "BINARY",
        "tilt": "Do not trade",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "N/A", "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 8,
        "name": "Vol-expansion pre-trend",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Trend Day",
        "action": "Sell into Rally",
        "actionDirection": "SELL",
        "tilt": "Fade extremes while gamma exists",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": "5DEMA/15DEMA", "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 9,
        "name": "Directionless Chop - Slight Bid",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Compression",
        "action": "Passive Buyers",
        "actionDirection": "CHOP",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 10,
        "name": "Short Bearish Gamma Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Sellers",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": "5DEMA/15DEMA", "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 11,
        "name": "Negative Convexity Vol Unwind (Compression Type)",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "High Risk - Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 12,
        "name": "Negative Convexity Vol Unwind (Expansion Type)",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "Momentum, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": "5DEMA/15DEMA", "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 13,
        "name": "The Gamma Trap / Crash-to-Melt Vanna",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Transitional / Expansion",
        "action": "Binary at open.",
        "actionDirection": "BINARY",
        "tilt": "Do not trade / Scalp Only",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "No", "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    // ═══════════════════════════════════════════════════════════════════
    //  LOW IV STRUCTURES
    // ═══════════════════════════════════════════════════════════════════
    {
        "id": 14,
        "name": "The Melt Up (Low IV)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Momentum, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": "PCS", "entry": null, "emas": "8/20", "approxBouncePts": null, "stochastic": "Yes - Works on Pullbacks", "vvixVix": "VIX Down, VVIX Down", "reversalSignal": "Change in Max Vanna", "trendEliminator": "Short upside calls"
    },
    {
        "id": 15,
        "name": "The Fade",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 16,
        "name": "V Bottom",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": null },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Trend Day, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 17,
        "name": "The Bleed",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": null, "Speed": null },
        "regime": "Compression",
        "action": "Dealer Sells",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 18,
        "name": "Volatility Mean Reversion Sideways Grind",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": null },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "SIDEWAYS GRIND",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 19,
        "name": "Volatility Mean Reversion Crush",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Compression",
        "action": "Buy the Dip / Sell the Rally",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 20,
        "name": "The Ceiling / The Call Pin",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Compression",
        "action": "Forced Sellers on Rips. Break of Pin on flat IV is a genuine breakout — do not fade otherwise causes snapback",
        "actionDirection": "SELL / PIN",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": "Break of Pin on flat IV is genuine breakout", "trendEliminator": null
    },
    {
        "id": 21,
        "name": "High Confidence Grind / PIN",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": null },
        "regime": "Compression",
        "action": "Supportive Buyers",
        "actionDirection": "BUY / PIN",
        "tilt": "Fade Extremes / PIN",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 22,
        "name": "Vanna-fueled Melt Up",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Momentum, Pull backs are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": true },
        "spreads": "PCS", "entry": null, "emas": "8/20", "approxBouncePts": null, "stochastic": "Yes - Works on Pullbacks", "vvixVix": "VIX Down, VVIX Down", "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 23,
        "name": "Pre-breakout Convexity Pocket / Gamma Squeeze",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": null },
        "regime": "Compression",
        "action": "Forced Buying",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    // ═══════════════════════════════════════════════════════════════════
    //  NEW EXTENDED STRUCTURES (N1-N14)
    // ═══════════════════════════════════════════════════════════════════
    {
        "id": 24,
        "name": "Bear trend coiled in a gamma pin / Pre breakdown structure",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Selling Pressure in Chop",
        "actionDirection": "CHOP -> SELL",
        "tilt": "Selling into Pin",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 25,
        "name": "Short Bearish Gamma Squeeze (Extended)",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Forced Selling / Liquidations",
        "actionDirection": "SELL",
        "tilt": "Trend Day, Aggressive Sells",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 26,
        "name": "Low IV positive gamma grind (mean-reverting compression)",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Passive Selling / Sideways",
        "actionDirection": "SELL LEAN",
        "tilt": "Mean Reverting",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 27,
        "name": "Compression regime with asymmetric vol expansion payoff",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Bullish Bias in Compression",
        "actionDirection": "BUY",
        "tilt": "Asymmetric Risk/Reward",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 28,
        "name": "Short Gamma Trap / Melt up",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Forced Buying on Trap",
        "actionDirection": "BUY",
        "tilt": "Momentum, Squeeze Potential",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "PCS / Long Calls", "entry": null, "emas": null, "approxBouncePts": null, "stochastic": "Yes - High Confidence", "vvixVix": "VIX Down, VVIX Down", "reversalSignal": "Gamma shift or spot stall", "trendEliminator": null
    },
    {
        "id": 29,
        "name": "Vanna Fueled Melt Up / Pre Gamma Squeeze",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "Stable Drift Up",
        "actionDirection": "BUY (Compression)",
        "tilt": "Slow Grind",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 30,
        "name": "The Waterfall Sell Off",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Aggressive Liquidations",
        "actionDirection": "SELL",
        "tilt": "High Volatility Sell",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 31,
        "name": "The Mean Reversion Anchor",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "Buying the Dips / Selling the Rallies",
        "actionDirection": "SELL/BUY",
        "tilt": "Range Bound High Vol",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 32,
        "name": "Short-Vol Capitulation / The Melt Up",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "Shorts Covering / Panicked Buying",
        "actionDirection": "BUY",
        "tilt": "Aggressive Upward Trend",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 33,
        "name": "Orderly Sell Off / Hedged Bear Market",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Managed Portfolios Hedging",
        "actionDirection": "SELL",
        "tilt": "Downward Drift",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 34,
        "name": "Fragile Vanna-Hollow Melt-Up / Fragile Drift",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "Unstable Buying",
        "actionDirection": "BUY",
        "tilt": "Fragile Upside",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 35,
        "name": "Volatility-Capped Slide / The Gamma Trap (in Reverse)",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Expansion",
        "action": "Selling Pressure with Vol Cap",
        "actionDirection": "Trade in direction",
        "tilt": "Binary - Watch Spreads",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null, "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 36,
        "name": "Possible Volatility Expansion Engine",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Expansion",
        "action": "Vol Coiling for Expansion",
        "actionDirection": "BUY/SELL",
        "tilt": "Binary Breakdown/Breakout",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "Straddle / Strangles", "entry": null, "emas": null, "approxBouncePts": null, "stochastic": null, "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    },
    {
        "id": 37,
        "name": "Orderly Bear Drift / Mean-Reverting Slide",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "Dealer Hedging Downside Moves",
        "actionDirection": "BUY/SELL",
        "tilt": "Drifting Lower",
        "flags": { "max_vanna_level": false, "ib_bounce": true, "dadu_pinning": false },
        "spreads": "Iron Condors", "entry": null, "emas": null, "approxBouncePts": null, "stochastic": "Yes", "vvixVix": null, "reversalSignal": null, "trendEliminator": null
    }
];
", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos" },
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
    }
];

/**
 * Utility to calculate EMA from an array of prices
 * @param {Array<number>} prices
 * @param {number} period 
 * @returns {number} The current EMA
 */
function calculateEMA(prices, period) {
    if (!prices || prices.length === 0) return null;
    let multiplier = 2 / (period + 1);
    let ema = prices[0]; // SMA for first day

    for (let i = 1; i < prices.length; i++) {
        ema = (prices[i] - ema) * multiplier + ema;
    }
    return ema;
}

/**
 * Convert 1-minute series to 5-minute candles to calculate EMA
 * @param {Array<Object>} series1m - { time: "HH:MM", price: 123 }
 * @returns {Array<number>} Array of closing prices for each 5m candle
 */
function resampleTo5Min(series1m) {
    if (!series1m || series1m.length === 0) return [];

    let closes = [];
    // We assume data is sorted chronologically
    for (let i = 0; i < series1m.length; i += 5) {
        // Find closing price of the 5-min interval
        // take min between (i+4) and length-1
        let endIndex = Math.min(i + 4, series1m.length - 1);
        let c = series1m[endIndex].price || series1m[endIndex].close;
        if (c !== undefined && c !== null) {
            closes.push(c);
        }
    }
    return closes;
}

/**
 * Returns the VIX Open and technicals based on IB data from backend
 * @param {string} dateStr YYYYMMDD
 * @returns {Promise<Object>} Object containing VIX_Open, spotEMA20, spotEMA50, vixEMA20, vix9d
 */
async function fetchTechnicals(dateStr) {
    // 1. Fetch VIX 1min data
    let vixOpen = null;
    let vix9dValue = null;
    let vixEMA20 = null;
    let vixPrevClose = null;

    try {
        const vixIB = await fetchIBData("VIX", dateStr); // In api.js
        if (vixIB && vixIB.series && vixIB.series.length > 0) {
            // Usually starts at 09:30 or first candle in normal hours
            // Find first element with time >= 09:30
            let startMarket = vixIB.series.find(d => d.time >= "09:30");
            if (startMarket) {
                vixOpen = startMarket.open || startMarket.price;
            } else {
                vixOpen = vixIB.series[0].open || vixIB.series[0].price;
            }
            // For VIX9D, we don't have a direct ticker usually unless available in api, 
            // if we don't have VIX9D ticker, we proxy with VIX Spot price for now as an approximation. 
            // Often VIX9D is another ticker. Let's try to fetch /VX or proxy with VIX
            const vix5m = resampleTo5Min(vixIB.series);
            vixEMA20 = calculateEMA(vix5m, 20);
            vix9dValue = vixIB.series[vixIB.series.length - 1].price;
        }

        // Let's get "VIX9D" if there is IB data for it, else just use VIX
        const vix9dIB = await fetchIBData("VIX9D", dateStr);
        if (vix9dIB && vix9dIB.series && vix9dIB.series.length > 0) {
            vix9dValue = vix9dIB.series[vix9dIB.series.length - 1].price;
            // Recalculate VIX9D EMA
            const vix9d_5m = resampleTo5Min(vix9dIB.series);
            vixEMA20 = calculateEMA(vix9d_5m, 20);
        }

        // Get VIX prev close from the main spot endpoint just to be safe
        const vixLive = await fetchChartData("VIX", "weekly");
        if (vixLive && vixLive.prev_close_price !== undefined) {
            vixPrevClose = vixLive.prev_close_price;
        }

    } catch (e) {
        console.warn("Error fetching VIX technicals", e);
    }

    // 2. Fetch SPX 1min data
    let spotEMA20 = null;
    let spotEMA50 = null;
    try {
        const spxIB = await fetchIBData("SPX", dateStr);
        if (spxIB && spxIB.series && spxIB.series.length > 0) {
            const spx5m = resampleTo5Min(spxIB.series);
            spotEMA20 = calculateEMA(spx5m, 20);
            spotEMA50 = calculateEMA(spx5m, 50);
        }
    } catch (e) {
        console.warn("Error fetching SPX technicals", e);
    }

    return {
        vixOpen,
        vixPrevClose,
        vixEMA20,
        vix9dValue,
        spotEMA20,
        spotEMA50
    };
}

/**
 * Aggregate the Net Greeks from the `/get_latest` output or cached tabs
 * @returns {Object} { gamma, zomma, delta, vex, vega, vomma }
 */
async function fetchNetGreeksLive(ticker) {
    // We can use the batch load pattern or fetch them explicitly
    const greeks = ["gamma", "zomma", "delta", "vex", "vega", "vomma", "speed"];
    let net = {};

    // Default fallback values
    for (let g of greeks) net[g] = 0;

    try {
        // Just fetch '0dte' for intraday flow, or 'all'? We'll fetch 0dte.
        // If the engine requires total sum across exps, we could fetch 'all'

        let batchReq = greeks.map(g => ({
            ticker: ticker,
            exp: "0dte" // You can adjust this if the engine requires a different expiration
        }));

        const uniqueReqs = [...new Set(batchReq.map(JSON.stringify))].map(JSON.parse);
        const resp = await authFetch('/get_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(uniqueReqs)
        });
        const batchData = await resp.json();

        // Calculate Net for each greek (sum over all strikes)
        for (let g of greeks) {
            const dataKey = `${ticker.toUpperCase()}_0dte`;
            if (batchData[dataKey]) {
                const optData = batchData[dataKey].option_data;
                const colMetric = optData.columns.findIndex(c => c.trim() === `total_${g}` || c.trim() === g);
                const colStrike = optData.columns.findIndex(c => c.trim().toLowerCase() === "strike_price" || c.trim().toLowerCase() === "strike");

                if (colMetric !== -1) {
                    let sum = 0;
                    let maxVal = -Infinity;
                    let strikeAtMax = 0;

                    optData.data.forEach(r => {
                        const val = (parseFloat(r[colMetric]) || 0);
                        sum += val;

                        // For Vanna, track the strike where exposure is highest (Max Vanna Level)
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

/**
 * Main function to evaluate the Market Structure
 * @returns {Object} matched structure and any warnings
 */
async function runMarketStructureEngine(ticker = "SPX") {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const todayStr = `${yyyy}${mm}${dd}`;

    // 1. Fetch Technicals
    const tech = await fetchTechnicals(todayStr);

    // 2. Fetch Net Greeks
    const netGreeks = await fetchNetGreeksLive(ticker);

    // 3. Layer 1: Volatility State (The Override)
    let ivState = "LOW";
    // Using current VIX spot vs open and prev close
    let vixCurrent = tech.vix9dValue; // Assuming this maps to current spot contextually or from live SPX / VIX spot
    const vixLive = await fetchChartData("VIX", "weekly");
    if (vixLive && vixLive.spot_price) {
        vixCurrent = vixLive.spot_price;
    }

    if (vixCurrent !== null && tech.vixOpen !== null && tech.vixPrevClose !== null) {
        if (vixCurrent < tech.vixOpen) {
            ivState = "Low";
        } else if (vixCurrent > tech.vixPrevClose) {
            ivState = "High";
        } else {
            ivState = "Low";
        }
    } else {
        ivState = "Low"; // Fallback
    }

    // Construct current conditions matrix
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

    // Match structures — null condition fields act as wildcards (match any value)
    let matchedStructure = MARKET_STRUCTURES.find(s => {
        return (
            s.condition.IV === currentConditions.IV &&
            s.condition.Gamma === currentConditions.Gamma &&
            s.condition.Zomma === currentConditions.Zomma &&
            s.condition.Delta === currentConditions.Delta &&
            s.condition.Vex === currentConditions.Vex &&
            s.condition.Vega === currentConditions.Vega &&
            (s.condition.Vomma === null || s.condition.Vomma === currentConditions.Vomma) &&
            (s.condition.Speed === undefined || s.condition.Speed === null || s.condition.Speed === currentConditions.Speed)
        );
    });

    // 4b. Heuristic Overlay: Vanna Tagging (Fragile Vol)
    let vannaTagging = false;
    if (netGreeks.max_vanna_strike && realSpotSPX > 0) {
        const dist = Math.abs(realSpotSPX - netGreeks.max_vanna_strike);
        if (dist < 6) { // Proximity threshold (e.g., within 6 points)
            vannaTagging = true;
        }
    }

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

    // 5. Layer 3: Spot & VIX9D Technical Confirmation
    let layer3Warning = null;
    let spotRegime = "Compression";
    if (tech.spotEMA20 !== null && tech.spotEMA50 !== null) {
        if (tech.spotEMA20 > tech.spotEMA50) {
            // Check VIX9D as well
            if (tech.vix9dValue !== null && tech.vixEMA20 !== null) {
                if (tech.vix9dValue > tech.vixEMA20) {
                    spotRegime = "Expansion";
                } else {
                    spotRegime = "Compression"; // Condition says AND
                }
            } else {
                spotRegime = "Expansion"; // Assume expansion if only Spot EMA satisfied without VIX9D
            }
        } else {
            spotRegime = "Compression";
        }
    }

    // Mismatch check — "Trend Day" in Excel maps to directional expansion
    if ((matchedStructure.regime.includes("Expansion") || matchedStructure.regime === "Trend Day") && spotRegime === "Compression") {
        layer3Warning = "REGIME MISMATCH - CAUTION";
    }

    return {
        structure: matchedStructure,
        conditions: currentConditions,
        warning: layer3Warning,
        technicals: tech,
        vannaTagging: vannaTagging,
        maxVannaStrike: netGreeks.max_vanna_strike
    };
}

/**
 * Update the UI Widget
 */
async function updateMarketStructureUI() {
    // SECURITY CHECK: Only ADMIN role can run the logic
    const role = sessionStorage.getItem("gex_user_role");
    if (role !== "ADMIN") return;

    const parentContainer = document.getElementById("market-structure-panel");
    if (!parentContainer) return;

    // Show loading state
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

        // Title and fallback colors
        const nameEl = document.getElementById("ms-structure-name");
        nameEl.innerText = struct.name;
        if (struct.isFallback) {
            nameEl.style.color = "var(--accent-yellow, #FFD700)";
        } else {
            nameEl.style.color = "white"; // Or theme color
        }

        // Subtitle: action + direction badge
        const dealerEl = document.getElementById("ms-dealer-action");
        if (struct.actionDirection) {
            const dirColors = {
                'BUY': '#00C853', 'SELL': '#FF1744', 'CHOP': '#FFA726',
                'BINARY': '#AB47BC', 'SIDEWAYS GRIND': '#FFA726',
                'BUY / PIN': '#00C853', 'SELL / PIN': '#FF1744',
                'N/A': '#666'
            };
            const dirColor = dirColors[struct.actionDirection] || '#888';
            dealerEl.innerHTML = `${struct.action} <span style="display:inline-block;margin-left:6px;padding:1px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;background:${dirColor};color:#fff;letter-spacing:0.5px;">${struct.actionDirection}</span>`;
        } else {
            dealerEl.innerText = struct.action;
        }

        // Tilt tag
        const tiltEl = document.getElementById("ms-tilt-tag");
        tiltEl.innerText = struct.tilt;
        tiltEl.style.display = 'inline-block';
        if (struct.tilt.includes("Momentum") || struct.tilt.includes("Trend Day")) {
            tiltEl.style.background = 'var(--pos-high, #00FF00)';
            tiltEl.style.color = '#000';
        } else if (struct.tilt.includes("Fade") || struct.tilt.includes("PIN")) {
            tiltEl.style.background = 'var(--accent-blue, #1E90FF)';
            tiltEl.style.color = '#fff';
        } else if (struct.tilt.includes("Do not trade")) {
            tiltEl.style.background = '#FF1744';
            tiltEl.style.color = '#fff';
        } else if (struct.tilt.includes("High Risk")) {
            tiltEl.style.background = '#FF6D00';
            tiltEl.style.color = '#fff';
        } else {
            tiltEl.style.background = 'var(--panel-bg, #2A2A2A)';
            tiltEl.style.color = '#fff';
        }

        // Cause Data Array
        const causeListEl = document.getElementById("ms-cause-list");
        if (causeListEl) {
            let causesHTML = '';

            // IV State
            const ivClass = cond.IV === 'High' ? 'ms-cause-high' : 'ms-cause-low';
            causesHTML += `<div class="ms-cause-item">IV: <span class="${ivClass}">${cond.IV}</span></div>`;

            // Greeks
            const greeks = ['Gamma', 'Zomma', 'Delta', 'Vex', 'Vega', 'Vomma', 'Speed'];
            greeks.forEach(g => {
                const val = cond[g];
                const cls = val === 'Pos' ? 'ms-cause-pos' : 'ms-cause-neg';
                causesHTML += `<div class="ms-cause-item">${g.substring(0, 3)}: <span class="${cls}">${val}</span></div>`;
            });

            // Regime Technical
            if (result.warning) {
                causesHTML += `<div class="ms-cause-item" style="width:100%; color:var(--accent-yellow); margin-top:2px;">Tech: Mismatch</div>`;
            } else if (result.technicals) {
                causesHTML += `<div class="ms-cause-item" style="width:100%; color:#aaa; margin-top:2px;">Trend Confirmed</div>`;
            }

            causeListEl.innerHTML = causesHTML;
        }

        // Flags
        const flagsContainer = document.getElementById("ms-flags-container");
        flagsContainer.innerHTML = '';
        if (struct.flags) {
            if (struct.flags.max_vanna_level) {
                flagsContainer.innerHTML += `<span class="ms-badge badge-vanna">WATCH: Max Vanna Level</span>`;
            }
            if (struct.flags.ib_bounce) {
                flagsContainer.innerHTML += `<span class="ms-badge badge-ib">WATCH: Sup/Res Bounce Level</span>`;
            }
            if (struct.flags.dadu_pinning) {
                flagsContainer.innerHTML += `<span class="ms-badge badge-dadu">Dadu Pinning Active</span>`;
            }
        }

        // ── Trading Details (new fields from Excel) ──
        const detailsContainer = document.getElementById("ms-details-container");
        if (detailsContainer) {
            let detailsHTML = '';

            // Regime
            if (struct.regime && struct.regime !== 'UNKNOWN') {
                const regimeColor = struct.regime === 'Trend Day' ? '#00E676' :
                    struct.regime === 'Compression' ? '#42A5F5' :
                        struct.regime.includes('Transitional') ? '#AB47BC' : '#888';
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">Regime</span><span class="ms-detail-value" style="color:${regimeColor}">${struct.regime}</span></div>`;
            }

            // Spreads
            if (struct.spreads && struct.spreads !== 'N/A' && struct.spreads !== 'No') {
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">Spreads</span><span class="ms-detail-value">${struct.spreads}</span></div>`;
            }

            // Entry
            if (struct.entry) {
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">Entry</span><span class="ms-detail-value">${struct.entry}</span></div>`;
            }

            // EMAs
            if (struct.emas) {
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">EMAs</span><span class="ms-detail-value">${struct.emas}</span></div>`;
            }

            // Approx Bounce Points
            if (struct.approxBouncePts) {
                detailsHTML += `<div class="ms-detail-item"><span class="ms-detail-label">Bounce</span><span class="ms-detail-value">${struct.approxBouncePts}</span></div>`;
            }

            // Stochastic
            if (struct.stochastic) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1"><span class="ms-detail-label">Stochastic</span><span class="ms-detail-value">${struct.stochastic}</span></div>`;
            }

            // VVIX & VIX
            if (struct.vvixVix) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1"><span class="ms-detail-label">VVIX & VIX</span><span class="ms-detail-value">${struct.vvixVix}</span></div>`;
            }

            // Reversal Signal
            if (struct.reversalSignal) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1"><span class="ms-detail-label">⚠ Reversal</span><span class="ms-detail-value" style="color:var(--accent-yellow,#FFD700)">${struct.reversalSignal}</span></div>`;
            }

            // Trend Eliminator
            if (struct.trendEliminator) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1"><span class="ms-detail-label">⚠ Trend Killer</span><span class="ms-detail-value" style="color:#FF6D00">${struct.trendEliminator}</span></div>`;
            }

            detailsContainer.innerHTML = detailsHTML;
        }

        // Warning & Vanna Tagging
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
