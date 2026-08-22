# Malaysian PDPA readiness gap analysis

**Review date:** 22 August 2026
**Status:** engineering and documentation assessment, not legal advice and not a statement of compliance.

MagicFin/Proofline is currently documented and supported only for public or synthetic fixtures. The repository does not identify the operating legal entity, the commercial arrangement, the deployment regions, or whether that operator determines processing purposes or acts only for another party. Those facts decide whether and how Malaysia's Personal Data Protection Act 2010 (Act 709) applies. They cannot be inferred from the product name or a hosted demo.

## Effective law checked

- Act 709 commenced on **15 November 2013**. It applies to a person processing, controlling, or authorising processing of personal data in respect of a commercial transaction, subject to its territorial rules and exclusions. Federal and State Governments are excluded. See the Commissioner's [official commencement page](https://www.pdp.gov.my/ppdpv1/en/akta/determination-of-effective-commencement-date/), [Act 709 text](https://www.pdp.gov.my/ppdpv1/en/akta/pdp-act-2010-en/), and [application/non-application summary](https://www.pdp.gov.my/ppdpv1/en/akta/application-and-non-application-of-the-act/).
- The Personal Data Protection (Amendment) Act 2024, Act A1727, received Royal Assent on **9 October 2024** and was gazetted on **17 October 2024**. Under P.U. (B) 522, sections 7, 11, 13 and 14 commenced **1 January 2025**; sections 2, 3, 4, 5, 8, 10 and 12 commenced **1 April 2025**; and sections 6 and 9 commenced **1 June 2025**. See [Act A1727](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2024/11/Act-A1727.pdf) and the [official commencement notification](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2024/12/PENETAPAN-TARIKH-PERMULAAN-KUAT-KUASA-1.pdf).
- The amendments now use “data controller,” add biometric data to sensitive personal data, impose the Security Principle directly on data processors, introduce DPO, breach-notification and portability provisions, and amend section 129 cross-border transfers. This repository reads the consolidated effect of Act 709 with Act A1727; the Commissioner's hosted Act 709 PDF is a 2022 text and does not itself consolidate the 2024 amendments.

## Current obligations if Act 709 applies

These are legal obligations for an in-scope controller processing personal data, not claims that the unidentified prototype operator is in scope.

| Area | Effective requirement | Repository gap/status |
| --- | --- | --- |
| Seven principles | Processing must satisfy the General, Notice and Choice, Disclosure, Security, Retention, Data Integrity, and Access Principles. Data must be lawfully necessary, adequate and not excessive; protected; accurate; and not retained beyond purpose. | Public/synthetic-only policy reduces exposure. No approved operating process exists for real personal data. |
| Notice | Section 7 requires written notice as soon as practicable at first request/collection, or before new use/disclosure. It must describe the data, purposes, known sources, access/correction and contact route, third-party classes, limiting choices, whether supply is mandatory/voluntary, and consequences. It must be in Bahasa Malaysia and English. | No controller identity, real contact, bilingual notice, deployed-provider list, or verified purposes. The draft notice is deliberately non-publishable. |
| Rights | Access and correction must be supported, subject to statutory procedures/exceptions. Written consent withdrawal requires processing to cease. Rights to prevent harmful/distressing processing and direct marketing also apply. Section 43A portability, subject to technical feasibility and compatible format, commenced 1 June 2025; a completion period still depends on prescribed rules. | No authenticated rights channel, identity-verification procedure, case log, portability operation, or responsible owner. Session deletion alone is not a rights process. |
| Security/processors | Practical safeguards must account for data nature/harm, storage location, equipment, personnel, and transfer. Controllers must obtain sufficient processor security guarantees and take reasonable compliance steps; processors are now directly subject to the Security Principle. | Technical upload controls are under review, but hosting/provider contracts, regions, subprocessors, operator access, backups, monitoring, and incident SLAs are unknown. |
| Retention/integrity | Data must not be kept longer than necessary and must be destroyed or permanently deleted when no longer required; reasonable steps must keep it accurate, complete, not misleading, and current for its purpose. | Proposed 30-minute idle/120-minute absolute file TTL is narrow and useful, but deployed cleanup, backup/log/provider scope, receipt retention, deletion failure handling, and correction propagation are not verified. |
| Breach notification | Section 12B is in force. The Commissioner's final DBN guideline uses a significant-harm notification test, a notification to the Commissioner as soon as practicable and within 72 hours, and affected-subject notice without unnecessary delay and no later than seven days after the Commissioner notice when required. | Runbook exists, but no named controller decision-maker, reporting credentials, provider escalation contacts, or exercised tabletop. |
| Cross-border transfer | Amended section 129 commenced 1 April 2025. A controller must identify a statutory transfer condition; the Commissioner's guideline describes transfer assessments and safeguards. | Hosting and model/OCR locations and onward transfers are unknown. Real-personal-data transfer is blocked. |

Primary references: [Act 709 official text](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2024/07/UNDANG-UNDANG-MALAYSIA_AKTA_PERLINDUNGAN_DATA_PERIBADI_2010_709_MALAY_AND-ENG_V2022.pdf), [privacy-notice guidance](https://www.pdp.gov.my/ppdpv1/en/akta/guidance-on-the-preparation-of-personal-data-protection-notices/), [DBN guideline](https://www.pdp.gov.my/ppdpv1/en/guidelines-and-circulars-on-data-breach-notification-dbn/), and [cross-border guideline](https://www.pdp.gov.my/ppdpv1/en/akta/personal-data-protection-guidelines-on-cross-border-transfer-of-personal-data-cbpdt/).

## Role-, scale-, or processing-dependent obligations

| Decision | Trigger/evidence | MagicFin status |
| --- | --- | --- |
| Controller versus processor | Who determines purposes/means and who processes solely on another controller's behalf must be decided per flow. An organisation may hold different roles for different flows. | Unknown. Must be documented by the actual operator and customers before private uploads. |
| DPO | From 1 June 2025, the Commissioner's criteria require a controller or processor to appoint one or more DPOs if processing exceeds 20,000 data subjects; sensitive personal data including financial information exceeds 10,000 data subjects; or activities require regular and systematic monitoring. The controller must notify the Commissioner within 21 days of appointment. | Scale is unknown. A financial-document prototype does not automatically cross a threshold, but future monitoring or scale may. See the Commissioner's [DPO guideline](https://www.pdp.gov.my/ppdpv1/en/akta/personal-data-protection-guidelines-on-the-appointment-of-data-protection-officer-dpo/) and [official DPO registration manual](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2025/07/Manual_Pengguna_Pendaftaran_DPO_EN.pdf). |
| Controller registration | Registration applies to controllers in the classes specified under sections 13–14 and the class orders. Controllers outside those classes may still be bound by the rest of Act 709. | Operator sector/licensing facts are unknown. Assess the 13 classes, the 2016 amendment order, and the current [Commissioner Circular No. 1/2026](https://www.pdp.gov.my/ppdpv1/en/akta/personal-data-protection-commissioners-circular-no-1-2026-registration-of-data-controllers/); do not infer a regulated financial-institution class from the product name. |
| Sensitive data | Biometric data is sensitive after the amendment. Other sensitive-personal-data conditions are in section 40. Financial information is expressly relevant to the DPO threshold even though all uploaded financial reports are not necessarily personal data. | Public issuer financial statements are not personal data merely because they are financial. Private workbooks may identify individuals or contain sensitive information and remain prohibited. |
| Automated decisions/profiling | Act 709 has no standalone ADMP provision, but its principles apply. The Commissioner's final 2026 ADMP guideline calls for early DPO engagement and a DPIA for ADMP. | Current findings are evidence support for human review, not a decision about an individual. Any credit, employment, eligibility, behavioural profiling, or other consequential personal decision is out of scope. See the [official ADMP guideline](https://www.pdp.gov.my/ppdpv1/en/akta/automated-decision-making-and-profiling-guideline-admp/). |
| Sector code | A registered sector code applies only when the actual operator falls within its defined class. | No evidence MagicFin is a licensed bank or financial institution. Do not apply or claim the banking code based on branding alone. |

## Recommended controls before widening the prototype

These are engineering recommendations, not assertions that each is independently mandated:

1. Name the operating entity, controller/processor role per flow, privacy owner, rights contact, incident lead, hosting account owner, and provider owner.
2. Complete and legally review a deployed-behaviour data map, bilingual section 7 notice, processing-condition record, processor terms, cross-border assessment, retention schedule, rights procedure, DPO threshold record, and registration-class decision.
3. Keep public/synthetic fixtures as the default; add a hard server-side block against private/personal uploads until the readiness gate is signed off.
4. Verify hosting/model/OCR regions, subprocessors, training use, content retention, access controls, logs, backups, deletion APIs, breach SLAs, and contract terms. Document changes before provider enablement.
5. Test idle/absolute TTL, periodic/startup/shutdown cleanup, explicit deletion, in-flight cancellation, partial failures, bounded receipt/tombstone retention, and configured-root safety. A receipt must distinguish app-managed deletion from secure media erasure and provider/export deletion.
6. Provide authenticated rights intake and tracking without putting personal data in public GitHub issues. Exercise breach and rights table-tops before any real-personal-data pilot.
7. Perform a DPIA and human-oversight review before any assistant uses personal data or influences consequential decisions.

## Prototype limitations and unresolved legal facts

- The browser demo, Sites host, API deployment, model provider, and storage feature do not have one verified production data-flow inventory. `data-flow-retention.md` records implemented and proposed states separately.
- Static hosting can create infrastructure request/access logs even when application analytics are absent. Regions, retention, operator access, cookies, and subprocessors have not been verified.
- Proposed upload storage uses local temporary files. Application deletion is not evidence of secure media erasure, host backup deletion, crash-dump deletion, or provider deletion.
- Downloaded JSON/PDF exports are outside session deletion. No application can honestly promise deletion of copies a user saves or redistributes.
- No valid statutory privacy notice can be published until a real controller identity and contact channel exist and the deployed flows are verified. The engineering draft is not consent and does not cure these gaps.
- Registration and DPO conclusions require facts about the operator, licences/sector, number and type of data subjects, and monitoring. Obtain Malaysian legal advice before enabling personal-data processing.

This analysis should be rechecked before release and when the Commissioner updates Act 709 materials, circulars, guidelines, regulations, or registration classes.
