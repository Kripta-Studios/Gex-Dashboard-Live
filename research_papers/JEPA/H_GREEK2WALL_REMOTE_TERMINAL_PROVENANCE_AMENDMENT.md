# H-GREEK2WALL remote Terminal provenance amendment

Status: frozen before any valid remote all-Greeks or direct-OI response. The
local frozen capture attempt returned HTTP 403 because the active subscription
was STANDARD and the endpoint requires PROFESSIONAL. It created no output,
staging directory or direct-value artifact.

The user supplied `http://91.99.90.39:25503/v3`, the same remote Theta Terminal
source configured in `D:/ThetaData/options_bulk.py`. V1 may use either localhost
or exactly this URL. No other remote host, port or path is authorized.

Local capture retains active JAR/process evidence. Remote capture must first
request `/terminal/mdds/status`, preserve and hash its raw bytes, HTTP status,
headers and server Date, and classify evidence as
`USER_SUPPLIED_REMOTE_THETA_TERMINAL`. It must not claim a local JAR or process.
Remote historical provenance is
`CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION`; live parity remains `BLOCKED`.
All-Greeks and OI HTTP status and headers are persisted separately. Validation
and sealing revalidate the exact base URL, evidence kind and stored status hash
without silently substituting local provenance.
