# Mercy Ships — Engagement Status Dashboard

Live URL: https://wezana-solutions.github.io/mercyships-status/

## What this is

A snapshot of every active Mercy Ships engagement ticket the team is working on, grouped by lifecycle stage:

- **✅ Closed** — live in MSPROD and verified
- **🟢 In Prod** — live in MSPROD, ticket still open (e.g. monitoring period)
- **🟠 In Sandbox** — built and verified in MSMO / MSUSFULL, awaiting Copado push to MSPROD
- **🟡 In Dev** — actively being scoped or built
- **🆕 New** — in the backlog, not yet picked up

Each row shows per-org presence (MSPROD · MSMO · MSUSFULL) and the next concrete action.

## Glyph key

| Glyph | Meaning |
|-------|---------|
| ✅ | live |
| ⚠ | partial — some artifacts present, others missing |
| ⏳ | awaiting — expected but not yet present |
| — | not yet built in this org |
| · | not applicable for this org |
| 🛑 | query error — refresh failed |

## Refresh cadence

This page is regenerated whenever the team wraps up a working session. The "Last refreshed" timestamp at the top of the dashboard reflects the most recent update.

There is no live polling — refreshing the page does not re-query Salesforce. Updates land in the order the team finishes sessions, not on a fixed schedule.

## What this is **not**

- Not real-time. The state is as-of the last session wrap-up.
- Not a comprehensive issue tracker. Detail per ticket lives in the engagement log; this page is the one-glance summary.
- Not a substitute for the architect-gate process. Items move from In-Sandbox to In-Prod only after architect sign-off + Copado push.

## Privacy

This page exposes only ticket identifiers, plain-English summaries, lifecycle stage, and a one-line next action. No record IDs, no SOQL, no internal class names, no credentials.
