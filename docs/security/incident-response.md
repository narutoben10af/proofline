# Prototype security and personal-data incident runbook

This is an engineering runbook, not legal advice. The supported demo should contain no private or personal documents. Treat evidence that this boundary failed as a security incident and potential personal data breach; do not wait for certainty before escalating.

## Before real-personal-data processing

The operator must name an incident lead, controller/privacy decision-maker, security engineer, legal adviser, communications owner, hosting/provider contacts, and a monitored private reporting channel. It must verify access to the Commissioner's reporting system. Those facts are not present in this repository, so real-personal-data processing remains blocked.

## First response

1. Record awareness time in UTC, reporter, affected revision/deployment, coarse systems, and a non-content incident ID.
2. Contain safely: disable the affected upload/provider route, revoke exposed credentials, isolate storage, and preserve relevant non-content evidence. Do not paste personal data, source text, secrets, filenames, or provider payloads into public issues, chat, CI, or routine logs.
3. Determine whether personal data may be involved; which operator is controller or processor for the flow; whether a processor/customer/provider must be notified; and which locations/receivers are implicated.
4. Establish scope: breach type, start/awareness times, likely cause, categories of data, approximate subjects/records, systems, recipients, safeguards, and likely consequences. Record uncertainty and update it.
5. Start parallel technical remediation and controller-led notification assessment. Preserve evidence proportionately without retaining the exposed content longer than necessary.

## Malaysian notification decision

Act 709 section 12B, inserted by Act A1727, is in force. The Commissioner's final DBN guideline says a controller notifies the Commissioner when a breach causes or is likely to cause significant harm. Indicators include physical harm, financial loss/credit or property effects, illegal misuse, sensitive personal data, combinations enabling identity fraud, or significant scale (more than 1,000 affected data subjects).

- Notify the Commissioner as soon as practicable and no later than **72 hours** after the controller becomes aware, using the required form/system. If late, include reasons and supporting evidence.
- If affected-subject notification is required, notify directly and individually without unnecessary delay and no later than **seven days after the initial Commissioner notification**, in intelligible language, with the breach, likely consequences, controller response, protective steps, and a contact.
- Initial missing information may be supplied in phases as soon as practicable and no later than **30 days after the initial notification** under the guideline.
- Keep a controller breach register for at least **two years**, including non-notified breaches and the notification/no-notification rationale. Store no more exposed content than needed; access-restrict the register.

Notification decisions and communications must be made by the actual controller with Malaysian legal advice. A processor should immediately escalate to its controller under the governing contract and preserve the controller's ability to meet the clock; it must not make itself the controller by assumption.

Official sources: [Act A1727](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2024/11/Act-A1727.pdf), [commencement notification](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2024/12/PENETAPAN-TARIKH-PERMULAAN-KUAT-KUASA-1.pdf), and the Commissioner's [DBN guideline/circular page](https://www.pdp.gov.my/ppdpv1/en/guidelines-and-circulars-on-data-breach-notification-dbn/).

## Recovery and evidence

- Rotate/revoke credentials before removing traces from the latest revision; inspect history and deployed artifacts.
- Verify app-managed deletion with non-content counts and directory absence. Separately request and record hosting/provider deletion or preservation outcomes; do not collapse them into one receipt.
- Patch and test the root cause, validate public-fixture/data-flow boundaries, and obtain independent review before re-enabling the path.
- Record timeline, root cause, affected data/systems, consequences, containment/recovery, notifications, decision rationale, and follow-up owners. Keep public post-incident text free of personal data and exploit-enabling secrets.
- Reconcile the privacy notice, data-flow register, retention schedule, processor terms, and threat model with what the incident revealed.
