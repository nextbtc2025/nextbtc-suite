# Release Notes

## Wallet V0.5.83 USD Special — first public source package

This public-source package is based on the V0.5.83 USD Special wallet.

Public-release-only changes:
- Replaced the private default Index Server address with the reserved
  `https://your-index-server.example:8777` placeholder.
- Removed historical private Index Server host/IP literals from the obsolete
  endpoint migration list.
- Preserved user-configured Index Server settings in browser storage.
- Corrected stale source comments that incorrectly described transaction
  signing as unimplemented.
- Added bilingual project documentation, API compatibility notes, security
  notes, MIT License, and the bundled QRCode.js third-party notice.

No Index Server implementation or private server configuration is included.

- Added a subtle, persistent GitHub repository link beside the wallet version in the footer; it opens the project repository in a new tab and is localized in English/Chinese.
