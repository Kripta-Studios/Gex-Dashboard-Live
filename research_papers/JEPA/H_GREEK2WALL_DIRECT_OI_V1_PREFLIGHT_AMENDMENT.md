# H-GREEK2WALL direct-OI V1 preflight amendment

Status: frozen outcome-free amendment before any direct all-Greeks or direct-OI
value is requested. It authorizes only the same twelve sessions already frozen
for V1 and no labels, PnL, model fitting or full historical download.

For each session the capture must atomically request both the complete 0DTE
all-Greeks chain and `/v3/option/history/open_interest` with
`symbol`, `expiration=date`, `date`, `strike=*`, `right=both`, `format=json`.
Direct OI is the primary causal OI reconstruction. Local OI is vintage parity
only. Raw responses, normalized parquets, schemas, request parameters and hashes
are stored separately.

Direct OI must have exact symbol/expiration/date/strike/right identity, a native
timestamp, nonnegative integer OI and one message per contract key. Missing
contracts remain missing, never zero. At a direct-Greek row the observation is
available only when its native timestamp is at or before that row; there is no
global or retrospective backfill. Any identity substitution, negative/fractional
OI or duplicate contract key rejects the atomic session capture.
