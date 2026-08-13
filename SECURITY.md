# Security Policy

## Supported versions

Security fixes are applied to the latest release on `main`.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Report privately through
[GitHub Security Advisories](https://github.com/AK20202007/Antivenom/security/advisories/new).

Include:

- A description of the issue and its impact
- Steps to reproduce, or a proof of concept
- Affected version / commit if known

You should receive an acknowledgment within a few days. Please give a reasonable window for a fix before any public disclosure.

## Scope notes

Antivenom repairs poisoned agent memory and optionally talks to MongoDB Atlas, LLM providers, and ElevenLabs. Prefer reports involving:

- Credential leakage into logs, committed history, or client bundles
- Binding the local event server (`antivenom serve`) beyond loopback without `ANTIVENOM_API_TOKEN`
- Path traversal or unsafe handling of uploaded / fixture artifacts
- Prompt-injection handling that escalates into tool misuse beyond the designed quarantine path

## Local event server

The dashboard event channel defaults to `127.0.0.1`. If you bind it off-loopback, set a strong `ANTIVENOM_API_TOKEN` and send `Authorization: Bearer …` on `/api/*` and `/ws`.
