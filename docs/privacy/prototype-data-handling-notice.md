# Prototype data-handling notice — engineering draft

> **Do not publish this file as a privacy notice.** It is not a section 7 PDPA notice, not consent, and not evidence of compliance. The operating entity/data controller, real contact channel, deployment/provider facts, and Bahasa Malaysia version have not been supplied.

This draft records what the repository can honestly say while it remains a public/synthetic-fixture prototype. Before a public or private pilot that processes personal data, an accountable operator must replace this draft with a legally reviewed notice in Bahasa Malaysia and English.

## Current prototype disclosure

- **Who operates the service:** not identified in the repository. This is a publication blocker.
- **Supported material:** only the repository's approved public or synthetic fixtures. Do not select confidential, private, credential-bearing, or personal documents.
- **Browser behavior on current `main`:** the file picker demonstrates names and types; it does not implement a document-byte upload. A selected filename may still be visible on the user's screen. Do not represent selection as server upload.
- **Hosted requests:** the static Sites worker serves application assets. The repository configures no application database or object storage, but the hosting platform may process connection/request metadata. Deployment regions, platform logs, retention, cookies, operator access, and subprocessors are not verified here.
- **Backend sessions on current `main`:** the v1 intake API stores process-local session metadata only; it does not accept document bytes. Its deletion receipt covers that metadata only.
- **Features under review:** a separate upload implementation proposes application-managed temporary storage with 30-minute idle and 120-minute absolute TTLs. A separate reporting implementation creates downloaded reports. These are not current behavior until merged and deployed.
- **Model/assistant:** provider calls are server-side and currently unavailable in the implemented adapter. The interface must not claim that document content was sent, retained, deleted, or excluded from training without verified deployed behavior and provider terms. Assistant output is cited prototype support, not financial advice or an automated decision about a person.
- **Exports:** a downloaded JSON or PDF is a new copy controlled by the user/device and is not removed by deleting a server or browser session.
- **Application logs:** policy forbids document content, extracted values, prompts/responses containing source material, user filenames, and secrets. Hosting/provider logs remain unverified external scopes.

## Required section 7 publication fields

The actual controller must complete and verify every item below; the blocker statuses deliberately describe missing facts rather than inventing them.

| Required notice content | Publication status |
| --- | --- |
| Controller identity and how to contact it for inquiries/complaints | **Blocked:** legal entity and monitored contact not designated. |
| Description of personal data processed | **Blocked for personal-data mode:** deployed flows and fields not approved. |
| Specific collection and further-processing purposes | **Blocked:** actual commercial purpose/operator decisions not documented. |
| Known sources of the data | Public fixture sources are recorded, but personal-data sources are not approved. |
| Access and correction rights and procedure | **Blocked:** no authenticated intake, identity verification, response owner, or case record. |
| Classes of third parties receiving data | **Blocked:** hosting/model/OCR/support providers and subprocessors not approved. |
| Choices and means to limit processing, including withdrawal where applicable | **Blocked:** no operational rights channel; the public-fixture checkbox is not consent. |
| Whether each supply is mandatory or voluntary and consequences of not supplying | **Blocked:** actual service terms and processing condition not approved. |
| Cross-border transfers and safeguards | **Blocked:** service locations, receivers, onward transfers, section 129 condition, and safeguards unknown. |
| Retention and deletion explanation | Application scopes are in the data-flow register; hosting/provider/backups and operational evidence are unverified. |
| Bahasa Malaysia and English versions | **Blocked:** this engineering draft is English only. |

The source checklist comes directly from Act 709 section 7 and the Commissioner's [privacy-notice guidance](https://www.pdp.gov.my/ppdpv1/en/akta/guidance-on-the-preparation-of-personal-data-protection-notices/) and [Quick Guide](https://www.pdp.gov.my/ppdpv1/en/akta/a-quick-guide-to-privacy-notice/).

## Product-route rule

Until the blockers are closed, `/privacy`, `/legal`, and `/settings` may link to a concise prototype disclosure that says public/synthetic fixtures only and identifies unavailable features. They must not call it a PDPA notice, display invented contact/controller details, treat a checkbox as consent, or say MagicFin is compliant.
