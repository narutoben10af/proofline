# Security policy

## Prototype status

Proofline is an early hackathon prototype and should not be used as a system of record or as a substitute for accounting, audit, investment, legal, or compliance review. No production security assurance is claimed.

## Supported versions

There are no released or supported versions yet. Security fixes will be applied to the default branch while the project remains in prototype development.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, confidential documents, or personal data in a public issue.

Use GitHub's private vulnerability reporting feature if it is enabled for this repository. If no private reporting channel is available, contact the repository owner privately through a verified channel shown on the owner's GitHub profile and share only the minimum information needed to establish a secure reporting path.

Include, where safe:

- the affected revision or component;
- reproduction steps or a minimal proof of concept;
- likely impact;
- suggested mitigation, if known; and
- whether any sensitive data may have been exposed.

Receipt and remediation timelines are not guaranteed during the prototype stage. Maintainers should acknowledge reports when operationally possible and coordinate disclosure after a fix is available.

## Sensitive data

- Use public or synthetic documents for demonstrations and tests.
- Never commit financial documents containing confidential, personal, or regulated information.
- Never commit API keys, tokens, credentials, or unredacted secrets.
- Treat extracted text, spreadsheet values, logs, and screenshots as potentially sensitive.
- Document retention and deletion behavior before accepting non-demo uploads.

## Scope priorities

Reports about arbitrary file processing, formula injection, path traversal, unsafe temporary files, prompt injection in documents, secret exposure, authorization bypass, and misleading evidence provenance are especially relevant to the proposed workflow.
