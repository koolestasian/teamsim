# Security Policy

## Reporting a vulnerability

Report vulnerabilities privately through GitHub private vulnerability reporting:

<https://github.com/koolestasian/teamsim/security/advisories/new>

Do not open a public issue, pull request or discussion for a vulnerability.

Include the affected commit, the steps to reproduce and the impact as you see it. Do not send
real API keys, tokens, chat messages or personal data. Describe what you found and we will agree
how to share the rest.

## Supported versions

No release has been made yet, so no version is supported.

## What to expect

teamsim is maintained by one person, part-time, on a best-effort basis. We aim to acknowledge a
report within 7 days. We do not promise a fixed timeline for a fix or for disclosure.

## Scope

In scope, for example:

- Exposure of API keys or tokens in logs, reports, the live view or error messages.
- Simulated or fixture content that makes the simulator, the product under test or an AI agent
  act on it as instructions.
- The simulator reaching anything other than its local emulator, the product under test and an
  explicitly configured model endpoint.

Out of scope: vulnerabilities in third-party services and in the products being tested. Report
those to their maintainers.
