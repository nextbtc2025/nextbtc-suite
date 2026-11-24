# Contributing

Thanks for your interest in nextBTC Suite.

## Project scope

This repository contains two independently versioned components:

- `wallet/` — nextBTC browser wallet.
- `indexserver/` — nextBTC Index Server and Explorer.

Please identify the affected component and version in each issue or pull request.

## Before submitting a change

- Explain user-visible behavior and security implications.
- Preserve Wallet / Index Server API compatibility unless a coordinated versioned change is intended.
- Do not add private server URLs, API credentials, wallet data, WIFs, seed phrases or test secrets.
- Keep local transaction notes local by default. Any OP_RETURN behavior must remain explicit opt-in and disclose public visibility and additional fees.
- Do not modify nextBTC Core consensus or DWG behavior without an explicit, separately reviewed protocol change.
- Include reproducible tests and migration notes for database or API changes.

## Pull requests

Include a concise summary, affected component/version, test evidence, configuration changes and any required migration or compatibility notes. Remove secrets and production data from logs and fixtures.
