# H-GREEK2WALL-DIRECT-ALL-V1 feasibility closure

Status: `BLOCKED_SOURCE_ENTITLEMENT`, closed before data, labels, models or
outcomes on 2026-07-13.

## Frozen scope reached

The outcome-free implementation and its 12-session canonical source inventory
remain valid at commit `20b9325415b084fcfc03dacca7954660c38f8854`:

- inventory: `D:/ThetaData/h_greek2wall_direct_all_preflight_v1r3_source_inventory`;
- inventory CSV SHA-256:
  `829ef75418190bf722af2213114a487f724f8c960d2d7d8aec6792654e6dce53`;
- inventory JSON SHA-256:
  `88b84f2a257bb12faf9746e15d55f6e8ee68ac362fb247abfc2f226279d2220f`;
- builder SHA-256:
  `bf8fda05fc0acc3a6eeb1d746a17a21575325c73856288fba0c1ff36f7a7bad0`;
- focused verification: `13 passed`; Ruff clean.

The inventory contains only the frozen 12 ticker-year sessions from
2022-08 through 2025-01. It does not reference 2026, labels, option payoff or
production artifacts.

## Authoritative remote attempt

The VPS recovered with exactly one systemd-managed Theta Terminal. Immediately
before and after the request:

- `thetadata_feed.service`, `realtime_feed.service` and `ai_bot.service` were
  all `active`;
- Theta Terminal MainPID was `954`, `NRestarts=0`, `SubState=running`;
- `/v3/terminal/mdds/status` returned HTTP 200 `CONNECTED`;
- status bytes SHA-256:
  `1f914c4386c0676ee418458a20c91d9db7c5cd18e88324b4908fdf27ec91dcc5`;
- status server Date: `Mon, 13 Jul 2026 08:43:56 GMT`.

Because TCP 25503 was not reachable directly from the research host, an SSH
SOCKS transport through the same VPS was used. The request URL and frozen
remote identity remained exactly `http://91.99.90.39:25503/v3`; no alternate
Terminal, endpoint or provider was substituted.

The first frozen request, SPXW 2022-08-01, returned HTTP 403 before direct OI:

```text
Requesting an option endpoint requiring a professional subscription, but you
only have a STANDARD subscription.
```

The 178-byte error body SHA-256 is
`13650acb2267f1e02b99667de36b26a56eac61b9c51bae5cafecd4efab5b1bb9`;
server Date was `Mon, 13 Jul 2026 08:43:57 GMT`. This independently confirms
the same entitlement blocker previously observed on the local Terminal.

The fail-closed capture created no output root, session directory, staging
directory, raw all-Greeks response, direct-OI response or parquet. Therefore
there is no partial capture to resume or seal.

## Scientific decision

H-GREEK2WALL-DIRECT-ALL-V1 is closed as `BLOCKED_SOURCE_ENTITLEMENT`. This is
not evidence for or against vanna/charm/vomma/zomma alpha. A Professional
entitlement would be a genuinely new external-state change and requires a new
prospective continuation from the same frozen protocol; the current Standard
source cannot support the experiment.

Do not substitute locally derived higher Greeks and call them direct provider
data. They are deterministic transforms of already studied spot/IV inputs and
do not satisfy this source hypothesis. Do not open labels, payoff or June 2026
for H-GREEK2WALL.

The next independent outcome-free direction already separated in the handoff is
H-IBQDYN1: directed intraminute NBBO pressure around the fixed complete set of
eight causally completed IB/Fibonacci levels. It requires its own
predeclaration, listing proof and capture; H-QDYN Greek-wall ticks may not be
relabelled or reused.
