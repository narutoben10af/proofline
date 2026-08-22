# ADR 0000: Record architecture decisions

- Status: Accepted
- Date: 2026-08-22

## Context

Proofline is time-constrained, but decisions about document processing, data handling, model use, evidence matching, and classification can materially affect trust and safety. These choices need a lightweight, reviewable history.

## Decision

Record consequential architecture decisions as numbered Markdown files in this directory. Each record includes context, decision, consequences, and any evidence still required. Decision changes are made through pull requests. A later ADR supersedes an accepted decision rather than silently rewriting it.

## Consequences

- Reviewers can distinguish chosen behavior from open research.
- Important tradeoffs remain visible after the hackathon.
- Contributors incur a small documentation cost when making consequential choices.
