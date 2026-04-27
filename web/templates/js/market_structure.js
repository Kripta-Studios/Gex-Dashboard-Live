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
    {
        "id": 1,
        "name": "Fragile Long Vol / Bearish Vol Expansion Regime with Mean-Reversion at Extremes",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Volatile bearish drift with bounded downside / Mean-reverting within bearish regime",
        "action": "SELL LEAN. Sell the Rally. But DON'T chase breakdowns.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade both extremes but lean short.  Volatile, Expect Whipsaw",
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
        "id": 2,
        "name": "Low-Vol Grind-Up / Melt-Up \u2014 Dealers Comfortable with Upside Drift",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "BUY on Pullback. Pullbacks are generally shallow.",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "CCS",
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
        "name": "High-IV Bearish Pin \u2014 Vanna-Cushioned Drift with Tail Exposure",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Fragile Compression",
        "action": "Fade extremes while pin holds. SELL LEAN on IV expansion \u2014 pin breaks down with no wing catch (Vomma Neg). Ride the break \u2014 no recovery mechanism.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade extremes. On gamma-flip breakdown: SELL trend, ride to exhaustion (no wing catch).",
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
        "id": 4,
        "name": "Low-IV Bearish Drift Pin \u2014 Vanna Cushion Loaded",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Fragile Compression",
        "action": "BUY LEAN - While the market is calm, trade the range \u2014 buy dips, sell rallies, both will mean-revert. If volatility picks up, expect the selloff to be cushioned - but no recovery mechanism.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fadeextremes. On gamma-flip breakdown: SELL trend, ride to exhaustion (no wing catch).",
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
        "name": "High-IV Long Vol Bearish Skew \u2014 Vanna-Cushioned Drift",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "SELL LEAN \u2014 PIN holds with bearish drift. On vol expansion, expect vanna-cushioned descent (not waterfall). Exit on IV peak, not exhaustion \u2014 Vex Pos arrests the move.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade both extremes \u2014 vanna cushion protects downside, pin caps upside.",
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
        "id": 6,
        "name": "Long Vol Convexity Book - Loaded with Vanna Cushion on Downside",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN into PIN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade both extremes \u2014 vanna cushion protects downside, pin caps upside.",
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
        "name": "High-IV Bearish Pin with Pre-Breakdown Structure \u2014 Coiled for downside vol expansion",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression \u2014 Bear-Coiled",
        "action": "SELL LEAN into PIN on IV expansion \u2014 pin breaks down. Chop otherwise.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes while pin holds. On gamma-flip breakdown: SELL trend, ride the bear move.",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": "Break of Gamma Flip"
    },
    {
        "id": 8,
        "name": "Low-IV Bearish Compression \u2014 Loaded for Downside with Wing Convexity Payoff",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression \u2014 Bear-Coiled",
        "action": "AVOID Buys. Neutral / Small SELL LEAN  on rally\u2014 pin holds while vol compressed. Await vol expansion trigger for size.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes with bearish lean. Don't fade downside \u2014 break risk on vol expansion.",
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
        "id": 9,
        "name": "Short-Call Gamma Squeeze \u2014 Upside Cascade at High IV",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day (Upside Squeeze)",
        "action": "AVOID Shorts. BUY LEAN on rally confirmation \u2014 squeeze risk. Vex Neg catches the squeeze at top.",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pullbacks are entries",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Yes -  The moment IV prints a lower high while spot prints a lower low \u2014 that is the turn, regardless of what price action looks like at that moment.",
        "trendEliminator": null
    },
    {
        "id": 10,
        "name": "Dealer Short Gamma Trap \u2014 Loaded for Upside Squeeze",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Dormant- Transitional - Trend Day",
        "action": "BUY LEAN (small) on upside trigger. Avoid shorts \u2014 squeeze loaded. No directional edge in dormant state \u2014 await IV trigger.",
        "actionDirection": "BUY LEAN",
        "tilt": "Transitional \u2014 squeeze loaded. Await entry.",
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
        "id": 11,
        "name": "Dealer-Overwhelmed Bearish Drift \u2014 Pos dealer book absorbs but doesn't reverse external selling",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with bearish drift",
        "action": "SELL LEAN. Dips are Deep & dip-buying is WEAK. Dealer book absorbs but doesn't reverse. Don't fight the external flow.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes. Don't expect bounces on dips.",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Yes -  The moment IV prints a lower high while spot prints a lower low \u2014 that is the turn, regardless of what price action looks like at that moment.",
        "trendEliminator": null
    },
    {
        "id": 12,
        "name": "Bullish Drift Ignition / Melt Up",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with bullish drift",
        "action": "BUY LEAN. Dips are shallow & dip-buying is STRONG. Max-gamma zone acts as magnet above, not ceiling.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes.",
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
        "id": 13,
        "name": "Bearish Pin \u2014 Vol compression with downside drift risk",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression with bearish drift \u2014 downside break risk",
        "action": "SELL LEAN - Neg Vex means IV spikes force additional selling",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes. Don't fade downside \u2014 break risk on vol expansion.",
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
        "id": 14,
        "name": "Low-IV Compression with Bearish Skew \u2014 Fragile Pin",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression with bearish drift \u2014 downside break risk",
        "action": "AVOID BUY. Neutral. Pin likely below (dex neg).  Await the SELL in high IV.  Pin holds while vol compressed but bearish drift within compression \u2014 downside cascade risk (no wing catch).",
        "actionDirection": "SELL",
        "tilt": "Fade upside extremes. Don't fade downside \u2014 break risk on vol expansion.",
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
        "id": 15,
        "name": "The Waterfall Sell- Off",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day no V-recovery, ride to exhaustion.",
        "action": "SELL the breakdown. Trend-follow aggressively. Don't catch the knife but watch for exhaustion.Possible V shape recovery.",
        "actionDirection": "SELL",
        "tilt": "Trend Day , bounces are entries",
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
        "name": "Volmageddon Setup / Complacency Trap",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Dormant - Coiled with Trend Day cascasde Risk",
        "action": "Dormant - Await the SELL.  Expected move is small - Cascade Risk if IV spikes.  Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts.",
        "actionDirection": "SELL",
        "tilt": "Wait for IV wake-up (transition to High IV row). Don't fade the eventual breakdown.",
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
        "name": "High-IV Long Gamma Compression \u2014 Fragile Pin with downside break risk (Vex Neg)",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Fragile Compression \u2014 pin-break risk on IV expansion.",
        "action": "SELL LEAN \u2014 dips are deep. Break-down leads to controlled descent toward wing strike. Slow U, not sharp V. Pre-break level typically not recovered.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes \u2014 break risk on vol expansion.",
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
        "name": "Long Gamma Pin \u2014  downside break on vol expansion",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Fragile Compression \u2014 pin-break risk on IV expansion.",
        "action": "Neutral/Cautious BUY Lean into Pin. Pin holds while vol compressed. Exit on IV expansion \u2014 downside break risk. Don't chase upside",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade upside extremes \u2014 break risk on vol expansion.",
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
        "name": "Compression / Pin Day (with squeeze potential)",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression \u2014 vol-crush risk. Pin until wing breach",
        "action": "Cautious SELL LEAN into PIN. Respect the PIN. Squeeze risk bias to upside.",
        "actionDirection": "SELL LEAN",
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
        "name": "High Confidence Grind / PIN",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN with conviction. Respect the PIN.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes/ PIN",
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
        "id": 21,
        "name": "Possible Short-Cover Cascade / Upside Gamma Squeeze",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Transitional Compression - Trend Day (Violent Upside) with squeeze mechanics. But squeeze requires a catalyst like news.",
        "action": "AVOID Short or size small. Buy dips aggressively \u2014 Squeeze risk to upside. Assumes short-cover catalyst active. Pre-catalyst: pin/range regime.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean (Squeeze risk)",
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
        "name": "Vanna-fueled Melt Up (Index can push far beyond expectations)",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression with upward drift",
        "action": "BUY with conviction \u2014 vanna-fueled melt-up",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": "PCS",
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks. Pullbacks can be decent or small.",
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 23,
        "name": "Short Gamma Cascade / Negative Convexity Unwind with built-in Feedback Loop ( V-recovery mechanism)",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day (Likely Violent) with with built in V-recovery mechanism",
        "action": "SELL the breakdown. Trend-follow aggressively but watch for IV peak \u2014 the tail hedge activates V-recovery earlier than pure Waterfall. Don't ride to exhaustion.",
        "actionDirection": "SELL",
        "tilt": "Trend Day \u2014 pullbacks are entries during the cascade. BUT V-recovery comes faster than Waterfall due to tail activation.",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Yes - Usually Large Gamma Wall",
        "trendEliminator": null
    },
    {
        "id": 24,
        "name": "Low Vol Coiled Spring \u2014 Bearish Skew",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Transitional \u2014 Bearish Bias",
        "action": "Awaiting Trigger/ IV Spike. Minimal hedging pressure in low IV; dealers inactive, gamma dormant, awaiting a vol expansion trigger.",
        "actionDirection": "N/A",
        "tilt": "Neutral",
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
        "id": 25,
        "name": "Active Short-Vol Cascade / Volatile Bearish Drift",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN on rallies. Bearish drift dominant despite Pos Zomma cushion.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
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
        "id": 26,
        "name": "Dormant Short-Vol Collector / Pre-Cascade Setup (Bearish Trigger)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Transitional \u2014 not yet trend day",
        "action": "Small size BUY LEAN in calm (Pos Delta bias). AVOID heavy long positions \u2014 regime is cascade-capable on IV wake-up. Options: buy cheap tail protection",
        "actionDirection": "BUY LEAN",
        "tilt": "Buy dips small in dormant state. Watch IV \u2014 cascade fires bearishly on IV wake-up.",
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
        "name": "Short-Vol Capitulation / Short covering can becom a Melt Up",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "AVOID Shorts. BUY the breakout \u2014 short-covering cascade",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "name": "Pre-Squeeze Setup / Short-Vol Capitulation Primer (Dormant)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Transitional\u2014 dormant pre-squeeze setup (primed for bullish squeeze)",
        "action": "BUY LEAN on dips. Dormant squeeze setup",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean.",
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
        "id": 29,
        "name": "Orderly Sell Off (grind) / Hedged Bear Market",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with bearish drift",
        "action": "SELL LEAN on rallies.",
        "actionDirection": "SELL LEAN",
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
        "id": 30,
        "name": "Hedged Long-Vol Compression / Orderly Grind Higher",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with upside drift",
        "action": "BUY LEAN on dips.",
        "actionDirection": "BUY LEAN",
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
        "id": 31,
        "name": "Active Vanna-Hollow Squeeze / Spot-Vol Correlation Trend Day",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day \u2014 spot-vol correlation dependent (squeeze firing)",
        "action": "BUY LEAN \u2014 melt-up is the baseline. AVOID Shorts. Correlation matrix in Tilt determines tactical direction.",
        "actionDirection": "BUY LEAN",
        "tilt": "Spot Down + VIX Flat: Dealers are Sellers; Spot Down + VIX Exploding: Dealers are Confused/Neutral; Spot Up + VIX Dropping: Dealers are Aggressive Buyers",
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
        "name": "Fragile Vanna-Hollow Melt-Up/ Bullish pre-melt-up squeeze",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional \u2014 not yet trend day",
        "action": "BUY LEAN. Buy the Dip.  Option traders can buy cheap protection.  Profile needs confirmation.",
        "actionDirection": "BUY LEAN",
        "tilt": "Transitional \u2014 not yet trend day. BUY dips small in current dormant state",
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
        "name": "Long convexity, Long volatility / Coiled Spring",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "AVOID the Short. BUY the Dips with conviction. Coiled bullish spring \u2014 upside break most likely, short trades have no edge.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes, waiting for breakout",
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
        "name": "Vanna-fueled Melt Up / Expansion",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with aggressive upside drift (vanna-fueled). Active melt-up",
        "action": "BUY with conviction. Avoid shorts.",
        "actionDirection": "BUY",
        "tilt": "Buy pullbacks aggressively, ride the vanna grind. No structural ceiling.",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": "Yes - Works on Pullbacks",
        "vvixVix": null,
        "reversalSignal": null,
        "trendEliminator": null
    },
    {
        "id": 35,
        "name": "High-IV Call Magnet (Pin) / Active Magnet Grind",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression with mechanical drift into Pin.",
        "action": "SELL LEAN only into pin strike. Neg Speed punishes extension.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes with lean towards PIN",
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
        "name": "Possible Volatility Expansion Setup (If IV wakes up)",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression / coiled pre-expansion. Aggressive upside drift (Pin above)",
        "action": "BUY LEAN with conviction on dips. Coiled setup.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes - Buy dips with upside lean into the coil.",
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
        "id": 37,
        "name": "Machine Driven Short Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "AVOID Shorts. BUY pullbacks aggressively \u2014 squeeze is mechanical. DO NOT CHASE at the highs \u2014 wait for the dip.",
        "actionDirection": "BUY",
        "tilt": "Momentum Breakout, High Probability Upside, Pullbacks are enteries",
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
        "id": 38,
        "name": "Pre-Squeeze Setup / Machine-Driven Squeeze Primer",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Transitional\u2014 dormant, pre-squeeze setup",
        "action": "BUY LEAN on dips. Dormant Bullish squeeze setup.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean.",
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
        "id": 39,
        "name": "Long Convexity Melt-Up",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with upside drift",
        "action": "AVOID Shorts. BUY the dip with conviction.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean",
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
        "id": 40,
        "name": "Pre-Ignition Setup / Low-IV Long-Gamma Compression with Bullish Coil",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with upside drift",
        "action": "BUY LEAN/ Buy the Dip",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean",
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
        "id": 41,
        "name": "High Volatility Grind Up",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with Upside Drift",
        "action": "AVOID Shorts. BUY LEAN on dips. High-IV grind up with IV-crush tailwind.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean. Strong Floor.",
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
        "id": 42,
        "name": "Dealer Long Gamma/ Low Volatility Grind Up",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with Upside Drift",
        "action": "BUY LEAN on dips.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean. Strong Floor.",
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
        "id": 43,
        "name": "Gamma Drain Short Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "BUY",
        "actionDirection": "BUY",
        "tilt": "Momentum Chasing, Trend Day.",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false },
        "spreads": null,
        "entry": null,
        "emas": null,
        "approxBouncePts": null,
        "stochastic": null,
        "vvixVix": null,
        "reversalSignal": "Yes - Usually Large Gamma Wall",
        "trendEliminator": null
    },
    {
        "id": 44,
        "name": "Forced Short Cover /Mechanical Melt Up",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional / Expansion",
        "action": "BUY the Dip/ Pullback",
        "actionDirection": "BUY",
        "tilt": "Strong Underlying Bid despite negative delta",
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
        "id": 45,
        "name": "The Silent Trap / High Probability Breakdown",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional (To Trend Down)",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "id": 46,
        "name": "Hedged Short-Put Book at Low Vol \u2014 Upside Grind, Downside Trap",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "",
        "actionDirection": "N/A",
        "tilt": "",
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
        "id": 47,
        "name": "False Breakout Fail",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "SELL",
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
        "id": 48,
        "name": "High IV Liquidation Failure",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Trend Down despite Positive Gamma",
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
        "id": 49,
        "name": "Vol-Expansion Downward Slide",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Mean Reverting Downward",
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
        "id": 50,
        "name": "Positive Gamma Coil with Bull Volatility Trigger Risk",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with Explosive Bullish Risk",
        "action": "BUY the Dip",
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
        "id": 51,
        "name": "Short Gamma Trap / Forced Melt Up \u2014 self-accelerating via Zomma",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "BUY the Dip (Pull backs are shallow) \u2014 avoid the short, mechanical squeeze",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "id": 52,
        "name": "High-Vol Short-Put Premium Harvest \u2014 Choppy Range with Asymmetric Breakout Paths. Pin gravity near short-put strikes",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression - Volatile Range",
        "action": "SELL LEAN on High IV. Sell (vol)  on Flat IV\u2014 sell premium via strangle / iron condor / put credit spread.",
        "actionDirection": "SELL LEAN",
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
        "id": 53,
        "name": "Long Gamma Environment",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
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
        "id": 54,
        "name": "Negative Delta / Long Gamma",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN (Low IV favours dip buying for IV expansion; floor is thin given Delta Neg + put-heavy \u2014 size accordingly",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with sell bias",
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
        "id": 55,
        "name": "Long Gamma Compression",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "Sell the Rally with caution (ceiling dissolves on breakout)",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes with BUY LEAN.",
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
        "id": 56,
        "name": "Long Gamma Pin",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "BUY",
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
        "id": 57,
        "name": "Long Gamma Compression \u2014 Negative Delta Bias- Ceiling is Strong, self reinforcing",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL LEAN. Avoid the long",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes with sell bias",
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
        "id": 58,
        "name": "Long Gamma Pin \u2014 Downward Lean with Upside Gamma Wall",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL",
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
        "id": 59,
        "name": "Short Gamma Trend \u2014 Negative Delta Bias",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "SELL LEAN \u2014 Follow Trend \u2014 Bounces can be deep.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Rallies are shorting opportunities",
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
        "id": 60,
        "name": "Short Gamma Slow Bleed \u2014 Dampened Cascade. Downward Lean.",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Trend Day , Rallies are enteries",
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
        "id": 61,
        "name": "Dealer Short Gamma / Vanna Unwind",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN - Follow Trend \u2014 Bounces will be shallow (Zomma Neg accelerates selloff)",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Rallies are shorting opportunities (Lean)",
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
        "id": 62,
        "name": "Bull Vol Expansion Trap / Short Squeeze with Vol Explosion",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "BUY LEAN \u2014 Follow squeeze, pullbacks are shallow. Avoid the short.",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "id": 63,
        "name": "Gamma Acceleration Selloff",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN \u2014 Follow Trend \u2014 Bounces will be shallow (Zomma Neg accelerates selloff). Avoid the Long",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Rallies are enteries",
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
        "id": 64,
        "name": "Gamma Cascade / The Gamma Trap",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN / CHASE",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Bounces are shorting opportunities",
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
        "id": 65,
        "name": "Long Downside Tail \u2014 Dealer Crash-Hedged at High Vol",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression  \u2014 not pure Compression, because the range is asymmetric (harder floor than ceiling)",
        "action": "Sell LEAN - ( however Buy is safer in IV Crush)",
        "actionDirection": "SELL LEAN",
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
        "id": 66,
        "name": "Positive Gamma Pinning",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY the Dip  \u2014 Respect the Pin",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes \u2014 revert to ATM pin",
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
        "id": 67,
        "name": "High-Vol Short-Put Unwind \u2014 Zomma-Dampened Cascade",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Bounces are shorting opportunities",
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
        "id": 68,
        "name": "Fading Melt-Up / Zomma-Dampened Squeeze",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day with built in Ceiling - Compression Transition",
        "action": "BUY LEAN \u2014 Pullbacks deepen as squeeze fades. Take profits into strength. Don't short until compression confirms",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend day but self limiting, transitions to compression.",
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
        "id": 69,
        "name": "High-Vol Short-Put Unwind with Long-Put Tail \u2014 Vanna Sells on IV Expansion",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day \u2014 Short-Duration Cascade (self-limiting via Zomma + latent vanna)",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
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
        "id": 70,
        "name": "Fading Selloff / Zomma-Dampened Breakdown",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day with built in Floor - Compression Transition",
        "action": "SELL LEAN \u2014 Follow trend early, reduce size as bounces deepen. Don't buy until compression confirms",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Bounces are shorting opportunities",
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
        "id": 71,
        "name": "Vanna Melt Up / Negative Gamma Short Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day \u2014 Vanna-Driven Melt-Up",
        "action": "BUY LEAN",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "id": 72,
        "name": "Counter-Delta Vanna Squeeze / Bearish Book Under BUY Pressure",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day with self-limiting character via positive zomma",
        "action": "BUY LEAN \u2014 Follow vanna squeeze early, reduce size as pullbacks deepen. Don't short until compression confirms \u2014 vanna BUY pressure dominates",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "id": 73,
        "name": "Vanna Melt Up",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "BUY LEAN",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
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
        "id": 74,
        "name": "Vanna-Pinned Coiled Compression",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression  - with transition risk if IV spikes",
        "action": "Small size BUY \u2014 pin breaks violently. Fade small ranges while IV stays pinned.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with extreme caution \u2014 pin breaks accelerate",
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
        "id": 75,
        "name": "Crisis-Continuation Short-Gamma Cascade \u2014 Downside Acceleration at High Vol",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day \u2014 No Floor",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
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
        "id": 76,
        "name": "Coiled with risk of downside cascade  (primed for violent vol expansion)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Dormant - Coiled with cascasde Risk",
        "action": "Dormant - Await the SELL.  Expected move is small - Cascade Risk if IV spikes.  Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts.",
        "actionDirection": "SELL",
        "tilt": "Bounces are shorting entries",
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
        "id": 77,
        "name": "High-Vol Coiled Cascade -  Accelerating Breakdown Risk",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day \u2014 No Floor",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
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
        "id": 78,
        "name": "Dormant; Pre-Cascade Setup",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Dormant - Coiled Low-Vol. Latent Downside Cascade Risk.",
        "action": "Dormant - Await the SELL.  Expected move is small - Cascade Risk if IV spikes.  Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts.",
        "actionDirection": "SELL",
        "tilt": "Neutral at rest; bearish if IV spikes. Bounces fade if cascade fires.",
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
        const batchData = await safeJsonParse(resp);

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