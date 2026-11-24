# Release Notes

## Wallet V0.5.84 Certificate Check

Based on the user-provided V0.5.83 Wallet source.

- The Wallet's certificate-check action now opens `/certificate-check` instead
  of exposing the raw `/api/v1/status` JSON response in the browser.
- Passes the Wallet's selected language to the certificate page.
- Keeps the GitHub repository link and public placeholder Index Server address.
- No changes to transaction construction, signing, UTXO handling, fees, change,
  local/on-chain notes, QR export, or USD valuation.
- The Index Server source is not included in this Wallet-only public package.
