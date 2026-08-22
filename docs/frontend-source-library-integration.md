# Source Library frontend integration contract

The product-shell branch owns page hierarchy, layout and styling. The storage branch provides the
provider-neutral request adapter in `frontend/src/session-api.js`; it does not own shared React page
components.

## Expected Review Desk behavior

- Integrate one section named **Files in this review** or **Source Library — temporary session** in
  the existing New Review / Review Desk hierarchy. Do not create another dashboard.
- Show the exact prototype retention boundary: 30 minutes idle and two hours absolute, in this
  running process only; no database or confidential-production claim.
- Present two required slots: **Financial report PDF** (`report_pdf`) and **Spreadsheet evidence**
  (`workbook`). Show display name, canonical type, byte size, role and only `Uploading`, `Checking`,
  `Ready` or `Needs attention`.
- Provide Remove per file and keep Start review disabled until both roles are `Ready`.
- Map stable `reason_code` values to readable copy. Never render response/parser detail, the
  capability, raw content or a key. Do not put the CSRF token in persistent browser storage.
- Add **Delete review and files** with the server receipt’s exact claim, counts/bytes, managed-root
  confirmation, provider-sent flag and four exclusions. Make the receipt readable and copyable.
- Keep **Try the public demo** separate. Label Apple as **Official source fixture** and PCG as
  **Project-derived fixture**. Load cached output only after an explicit user action and matching
  `fixture_hash`; never replace failed live input silently.

## Route sequence

1. `POST /api/sessions` with same-origin credentials. Keep returned `session_id` and `csrf_token`
   only in current UI memory; the capability arrives only in the HttpOnly cookie.
2. `POST /api/sessions/{id}/files` multipart with `role` and `file`, plus
   `X-Proofline-CSRF`. Use the returned metadata as the authoritative `Ready` state.
3. `GET /api/sessions/{id}/files` to refresh the list; authorized preview/download uses
   `GET /api/sessions/{id}/files/{file_id}/content?disposition=inline|attachment`.
4. `POST /api/sessions/{id}/analysis` to run the local, source-cited digital-text/XLSX path once
   both files are `Ready`. Map `WORKBOOK_MAPPING_REQUIRED` and `PDF_MAPPING_REQUIRED` to a reviewed
   mapping state; do not select a fixture on failure.
5. `DELETE /api/sessions/{id}/files/{file_id}` for Remove and
   `DELETE /api/sessions/{id}` for the idempotent deletion receipt.
6. `POST /api/sessions/{id}/start` only when both roles are ready for a future provider-backed
   worker. A
   `PROVIDER_ACCESS_REQUIRED` response must expose the separate public-demo option.
7. `GET /api/public-demo/{apple-fy2025|pcg-fy2025}` returns a checked-in hash-verified fixture
   without requiring a model key.

All session mutations use `credentials: "same-origin"` and `X-Proofline-CSRF`. The adapter uses
relative URLs and contains no secrets.
