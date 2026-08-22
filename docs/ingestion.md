# Deterministic ingestion boundary

This slice implements a deliberately narrow, local ingestion and workbook-normalization path. It
does not call a model, extract narrative claims, or claim universal document support.

## Implemented

- Native digital-PDF text extraction with PyMuPDF, page-number provenance, deterministic span IDs,
  encrypted-file rejection, size/page limits, and explicit missing/sparse-text warnings.
- Structural `.xlsx` reading with openpyxl in read-only mode. Every non-empty cell retains document
  ID, sheet, coordinate, display value, data type, and a deterministic source-span ID.
- Formula cells are never evaluated. A formula without a cached value is returned as formula text
  with a typed warning. Cached formula values remain unverified and are not safe normalizer inputs.
- A provider-neutral OCR protocol and `PaddleOcrCompatibleAdapter` for an injected server-side OCR
  callable. OCR confidence and warnings remain attached to page evidence.
- Deterministic workbook normalization for row-oriented or transposed statement matrices. It
  requires explicit issuer, entity scope, ISO currency, source scale, and restatement metadata;
  recognizes a conservative Tier-0 concept vocabulary; converts monetary values to currency base
  units; and retains value, label, period, and metadata cell spans with confidence and warnings.
- Tier-0 calculation-plan generation only when every required concept/period intersection is
  unique. Conflicting metadata and duplicate facts fail closed rather than selecting a value.
- Synthetic PDF/XLSX tests across unrelated issuers, currencies, and layouts; no issuer document,
  secret, or private content is stored.

## Optional, not configured

PaddleOCR and PaddlePaddle are **not bundled** in the prototype dependency lock. Their platform-
specific runtime is too large and variable to claim as a verified default in this slice. A later
deployment may install pinned, reviewed Paddle packages and inject an engine returning `(text,
confidence)` lines through the existing adapter. Until then, scanned pages return
`ocr_not_configured`; they do not silently become evidence.

## Security and accuracy limits

- Only PDF-signature content and structurally valid `.xlsx` ZIP packages are accepted. Macro-bearing
  packages are rejected.
- Limits bound file size, page count, OCR raster and output size, ZIP entry and expanded-size totals,
  sheet count, declared worksheet dimensions, extracted cell count, and extracted quote length.
  Container CPU/memory/time limits remain a deployment responsibility.
- Native/OCR text and spreadsheet values are untrusted evidence candidates. The deterministic
  normalizer recognizes only exact allowlisted labels and explicit metadata. Unsupported labels,
  fiscal-year shorthand without a date, multi-currency tables, per-column scales/restatement
  bases, merged-cell headers, and more complex statement structures require a reviewed mapping.
- Confidence is an extraction signal, not an accuracy guarantee. OCR output must not become
  authoritative arithmetic or classification.
- This slice does not provide malware scanning, password recovery, secure erasure, PDPA compliance,
  PDF table reconstruction, formula calculation, narrative claim extraction, or universal
  workbook support.
