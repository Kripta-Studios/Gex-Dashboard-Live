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
        "tilt": "Fade both extremes but lean short. Volatile, Expect Whipsaw",
        "dealersAction": "SELL the Rally dominant. Pro-cyclical selling on drops (short gamma forces selling into weakness) \u2014 but vanna/vomma flows trigger counter-cyclical buying on IV spikes.",
        "charmNetNegative": "Supportive but weak \u2014 tries to create floor via forced dealer buying, but short gamma dominates and pro-cyclical selling overwhelms charm support on real moves.",
        "charmNetPositive": "Suppressive \u2014 reinforces the bearish drift; charm-driven selling compounds with short-gamma pro-cyclical selling.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises; Less overhead resistence.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 2,
        "name": "Low-Vol Grind-Up / Melt-Up \u2014 Dealers Comfortable with Upside Drift",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "BUY on Pullback. Pullbacks are generally shallow.",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Pro-cyclical hedging \u2014 buying into strength, chase accelerates on rallies",
        "charmNetNegative": "Supportive \u2014 compounds the melt-up. Charm buying aligns with dealer de-risking on upside \u2192 reinforces floor on pullbacks.",
        "charmNetPositive": "Suppressive \u2014 fights the melt-up mildly. Overridden by Vanna.",
        "vannaNetNegative": "Suppressive",
        "vannaNetPositive": "Supportive",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "Yes, but not always",
        "vShapeRecovery": "",
        "spreads": "CCS",
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 3,
        "name": "High-IV Bearish Pin \u2014 Vanna-Cushioned Drift with Tail Exposure",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Fragile Compression",
        "action": "Fade extremes while pin holds. SELL LEAN on IV expansion \u2014 pin breaks down with no wing catch (Vomma Neg). Ride the break \u2014 no recovery mechanism.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade extremes. On gamma-flip breakdown: SELL trend, ride to exhaustion (no wing catch).",
        "dealersAction": "Sell rallies / Buy dips weakly (gamma pin with bearish lean). On IV lifts, Vex Pos adds vanna buying \u2014 cushions downside moves at pin. But no wing catch if spot breaches tail",
        "charmNetNegative": "Supportive \u2014 creates a pin floor. Reinforced by Vex Pos vanna buying on IV lifts. But Vomma Neg means no floor at tail \u2014 pin floor fails on tail breach with no catch below.",
        "charmNetPositive": "Weakly suppressive \u2014 soft ceiling. Overridden by Vex Pos vanna buying on IV lifts \u2014 ceiling fails on vol expansion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 4,
        "name": "Low-IV Bearish Drift Pin \u2014 Vanna Cushion Loaded",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Fragile Compression",
        "action": "BUY LEAN - While the market is calm, trade the range \u2014 buy dips, sell rallies, both will mean-revert. If volatility picks up, expect the selloff to be cushioned - but no recovery mechanism.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fadeextremes. On gamma-flip breakdown: SELL trend, ride to exhaustion (no wing catch).",
        "dealersAction": "Dormant while vol compressed. Sell rallies / Buy dips weakly (gamma pin with bearish lean). On IV lifts, Vex Pos adds vanna buying \u2014 cushions downside moves at pin. But no wing catch if spot breaches tail",
        "charmNetNegative": "Supportive \u2014 creates a pin floor while vol compressed. Vex Pos cushion loaded \u2014 floor strengthens on IV expansion, fails on tail breach (Vomma Neg).",
        "charmNetPositive": "Weakly suppressive \u2014 soft ceiling while vol compressed. Overridden on IV expansion by Vex Pos vanna buying. Not a real cap.\"",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 5,
        "name": "High-IV Long Vol Bearish Skew \u2014 Vanna-Cushioned Drift",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "SELL LEAN \u2014 PIN holds with bearish drift. On vol expansion, expect vanna-cushioned descent (not waterfall). Exit on IV peak, not exhaustion \u2014 Vex Pos arrests the move.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade both extremes \u2014 vanna cushion protects downside, pin caps upside.",
        "dealersAction": "Sells rallies / Buys dips (gamma pin with bearish lean). On IV lifts, Vex Pos adds vanna buying \u2014 cushions downside moves during vol expansion.",
        "charmNetNegative": "Supportive \u2014 pin floor holds at current IV. Vanna cushion takes over on vol expansion as pin fades",
        "charmNetPositive": "Weakly suppressive \u2014 soft ceiling. Overridden by Vex Pos vanna buying on IV lifts \u2014 ceiling fails on vol expansion",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "Yes",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 6,
        "name": "Long Vol Convexity Book - Loaded with Vanna Cushion on Downside",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN into PIN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade both extremes \u2014 vanna cushion protects downside, pin caps upside.",
        "dealersAction": "Passive / Dormant while vol compressed. On IV expansion, Vex Pos triggers forced buying \u2014 cushions any downside move.",
        "charmNetNegative": "Supportive \u2014 pin floor while vol compressed. On vol wake-up, pin fades (Zomma Neg) but vanna cushion + Vex Pos forced buying take over as the support mechanism.",
        "charmNetPositive": "Weakly suppressive \u2014 overridden by Vex Pos vanna buying on IV lifts. Ceiling is fragile, not a real cap.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 7,
        "name": "High-IV Bearish Pin with Pre-Breakdown Structure \u2014 Coiled for downside vol expansion",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression \u2014 Bear-Coiled",
        "action": "SELL LEAN into PIN on IV expansion \u2014 pin breaks down. Chop otherwise.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes while pin holds. On gamma-flip breakdown: SELL trend, ride the bear move.",
        "dealersAction": "Buy dips / Sell rallies weakly (gamma pin with bearish lean). Vex Neg compounds selling on IV lifts \u2014 pin breaks down on vol expansion.",
        "charmNetNegative": "Supportive \u2014 absorbs downside pre-breakdown; overridden post-break.",
        "charmNetPositive": "Suppressive \u2014 compounds with vanna on downside break",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": "Break of Gamma Flip",
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 8,
        "name": "Low-IV Bearish Compression \u2014 Loaded for Downside with Wing Convexity Payoff",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression \u2014 Bear-Coiled",
        "action": "AVOID Buys. Neutral / Small SELL LEAN on rally\u2014 pin holds while vol compressed. Await vol expansion trigger for size.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes with bearish lean. Don't fade downside \u2014 break risk on vol expansion.",
        "dealersAction": "Buy dips / Sell rallies weakly (gamma pin with bearish lean). Vex Neg compounds selling on IV lifts \u2014 pin breaks down on vol expansion.",
        "charmNetNegative": "Supportive \u2014 creates a pin floor while vol compressed. Floor fails on IV expansion as Vex Neg selling overwhelms charm.",
        "charmNetPositive": "Suppressive \u2014 soft ceiling while vol compressed. Vex Neg vanna selling reinforces the ceiling on IV lifts",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 9,
        "name": "Short-Call Gamma Squeeze \u2014 Upside Cascade at High IV",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day (Upside Squeeze)",
        "action": "AVOID Shorts. BUY LEAN on rally confirmation \u2014 squeeze risk. Vex Neg catches the squeeze at top.",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pullbacks are entries",
        "dealersAction": "Mechanical forced BUYING. Pro-cyclical chase on rallies (short-call squeeze). Passive on downside. Dormant while vol compressed.",
        "charmNetNegative": "Supportive \u2014 floor flow (dealer buying) aligns with squeeze direction. Compounds the cascade. Small magnitude vs dominant squeeze flow",
        "charmNetPositive": "Suppressive \u2014 fights the squeeze. Reinforced by Vex Neg vanna selling on IV lifts. Eventually catches the squeeze at exhaustion \u2014 this is where the move tops.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "Yes - The moment IV prints a lower high while spot prints a lower low \u2014 that is the turn, regardless of what price action looks like at that moment.",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 10,
        "name": "Dealer Short Gamma Trap \u2014 Loaded for Upside Squeeze",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Dormant- Transitional - Trend Day",
        "action": "BUY LEAN (small) on upside trigger. Avoid shorts \u2014 squeeze loaded. No directional edge in dormant state \u2014 await IV trigger.",
        "actionDirection": "BUY LEAN",
        "tilt": "Transitional \u2014 squeeze loaded. Await entry.",
        "dealersAction": "Dormant while vol compressed. Pro-cyclical chase on rallies (short-call squeeze loaded). Passive on downside.",
        "charmNetNegative": "Supportive \u2014 weak floor while vol compressed. Loaded to compound the squeeze once IV expansion fires",
        "charmNetPositive": "Suppressive \u2014 weak cap while dormant. Vex Neg vanna selling reinforces the cap if IV lifts, but short-call gamma chase overrides both on upside trigger.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 11,
        "name": "Dealer-Overwhelmed Bearish Drift \u2014 Pos dealer book absorbs but doesn't reverse external selling",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with bearish drift",
        "action": "SELL LEAN. Dips are Deep & dip-buying is WEAK. Dealer book absorbs but doesn't reverse. Don't fight the external flow.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes. Don't expect bounces on dips.",
        "dealersAction": "Sells rallies/ Buys dips. IV spike causes Deep retracements that do not recover.",
        "charmNetNegative": "Supportive \u2014 weak vs the asymmetric pin. Tries to create floor but Speed Pos means dealer support is thin; charm alone isn't enough.",
        "charmNetPositive": "Suppressive \u2014 compounds/ accelerates the bearish drift.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "Yes - The moment IV prints a lower high while spot prints a lower low \u2014 that is the turn, regardless of what price action looks like at that moment.",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 12,
        "name": "Bullish Drift Ignition / Melt Up",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with bullish drift",
        "action": "BUY LEAN. Dips are shallow & dip-buying is STRONG. Max-gamma zone acts as magnet above, not ceiling.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes.",
        "dealersAction": "Sells rallies/ Buys dips. IV spike causes Deep retracements that do not recover.",
        "charmNetNegative": "Supportive \u2014 charm reinforces the melt up",
        "charmNetPositive": "Suppressive (but forced buying dominates)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises; Less overhead resistence.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 13,
        "name": "Bearish Pin \u2014 Vol compression with downside drift risk",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression with bearish drift \u2014 downside break risk",
        "action": "SELL LEAN - Neg Vex means IV spikes force additional selling",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes. Don't fade downside \u2014 break risk on vol expansion.",
        "dealersAction": "Sell the Rally aggressively / Buy the Dip weakly (gamma pin with bearish lean). On IV lifts, Vex Neg compounds selling. Pin holds while vol compressed.",
        "charmNetNegative": "Supportive but swamped \u2014 charm-driven buying gets cancelled by the vol-hedging overlay.",
        "charmNetPositive": "Suppressive \u2014 reinforces the pin on upside. Neg Vex compounds the selling on IV spikes, hardening the ceiling.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 14,
        "name": "Low-IV Compression with Bearish Skew \u2014 Fragile Pin",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression with bearish drift \u2014 downside break risk",
        "action": "AVOID BUY. Neutral. Pin likely below (dex neg). Await the SELL in high IV. Pin holds while vol compressed but bearish drift within compression \u2014 downside cascade risk (no wing catch).",
        "actionDirection": "SELL",
        "tilt": "Fade upside extremes. Don't fade downside \u2014 break risk on vol expansion.",
        "dealersAction": "Sell the Rally aggressively / Buy the Dip weakly (gamma pin with bearish lean). On IV lifts, Vex Neg compounds selling. Pin holds while vol compressed.",
        "charmNetNegative": "Supportive \u2014 creates a pin, not a true floor. Holds while vol compressed. Vanna selling overrides the charm bid on IV lifts.",
        "charmNetPositive": "Suppressive - not generating downside momentum, it's creating a ceiling. Neg Vex compounds the suppression on IV lifts, hardening the ceiling. Gets stronger, not weaker, if vol wakes up.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 15,
        "name": "The Waterfall Sell- Off",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day no V-recovery, ride to exhaustion.",
        "action": "SELL the breakdown. Trend-follow aggressively. Don't catch the knife but watch for exhaustion.Possible V shape recovery.",
        "actionDirection": "SELL",
        "tilt": "Trend Day , bounces are entries",
        "dealersAction": "Forced Pro-cyclical selling on every downtick.Acceleration as spot moves. No flow reversal at tails. in low IV the dealer is dormant - dealer does minimal flow.",
        "charmNetNegative": "Swamped \u2014 charm can't arrest the cascade.",
        "charmNetPositive": "Suppressive- Compounds the Selling",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 16,
        "name": "Volmageddon Setup / Complacency Trap",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Dormant - Coiled with Trend Day cascasde Risk",
        "action": "Dormant - Await the SELL. Expected move is small - Cascade Risk if IV spikes. Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts.",
        "actionDirection": "SELL",
        "tilt": "Wait for IV wake-up (transition to High IV row). Don't fade the eventual breakdown.",
        "dealersAction": "Dormant - dealer does minimal flow because IV is low and price isn't moving much. BUT the book is primed: any IV spike triggers forced pro-cyclical selling",
        "charmNetNegative": "Supportive \u2014 weak floor while vol compressed. Floor fails on IV expansion.",
        "charmNetPositive": "Suppressive \u2014 compounds latent bearish bias while dormant. Accelerant once cascade fires (stacks with dealer selling and vanna selling into the breakdown).",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 17,
        "name": "High-IV Long Gamma Compression \u2014 Fragile Pin with downside break risk (Vex Neg)",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Fragile Compression \u2014 pin-break risk on IV expansion.",
        "action": "SELL LEAN \u2014 dips are deep. Break-down leads to controlled descent toward wing strike. Slow U, not sharp V. Pre-break level typically not recovered.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes \u2014 break risk on vol expansion.",
        "dealersAction": "Buy the Dip / Sell the Rally (gamma pin). On IV lifts, Vex Neg forces dealer selling \u2014 vanna flow breaks the pin to the downside. Pin stable while vol compressed.",
        "charmNetNegative": "Supportive \u2014 creates a floor. Tested when Vex Neg breaks the pin down. Break-down leads to controlled descent toward wing strike, not sharp bounce.",
        "charmNetPositive": "Suppressive \u2014 ceiling holds. Upside isn't the break risk.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 18,
        "name": "Long Gamma Pin \u2014 downside break on vol expansion",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Fragile Compression \u2014 pin-break risk on IV expansion.",
        "action": "Neutral/Cautious BUY Lean into Pin. Pin holds while vol compressed. Exit on IV expansion \u2014 downside break risk. Don't chase upside",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade upside extremes \u2014 break risk on vol expansion.",
        "dealersAction": "Buy the Dip / Sell the Rally (gamma pin). On IV lifts, Vex Neg forces dealer selling \u2014 vanna flow breaks the pin to the downside. Pin stable while vol compressed.",
        "charmNetNegative": "Supportive \u2014 creates a floor while vol compressed. Floor fails on IV expansion as Vex Neg flips dealer to selling.",
        "charmNetPositive": "Suppressive \u2014 ceiling holds",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 19,
        "name": "Compression / Pin Day (with squeeze potential)",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression \u2014 vol-crush risk. Pin until wing breach",
        "action": "Cautious SELL LEAN into PIN. Respect the PIN. Squeeze risk bias to upside.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the Dip aggressively / Sell the Rally weakly. Wing breach either side flips dealer to forced chaser \u2014 upside biased due to Pos Delta.. Respect the PIN",
        "charmNetNegative": "Supportive \u2014 creates a pin, not a true floor. Holds while spot is near ATM. On wing breach or IV shock, pin fails with no catch below although bias is upside squeeze.",
        "charmNetPositive": "Suppressive - not generating downside momentum, it's creating a ceiling",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 20,
        "name": "High Confidence Grind / PIN",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN with conviction. Respect the PIN.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes/ PIN",
        "dealersAction": "Buy the Dip aggressively / Sell the Rally weakly. Wing breach either side flips dealer to forced chaser \u2014 upside biased due to Pos Delta.. Respect the PIN",
        "charmNetNegative": "Supportive \u2014 creates a pin. Fragile: no true floor \u2014 Vomma Neg means IV expansion breaks the pin with no catch below, although bias is upside squeeze.",
        "charmNetPositive": "Weakly suppressive \u2014 nominally caps, not a real ceiling. Overridden on squeeze",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 21,
        "name": "Possible Short-Cover Cascade / Upside Gamma Squeeze",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Transitional Compression - Trend Day (Violent Upside) with squeeze mechanics. But squeeze requires a catalyst like news.",
        "action": "AVOID Short or size small. Buy dips aggressively \u2014 Squeeze risk to upside. Assumes short-cover catalyst active. Pre-catalyst: pin/range regime.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean (Squeeze risk)",
        "dealersAction": "Pre-cascade: sells rallies, buys dips (gamma pinning). Post-trigger: forced buyer. Low IV Vanna Melt up.",
        "charmNetNegative": "Nominally supportive \u2014 but swamped by the short-squeeze cascade when triggered. Charm is a footnote. Creates a floor, not generating upside momentum, it's absorbing downside.",
        "charmNetPositive": "Suppressive \u2014 transient cap near call strike. Overridden by short-cover cascade.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 22,
        "name": "Vanna-fueled Melt Up (Index can push far beyond expectations)",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression with upward drift",
        "action": "BUY with conviction \u2014 vanna-fueled melt-up",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean",
        "dealersAction": "Low IV vanna melt up. High IV Sells rallies, Buys dips Pre-cascade. On News Post Cascade: Buys dips aggressively.",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing dips. Compounds with the vanna-fueled melt-up flows",
        "charmNetPositive": "Weakly suppressive \u2014 transient cap. Overridden by Vanna.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises; Less overhead resistence.",
        "mxVannaLevelsWork": "No",
        "vShapeRecovery": "",
        "spreads": "PCS",
        "stochastic": "Yes - Works on Pullbacks. Pullbacks can be decent or small.",
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 23,
        "name": "Short Gamma Cascade / Negative Convexity Unwind with built-in Feedback Loop ( V-recovery mechanism)",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day (Likely Violent) with with built in V-recovery mechanism",
        "action": "SELL the breakdown. Trend-follow aggressively but watch for IV peak \u2014 the tail hedge activates V-recovery earlier than pure Waterfall. Don't ride to exhaustion.",
        "actionDirection": "SELL",
        "tilt": "Trend Day \u2014 pullbacks are entries during the cascade. BUT V-recovery comes faster than Waterfall due to tail activation.",
        "dealersAction": "Forced pro-cyclical selling on every downtick in High IV. Inactive/ Position carrying in Low IV.",
        "charmNetNegative": "Weakly supportive but swamped \u2014 Neg Gamma compounds faster than charm cushions",
        "charmNetPositive": "Suppressive \u2014 compounds the cascade. Hardens the ceiling of V shape recovery",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "No",
        "vShapeRecovery": "Yes - Usually Large Gamma Wall",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 24,
        "name": "Low Vol Coiled Spring \u2014 Bearish Skew",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Transitional \u2014 Bearish Bias",
        "action": "Awaiting Trigger/ IV Spike. Minimal hedging pressure in low IV; dealers inactive, gamma dormant, awaiting a vol expansion trigger.",
        "actionDirection": "N/A",
        "tilt": "Neutral",
        "dealersAction": "Inactive/ Position carrying in Low IV. Forced pro-cyclical selling on every downtick in High IV",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing downside. Fails on IV wake-up as cascade fires.",
        "charmNetPositive": "Weakly suppressive \u2014 transient cap. Overridden on IV lift as cascade trigger activates.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 25,
        "name": "Active Short-Vol Cascade / Volatile Bearish Drift",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN on rallies. Bearish drift dominant despite Pos Zomma cushion.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
        "dealersAction": "Forced seller on IV lift (Neg Vex). Cascade risk on IV wake-up or break. Passive theta collection in calm",
        "charmNetNegative": "Weakly supportive but swamped \u2014 Neg Gamma amplifies moves faster than charm cushions. Floor is fragile.",
        "charmNetPositive": "Suppressive \u2014 compounds with Neg Vex on IV lifts, hardening the downside pressure.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 26,
        "name": "Dormant Short-Vol Collector / Pre-Cascade Setup (Bearish Trigger)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Transitional \u2014 not yet trend day",
        "action": "Small size BUY LEAN in calm (Pos Delta bias). AVOID heavy long positions \u2014 regime is cascade-capable on IV wake-up. Options: buy cheap tail protection",
        "actionDirection": "BUY LEAN",
        "tilt": "Buy dips small in dormant state. Watch IV \u2014 cascade fires bearishly on IV wake-up.",
        "dealersAction": "Passive theta collection in calm. Forced seller on IV lift (Neg Vex). Cascade risk on IV wake-up or break.",
        "charmNetNegative": "Weakly supportive \u2014 Pos Delta bid in dormant calm. Neg Gamma limits effectiveness; floor is a cushion, not firm support. Fails on IV wake-up as cascade fires",
        "charmNetPositive": "Weakly suppressive \u2014 transient cap. Overridden on IV lift as Neg Vex compounds the cascade trigger.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 27,
        "name": "Short-Vol Capitulation / Short covering can becom a Melt Up",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "AVOID Shorts. BUY the breakout \u2014 short-covering cascade",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Forced Buying",
        "charmNetNegative": "Nominally supportive \u2014 but swamped by the short-squeeze cascade. Charm is a footnote.",
        "charmNetPositive": "Suppressive - weak by nature \u2014 overridden by the short-squeeze.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 28,
        "name": "Pre-Squeeze Setup / Short-Vol Capitulation Primer (Dormant)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg" },
        "regime": "Transitional\u2014 dormant pre-squeeze setup (primed for bullish squeeze)",
        "action": "BUY LEAN on dips. Dormant squeeze setup",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean.",
        "dealersAction": "Passive hedging in calm. Primed for forced bullish covering on IV lift or rally into gamma zone.",
        "charmNetNegative": "Supportive \u2014 weak bid while dormant. Compounds with Pos Vex on IV lifts \u2014 same mechanism that fires the squeeze.",
        "charmNetPositive": "Weakly suppressive \u2014 transient cap. Overridden on any IV lift as squeeze mechanics activate.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 29,
        "name": "Orderly Sell Off (grind) / Hedged Bear Market",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with bearish drift",
        "action": "SELL LEAN on rallies.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing downside. But swamped by frequent Neg Vex firings at High IV \u2014 floor fails often.",
        "charmNetPositive": "Suppressive \u2014 creates a ceiling. Neg Vex compounds on IV lifts, hardening the ceiling.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 30,
        "name": "Hedged Long-Vol Compression / Orderly Grind Higher",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with upside drift",
        "action": "BUY LEAN on dips.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing downside. Fragile: Neg Vex cancels the bid on IV lifts.",
        "charmNetPositive": "Suppressive \u2014 creates a ceiling. Neg Vex compounds on IV lifts, hardening the ceiling.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 31,
        "name": "Active Vanna-Hollow Squeeze / Spot-Vol Correlation Trend Day",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day \u2014 spot-vol correlation dependent (squeeze firing)",
        "action": "BUY LEAN \u2014 melt-up is the baseline. AVOID Shorts. Correlation matrix in Tilt determines tactical direction.",
        "actionDirection": "BUY LEAN",
        "tilt": "Spot Down + VIX Flat: Dealers are Sellers; Spot Down + VIX Exploding: Dealers are Confused/Neutral; Spot Up + VIX Dropping: Dealers are Aggressive Buyers",
        "dealersAction": "Pro-cyclical hedging / Chasing. Passive hedging in calm.",
        "charmNetNegative": "Supportive \u2014 forces dealer buying, compounds with the vanna-fueled melt-up flows",
        "charmNetPositive": "Suppressive \u2014 creates a ceiling, but overridden by the squeeze dynamic as forced covering accelerates the rally.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 32,
        "name": "Fragile Vanna-Hollow Melt-Up/ Bullish pre-melt-up squeeze",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional \u2014 not yet trend day",
        "action": "BUY LEAN. Buy the Dip. Option traders can buy cheap protection. Profile needs confirmation.",
        "actionDirection": "BUY LEAN",
        "tilt": "Transitional \u2014 not yet trend day. BUY dips small in current dormant state",
        "dealersAction": "Passive hedging in calm.Pro-cyclical hedging / Chasing if IV wakes up.",
        "charmNetNegative": "Supportive \u2014 forces dealer buying, compounds with Pos Vex on IV lifts. Pre-melt-up bid building quietly.",
        "charmNetPositive": "Flat to weakly suppressive \u2014 caps lightly in dormant state. Overridden when the squeeze fires (IV wake-up or rally into gamma zone).",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 33,
        "name": "Long convexity, Long volatility / Coiled Spring",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "AVOID the Short. BUY the Dips with conviction. Coiled bullish spring \u2014 upside break most likely, short trades have no edge.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes, waiting for breakout",
        "dealersAction": "Buy the Dip aggressively. Sell the Rally weakly. (Waiting for the breakout).",
        "charmNetNegative": "Supportive \u2014 coiled floor absorbing downside, dealer buys dips while awaiting breakout.",
        "charmNetPositive": "Weakly suppressive \u2014 transient cap, overridden by the dominant bullish flows.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 34,
        "name": "Vanna-fueled Melt Up / Expansion",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with aggressive upside drift (vanna-fueled). Active melt-up",
        "action": "BUY with conviction. Avoid shorts.",
        "actionDirection": "BUY",
        "tilt": "Buy pullbacks aggressively, ride the vanna grind. No structural ceiling.",
        "dealersAction": "Buy the Dip aggressively. Sell the Rally weakly. Aggressive upward drift.",
        "charmNetNegative": "Supportive \u2014 forces dealer buying, compounds with the vanna-fueled melt-up flows",
        "charmNetPositive": "Weakly suppressive \u2014 transient cap, overridden by the dominant bullish flows.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "No",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": "Yes - Works on Pullbacks",
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 35,
        "name": "High-IV Call Magnet (Pin) / Active Magnet Grind",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression with mechanical drift into Pin.",
        "action": "SELL LEAN only into pin strike. Neg Speed punishes extension.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes with lean towards PIN",
        "dealersAction": "Buy the Dip aggressively. Sell the Rally weakly. Dealer positioned for active magnet/pin.",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing downside. Vanna compounds charm on IV lifts.",
        "charmNetPositive": "Weakly suppressive \u2014 overridden by vanna, but magnet strike pin is the real cap.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 36,
        "name": "Possible Volatility Expansion Setup (If IV wakes up)",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression / coiled pre-expansion. Aggressive upside drift (Pin above)",
        "action": "BUY LEAN with conviction on dips. Coiled setup.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes - Buy dips with upside lean into the coil.",
        "dealersAction": "Buy the Dip aggressively. Sell the Rally weakly. Dealer positioned for vol expansion.",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing downside. Vanna compounds charm on IV lifts.",
        "charmNetPositive": "Weakly suppressive \u2014 overridden by vanna, but magnet strike pin is the real cap.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 37,
        "name": "Machine Driven Short Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "AVOID Shorts. BUY pullbacks aggressively \u2014 squeeze is mechanical. DO NOT CHASE at the highs \u2014 wait for the dip.",
        "actionDirection": "BUY",
        "tilt": "Momentum Breakout, High Probability Upside, Pullbacks are enteries",
        "dealersAction": "Aggressive Chasing",
        "charmNetNegative": "Supportive \u2014 reinforces the chase up",
        "charmNetPositive": "Suppressive \u2014 overridden by vanna-fueled buying",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 38,
        "name": "Pre-Squeeze Setup / Machine-Driven Squeeze Primer",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Transitional\u2014 dormant, pre-squeeze setup",
        "action": "BUY LEAN on dips. Dormant Bullish squeeze setup.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean.",
        "dealersAction": "Passive pinning in calm. Primed for bullish agressive chasing on IV lift",
        "charmNetNegative": "Supportive \u2014 reinforces the upside bias.",
        "charmNetPositive": "Weak Suppressive \u2014 temporary ceiling. May be overwhelmed in a snap/squeeze scenario",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 39,
        "name": "Long Convexity Melt-Up",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with upside drift",
        "action": "AVOID Shorts. BUY the dip with conviction.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Supportive \u2014 reinforces the chase up",
        "charmNetPositive": "Weakly suppressive \u2014 overridden by upside forces",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 40,
        "name": "Pre-Ignition Setup / Low-IV Long-Gamma Compression with Bullish Coil",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with upside drift",
        "action": "BUY LEAN/ Buy the Dip",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Supportive \u2014 creates a floor, absorbing downside",
        "charmNetPositive": "Weakly suppressive \u2014 overridden by upside drift.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 41,
        "name": "High Volatility Grind Up",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with Upside Drift",
        "action": "AVOID Shorts. BUY LEAN on dips. High-IV grind up with IV-crush tailwind.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean. Strong Floor.",
        "dealersAction": "Buy the Dip aggressively. Sell the Rally weakly. Mild upward drift.",
        "charmNetNegative": "Supportive \u2014 reinforces the grind up",
        "charmNetPositive": "Suppressive - not generating downside momentum, it's creating a ceiling. Neg Vex compounds on IV lifts, hardening the ceiling.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 42,
        "name": "Dealer Long Gamma/ Low Volatility Grind Up",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with Upside Drift",
        "action": "BUY LEAN on dips.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean. Strong Floor.",
        "dealersAction": "Buy the Dip aggressively. Sell the Rally weakly. Mild upward drift.",
        "charmNetNegative": "Supportive \u2014 reinforces the grind up",
        "charmNetPositive": "Suppressive - not generating downside momentum, it's creating a ceiling. Neg Vex compounds on IV lifts, hardening the ceiling.\"",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 43,
        "name": "Gamma Drain Short Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "BUY",
        "actionDirection": "BUY",
        "tilt": "Momentum Chasing, Trend Day.",
        "dealersAction": "Forced Covering",
        "charmNetNegative": "Supportive \u2014 charm tailwind reinforces squeeze",
        "charmNetPositive": "Suppressive (but forced covering dominates)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "Yes - Usually Large Gamma Wall",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 44,
        "name": "Vol-Expansion Downward Slide",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Mean Reverting Downward",
        "dealersAction": "Dealer sells the Rally",
        "charmNetNegative": "Supportive (but forced selling dominates)",
        "charmNetPositive": "Weak Suppression to Flat",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises - Acts as Floor.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 45,
        "name": "Mechanical Melt-Up / Vanna-Driven Grind Higher",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional / Expansion",
        "action": "AVOID Shorts / BUY the Dip",
        "actionDirection": "BUY",
        "tilt": "Fade downside extreme only; ride upside extension already in motion. Strong Floor, weak ceiling.",
        "dealersAction": "BUY PULLBACKS aggressively; rip-selling is overwhelmed by vanna + delta hedging flows",
        "charmNetNegative": "Supportive \u2014 piles on the melt-up momentum",
        "charmNetPositive": "Suppressive (but vanna override + mechanical flow dominate to the upside)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 46,
        "name": "Positive Gamma Coil with Bull Volatility Trigger Risk",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression with Explosive Bullish Risk",
        "action": "BUY the Dip",
        "actionDirection": "BUY",
        "tilt": "Fade downside extreme only; respect upside trigger \u2014 squeeze ignites on IV expansion. Strong Floor, fragile ceiling.",
        "dealersAction": "BUY the Dip / Sell the Rally with caution \u2014 Bull Vol upside squeeze risk. In high IV Rip-selling is overwhelmed by vanna + delta hedging flows",
        "charmNetNegative": "Supportive (creates a floor absorbing downside until vol trigger fires \u2014 then regime flips)",
        "charmNetPositive": "Suppressive (but vanna will likely override charm here to the upside)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 47,
        "name": "Vol-Expanded Downside Trend / Self-Accelerating Breakdown via Zomma",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day. Forced-Flow Trend with Whipsaw Risk",
        "action": "SELL LEAN. SELL Bounces, Avoid Longs.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend with whipsaw \u2014 chase weakness, don't fade. Pullbacks are NOT safe entries.",
        "dealersAction": "At High IV, pro-cyclical selling on weakness dominates. Reluctant buying on bounces (Neg Delta hedge) gets overwhelmed by Neg Gamma + Vega flow. At Low IV the book is dormant.",
        "charmNetNegative": "Supportive \u2014 creates a soft floor via Neg Delta forced buying. Floor holds intraday but Neg Gamma + Vega flow breaks it on real moves.",
        "charmNetPositive": "Suppressive \u2014 erodes bounce-buy fuel. Compounds with pro-cyclical selling. Reinforces breakdown",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 48,
        "name": "The Silent Trap / High Probability Coiled Breakdown",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional (To Possible Trend Down)",
        "action": "Pre-trigger the book is dormant. Don't pre-empt the break; chase it.",
        "actionDirection": "N/A",
        "tilt": "Transition - Trend Day , Coiled \u2014 wait for break. Bounces are short entries, not longs. Don't fade range pre-trigger.",
        "dealersAction": "At Low IV the book is dormant until a vol trigger fires. At High IV, pro-cyclical selling on weakness dominates. Reluctant buying on bounces (Neg Delta hedge) gets overwhelmed by Neg Gamma + Vega flow.",
        "charmNetNegative": "Supportive \u2014 Neg Delta drift forces buying, holds the range. Fails on downside break \u2014 vanna takes over.",
        "charmNetPositive": "Suppressive \u2014 erodes the range floor. Primes the downside break. Vanna piles on once vol expands",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises; Coiled.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 49,
        "name": "High-Vol Short-Put Book Under Pressure \u2014 Trend Day with Sold Bounces",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "SELL LEAN. SELL bounces into resistance. Trend continues \u2014 don't fade.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , bounces are short entries",
        "dealersAction": "Pro-cyclical: sell weakness, buy strength reluctantly. At Low IV book is dormant.",
        "charmNetNegative": "Supportive but weak \u2014 charm relieves Pos Delta sell-pressure on bounces. Doesn't reverse the trend",
        "charmNetPositive": "Suppressive \u2014 charm-driven Pos Delta growth reinforces sold bounces. Compounds the trend.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 50,
        "name": "Hedged Short-Put Book at Low Vol \u2014 Upside Grind, Downside Trap",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Transitional - Trend Day. Pin / Upside Grind with Latent Downside Trap",
        "action": "BUY grind cautiously; flip short on put-strike break",
        "actionDirection": "BUY",
        "tilt": "Cautious lean long on grind. Possible transition to bear Trend Day.",
        "dealersAction": "Pro-cyclical: sell weakness, buy strength reluctantly. At Low IV book is dormant; at High IV pro-cyclical flow fires. Pos Delta + Neg Gamma compound on rallies (sold) and breaks lower (chased).",
        "charmNetNegative": "Supportive \u2014 charm bleed reduces Pos Delta sell-pressure. Lets the grind extend. Overwhelmed only on a vol shock",
        "charmNetPositive": "Suppressive \u2014 charm-driven Pos Delta growth caps the grind. On vol spike, vanna stacks and downside trap fires",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 51,
        "name": "Compressed Range \u2014 Long Gamma Floor, IV Mean-Reverting Lower",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "SELL LEAN towards PIN",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade near extremes. Caution at far extremes \u2014 Neg Speed weakens dampening",
        "dealersAction": "Buy the Dip / Sell the Rally \u2014 counter-cyclical dampening (book dormant at Low IV)",
        "charmNetNegative": "Supportive creates a floor, not generating upside momentum, it's absorbing downside.",
        "charmNetPositive": "Suppressive - not generating downside momentum, it's creating a ceiling",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 52,
        "name": "Quiet Pin / Dormant Range \u2014 Long Gamma at rest, breakouts fail",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN towards PIN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade near extremes. Caution at far extremes \u2014 Neg Speed weakens dampening",
        "dealersAction": "Buy the Dip / Sell the Rally \u2014 counter-cyclical dampening (book dormant at Low IV)",
        "charmNetNegative": "Supportive but small \u2014 soft floor, muted at Low IV",
        "charmNetPositive": "Suppressive but small \u2014 soft ceiling, muted at Low IV",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 53,
        "name": "Long Put Book Engaged \u2014 High IV Reinforces the Floor",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "SELL LEAN. Sell the rally. However,defended floor active \u2014 don't chase shorts into dealer support.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade extremes - Defended floor",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Supportive \u2014 creates floor, it's absorbing downside, liquidation fails to break it",
        "charmNetPositive": "Suppressive \u2014 ceiling caps rallies. Vanna may override on IV expansion (Pos Vega tailwind)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 54,
        "name": "Compressed Range \u2014 Long Put Floor Loaded but Idle",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY LEAN. BUY shallow dips \u2014 long-put floor + Neg Delta hedge support. IV expansion is tailwind. Defended floor is robust at Low IV.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade extremes - Defended floor",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Supportive \u2014 soft floor at Low IV. Neg Delta hedge + Pos Gamma reinforce; muted only by low charm magnitude.",
        "charmNetPositive": "Suppressive \u2014 soft ceiling at Low IV. Vanna can override to downside on a vol shock.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 55,
        "name": "High-IV Compression with Breakout Risk \u2014 Dealer Dampening Fading",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL LEAN towards Pin. CAUTION: Zomma Neg weakens dampening; ceiling dissolves on breakout. Don't fade conviction breakouts.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes; Bias Upside Risk",
        "dealersAction": "BUY the Dip / Sell the Rally \u2014 counter-cyclical dampening. Slight buy-lean on dips.",
        "charmNetNegative": "Supportive \u2014 creates floor, absorbs downside. Reinforced by Pos Gamma counter-cyclical buying",
        "charmNetPositive": "Suppressive \u2014 ceiling caps rallies. Pos Gamma + Pos Delta hedging both push back on upside extension.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 56,
        "name": "Long Gamma Pin",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "BUY LEAN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes; Bias Upside Risk",
        "dealersAction": "BUY the Dip / Sell the Rally \u2014 counter-cyclical dampening. Slight buy-lean on dips.",
        "charmNetNegative": "Supportive but weak \u2014 soft floor reinforces dip-buying. Gamma pin dominates.",
        "charmNetPositive": "Suppressive but weak \u2014 soft ceiling reinforces rally-selling. Gamma pin dominates",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 57,
        "name": "Long Gamma Compression \u2014 Negative Delta Bias- Ceiling is Strong, self reinforcing",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL LEAN. Avoid the long",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes with sell bias",
        "dealersAction": "Sell the Rally",
        "charmNetNegative": "Supportive but lean-constrained \u2014 floor exists but thin given bearish skew and Delta Neg. Floor may dissolve faster than expected",
        "charmNetPositive": "Suppressive \u2014 but vanna will likely override charm here to the downside",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 58,
        "name": "Long Gamma Pin \u2014 Downward Lean with Upside Gamma Wall",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Compression",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Fade Extremes",
        "dealersAction": "Sell the Rally",
        "charmNetNegative": "Supportive \u2014 creates floor despite downward lean, absorbing downside (not generating upside momentum). Note:if price does rally, charm buying combined with upper-strike gamma wall creates compounded resistance \u2014 rallies exhaust quickly into the wall.",
        "charmNetPositive": "Suppressive and vanna will reinforce the downward lean charm has here. Pin-break risk is to the DOWNSIDE.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 59,
        "name": "Short Gamma Trend \u2014 Negative Delta Bias",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "SELL LEAN \u2014 Follow Trend \u2014 Bounces can be deep.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Rallies are shorting opportunities",
        "dealersAction": "Mechanical Forced Selling \u2014 selling into weakness",
        "charmNetNegative": "Supportive \u2014 floor fights the trend but is overwhelmed",
        "charmNetPositive": "Suppressive \u2014 charm piles on the sell off momentum",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 60,
        "name": "Short Gamma Slow Bleed \u2014 Dampened Cascade. Downward Lean.",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day",
        "action": "SELL",
        "actionDirection": "SELL",
        "tilt": "Trend Day , Rallies are enteries",
        "dealersAction": "Pro-cyclical hedging \u2014 sell into weakness (dominant), buy into strength (secondary). Bias toward selling due to negative delta tilt.",
        "charmNetNegative": "Supportive \u2014 cushions the bleed. Floor builds as gamma dampens; Late-session: charm dominates exhausted gamma \u2192 modest upside drift into close. Floor breaks on: early-session gamma \u00b7 IV expansion (vanna) \u00b7 price at lower-strike gamma zone (speed)",
        "charmNetPositive": "Suppressive \u2014 compounds the downward lean. As gamma self-dampens, charm selling takes over the tape \u2192 late-session grind lower even as gamma flow exhausts. No natural floor from dealer flow.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 61,
        "name": "Dealer Short Gamma / Vanna Unwind",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN - Follow Trend \u2014 Bounces will be shallow (Zomma Neg accelerates selloff)",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Rallies are shorting opportunities (Lean)",
        "dealersAction": "Pro-cyclical hedging \u2014 Chasing weakness, Selling rallies",
        "charmNetNegative": "Supportive \u2014 floor fights the trend but is overwhelmed by vanna unwind + forced selling",
        "charmNetPositive": "Suppressive \u2014 vanna unwind piles on the selloff",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 62,
        "name": "Bull Vol Expansion Trap / Short Squeeze with Vol Explosion",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "BUY LEAN \u2014 Follow squeeze, pullbacks are shallow. Avoid the short.",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Mechanical Forced Buying \u2014 vol expansion forces short cover",
        "charmNetNegative": "Supportive \u2014 charm reinforces the melt-up momentum",
        "charmNetPositive": "Suppressive \u2014 but vol expansion + vanna override charm to the upside",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 63,
        "name": "Gamma Acceleration Selloff",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN \u2014 Follow Trend \u2014 Bounces will be shallow (Zomma Neg accelerates selloff). Avoid the Long",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Rallies are enteries",
        "dealersAction": "Mechanical Forced Selling \u2014 selling into weakness",
        "charmNetNegative": "Supportive \u2014 floor fights the trend but is overwhelmed; charm sensitivity minimal in gamma-driven regime",
        "charmNetPositive": "Suppressive \u2014 charm piles on the selloff momentum",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 64,
        "name": "Gamma Cascade / The Gamma Trap",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN / CHASE",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Bounces are shorting opportunities",
        "dealersAction": "Pro-cyclical hedging / Chasing / Selling into Weakness (and Buying into Strength)",
        "charmNetNegative": "Supportive/ Cushions the trend. Creates a floor, not generating upside momentum, it's absorbing downside. The dominant flow in the regime is still gamma-driven selling.",
        "charmNetPositive": "Suppressive - Creates a ceiling during consolidation & piles on the selloff momentum during breakdown.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 65,
        "name": "Long Downside Tail \u2014 Dealer Crash-Hedged at High Vol",
        "condition": { "IV": "High", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression \u2014 not pure Compression, because the range is asymmetric (harder floor than ceiling)",
        "action": "Sell LEAN - ( however Buy is safer in IV Crush)",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the Dip/ Sell the Rally. Asymmetric: harder floor than ceiling. Buy the Dip (Dominant)",
        "charmNetNegative": "Supportive \u2014 Cushions dip-absorption. Creates a weak floor aligned with put-wing buying, not generating upside momentum on its own.",
        "charmNetPositive": "Suppressive \u2014 Creates a weak ceiling during consolidation, but overridden when put-wing gamma fires on downside moves and vanna fires on IV compression.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 66,
        "name": "Positive Gamma Pinning",
        "condition": { "IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression",
        "action": "BUY the Dip \u2014 Respect the Pin",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes \u2014 revert to ATM pin",
        "dealersAction": "Buy the Dip / Sell the Rally \u2014 defending the ATM pin",
        "charmNetNegative": "Supportive \u2014 creates a floor around the pin, absorbing downside",
        "charmNetPositive": "Suppressive \u2014 creates a ceiling around the pin, capping upside",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 67,
        "name": "High-Vol Short-Put Unwind \u2014 Zomma-Dampened Cascade",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Bounces are shorting opportunities",
        "dealersAction": "Pro-cyclical: Chase breakdowns (dominant) / Chase rallies lightly",
        "charmNetNegative": "Supportive \u2014 cushions the breakdown weakly. Floor creates brief stalls but does not halt the cascade. Dominant flow in the regime is short-put gamma chasing.",
        "charmNetPositive": "Suppressive \u2014 charm selling compounds the short-gamma cascade. Ceiling firm during rallies; accelerant on breakdowns.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 68,
        "name": "Fading Melt-Up / Zomma-Dampened Squeeze",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day with built in Ceiling - Compression Transition",
        "action": "BUY LEAN \u2014 Pullbacks deepen as squeeze fades. Take profits into strength. Don't short until compression confirms",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend day but self limiting, transitions to compression.",
        "dealersAction": "Forced Buying \u2014 buying into strength (moderating as squeeze fades)",
        "charmNetNegative": "Supportive \u2014 floor weak during trend, strengthens into compression",
        "charmNetPositive": "Suppressive \u2014 ceiling weak during trend, strengthens into compression",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises - Acts as Floor.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 69,
        "name": "High-Vol Short-Put Unwind with Long-Put Tail \u2014 Vanna Sells on IV Expansion",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day \u2014 Short-Duration Cascade (self-limiting via Zomma + latent vanna)",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
        "dealersAction": "Pro-cyclical: Chase breakdowns (dominant) / Chase rallies lightly",
        "charmNetNegative": "Supportive \u2014 weak floor from charm buying. Overridden to downside on IV expansion (vanna selling compounds cascade).",
        "charmNetPositive": "Suppressive \u2014 compounds short-gamma cascade on IV expansion. Overridden on IV crush (positive vanna flips to buying, supports price into compression).",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 70,
        "name": "Fading Selloff / Zomma-Dampened Breakdown",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day with built in Floor - Compression Transition",
        "action": "SELL LEAN \u2014 Follow trend early, reduce size as bounces deepen. Don't buy until compression confirms",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day \u2014 Bounces are shorting opportunities",
        "dealersAction": "Mechanical Forced Selling \u2014 moderating as Zomma Pos kicks in",
        "charmNetNegative": "Supportive \u2014 Reinforces the built-in floor. Early trend phase: cushions downside alongside fading gamma pressure. Late trend / compression phase: charm buying dominates as gamma exhausts \u2014 floor becomes a springboard for reversals.",
        "charmNetPositive": "Suppressive \u2014 ceiling weak during trend, strengthens into compression",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 71,
        "name": "Vanna Melt Up / Negative Gamma Short Squeeze",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day \u2014 Vanna-Driven Melt-Up",
        "action": "BUY LEAN",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Forced Systematic Buying - Chase the Breakout / Buy as IV Crushes",
        "charmNetNegative": "Weak Supportive to Flat \u2014 vanna + short-gamma chase override charm to the upside",
        "charmNetPositive": "Suppressive (But Vanna will likely override Charm here to the upside)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 72,
        "name": "Counter-Delta Vanna Squeeze / Bearish Book Under BUY Pressure",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day with self-limiting character via positive zomma",
        "action": "BUY LEAN \u2014 Follow vanna squeeze early, reduce size as pullbacks deepen. Don't short until compression confirms \u2014 vanna BUY pressure dominates",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Mechanical Forced Buying \u2014 vanna unwind drives short covering",
        "charmNetNegative": "Weak Supportive to Flat \u2014 vanna overrides charm to the upside (floor irrelevant during squeeze)",
        "charmNetPositive": "Suppressive (But Vanna will likely override Charm here, ceiling fails during squeeze)",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 73,
        "name": "Vanna Melt Up",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Trend Day",
        "action": "BUY LEAN",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Mechanical Forced Buying - vanna (primary) + short-gamma chase (secondary).",
        "charmNetNegative": "Weak Supportive to Flat \u2014 vanna overrides charm to the upside.",
        "charmNetPositive": "Weak Suppressive to Flat \u2014 vanna overrides charm to the upside",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 74,
        "name": "Vanna-Pinned Coiled Compression",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg" },
        "regime": "Compression - with transition risk if IV spikes",
        "action": "Small size BUY \u2014 pin breaks violently. Fade small ranges while IV stays pinned.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with extreme caution \u2014 pin breaks accelerate",
        "dealersAction": "Buy the Dip/ Sell the Rally",
        "charmNetNegative": "Weak Support to Flat \u2014 vanna override to downside on IV spike",
        "charmNetPositive": "Weak Suppression to Flat \u2014 vanna override to downside on IV spike",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 75,
        "name": "Crisis-Continuation Short-Gamma Cascade \u2014 Downside Acceleration at High Vol",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day \u2014 No Floor",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
        "dealersAction": "Pro-cyclical Forced Selling",
        "charmNetNegative": "Supportive \u2014 Weak floor, dominant cascade flow (short-gamma + vanna selling on IV expansion).",
        "charmNetPositive": "Suppressive - compounds the downward lean.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 76,
        "name": "Coiled with risk of downside cascade (primed for violent vol expansion)",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Dormant - Coiled with cascasde Risk",
        "action": "Dormant - Await the SELL. Expected move is small - Cascade Risk if IV spikes. Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts.",
        "actionDirection": "SELL",
        "tilt": "Bounces are shorting entries",
        "dealersAction": "Quiet at flat Low IV (theta harvest on short puts). If triggered: pro-cyclical forced selling \u2014 short-put gamma chase intensifies with IV expansion (Zomma Neg accelerant) + long-put tail vanna selling compounds. No built-in brake.",
        "charmNetNegative": "Supportive \u2014 weak floor at flat Low IV while cascade dormant. Overridden downward if cascade fires (short-put gamma + vanna selling on IV expansion overwhelm charm).",
        "charmNetPositive": "Suppressive \u2014 compounds latent bearish bias while dormant. Accelerant once cascade fires (stacks with dealer selling and vanna selling into the breakdown).",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises, but self exhausting.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 77,
        "name": "High-Vol Coiled Cascade - Accelerating Breakdown Risk",
        "condition": { "IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Trend Day \u2014 No Floor",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are enteries",
        "dealersAction": "Pro-cyclical: Chase / SELL Breakdowns (dominant)",
        "charmNetNegative": "Supportive \u2014 Weak floor, overridden fast by Speed-Pos cascade acceleration once breakdown triggers.",
        "charmNetPositive": "Suppressive \u2014 stacks with Speed-Pos gamma acceleration and vanna selling. Strong breakdown accelerant.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active \u2014 Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
    },
    {
        "id": 78,
        "name": "Dormant; Pre-Cascade Setup",
        "condition": { "IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Pos", "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos" },
        "regime": "Dormant - Coiled Low-Vol. Latent Downside Cascade Risk.",
        "action": "Dormant - Await the SELL. Expected move is small - Cascade Risk if IV spikes. Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts.",
        "actionDirection": "SELL",
        "tilt": "Neutral at rest; bearish if IV spikes. Bounces fade if cascade fires.",
        "dealersAction": "Minimal directional flow. Quiet at flat Low IV (theta harvest). If triggered: pro-cyclical chase \u2014 breakdowns dominant, Zomma Neg amplifies, vanna selling on IV expansion compounds. No brake.",
        "charmNetNegative": "Supportive \u2014 weak floor at flat Low IV while cascade dormant. Overridden downward if cascade fires",
        "charmNetPositive": "Suppressive \u2014 compounds latent bearish bias while dormant. Accelerant once cascade fires",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant \u2014 Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": { "max_vanna_level": false, "ib_bounce": false, "dadu_pinning": false }
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
    const greeks = ["gamma", "zomma", "delta", "vex", "vega", "vomma", "speed", "charm", "vanna"];
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
        netCharm: netGreeks.charm || 0,
        netVanna: netGreeks.vanna || 0,
        ivState: ivState
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

            if (struct.dealersAction && struct.dealersAction !== 'N/A') {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;border:1px solid rgba(255, 255, 255, 0.1);border-radius:6px;padding:8px 10px;background:rgba(255,255,255,0.05);">`
                    + `<span class="ms-detail-label" style="color:#FFF;">Dealers Action</span>`
                    + `<div style="color:#eee;font-size:0.75rem;margin-top:3px;white-space:normal;">${struct.dealersAction}</div>`
                    + `</div>`;
            }

            // ── Net Vanna box ──
            // Vanna flow depends on IV direction:
            //   +Vanna + IV falling → delta decreases → dealers BUY → SUPPORTIVE
            //   +Vanna + IV rising  → delta increases → dealers SELL → SUPPRESSIVE
            //   -Vanna + IV rising  → delta decreases → dealers BUY → SUPPORTIVE
            //   -Vanna + IV falling → delta increases → dealers SELL → SUPPRESSIVE
            const netVannaVal = result.netVanna || 0;
            const vannaIVState = result.ivState || 'Low';
            const vannaIsPos = netVannaVal >= 0;
            // IV High = rising environment, IV Low = falling/compressed environment
            const ivIsRising = vannaIVState === 'High';
            const vannaSupportive = (vannaIsPos && !ivIsRising) || (!vannaIsPos && ivIsRising);
            const vannaFlowLabel = vannaSupportive ? 'SUPPORTIVE' : 'SUPPRESSIVE';
            const vannaFlowColor = vannaSupportive ? '#00BCD4' : '#FFB300';
            const vannaFlowAction = vannaSupportive ? 'Dealers BUYING' : 'Dealers SELLING';
            let vannaDesc = vannaSupportive
                ? `IV ${vannaIVState} — vanna induces dealer buying pressure`
                : `IV ${vannaIVState} — vanna induces dealer selling pressure`;
            
            if (struct.vannaNetPositive && vannaIsPos) {
                vannaDesc += ' — ' + struct.vannaNetPositive;
            } else if (struct.vannaNetNegative && !vannaIsPos) {
                vannaDesc += ' — ' + struct.vannaNetNegative;
            }

            detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;border:1px solid ${vannaFlowColor}33;border-radius:6px;padding:8px 10px;background:${vannaFlowColor}11;">`
                + `<div style="display:flex;justify-content:space-between;align-items:center;">`
                + `<span class="ms-detail-label" style="color:${vannaFlowColor};">Net Vanna</span>`
                + `<span style="font-size:8px;font-weight:700;color:${vannaFlowColor};opacity:0.7;">${vannaFlowAction}</span>`
                + `</div>`
                + `<span class="ms-detail-value" style="color:${vannaFlowColor};font-weight:700;font-size:0.9rem;">${vannaFlowLabel}</span>`
                + `<div style="color:#aaa;font-size:0.65rem;margin-top:3px;white-space:normal;">${vannaDesc} (${netVannaVal >= 0 ? '+' : ''}${netVannaVal.toFixed(4)})</div>`
                + `</div>`;

            // ── Net Charm box ──
            // Positive (+) charm → time decay increases delta for ITM calls/OTM puts → induces SELLING
            // Negative (-) charm → time decay decreases delta for ITM puts/OTM calls → induces BUYING
            const netCharmVal = result.netCharm || 0;
            const charmIsSuppressive = netCharmVal > 0;
            const charmLabel = charmIsSuppressive ? 'SUPPRESSIVE' : 'SUPPORTIVE';
            const charmColor = charmIsSuppressive ? '#FFB300' : '#00BCD4';
            const charmFlowAction = charmIsSuppressive ? 'Dealers SELLING' : 'Dealers BUYING';
            let charmDesc = charmIsSuppressive
                ? 'Time decay induces dealer selling pressure'
                : 'Time decay induces dealer buying pressure';
            
            if (struct.charmNetPositive && charmIsSuppressive) {
                charmDesc += ' — ' + struct.charmNetPositive;
            } else if (struct.charmNetNegative && !charmIsSuppressive) {
                charmDesc += ' — ' + struct.charmNetNegative;
            }

            detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;border:1px solid ${charmColor}33;border-radius:6px;padding:8px 10px;background:${charmColor}11;">`
                + `<div style="display:flex;justify-content:space-between;align-items:center;">`
                + `<span class="ms-detail-label" style="color:${charmColor};">Net Charm</span>`
                + `<span style="font-size:8px;font-weight:700;color:${charmColor};opacity:0.7;">${charmFlowAction}</span>`
                + `</div>`
                + `<span class="ms-detail-value" style="color:${charmColor};font-weight:700;font-size:0.9rem;">${charmLabel}</span>`
                + `<div style="color:#aaa;font-size:0.65rem;margin-top:3px;white-space:normal;">${charmDesc} (${netCharmVal >= 0 ? '+' : ''}${netCharmVal.toFixed(4)})</div>`
                + `</div>`;
                
            if (struct.zommaText) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;"><span class="ms-detail-label">Zomma</span><div style="color:#bbb;font-size:0.7rem;margin-top:3px;white-space:normal;">${struct.zommaText}</div></div>`;
            }
            if (struct.vShapeRecovery) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;"><span class="ms-detail-label">V-Shape Recovery</span><div style="color:#bbb;font-size:0.7rem;margin-top:3px;white-space:normal;">${struct.vShapeRecovery}</div></div>`;
            }
            if (struct.trendEliminator) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;"><span class="ms-detail-label">Eliminates Structure</span><div style="color:#bbb;font-size:0.7rem;margin-top:3px;white-space:normal;">${struct.trendEliminator}</div></div>`;
            }
            if (struct.stochastic) {
                detailsHTML += `<div class="ms-detail-item" style="grid-column:1/-1;"><span class="ms-detail-label">Stochastic Entry</span><div style="color:#bbb;font-size:0.7rem;margin-top:3px;white-space:normal;">${struct.stochastic}</div></div>`;
            }

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