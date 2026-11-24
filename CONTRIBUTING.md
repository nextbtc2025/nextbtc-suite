# Contributing

Thanks for your interest in nextBTC Suite.

## Scope

The first public stage contains the nextBTC Wallet only. The Index Server
implementation is not included yet.

## Before submitting a change

- Explain the user-visible behavior and security implications.
- Keep the single-file wallet build reproducible.
- Do not add private server URLs, API credentials, wallet data, WIFs, or test
  secrets to commits.
- Preserve the default behavior where local notes are not written on-chain.
- Any OP_RETURN behavior must remain explicit opt-in and clearly disclose
  public visibility and additional fees.
- Test transaction construction and fee/change calculations before proposing
  changes to the transaction engine.

## Pull requests

Please include a concise summary, test evidence, affected wallet version, and
any required migration or compatibility notes.
