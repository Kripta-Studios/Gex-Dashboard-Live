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
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Volatile bearish drift with bounded downside / Mean-reverting within bearish regime",
        "action": "SELL LEAN. Sell the Rally. But DON'T chase breakdowns.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade both extremes but lean short.  Volatile, Expect Whipsaw",
        "dealersAction": "SELL the rally dominant.  Pro-cyclical gamma hedging. Vanna piles on as buyer on selloffs  — cushions the move and drives mean-reversion at extremes.",
        "charmNetNegative": "Charm buys, active. Small counter-flow against the chase, gets overrun. Pos Vex + Pos Vomma are the real defense.  SELL LEAN, fade rallies. Don't chase breakdowns — but charm won't save you either.",
        "charmNetPositive": "Charm sells, active. Stacks with the chase → compounds the breakdown. Dangerous downside cell. SELL LEAN harder. Don't fade the break — let it run. Cover at exhaustion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises; Less overhead resistence.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 2,
        "name": "Low-Vol Grind-Up / Melt-Up — Dealers Comfortable with Upside Drift",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day - Pos Speed grind. ",
        "action": "BUY on Pullback. Pullbacks are generally shallow. ",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "BUY the dip dominant. Pro-cyclical hedging — buying into strength, chase accelerates on rallies. Ride the trend — on IV spike trend changes to dominant selling. ",
        "charmNetNegative": "Charm buys, dormant. Aligned with melt-up but too small to matter. Ignore charm. BUY-the-pullback per row. Max Vanna if above, can act as magnet.",
        "charmNetPositive": "Charm sells, small but active. Mild headwind on the chase — caps rallies, deepens dips slightly. Melt-up still wins.  BUY-the-pullback per row. Grind slower than typical melt-up.",
        "vannaNetNegative": "Suppressive",
        "vannaNetPositive": "Supportive",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "Yes, but not always",
        "vShapeRecovery": "",
        "spreads": "CCS",
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 3,
        "name": "High-IV Bearish Pin — Vanna-Cushioned Drift with Tail Exposure",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Fragile Compression ",
        "action": "Fade extremes while pin holds. SELL LEAN on IV expansion — pin breaks down with no wing catch (Vomma Neg). Ride the break — no recovery mechanism.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade extremes. On gamma-flip breakdown: SELL trend, ride to exhaustion (no wing catch).",
        "dealersAction": "Sell rallies / Buy dips weakly (gamma pin with bearish lean). On IV lifts, Vex pos  adds vanna buying — cushions downside moves at pin. But no wing catch if spot breaches tail. ",
        "charmNetNegative": "Charm buys, active. Small support, floor erodes anyway. No catch at tail. SELL LEAN. Mean-reversion AM only. Don't buy late breakdowns expecting a bounce.",
        "charmNetPositive": "Charm sells, active. Hardens ceiling, weakens floor. Retail: SELL LEAN, fade rallies aggressively — ceiling fails early. Breakdown uncaught at tail. Cover at exhaustion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 4,
        "name": "Low-IV Bearish Drift Pin — Vanna Cushion Loaded",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Fragile Compression ",
        "action": "Neutral /Small BUY LEAN -  Buy the dip while the market is calm. ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade extremes. On gamma-flip breakdown: SELL trend, ride to exhaustion (no wing catch).",
        "dealersAction": "Dormant while vol compressed. Sell rallies / Buy dips weakly (gamma pin with bearish lean). On IV lifts,Vex pos  adds vanna buying — cushions downside moves at pin. But no wing catch if spot breaches tail. ",
        "charmNetNegative": "Charm buys, small but active. Thin pin support — overrun when Neg Vex fires, no Vomma catch.  Range trade to NEUTRAL while VIX low. Exit dip-buys on first IV tick — trap is charm's grip breaking.",
        "charmNetPositive": "Charm sells, small but active. Slow drag against row's BUY LEAN; pin holds in compressed vol.  BUY LEAN / Neutral per row, mild tilt only. Exit on first vol tick — charm is the slow leak.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 5,
        "name": "High-IV Long Vol Bearish Skew — Vanna-Cushioned Drift ",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression ",
        "action": "SELL LEAN into PIN — PIN holds with bearish drift. On vol expansion, expect vanna-cushioned descent (not waterfall). ",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade both extremes — vanna cushion protects downside, pin caps upside.",
        "dealersAction": "Sells rallies / Buys dips (gamma pin with bearish lean). On IV lifts, Vex pos adds vanna buying — cushions downside moves during vol expansion.",
        "charmNetNegative": "Charm buys, active. Small support; Vex + Vomma do the work. SELL LEAN, cushioned descent not waterfall. Cover at IV peak.",
        "charmNetPositive": "Charm sells, active. Hardens ceiling, weakens floor — but Vomma catches at tail. SELL LEAN, fade rallies aggressively. Defined-move trade.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "Yes",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 6,
        "name": "Long Vol Convexity Book - Loaded with Vanna Cushion on Downside",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression ",
        "action": " BUY LEAN into PIN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade both extremes — vanna cushion protects downside, pin caps upside.",
        "dealersAction": "Passive / Dormant while vol compressed. On IV expansion, Vex pos triggers forced buying — cushions any downside move.",
        "charmNetNegative": "Charm buys, dormant. Aligned with BUY LEAN, too small to matter. Wing caught structurally.  BUY LEAN per row. Cushioned dip on vol expansion.",
        "charmNetPositive": "Charm sells, small but active. Slow drag against BUY LEAN; Vomma still catches. Retail: BUY LEAN, mild tilt only. Exit dip-buys on first vol tick.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 7,
        "name": "High-IV Bearish Pin with Pre-Breakdown Structure — Coiled for downside vol expansion",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression — Bear-Coiled",
        "action": "SELL LEAN into PIN on IV expansion — pin breaks down. Chop otherwise.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes while pin holds. On gamma-flip breakdown: SELL trend, ride the bear move.",
        "dealersAction": "Sell rallies / Buy dips weakly (gamma pin with bearish lean). Vex Neg compounds selling on IV lifts — pin breaks down on vol expansion.",
        "charmNetNegative": "Charm buys, active. Small support but overrun.  Neg Vex fires the break, Vomma catches only at tail. SELL LEAN, ride don't fade. Fast descent. Cover at IV peak.",
        "charmNetPositive": "Charm sells, active. Stacks with Neg Vex on rallies; floor weaker, ceiling harder. Vomma backstops. SELL LEAN, fade rallies aggressively. Defined-move trade.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": "Break of Gamma Flip",
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 8,
        "name": "Low-IV Bearish Compression — Loaded for Downside with Wing Convexity Payoff",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression — Bear-Coiled (Latent)",
        "action": "AVOID Buys. Neutral / Small SELL LEAN  on rally— pin holds while vol compressed. Await vol expansion trigger for size.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes with bearish lean. Don't fade downside — break risk on vol expansion.",
        "dealersAction": "Buy dips weakly / Sell rallies (gamma pin with bearish lean). Vex Neg compounds selling on IV lifts — pin breaks down on vol expansion.",
        "charmNetNegative": "Charm buys, small but active. Thin pin grip — overrun when Neg Vex fires; Vomma catches at tail. AVOID buys hard. First vol tick = size short to Vomma catch.",
        "charmNetPositive": "Charm sells, small but active. Slow bearish drag; pin holds for now. Small SELL LEAN on rallies — escalate on first vol tick. Don't get long the range. ",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 9,
        "name": "Short-Call Gamma Squeeze — Upside Cascade at High IV",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Trend Day (Upside Squeeze)",
        "action": "AVOID Shorts. BUY LEAN on rally confirmation — squeeze risk. Vex Neg catches the squeeze at top.",
        "actionDirection": "BUY LEAN",
        "tilt": "Trend Day , Pullbacks are entries",
        "dealersAction": "Mechanical forced BUYING. Pro-cyclical chase on rallies (short-call squeeze). Passive on downside. Dormant while vol compressed.",
        "charmNetNegative": "Charm fuels the squeeze, no ceiling. Charm buying stacks with chase; Neg Vomma = no catch.  BUY LEAN, ride to organic exhaustion. Cover at IV peak.",
        "charmNetPositive": "Charm slows the squeeze, doesn't catch it. The top comes from squeeze exhaustion, not from charm/vex defense. Reduce long size into rallies but don't flip short.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "Yes - The moment IV prints a lower high while spot prints a lower low — that is the turn, regardless of what price action looks like at that moment.",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 10,
        "name": "Dealer Short Gamma Trap — Loaded for Upside Squeeze",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day ",
        "action": "BUY LEAN (small) on upside trigger. Avoid shorts — squeeze loaded. No directional edge in dormant state — await IV trigger.",
        "actionDirection": "BUY LEAN",
        "tilt": "Transitional — squeeze loaded. Await entry. ",
        "dealersAction": "Dormant while vol compressed. Pro-cyclical chase on rallies (short-call squeeze loaded). Passive on downside. ",
        "charmNetNegative": "Charm is a non-factor here. Latent buying drip too small to matter against the loaded short-call book. Real danger: squeeze trigger . First IV tick = size long.",
        "charmNetPositive": "Weak ceiling, overrun on trigger. Charm + Vex dormant in compressed vol; squeeze overrides both.  Don't fade rallies — charm caps nothing.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 11,
        "name": "Dealer-Overwhelmed Bearish Drift — Pos dealer book absorbs but doesn't reverse external selling",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with bearish drift",
        "action": "SELL LEAN. Dips are Deep & dip-buying is WEAK. Dealer book absorbs but doesn't reverse. Don't fight the external flow.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes. Don't expect bounces on dips.",
        "dealersAction": "Sells rallies/ Buys dips. IV spike causes deep retracements that do not recover. ",
        "charmNetNegative": "Charm sells, active. Stacks ceiling, erodes floor through session. Vomma catches at tail.  Mean-reversion works AM, fails PM — don't buy late breakdowns expecting bounce.— bearish drift gets help.",
        "charmNetPositive": "Charm buys, active. Floor doubly defended; ceiling leaks. SELL LEAN, but delay entry. Wait for rally exhaustion. Squeeze risk into close.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "Yes - The moment IV prints a lower high while spot prints a lower low — that is the turn, regardless of what price action looks like at that moment.",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 12,
        "name": "Bullish Drift Ignition / Melt Up",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with bullish drift",
        "action": "BUY LEAN. Dips shallow, dip-buying strong, max-gamma magnet above. (You almost always get a tradeable pullback. Watch Vwap). ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes. ",
        "dealersAction": "Sells rallies/ Buys dips. IV spike causes deep retracements that do not recover. ",
        "charmNetNegative": "Charm sells, dormant. — too small to matter.  Dips shallow early, fade late. BUY LEAN. Overshoots above the ceiling get sold — charm working, not breaking.",
        "charmNetPositive": "Charm buys, active. Charm IS the melt-up. Pin stops capping, becomes magnet. BUY LEAN, face-ripper grind. Chase or sit out — dips won't come.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises; Less overhead resistence.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 13,
        "name": "Bearish Pin — Vol compression with downside drift risk",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Compression with bearish drift — downside break risk",
        "action": "SELL LEAN - Neg Vex means IV spikes force additional selling",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes. Don't fade downside — break risk on vol expansion.",
        "dealersAction": "Sell the Rally aggressively / Buy the Dip weakly (gamma pin with bearish lean). On IV lifts, Vex Neg compounds selling. Pin holds while vol compressed.",
        "charmNetNegative": "Charm buys, active. Too small to defend; floor erodes. Pos Vega cushions briefly, Neg Vomma reverses → no catch at tail.  SELL LEAN. Don't fade the break. Cover at exhaustion only.",
        "charmNetPositive": "Charm sells, active. Hardens ceiling, weakens floor; downside still uncaught (Neg Vomma). SELL LEAN, fade rallies confidently — ceiling fails early. Size shorts for runaway move on breakdown.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 14,
        "name": "Low-IV Compression with Bearish Skew — Fragile Pin",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Compression with bearish drift — downside break risk",
        "action": "AVOID BUYS. Neutral. Pin likely below (dex neg).  Await the SELL in high IV.  Pin holds while vol compressed but bearish drift within compression — downside cascade risk (no wing catch).",
        "actionDirection": "BUY",
        "tilt": "Fade upside extremes. Don't fade downside — break risk on vol expansion.",
        "dealersAction": "Sell the rally aggressively / Buy the dip weakly (gamma pin with bearish lean). On IV lifts, Vex Neg compounds selling. Pin holds while vol compressed.",
        "charmNetNegative": "Charm buys, small but active. Thin pin grip — overrun when Neg Vex fires; loaded cascade, no catch below. AVOID buys hard. First IV tick = size short, ride uncaught.",
        "charmNetPositive": "Charm sells, small but active. Stacks with Neg Vex on rallies → ceiling hardens; downside undefended on break. Fade rallies on vol wake. Never buy dips — no floor below.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 15,
        "name": "The Waterfall Sell- Off",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Neg",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Trend Day no V-recovery, ride to exhaustion.",
        "action": "SELL the breakdown. Trend-follow aggressively. Don't catch the knife but watch for exhaustion.Possible V shape recovery. ",
        "actionDirection": "SELL",
        "tilt": "Trend Day , bounces are entries",
        "dealersAction": "Forced pro-cyclical selling on every downtick.Acceleration as spot moves. No flow reversal at tails. in low IV  the dealer is dormant - dealer does minimal flow.",
        "charmNetNegative": "Charm buys, swamped. Counter-flow can't arrest the cascade. SELL the breakdown. Don't fade — charm can't help. Cover at organic exhaustion only.",
        "charmNetPositive": "Charm sells, active. Every flow aligned, no counter-flow exists. SELL harder than Neg Charm version. Ride to organic exhaustion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 16,
        "name": "Volmageddon Setup / Complacency Trap",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Neg",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Dormant - Coiled with Trend Day cascasde Risk",
        "action": "Dormant - Await the SELL.  Expected move is small - Cascade Risk if IV spikes.  Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts. ",
        "actionDirection": "BUY",
        "tilt": "Wait for IV wake-up (transition to High IV row). Don't fade the eventual breakdown.",
        "dealersAction": "Dormant - dealer does minimal flow because IV is low and price isn't moving much. BUT the book is primed: any IV spike triggers forced pro-cyclical selling",
        "charmNetNegative": "Charm buys, small but active. Thin pin support — overrun on IV expansion, no defense anywhere. Await the SELL. First IV tick = size short, runaway move.",
        "charmNetPositive": "Charm sells, small but active. Slow drag now, accelerant on trigger. Every flow loaded the same direction. Most dangerous loaded setup. First IV tick = size short aggressively.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 17,
        "name": "High-IV Long Gamma Compression — Fragile Pin with downside break risk (Vex Neg)",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Fragile Compression — pin-break risk on IV expansion.",
        "action": "SELL LEAN — dips are deep. Break-down leads to controlled descent toward wing strike. Slow U, not sharp V. Pre-break level typically not recovered.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade upside extremes — break risk on vol expansion.",
        "dealersAction": "Buy the dip / Sell the rally (gamma pin). On IV lifts, Vex Neg forces dealer selling — vanna flow breaks the pin to the downside. Pin stable while vol compressed.",
        "charmNetNegative": "Charm sells, active. Stacks with Neg Vex on rallies, erodes floor; Vomma catches at wing. SELL LEAN. Fade rallies aggressively. Defined descent to wing strike.",
        "charmNetPositive": "Charm buys, active. Floor doubly defended; ceiling leaks. SELL LEAN, delay entry. Wait for rally exhaustion. Vomma catches breakdown at wing.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 18,
        "name": "Long Gamma Pin —  downside break on vol expansion",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Fragile Compression — pin-break risk on IV expansion.",
        "action": "Neutral/Cautious BUY Lean into Pin. Pin holds while vol compressed. Exit on IV expansion — downside break risk. Don't chase upside ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade upside extremes — break risk on vol expansion.",
        "dealersAction": "Buy the dip / Sell the rally (gamma pin). On IV lifts, Vex Neg forces dealer selling — vanna flow breaks the pin to the downside. Pin stable while vol compressed.",
        "charmNetNegative": "Charm sells, small but active. Slow bearish drag; pin holds for now. Retail: Cautious BUY Lean per row, mild tilt only. Exit on IV expansion.",
        "charmNetPositive": "Charm buys, small but active. Slow floor reinforcement, pin migrates higher session-over-session. BUY Lean per row with mild long tilt. Exit on IV expansion —— charm doesn't save the floor but Vomma catches at wing.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 19,
        "name": "Compression / Pin Day (with squeeze potential)",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Compression — vol-crush risk. Pin until wing breach",
        "action": "Cautious SELL LEAN into PIN. Respect the PIN. Squeeze risk bias to upside.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the dip aggressively / Sell the rally weakly. Wing breach either side flips dealer to forced chaser — upside biased due to Pos Delta.. Respect the PIN",
        "charmNetNegative": "Charm sells, active. Stacks with rally-cap; mild offset against squeeze bias. Cautious SELL LEAN. Respect PIN. Downside uncaught if pin fails  although bias is upside squeeze.",
        "charmNetPositive": "Charm buys, active. Amplifies upside squeeze risk; no catch above. Retail: Cautious SELL LEAN, size shorts smaller — squeeze risk elevated. Don't fade rallies aggressively.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 20,
        "name": "High Confidence Grind / PIN",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Compression",
        "action": "BUY LEAN with conviction. Respect the PIN.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes/ PIN",
        "dealersAction": "Buy the dip aggressively / Sell the rally weakly. Wing breach either side flips dealer to forced chaser — upside biased due to Pos Delta.. Respect the PIN",
        "charmNetNegative": "Charm sells, small but active. Slow bearish drag; pin holds for now, breaks fast on expansion (no Vomma catch).  BUY LEAN per row, mild tilt only. Exit on first vol tick — downside wing breach uncaught.",
        "charmNetPositive": "Charm buys, small but active. Slow floor reinforcement; loads upside squeeze. Retail: BUY LEAN with conviction. Size for asymmetric upside on wing breach.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 21,
        "name": "Possible Short-Cover Cascade / Upside Gamma Squeeze ",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Transitional Compression - Trend Day (Violent Upside) with squeeze mechanics. But squeeze requires a catalyst like news. ",
        "action": "AVOID Short or size small. Buy dips aggressively — Squeeze risk to upside. Assumes short-cover catalyst active. Pre-catalyst: pin/range regime.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean (Squeeze risk)",
        "dealersAction": "Pre-cascade: sells rallies, buys dips (gamma pinning). Post-trigger: forced buyer. Low IV vanna melt up. ",
        "charmNetNegative": "Charm sells, swamped. Counter-flow drowned by squeeze cascade; full defense absorbs downside. Retail: AVOID Short. Buy dips aggressively.",
        "charmNetPositive": "Charm buys, active. Apex bullish setup. Every flow aligned up; full defense supports. Retail: AVOID Shorts hard. Buy dips aggressively, ride to organic exhaustion or wing strike.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 22,
        "name": "Vanna-fueled Melt Up (Index can push far beyond expectations)",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression with upward drift",
        "action": "BUY with conviction — vanna-fueled melt-up",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean",
        "dealersAction": "Low IV vanna melt up. High IV sells rallies, buys dips pre-cascade. On news post cascade: buys dips aggressively. ",
        "charmNetNegative": "Charm sells, small but active. Slow bearish drag against the vanna-fueled melt-up — too small to fight the dominant flow. BUY with conviction per row. Charm provides minor pullbacks that get bought instantly. Don't wait for deeper dips — they won't come.",
        "charmNetPositive": "Charm buys, active — IS the melt-up. Sustained grind up. BUY with conviction. Face-ripper grind — index can push far beyond expectations. Chase or sit out.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises; Less overhead resistence.",
        "mxVannaLevelsWork": "No",
        "vShapeRecovery": "",
        "spreads": "PCS",
        "stochastic": "Yes - Works on Pullbacks. Pullbacks can be decent or small.",
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 23,
        "name": "Short Gamma Cascade / Negative Convexity Unwind with built-in Feedback Loop ( V-recovery mechanism)",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day (Likely Violent) with with built in V-recovery mechanism",
        "action": "SELL the breakdown. Trend-follow aggressively but watch for IV peak — the tail hedge activates V-recovery earlier than pure Waterfall. Don't ride to exhaustion.",
        "actionDirection": "SELL",
        "tilt": "Trend Day — pullbacks are entries during the cascade. BUT V-recovery comes faster than Waterfall due to tail activation.",
        "dealersAction": "Active / Forced pro-cyclical selling on every downtick in High IV. Short ATM gamma drives selling into the cascade until OTM wings activate near IV peak — dealer flow flips from selling to buying, fueling V-recovery. Decays to inactive as IV normalizes.",
        "charmNetNegative": "Charm buys, swamped. Counter-flow drowned by cascade; Vex + Vega + Vomma drive V-recovery. SELL per row. Cover at IV peak / V-recovery point. Recovery comes faster than Waterfall.",
        "charmNetPositive": "Charm sells, active. Stacks with cascade; caps V-recovery bounce. SELL harder. On V-recovery, don't flip long aggressively — ceiling hardened. Cover short at IV peak.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "No",
        "vShapeRecovery": "Yes - Usually Large Gamma Wall",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 24,
        "name": "Low Vol Coiled Spring — Bearish Skew with latent V-recovery mechanism (armed but not triggered)",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day  — Bearish Bias",
        "action": "Awaiting Trigger/ IV Spike. Minimal hedging pressure in low IV.",
        "actionDirection": "N/A",
        "tilt": "Neutral",
        "dealersAction": "Inactive / position carrying in Low IV. Short ATM straddle dormant, OTM wings cheap and armed awaiting vol expansion trigger. On IV breakout, flips to forced pro-cyclical selling with V-recovery mechanism latent until activated.",
        "charmNetNegative": "Charm buys, small but active. Thin pin grip; cascade fires on vol expansion, V-recovery still activates. Awaiting trigger. First IV tick = size short, cover at V-recovery.",
        "charmNetPositive": "Charm sells, small but active. Slow drag; on trigger, caps V-recovery bounce. Awaiting trigger. First IV tick = size short. V-recovery long weaker here — size smaller.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 25,
        "name": "Active Short-Vol Cascade / Volatile Bearish Drift",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Neg",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Trend Day",
        "action": "SELL LEAN on rallies. Bearish drift dominant despite Pos Zomma cushion.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are entries",
        "dealersAction": "Forced seller on IV lift (Neg Vex). Cascade risk on IV wake-up or break. Passive theta collection in calm.",
        "charmNetNegative": "Charm sells, active. Stacks with bearish drift; weakens Pos Delta cushion; no Vomma catch. SELL LEAN on rallies aggressively. Cushion fragile — no floor below.",
        "charmNetPositive": "Charm buys, active. Adds to dip-cushion; cushion still fragile (Neg Vomma).  SELL LEAN per row, less aggressively. Don't over-size shorts — minor dip support.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 26,
        "name": "Dormant Short-Vol Collector / Pre-Cascade Setup (Bearish Trigger)",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Neg",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day ",
        "action": "Small size BUY LEAN in calm (Pos Delta bias). AVOID heavy long positions — regime is cascade-capable on IV wake-up. Options: buy cheap tail protection",
        "actionDirection": "BUY LEAN",
        "tilt": "Buy dips small in dormant state. Watch IV — cascade fires bearishly on IV wake-up.",
        "dealersAction": "Passive theta collection in calm. Forced seller on IV lift (Neg Vex). Cascade risk on IV wake-up or break.",
        "charmNetNegative": "Charm sells, small but active. Slow bearish drag; pin holds for now, breaks fast on trigger. Retail: Small BUY LEAN per row, mild bearish tilt. Buy tail protection. Exit on first vol tick.",
        "charmNetPositive": "Charm buys, small but active. Minor cushion reinforcement; doesn't save floor on trigger. Retail: Small BUY LEAN, mild long tilt. Buy tail protection. Exit on first vol tick.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 27,
        "name": "Active Squeeze / Short-Vol Capitulation — Melt-Up Cascade",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Neg",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Trend Day",
        "action": "AVOID Shorts. BUY the breakout — short-covering cascade",
        "actionDirection": "BUY",
        "tilt": "Trend Day , Pull backs are enteries",
        "dealersAction": "Forced buying/ squeeze. Passive hedging in calm.",
        "charmNetNegative": "Charm buys, active. Fuels the squeeze. Aligned with cascade + Pos Vex; no Vomma cap above. Retail: AVOID Shorts hard. BUY breakout, ride to exhaustion. Cover at IV peak.",
        "charmNetPositive": "Charm sells, active. Headwind on squeeze, overrun. Squeeze runs anyway. Still AVOID Shorts. Don't fade rallies — charm doesn't cap.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 28,
        "name": "Pre-Squeeze Setup / Short-Vol Capitulation Primer (Dormant)",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Neg",
            "Vomma": "Neg",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day — dormant bullish pre-squeeze setup ",
        "action": "BUY LEAN on dips. Dormant squeeze setup",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean.",
        "dealersAction": "Passive hedging in calm. Primed for forced bullish squeeze on IV lift or rally into gamma zone.",
        "charmNetNegative": "Charm buys, small but active. Loaded squeeze fuel; fires on trigger, no cap above. Awaiting trigger. First IV tick = size long. Apex squeeze setup on this row.",
        "charmNetPositive": "Charm sells, small but active. Slow counter-flow against latent squeeze loading; pin holds for now. On trigger, charm overrun.  Awaiting trigger per row. First IV tick = size long, but less aggressively than Neg Charm version — charm provides small headwind.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 29,
        "name": "Orderly Sell Off (grind) / Hedged Bear Market",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with bearish drift",
        "action": "SELL LEAN on rallies.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the dip/ Sell the rally ",
        "charmNetNegative": "Charm buys, active. Stacks with Pos Vex on dips; Vomma catches at wing. SELL LEAN on rallies. Cushioned descent to wing strike. Cover at Vomma activation.",
        "charmNetPositive": "Charm sells, active. Hardens cap modestly; floor still defended by Pos Vex + Vomma. Retail: SELL LEAN on rallies, pin holds longer. Wait for rally exhaustion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 30,
        "name": "Hedged Long-Vol Compression / Orderly Grind Higher ",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with upside drift",
        "action": "BUY LEAN on dips. ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the dip/ Sell the rally ",
        "charmNetNegative": "Charm buys, small but active. Aligned with BUY LEAN bias; Pos Vex + Vomma defend dips. BUY LEAN on dips per row. Floor robust.",
        "charmNetPositive": "Charm sells, small but active. Slow bearish drag; floor still defended structurally.  BUY LEAN on dips per row, mild bearish tilt only. Don't oversize long — charm provides slow headwind. Floor defended structurally.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 31,
        "name": "Active Vanna-Hollow Squeeze / Spot-Vol Correlation Trend Day",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day — spot-vol correlation dependent (squeeze firing)",
        "action": "Correlation matrix in Tilt determines tactical direction.",
        "actionDirection": "N/A",
        "tilt": "Spot Down + VIX Flat: Dealers are Sellers; Spot Down + VIX Exploding: Dealers are Confused/Neutral; Spot Up + VIX Dropping: Dealers are Aggressive Buyers; Spot Up + VIX Flat/Rising slightly: Dealers are Moderate Buyers ",
        "dealersAction": "Pro-cyclical hedging / Chasing. Passive hedging in calm.",
        "charmNetNegative": "Charm buys, active. Aligned with bullish squeeze; fights bearish scenarios weakly. Await correlation confirmation. Bullish regime: BUY. Bearish regime: cascade dominates.",
        "charmNetPositive": "Charm sells, active. Helps shorts if bearish regime fires; fights longs if bullish regime fires. Await correlation confirmation. Bullish regime: BUY. Bearish regime: cascade dominates.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 32,
        "name": "Vanna-Hollow Coiled — Direction Unconfirmed",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Dormant — Vanna Coiled. Trend Day Risk in Either Direction",
        "action": "Dormant. Await spot-vol correlation confirmation. No directional trade — correlation matrix not yet revealed.",
        "actionDirection": "N/A",
        "tilt": "Transitional — not yet trend day. Neutral. Do not front run. Wait for spot-vol correlation to confirm direction.",
        "dealersAction": "Passive hedging in calm.Pro-cyclical hedging / Chasing if IV wakes up.",
        "charmNetNegative": "Charm buys, small but active. Pre-melt-up bid building; bullish-correlation-conditional.  Dormant, await correlation. Don't front-run.",
        "charmNetPositive": "Charm sells, small but active. Light cap; direction-conditional. Dormant, await correlation. Don't front-run.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 33,
        "name": "Long convexity, Long volatility / Coiled Spring",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression",
        "action": "AVOID the Short. BUY the Dips with conviction. Coiled bullish spring — upside break most likely, short trades have no edge.",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes, waiting for breakout",
        "dealersAction": "Buy the dip aggressively. Sell the rally weakly. (Waiting for the breakout).",
        "charmNetNegative": "Charm sells, swamped. Counter-flow drowned by every-Greek-aligned bullish setup. AVOID Short. BUY Dips with conviction — coiled spring still triggers upside.",
        "charmNetPositive": "Charm buys, active. Apex bullish setup. Every flow aligned up with full defense. AVOID Shorts hard. BUY Dips aggressively, ride to organic exhaustion or wing strike.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 34,
        "name": "Vanna-fueled Melt Up / Expansion",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with aggressive upside drift (vanna-fueled). Active melt-up",
        "action": "BUY with conviction. Avoid shorts.",
        "actionDirection": "BUY",
        "tilt": "Buy pullbacks aggressively, ride the vanna grind. No structural ceiling.",
        "dealersAction": "Buy the dip aggressively. Sell the rally weakly. Aggressive upward drift.",
        "charmNetNegative": "Charm sells, small but active. Minor counter-flow; defense stack defends pullbacks. BUY with conviction per row. Pullbacks bought instantly — don't wait for deeper dips.",
        "charmNetPositive": "Charm buys, active — IS the melt-up. Sustained grind with Pos Vomma defining upside; full defense cushions pullbacks. BUY with conviction. Face-ripper grind — index can push far beyond expectations. Chase or sit out.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "No",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": "Yes - Works on Pullbacks",
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 35,
        "name": "High-IV Call Magnet (Pin) / Active Magnet Grind",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression with mechanical drift into Pin.",
        "action": "SELL LEAN on extension only into pin strike. Neg Speed punishes extension.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes with lean towards PIN",
        "dealersAction": "Buy the dip aggressively. Sell the rally weakly. Dealer positioned for active magnet/pin.",
        "charmNetNegative": "Charm sells, active. Stacks with Pos Vex on rallies away from pin; combined with Neg Speed (gamma shrinks on extension), upside extensions fail back to pin. Pin defends. SELL LEAN into pin strike. Fade upside extensions confidently. Don't fade dips back to pin.",
        "charmNetPositive": "Charm buys, active. Reinforces floor on dips; magnet caps extensions regardless. Retail: SELL LEAN into pin strike per row. Buy dips back to pin with confidence. Magnet does the capping.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 36,
        "name": "Possible Volatility Expansion Setup (If IV wakes up)",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression / coiled pre-expansion. Aggressive upside drift (Pin above)",
        "action": "BUY LEAN with conviction on dips. Coiled setup.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes - Buy dips with upside lean into the coil. ",
        "dealersAction": "Buy the dip aggressively.  Sell the rally weakly. Dealer positioned for vol expansion.",
        "charmNetNegative": "Charm sells, small but active. Minor headwind against bullish bias; magnet holds pin. Retail: BUY LEAN on dips per row. Charm provides drag but doesn't threaten the setup.",
        "charmNetPositive": "Charm buys, small but active. Slow floor reinforcement; loads bullish breakout if IV wakes. Retail: BUY LEAN with conviction. Coiled bullish — charm loads the floor for the vol expansion trigger.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 37,
        "name": "Machine Driven Short Squeeze",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day",
        "action": "AVOID Shorts. BUY pullbacks aggressively — squeeze is mechanical. DO NOT CHASE at the highs — wait for the dip. ",
        "actionDirection": "BUY",
        "tilt": "Momentum Breakout, High Probability Upside, Pullbacks are enteries",
        "dealersAction": "Aggressive chasing. Passive pinning in calm",
        "charmNetNegative": "Charm sells, active. Headwind on squeeze; deepens pullbacks,  better entries. Vomma catches at wing. AVOID Shorts. BUY pullbacks aggressively — charm makes dips deeper. Don't chase highs.",
        "charmNetPositive": "Charm buys, active. Every flow aligned up; Vomma catches at wing, Neg Speed produces dip. AVOID Shorts hard. DO NOT CHASE highs — wait for the dip, next leg is explosive.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 38,
        "name": "Pre-Squeeze Setup / Machine-Driven Squeeze Primer",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day  — dormant, pre-squeeze setup",
        "action": "BUY LEAN on dips. Dormant bullish squeeze setup.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean.",
        "dealersAction": "Passive pinning in calm. Primed for bullish agressive chasing on IV lift",
        "charmNetNegative": "Charm sells, small but active. Slow headwind delays trigger; pin holds for now. BUY LEAN on dips per row. Headwind doesn't prevent the squeeze.",
        "charmNetPositive": "Charm buys, small but active. Loads squeeze; pin migrates higher session-over-session. BUY LEAN on dips with conviction. Loaded bullish setup — first IV tick fires the cascade.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 39,
        "name": "Long Convexity Melt-Up",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with upside drift ",
        "action": "AVOID Shorts. BUY the dip with conviction. ",
        "actionDirection": "BUY",
        "tilt": "Fade Extremes with upside lean",
        "dealersAction": "Buy the dip/ Sell the rally",
        "charmNetNegative": "Charm sells, active. Stacks with Neg Vex caps; deepens dips. Vomma catches wing. Retail: AVOID Shorts. BUY the dip — charm makes dips deeper, better entries. Don't chase rallies.",
        "charmNetPositive": "Charm buys, active. Every flow except Neg Vex aligned up; mechanical rally-caps via Vex. AVOID Shorts hard. BUY the dip aggressively — next leg explosive. Don't chase, wait for Vex retracement.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 40,
        "name": "Pre-Ignition Setup / Low-IV Long-Gamma Compression with Bullish Coil",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with upside drift ",
        "action": "BUY LEAN/ Buy the Dip",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean",
        "dealersAction": "Buy the dip/ Sell the rally",
        "charmNetNegative": "Charm sells, small but active. Minor headwind delays ignition; floor defended structurally.  BUY LEAN per row. Headwind doesn't prevent the coil.",
        "charmNetPositive": "Charm buys, small but active. Loads bullish coil; pin migrates higher session-over-session. BUY LEAN with conviction. Loaded bullish coil — charm pre-loads the ignition.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 41,
        "name": "High Volatility Grind Up",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with Upside Drift",
        "action": "AVOID Shorts. BUY LEAN on dips. High-IV grind up with IV-crush tailwind. ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean. Strong Floor. ",
        "dealersAction": "Buy the dip aggressively. Sell the rally weakly. Mild upward drift.",
        "charmNetNegative": "Charm buys, active. Fuels grind; Pos Speed amplifies; IV-crush removes Vex cap. AVOID Shorts. BUY LEAN on dips with conviction.",
        "charmNetPositive": "Charm sells, active. Mechanical rally caps via charm + Neg Vex; floor defended. AVOID Shorts. BUY LEAN on dips — rrally retracements ARE the dip entries. Don't short the cap.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 42,
        "name": "Dealer Long Gamma/ Low Volatility Grind Up",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with Upside Drift",
        "action": "BUY LEAN on dips. ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes with upside lean. Strong Floor. ",
        "dealersAction": "Buy the dip aggressively. Sell the rally weakly. Mild upward drift.",
        "charmNetNegative": "Charm buys, small but active. Aligned with grind; pin migrates higher.  BUY LEAN on dips. Slow grind.",
        "charmNetPositive": "Charm sells, small but active. Caps rallies on vol wake; floor defended. Retail: AVOID Shorts. BUY LEAN on dips.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 43,
        "name": "Gamma Drain Short Squeeze",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day",
        "action": "BUY",
        "actionDirection": "BUY",
        "tilt": "Momentum Chasing, Trend Day. ",
        "dealersAction": "Forced buying - Delta buffer consumed by gamma drain — mechanical buying as delta flips. In low IV dealers are mostly dormant.",
        "charmNetNegative": "Charm sells, active. Accelerates Pos Delta buffer consumption — getting the dealer to the delta-flip point faster. Once flipped, forced covering squeeze fires. BUY per row. Neg Charm accelerates the squeeze trigger timing. Charm helps the squeeze fire sooner; don't wait for ideal entry — chase the breakout when delta flips.",
        "charmNetPositive": "Charm buys, active. Reinforces buffer → delays trigger, more violent squeeze when fires. BUY per row. Size for asymmetric upside — Pos Charm cell produces the most violent squeeze.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "Yes - Usually Large Gamma Wall",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 44,
        "name": "Low Vol Coiled — Upside Squeeze Risk (dormant)",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Dormant — Squeeze Risk",
        "action": "BUY but future traders await trigger. Can chop until trigger. Option traders can buy cheap calls/call spreads while IV is suppressed.",
        "actionDirection": "BUY",
        "tilt": "Neutral at rest; bullish if squeeze fires. ",
        "dealersAction": "Quiet theta harvest. If triggered: forced buying — gamma drain consumes delta, mechanical squeeze up.",
        "charmNetNegative": "Charm sells, small but active. Pre-loads buffer consumption. BUY but await trigger. First IV tick = squeeze fires sooner. Buy cheap calls while IV suppressed.",
        "charmNetPositive": "Charm buys, small but active. Reinforces buffer; violent squeeze on trigger. BUY but await trigger. Size for asymmetric upside on trigger fire.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises - Acts as Floor.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 45,
        "name": "Mechanical Melt-Up / Vanna-Driven Grind Higher",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day ",
        "action": "AVOID Shorts / BUY the Dip",
        "actionDirection": "BUY",
        "tilt": "Fade downside extreme only; ride upside extension already in motion. Strong Floor, weak ceiling.",
        "dealersAction": "BUY PULLBACKS aggressively; rip-selling is overwhelmed by vanna + delta hedging flows",
        "charmNetNegative": "Charm buys, active. Aligned with melt-up; every flow stacks up; strong floor, weak ceiling. AVOID Shorts. BUY the Dip aggressively — sustained melt-up.",
        "charmNetPositive": "Charm sells, active. Small headwind on melt-up; vanna + speed override. Choppier grind with retracements.  AVOID Shorts. BUY the Dip — retracements are better entries. Don't fade rallies.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 46,
        "name": "Positive Gamma Coil with Bull Volatility Trigger Risk",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression with Explosive Bullish Risk",
        "action": "BUY the Dip ",
        "actionDirection": "BUY",
        "tilt": "Fade downside extreme only; respect upside trigger — squeeze ignites on IV expansion. Strong Floor, fragile ceiling.",
        "dealersAction": "BUY the dip / Sell the rally with caution — Bull vol upside squeeze risk. In high IV  rip-selling is overwhelmed by vanna + delta hedging flows",
        "charmNetNegative": "Charm buys, small but active. Pre-loads the bullish trigger; pin migrates higher session-over-session.  BUY the Dip per row. Charm loads the trigger for vol expansion.",
        "charmNetPositive": "Charm sells, small but active. Minor delay to bullish trigger; vanna overruns on vol wake. BUY the Dip per row. Vol wake = melt-up regardless.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 47,
        "name": "Vol-Expanded Downside Trend / Self-Accelerating Breakdown via Zomma",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day.  Forced-Flow Trend with Whipsaw Risk",
        "action": "SELL LEAN. SELL Bounces, Avoid Longs.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend with whipsaw — chase weakness, don't fade. Pullbacks are NOT safe entries.",
        "dealersAction": "At High IV, pro-cyclical selling on weakness dominates. Reluctant buying on bounces (Neg Delta hedge) gets overwhelmed by Neg Gamma + Vega flow. At Low IV the book is dormant.",
        "charmNetNegative": "Charm sells, active. Stacks with cascade; Vex + Vomma defense overrun on real moves. SELL LEAN. SELL bounces, avoid longs. Pullbacks NOT safe entries.",
        "charmNetPositive": "Charm buys, active. Counter-flow, soft floor intraday; overrun on real moves. SELL LEAN, bounces hold briefly but still SELL. Whipsaw risk elevated.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 48,
        "name": "The Silent Trap / High Probability Coiled Breakdown",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day ",
        "action": "Pre-trigger the book is dormant. Don't pre-empt the break; chase it.",
        "actionDirection": "N/A",
        "tilt": "Transition - Trend Day , Coiled — wait for break. Bounces are short entries, not longs. Don't fade range pre-trigger.",
        "dealersAction": "At Low IV the book is dormant until a vol trigger fires. At High IV, pro-cyclical selling on weakness dominates. Reluctant buying on bounces (Neg Delta hedge) gets overwhelmed by Neg Gamma + Vega flow. ",
        "charmNetNegative": "Charm sells, small but active. Slow bearish drag pre-loading the trigger. Retail: Don't pre-empt; chase the break. First IV tick = size short.",
        "charmNetPositive": "Charm buys, small but active. Slow floor support pre-trigger; overrun when vol expands. Don't pre-empt; chase the break. Pre-trigger floor breaks on first IV tick.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises; Coiled.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 49,
        "name": "High-Vol Short-Put Book Under Pressure — Trend Day with Sold Bounces",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day",
        "action": "SELL LEAN. SELL bounces into resistance. Trend continues — don't fade. ",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , bounces are short entries",
        "dealersAction": "Pro-cyclical: sell weakness, buy strength reluctantly. At Low IV book is dormant.",
        "charmNetNegative": "Charm sells, active. Stacks with Neg Gamma sell-into-weakness; bounces shallow, breaks accelerate late. SELL LEAN, SELL bounces. Don't fade. Trend day with weak retracements.",
        "charmNetPositive": "Charm buys, active. Stacks with Neg Gamma buy-into-strength on bounces; sold bounces get bought back. SELL LEAN but size shorts smaller — squeeze risk into close. Don't fade rallies aggressively.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 50,
        "name": "Hedged Short-Put Book at Low Vol — Upside Grind, Downside Trap",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Transitional — Pre-Trend Day - . Pin / Upside Grind with Latent Downside Trap",
        "action": "BUY grind cautiously; flip short on put-strike break",
        "actionDirection": "BUY",
        "tilt": "Cautious lean long on grind. Possible transition to bear Trend Day.",
        "dealersAction": "Pro-cyclical: sell weakness, buy strength reluctantly. At Low IV book is dormant; at High IV pro-cyclical flow fires. Pos Delta + Neg Gamma compound on rallies (sold) and breaks lower (chased).",
        "charmNetNegative": "Charm sells, small but active. Pre-loaded bearish bias; vol shock = trap fires (charm + Neg Gamma compound). BUY grind cautiously, flip short on put-strike break. Apex downside trap on this row.",
        "charmNetPositive": "Charm buys, small but active. Caps the grind via accumulated dealer length; vol spike = forced unwind downside. BUY grind cautiously, flip short on put-strike break. Vol spike fires trap from this side too.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 51,
        "name": "Compressed Range — Long Gamma Floor, IV Mean-Reverting Lower",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression",
        "action": "SELL LEAN towards PIN",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade near extremes. Caution at far extremes — Neg Speed weakens dampening",
        "dealersAction": "Buy the dip / Sell the rally — counter-cyclical dampening (book dormant at Low IV)",
        "charmNetNegative": "Charm sells, active. Stacks with Neg Vex + Neg Speed; reinforces rally cap. Floor defended by Vega + Vomma. SELL LEAN towards PIN. Fade upside extensions confidently. Don't fade dips.",
        "charmNetPositive": "Charm buys, active. Reinforces floor on dips; magnet caps extensions regardless. SELL LEAN towards PIN per row. Buy dips back to pin confidently — floor doubly defended.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 52,
        "name": "Quiet Pin / Dormant Range — Long Gamma at rest, breakouts fail",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression",
        "action": "BUY LEAN towards PIN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade near extremes. Caution at far extremes — Neg Speed weakens dampening",
        "dealersAction": "Buy the dip / Sell the rally — counter-cyclical dampening (book dormant at Low IV)",
        "charmNetNegative": "Charm sells, small but active. Minor headwind against BUY LEAN; pin holds via Pos Gamma + Neg Speed. BUY LEAN towards PIN per row. Headwind doesn't threaten pin.",
        "charmNetPositive": "Charm buys, small but active. Slow floor reinforcement; pin migrates higher session-over-session. BUY LEAN towards PIN per row. Charm reinforces buy-dip leg.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 53,
        "name": "Long Put Book Engaged — High IV Reinforces the Floor",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression",
        "action": "SELL LEAN. Sell the rally. However,defended floor active — don't chase shorts into dealer support.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade extremes - Defended floor ",
        "dealersAction": "Buy the dip/ Sell the rally",
        "charmNetNegative": "Charm buys, active. Aligned with defended floor; long puts + Pos Vega + Vomma reinforce. SELL LEAN, sell rally. Don't chase shorts — floor robust, cover at put-strike.",
        "charmNetPositive": "Charm sells, active. Stacks with Neg Vex on rallies → cap; floor still defended structurally. SELL LEAN, sell rally. Floor robust. Defined-move trade.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 54,
        "name": "Compressed Range — Long Put Floor Loaded but Idle",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression",
        "action": "BUY LEAN. BUY shallow dips — long-put floor + Neg Delta hedge support. IV expansion is tailwind. Defended floor is robust at Low IV.",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade extremes - Defended floor ",
        "dealersAction": "Buy the dip/ Sell the rally",
        "charmNetNegative": "Charm buys, small but active. Aligned with defended floor; pin holds via loaded long-put hedge. BUY LEAN, buy shallow dips. IV expansion = tailwind. Floor robust.",
        "charmNetPositive": "Charm sells, small but active. Slow drag; long put floor + Pos Vega defend on vol shock.BUY LEAN, buy shallow dips. Charm headwind doesn't threaten floor.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 55,
        "name": "High-IV Compression with Breakout Risk — Dealer Dampening Fading",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression ",
        "action": "SELL LEAN towards Pin. CAUTION: Zomma Neg weakens dampening; ceiling dissolves on breakout. Don't fade conviction breakouts.",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes;  Bias Upside Risk",
        "dealersAction": "BUY the dip / Sell the rally — counter-cyclical dampening. Slight buy-lean on dips.",
        "charmNetNegative": "Charm sells, active. Stacks with Neg Vex; reinforces rally cap during compression.  SELL LEAN towards Pin. CAUTION: ceiling dissolves on conviction breakouts. Don't fade.",
        "charmNetPositive": "Charm buys, active. Reinforces floor; amplifies upside breakout risk via Pos Delta + Pos Speed. SELL LEAN towards Pin but size shorts smaller — breakout risk elevated. Don't fade conviction breakouts.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 56,
        "name": "Long Gamma Pin",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression ",
        "action": "BUY LEAN",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes; Bias Upside Risk",
        "dealersAction": "BUY the dip / Sell the rally — counter-cyclical dampening. Slight buy-lean on dips.",
        "charmNetNegative": "Charm sells, small but active. Minor headwind; pin holds. BUY LEAN per row. Charm doesn't threaten pin. Watch for upside breakouts.",
        "charmNetPositive": "Charm buys, small but active. Floor reinforced; pre-loads upside breakout potential. BUY LEAN with conviction. Loaded bullish bias for vol-expansion trigger.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 57,
        "name": "High-IV Compression — Strong Ceiling, Weakening Floor",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression ",
        "action": "SELL LEAN. FADE rallies into wall towards PIN. Don't chase shorts — long-put floor still active. ",
        "actionDirection": "SELL LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the dip (Pos Gamma counter-cyclical) + buy rallies (Neg Delta hedge). Ceiling holds via Pos Speed gamma wall. Retail can fade rallies into wall towards PIN.",
        "charmNetNegative": "Charm buys, active. Aligned with floor defense — vega and vomma support dips. But Neg Zomma weakens floor support faster than expected, so charm-driven floor can dissolve.  SELL LEAN, fade rallies into wall toward PIN per row. Don't chase shorts — long-put floor still active. But don't expect the floor to hold indefinitely either.",
        "charmNetPositive": "Charm sells, active. Stacks with Neg Vex on rallies → reinforces the upside gamma wall ceiling. Same flow weakens floor on dips; Pos Vega + Pos Vomma defend but Neg Zomma erodes faster than the wall. Pin-break risk skewed to downside on vol shock. SELL LEAN, fade rallies into wall confidently. Downside break is the bigger risk — exit shorts cautiously on vol expansion (downside may run faster than expected).",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Positive Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 58,
        "name": "Long Gamma Pin — Downward Lean with Upside Gamma Wall",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Compression ",
        "action": "BUY LEAN. Buy the dip into the wall. ",
        "actionDirection": "BUY LEAN",
        "tilt": "Fade Extremes",
        "dealersAction": "Buy the dip (Pos Gamma counter-cyclical) + buy rallies (Neg Delta hedge). Ceiling holds via Pos Speed gamma wall. Retail can fade rallies into wall towards PIN.",
        "charmNetNegative": "Charm buys, small but active. Aligned with the long-put floor defense in compressed vol; pin holds. BUY LEAN, buy the dip into the wall per row. Floor reinforced but Neg Zomma flag — don't oversize dip-buys, floor may weaken faster than apparent.",
        "charmNetPositive": "Charm sells, small but active. Reinforces wall; pin-break skewed downside on vol shock. Retail: BUY LEAN per row, flag downside risk on vol expansion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 59,
        "name": "Neg Gamma Trend — Bearish Lean via Vol-Expansion Tailwind",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day",
        "action": "SELL LEAN — Follow Trend — Bearish lean structurally- Bounces can be deep.",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are short entries",
        "dealersAction": "Pro-cyclical hedging — sell into weakness (dominant), buy into strength (secondary). Bias toward selling due to positive Vega  which favors IV expansion, which empirically correlates with downside.",
        "charmNetNegative": "Charm buys, active. Counter-flow overwhelmed by cascade + Pos Vega + Neg Vex; Vomma catches wing.Charm doesn't help shorts but doesn't save them either.  SELL LEAN follow trend. Cover at Vomma activation. Bounces deep — charm occasional support.",
        "charmNetPositive": "Charm sells, active. Stacks with cascade; bounces shallower than Neg Charm version. SELL LEAN harder. Cover at Vomma activation.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 60,
        "name": "Short Gamma Slow Bleed — Dampened Cascade. Downward Lean.",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Transitional  — Pre-Trend Day ",
        "action": "AVOID LONGS. SELL LEAN - Sell bounces with patience — slow bleed regime. Wait for confirmed downside expansion before chasing. Don't pre-empt — book mostly dormant at Low IV.",
        "actionDirection": "SELL LEAN",
        "tilt": "Transitional - Trend Day, Bounces are short  entries - Bearish drift",
        "dealersAction": "Pro-cyclical hedging — sell into weakness (dominant), buy into strength (secondary). Bias toward selling due to positive Vega  which favors IV expansion, which empirically correlates with downside.",
        "charmNetNegative": "Charm buys, small but active. Counter-flow; late session: gamma exhausts, charm dominates, modest upside drift. AVOID LONGS per row, SELL bounces with patience. Charm's late-session lift provides better bounce-sell entries; don't pre-empt the break.",
        "charmNetPositive": "Charm sells, small but active. Stacks with bleed; late session: charm grinds tape lower, no natural floor. Retail: AVOID LONGS, SELL bounces. Confident short once expansion confirmed.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 61,
        "name": "High-IV Liquidation Cascade — Pos Delta Capitulation, Vanna Unwind Down",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day — Liquidation Cascade, Bearish Lean",
        "action": "SELL LEAN - Follow Trend — Bounces will be shallow (Zomma Neg accelerates selloff).",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day — Bounces are shorting opportunities ",
        "dealersAction": "Pro-cyclical selling on weakness + forced selling on rallies (Pos Delta hedge). Net flow: persistent downward pressure.",
        "charmNetNegative": "Charm sells, active. Stacks with cascade + Pos Vega unwind + Neg Vex; Vomma catches at wing. SELL LEAN follow trend. Bounces shallow — charm compounds the selloff momentum. Cover at Pos Vomma activation / IV peak.",
        "charmNetPositive": "Charm buys, active. Counter-flow overrun by cascade; deeper bounces than Neg Charm version.  SELL LEAN. Bounces = short entries. Cover at Vomma activation.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 62,
        "name": "Coiled Short-Put Book — Pre-Liquidation Drift",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day -  Slow Drift  — Pre-Liquidation",
        "action": "AVOID BUYS. Sell bounces with patience — book dormant at Low IV. Wait for confirmed downside vol expansion before chasing shorts.",
        "actionDirection": "BUY",
        "tilt": "Transitional - Trend Day , Bounces are short entries. Bearish drift.",
        "dealersAction": "Pro-cyclical hedging — sell weakness, sell rallies (Pos Delta hedge). Book dormant at Low IV until vol expands.",
        "charmNetNegative": "Charm sells, small but active. Pre-loads bearish bias; pin holds for now. AVOID BUYS, sell bounces with patience. Wait for confirmed expansion.",
        "charmNetPositive": "Charm buys, small but active. Soft floor breaks on first IV tick; cascade overruns. AVOID BUYS. Don't trust the floor — wait for confirmed expansion to chase shorts.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 63,
        "name": "Gamma Acceleration Selloff — Short-Vol Book Bleeding",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day - Bearish Asymmetry",
        "action": "SELL LEAN — Follow Trend — Bounces will be shallow (Zomma Neg accelerates selloff). Avoid the Long",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day ,  Bounces are shorting opportunities",
        "dealersAction": "Pro-cyclical hedging — sell weakness , buy rallies reluctantly. Net flow: bearish asymmetry on breakdowns.",
        "charmNetNegative": "Charm buys, swamped. Counter-flow overrun by cascade; Pos Vega cushions briefly, Vomma catches at wing.  SELL LEAN follow trend. Charm provides occasional soft bounces — those are shorting opportunities, not long entries.  Cover at Vomma activation.",
        "charmNetPositive": "Charm sells, active. Stacks with cascade; Pos Vega briefly cushions; Vomma catches at wing. SELL LEAN harder.  Bounces shallow — charm compounds the selloff momentum. Cover at Vomma activation.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 64,
        "name": "Coiled Gamma Trap — Latent Cascade Risk",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Transitional / Coiled — Pre-Trend Day - Pre-Cascade",
        "action": "AVOID BUYS. Sell bounces with patience — book dormant at Low IV. Wait for confirmed downside vol expansion before chasing.",
        "actionDirection": "BUY",
        "tilt": "Coiled — bounces are short entries with patience. Bearish asymmetry latent.",
        "dealersAction": "Pro-cyclical hedging — sell weakness , buy rallies reluctantly. Net flow: bearish asymmetry on breakdowns. Book dormant at Low IV until vol expands.",
        "charmNetNegative": "Charm buys, small but active. Thin range support; overrun on trigger.  AVOID BUYS, sell bounces with patience. Charm holds the range until trigger.  First IV tick = size short to Vomma.",
        "charmNetPositive": "Charm sells, small but active. Pre-loads bearish bias; on trigger, stacks with cascade. Retail: AVOID BUYS, sell bounces. First IV tick = confident short.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 65,
        "name": "Long Downside Tail — Dealer Crash-Hedged at High Vol",
        "condition": {
            "IV": "High",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression  — not pure Compression, because the range is asymmetric (harder floor than ceiling)",
        "action": "AVOID SELL or FADE rallies cautiously into the PIN — floor strong, ceiling weak. ",
        "actionDirection": "SELL",
        "tilt": "Fade extremes towards PIN — floor robust, ceiling fragile ",
        "dealersAction": "Buy the Dip (Pos Gamma) + Buy rallies (Neg Delta hedge). At Low IV book is dormant; at High IV the floor engages and Pos Zomma reinforces",
        "charmNetNegative": "Charm buys, active. Aligned with structurally strong floor; ceiling weak. (no structural cap)  AVOID SELL or fade rallies cautiously into PIN. Floor robust, don't chase shorts.",
        "charmNetPositive": "Charm sells, active. Only cap mechanism on rallies — easily broken on conviction. Floor still defended. Fade rallies even more cautiously than Neg Charm version. Buy dips with confidence.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds/ Strengthens Positive Gamma",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 66,
        "name": "Quiet Pin with Positive Gamma Pinning",
        "condition": {
            "IV": "Low",
            "Gamma": "Pos",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Compression",
        "action": "BUY the Dip  — Respect the Pin",
        "actionDirection": "BUY",
        "tilt": "Fade extremes towards PIN — floor robust, ceiling fragile ",
        "dealersAction": "Buy the Dip (Pos Gamma) + Buy rallies (Neg Delta hedge). At Low IV book is dormant; at High IV the floor engages and Pos Zomma reinforces",
        "charmNetNegative": "Charm buys, small but active. Aligned with long-put defended floor; pin holds. BUY the Dip, Respect the Pin. Floor robust.",
        "charmNetPositive": "Charm sells, small but active. Soft ceiling via charm + Neg Speed magnet. BUY the Dip per row. Fade upside extensions back to pin cautiously — charm + Neg Speed combine to cap extensions, but be cautious on conviction breakouts (ceiling structurally fragile). ",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds/ Strengthens Positive Gamma if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 67,
        "name": "High-Vol Short-Put Unwind — Zomma-Dampened Cascade",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day with built-in Floor — Cascade-to-Compression Transition.",
        "action": "SELL LEAN — short bounces, do not chase at extension. Zomma+ deepens the cascade, but Neg Speed decelerates it at the tails — take profits as gamma exhausts. ",
        "actionDirection": "SELL LEAN",
        "tilt": "Self-limiting trend day.  Bounces are shorting opportunities until compression confirms.",
        "dealersAction": "Pro-cyclical: Chase breakdowns (dominant) / Chase rallies lightly.  Neg Speed → cascade decelerates on extension; chase exhausts at the tails and regime will switch to compression.",
        "charmNetNegative": "Charm sells, active. Stacks with cascade during trend; soft ceiling forms post-cascade. Post-cascade transitions to compression — charm becomes a soft ceiling as new regime forms.  SELL LEAN per row, short bounces, take profits as gamma exhausts. Charm reinforces the cascade — bounces shallow until transition.",
        "charmNetPositive": "Charm buys, active. Counter-flow during trend; bounces deeper. SELL LEAN but bounces are better entries than Neg Charm version. Take profits as gamma exhausts.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 68,
        "name": "Low-Vol Short-Call Unwind — Zomma-Dampened Squeeze",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day with built-in Ceiling — Squeeze-to-Compression Transition.",
        "action": "BUY LEAN — Pullbacks deepen as squeeze fades. Take profits into strength. Don't short until compression confirms",
        "actionDirection": "BUY LEAN",
        "tilt": "Self-limiting trend day. Pullbacks are buying opportunities until compression confirms.",
        "dealersAction": "Pro-cyclical chase up: covering short calls on rallies → squeeze fades mechanically and regime will switche to compression.",
        "charmNetNegative": "Charm sells, small but active. Adds to squeeze fade; pullbacks deepen. BUY LEAN, take profits into strength. Don't short until compression confirms.",
        "charmNetPositive": "Charm buys, small but active. Counter-flow against squeeze fade; pullbacks shallower. BUY LEAN, take profits into strength. Entries less attractive than Neg Charm version.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises - Acts as Floor.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 69,
        "name": "High-Vol Short-Put Unwind / Vanna-Compounded Cascade",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day — Short-Duration Cascade (self-limiting via Zomma ). Cascade-to-Compression Transition.",
        "action": "SELL LEAN — short bounces. Two exits: (a) Zomma+ / Neg Speed exhaust gamma at the tails; (b) IV crush flips vanna to buying. ",
        "actionDirection": "SELL LEAN",
        "tilt": "Bounces are short entries until gamma exhausts",
        "dealersAction": "Pro-cyclical: Chase breakdowns (dominant) / Chase rallies lightly. Breakdown is vanna-amplified. Cascade exhausts on either gamma exhaustion OR IV crush (vanna flip).",
        "charmNetNegative": "Charm sells, active. Stacks with vanna-compounded cascade; Vomma catches at wing. SELL LEAN, short bounces. Exit on gamma exhaust or IV crush trigger. Bounces shallow.",
        "charmNetPositive": "Charm buys, active. Counter-flow; bounces deeper, better short entries. SELL LEAN, don't chase at extension. Cover on IV crush — charm + vanna flip drive recovery.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 70,
        "name": "Low-Vol Short-Gamma Breakdown / Zomma-Dampened, Vanna-Dormant Selloff",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day with built in Floor -  Cascade-to-Compression Transition. ",
        "action": "AVOID BUYS. SELL LEAN —short bounces. Reduce size as bounces deepen. Watch for IV lift: Neg Vex means any IV expansion will activate vanna selling . ",
        "actionDirection": "SELL LEAN",
        "tilt": "Bounces are short entries until gamma exhausts",
        "dealersAction": "Mechanical Forced Selling — moderating as Zomma Pos kicks in. Any IV expansion will activate vanna selling. ",
        "charmNetNegative": "Charm sells, small but active. Pre-loads bearish trigger; no V-recovery mechanism.  AVOID BUYS, SELL LEAN short bounces. Reduce size as bounces deepen.",
        "charmNetPositive": "Charm buys, small but active. Counter-flow against bearish bias; bounces slightly deeper. AVOID BUYS, SELL LEAN short bounces. Better short entries via deeper bounces.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 71,
        "name": "High-Vol Short-Call Unwind / Vanna-Dampened Squeeze",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day — Gamma-Driven Squeeze with Vanna Headwind. Squeeze-to-Compression Transition.",
        "action": "AVOID SHORTS. BUY LEAN  — buy dips. Flat at IV peak or gamma exhaust. Neg Speed kills the tail. Built in ceiling. ",
        "actionDirection": "BUY LEAN",
        "tilt": "Pullbacks are long entries until IV peaks or gamma exhausts.",
        "dealersAction": "Mechanical Forced Buying.",
        "charmNetNegative": "Charm buys, active. Fuels the squeeze; Neg Vex dampens, Neg Speed kills tail, Vomma catches wing. AVOID SHORTS, BUY LEAN. Buy dips. Flat at IV peak.",
        "charmNetPositive": "Charm sells, active. Stacks with Neg Vex on rallies; gamma covering overrides.  AVOID SHORTS, BUY LEAN. Dips deeper, better entries. Flat at IV peak.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Drains/ Weakens Gamma toward Zero",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 72,
        "name": "Low-Vol Short-Call Unwind / Vanna-Dormant Squeeze",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Pos",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day — Gamma-Driven Squeeze, Vanna Dormant. Squeeze-to-Compression.",
        "action": "BUY LEAN — buy dips early, reduce size as pullbacks deepen.",
        "actionDirection": "BUY LEAN",
        "tilt": "Pullbacks are long entries until gamma exhausts.",
        "dealersAction": "Mechanical Forced Buying.",
        "charmNetNegative": "Charm buys, small but active. Pre-loads squeeze fuel; aligned with latent upside. BUY LEAN, buy dips early. Reduce size as pullbacks deepen.",
        "charmNetPositive": "Charm sells, small but active. Counter-flow overridden on trigger; dips slightly deeper. BUY LEAN, buy dips early — better entries via deeper dips. Reduce size as pullbacks deepen.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 73,
        "name": "High-Vol Vanna-Fueled Melt-Up with no Ceiling",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day - No structural exhaustion",
        "action": "AVOID SHORTS. BUY LEAN — buy dips. No built-in ceiling.  Flat on first IV roll-over (IV stops rising, starts falling) or use external stops.",
        "actionDirection": "BUY LEAN",
        "tilt": "Pullbacks are long entries.",
        "dealersAction": "Mechanical gamma covering drives the rip; vanna buying amplifies on IV expansion. No ceiling.",
        "charmNetNegative": "Charm buys, active. Fuels vanna-fueled melt-up; no built-in ceiling.  AVOID SHORTS, BUY LEAN. Flat on IV roll-over or use external stops.",
        "charmNetPositive": "Charm sells, active. Counter-flow overrun by vanna + gamma; ceiling fails until external supply emerges. AVOID SHORTS, BUY LEAN. Dips deeper, better entries. Use external stops.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 74,
        "name": "Low-Vol Short-Call Unwind / Vanna-Dormant Squeeze ",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Pos",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Neg"
        },
        "regime": "Trend Day - No structural exhaustion",
        "action": "BUY LEAN- buy the Dip. IV lift = Vanna Squeeze to the upside with no ceiling. Use external stops.",
        "actionDirection": "BUY LEAN",
        "tilt": "Pullbacks are long entries.",
        "dealersAction": "Mechanical gamma covering drives the rip; vanna buying amplifies on IV expansion. No ceiling.",
        "charmNetNegative": "Charm buys, small but active. Pre-loads upside bias; IV lift = Vanna Squeeze with no ceiling. BUY LEAN, buy dip. Use external stops on trigger.",
        "charmNetPositive": "Charm sells, small but active. Counter-flow overridden on trigger; dips slightly deeper. BUY LEAN, buy dip — better entries via deeper dips. Use external stops.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 75,
        "name": "Crisis-Continuation Short-Gamma Cascade — Downside Acceleration at High Vol",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day — No Floor",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are entries",
        "dealersAction": "Pro-cyclical Forced Selling",
        "charmNetNegative": "Charm buys, swamped. Counter-flow drowned by violent cascade; Vomma catches at wing. SELL LEAN per row. Don't fade — charm too small to provide floor in this regime. Trend Day — No Floor. Cover at Pos Vomma activation.",
        "charmNetPositive": "Charm sells, active. Apex-danger. Stacks with cascade; every flow aligned down. SELL LEAN harder. Bounces shallow. Cover at Vomma activation or organic exhaustion.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 76,
        "name": "Coiled with risk of downside cascade  (primed for violent vol expansion)",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Neg",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Dormant - Coiled with cascasde Risk",
        "action": "Dormant - Await the SELL.  Expected move is small - Cascade Risk if IV spikes.  Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts. ",
        "actionDirection": "BUY",
        "tilt": "Pre-trigger: No trade. Post-trigger: Bounces are shorting entries",
        "dealersAction": "Quiet at flat Low IV (theta harvest on short puts). If triggered: pro-cyclical forced selling — short-put gamma chase intensifies with IV expansion (Zomma Neg accelerant) + long-put tail vanna selling compounds. No built-in brake.",
        "charmNetNegative": "Charm buys, small but active. Thin floor; overrun on cascade trigger. Dormant per row, don't front-run. First IV tick = size short. Buy cheap puts.",
        "charmNetPositive": "Charm sells, small but active. Apex-danger latent. Compounds bearish bias; accelerant on trigger.  Dormant per row, don't front-run. First IV tick = confident short aggressively.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises, but self exhausting.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 77,
        "name": "High-Vol Coiled Cascade -  Accelerating Breakdown Risk",
        "condition": {
            "IV": "High",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Trend Day — No Floor",
        "action": "SELL LEAN",
        "actionDirection": "SELL LEAN",
        "tilt": "Trend Day , Bounces are entries",
        "dealersAction": "Pro-cyclical: Chase / SELL Breakdowns (dominant). Delta bleeding lower as spot falls.  Zomma Neg amplifies, vanna selling on IV expansion compounds.  Positive delta buffer being consumed. No brake. In Low IV dealers are moistly dormant.",
        "charmNetNegative": "Charm sells, active. Accelerates Pos Delta buffer consumption; no brake once consumed. SELL LEAN. Trend Day — No Floor. Charm accelerates breakdown timing. Don't fade. Cover at Pos Vomma activation.",
        "charmNetPositive": "Charm buys, active. Delays trigger by reinforcing Pos Delta buffer; violent unwind when buffer exhausts. SELL LEAN, timing later than Neg Charm version. Bounces deeper, better short entries.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Active — Feeds Gamma making it more Negative.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
    },
    {
        "id": 78,
        "name": "Dormant; Pre-Cascade Setup",
        "condition": {
            "IV": "Low",
            "Gamma": "Neg",
            "Zomma": "Neg",
            "Delta": "Pos",
            "Vex": "Neg",
            "Vega": "Pos",
            "Vomma": "Pos",
            "Speed": "Pos"
        },
        "regime": "Dormant - Coiled Low-Vol. Latent Downside Cascade Risk.",
        "action": "Dormant - Await the SELL.  Expected move is small - Cascade Risk if IV spikes.  Don't Front run. No directional edge for futures in low IV. Option traders can buy cheap long puts. ",
        "actionDirection": "BUY",
        "tilt": "Neutral at rest; bearish if IV spikes. Bounces fade if cascade fires.",
        "dealersAction": "Minimal directional flow. Quiet at flat Low IV (theta harvest). If triggered: pro-cyclical chase — breakdowns dominant, Zomma Neg amplifies, vanna selling on IV expansion compounds. No brake.",
        "charmNetNegative": "Charm sells, small but active. Pre-loads buffer consumption. Dormant, await SELL. First IV tick = size short.",
        "charmNetPositive": "Charm buys, small but active. Reinforces buffer in compressed vol; violent unwind on trigger. Dormant, await SELL. First IV tick = size short, expect violent unwind.",
        "vannaNetNegative": "",
        "vannaNetPositive": "",
        "zommaText": "Zomma Dormant — Feeds Gamma making it more negative if IV rises.",
        "mxVannaLevelsWork": "",
        "vShapeRecovery": "",
        "spreads": null,
        "stochastic": null,
        "trendEliminator": null,
        "flags": {
            "max_vanna_level": false,
            "ib_bounce": false,
            "dadu_pinning": false
        }
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