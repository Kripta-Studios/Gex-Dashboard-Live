# Execution and accounting
ECON-001/002, COST-001/002, SCHED-001 bind. One contract; USD primary, return secondary.
For each right take first valid native q in [D+1ms,D+1ms+60s]; choose target delta
only among valid 0DTE contracts at q. Tie: delta distance, proportional spread,
strike, contractual key. No later timestamp improvement or second-best action.
Same-contract first executable exit between entry+hold and min(+5m,16:00), inclusive.
Missing exit is zero penalty at deadline, exit commission retained; no observed fill.
Decimal prices/costs precision34; slippage .01/.02; commissions1.30 per side;
multiplier100. No intermediate rounding. See binding formulas in01.
Reject decisions while position open; release precedes decision at same instant.
Report all decisions and reasons, scenarios independently, max simultaneous
cash outlay and individual outlays; never label this account return.
