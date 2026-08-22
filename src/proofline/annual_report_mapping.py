from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import fitz

from proofline.contracts import FinancialClaim, MetricId, PdfSourceRef, SourceSpan
from proofline.metrics import REGISTRY, calculate_metric
from proofline.normalization import NormalizationResult
from proofline.parsing.models import ExtractedPage, ExtractionMethod, ExtractionWarning
from proofline.parsing.pdf import (
    MAX_PAGE_TEXT,
    MAX_PAGES,
    MAX_PDF_BYTES,
    MIN_NATIVE_CHARACTERS,
    PdfExtractionError,
)

MAX_DOCUMENT_PAGES = 500
MAX_DISCOVERY_PAGE_TEXT = 12_000
MAX_DISCOVERY_TEXT = 4_000_000
MAX_DISCOVERY_SECONDS = 10.0
MAX_SELECTED_PAGES = 32
MIN_SELECTED_PAGE_SCORE = 5
MIN_MAPPING_CONFIDENCE = 0.60
REVIEW_CONFIDENCE = 0.85

_STATEMENT_TITLES = (
    "statement of financial position",
    "statements of financial position",
    "statement of income",
    "statements of income",
    "statement of profit or loss",
    "statements of profit or loss",
    "statement of cash flows",
    "statements of cash flows",
    "financial highlights",
    "financial summary",
)
_BANK_INDICATORS = (
    "deposits from customers",
    "loans advances and financing",
    "net interest income",
    "expected credit losses",
    "banking operations",
)
_CONCEPT_LABELS: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue", "net sales", "sales revenue", "turnover", "operating revenue"),
    "operating_profit": (
        "operating profit",
        "operating income",
        "operating loss profit",
        "operating profit loss",
    ),
    "current_assets": ("current assets", "total current assets"),
    "current_liabilities": ("current liabilities", "total current liabilities"),
    "operating_cash_flow": (
        "net cash from operating activities",
        "net cash generated from operating activities",
        "net cash provided by operating activities",
        "operating cash flow",
    ),
    "capex": (
        "capital expenditure",
        "capital expenditures",
        "purchase of property plant and equipment",
        "purchases of property plant and equipment",
    ),
}
_CURRENCY_UNIT_PATTERN = re.compile(
    r"\b(?:amounts?\s+in|in|currency)\s+(?P<currency>myr|rm|usd|us\$|eur|gbp|sgd|s\$)\b",
    re.IGNORECASE,
)
_DECLARED_ISSUER_PATTERN = re.compile(
    r"\b(?:issuer|reporting\s+entity)\s*:\s*(?P<issuer>[^\n]{2,160})",
    re.IGNORECASE,
)


class AnnualReportMappingError(ValueError):
    pass


@dataclass(frozen=True)
class AnnualReportMapping:
    pages: tuple[ExtractedPage, ...]
    claims: tuple[FinancialClaim, ...]


@dataclass(frozen=True)
class _CandidatePage:
    page: int
    text: str
    confidence: float
    warnings: tuple[ExtractionWarning, ...] = ()
    score: int = 0


_NARRATIVE_PATTERNS: tuple[tuple[MetricId, re.Pattern[str], Decimal], ...] = (
    (
        MetricId.REVENUE_GROWTH_YOY,
        re.compile(
            r"\brevenue\s+(?:grew|growth(?:\s+yoy)?\s+(?:was|of))\s+"
            r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*%"
            r"\s+(?:in|for)\s+(?P<year>20\d{2})",
            re.IGNORECASE,
        ),
        Decimal("0.01"),
    ),
    (
        MetricId.OPERATING_MARGIN,
        re.compile(
            r"\boperating\s+margin\s+(?:was|of)\s+"
            r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*%"
            r"\s+(?:in|for)\s+(?P<year>20\d{2})",
            re.IGNORECASE,
        ),
        Decimal("0.01"),
    ),
    (
        MetricId.CURRENT_RATIO,
        re.compile(
            r"\bcurrent\s+ratio\s+(?:was|of)\s+"
            r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))"
            r"\s+(?:in|for)\s+(?P<year>20\d{2})",
            re.IGNORECASE,
        ),
        Decimal(1),
    ),
    (
        MetricId.FCF_MARGIN,
        re.compile(
            r"\b(?:project[- ]defined\s+)?(?:free[- ]cash[- ]flow|fcf)\s+margin\s+"
            r"(?:was|of)\s+(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*%"
            r"\s+(?:in|for)\s+(?P<year>20\d{2})",
            re.IGNORECASE,
        ),
        Decimal("0.01"),
    ),
)


class AnnualReportMapper:
    """Map bounded annual-report pages to cited metric claims without issuer rules."""

    def map(
        self,
        content: bytes,
        document_id: str,
        normalized: NormalizationResult,
        *,
        inherited_warnings: Sequence[str] = (),
    ) -> AnnualReportMapping:
        pages = self._discover_pages(content, normalized)
        return self._map_candidates(
            pages,
            document_id,
            normalized,
            inherited_warnings=tuple(inherited_warnings),
        )

    def map_extracted_pages(
        self,
        pages: Sequence[ExtractedPage],
        document_id: str,
        normalized: NormalizationResult,
        *,
        inherited_warnings: Sequence[str] = (),
    ) -> AnnualReportMapping:
        candidates = []
        for page in pages:
            if page.span is None or page.span.source.kind != "pdf":
                continue
            if (
                page.span.document_version_id != document_id
                or page.span.source.document_id != document_id
            ):
                raise AnnualReportMappingError(
                    "PDF page provenance does not match the mapped document"
                )
            candidates.append(
                _CandidatePage(
                    page=page.page,
                    text=page.span.source.quote,
                    confidence=page.confidence,
                    warnings=page.warnings,
                    score=self._page_score(page.span.source.quote, normalized),
                )
            )
        return self._map_candidates(
            tuple(candidates),
            document_id,
            normalized,
            inherited_warnings=tuple(inherited_warnings),
        )

    def _discover_pages(
        self, content: bytes, normalized: NormalizationResult
    ) -> tuple[_CandidatePage, ...]:
        if not content.startswith(b"%PDF-"):
            raise AnnualReportMappingError("content is not a PDF")
        if len(content) > MAX_PDF_BYTES:
            raise AnnualReportMappingError("PDF exceeds the extraction size limit")
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as error:
            raise AnnualReportMappingError("PDF could not be opened") from error
        try:
            if document.needs_pass:
                raise AnnualReportMappingError("encrypted PDFs are not supported")
            if document.page_count > MAX_DOCUMENT_PAGES:
                raise AnnualReportMappingError("PDF exceeds the document discovery page limit")
            candidates: list[_CandidatePage] = []
            total_text = 0
            started = time.monotonic()
            for index in range(document.page_count):
                self._check_discovery_time(started)
                try:
                    raw = document[index].get_text("text")
                except Exception as error:
                    raise AnnualReportMappingError("PDF page text extraction failed") from error
                self._check_discovery_time(started)
                text = raw[:MAX_DISCOVERY_PAGE_TEXT]
                total_text += len(text.encode("utf-8"))
                if total_text > MAX_DISCOVERY_TEXT:
                    raise AnnualReportMappingError("PDF exceeds the discovery text limit")
                if len("".join(text.split())) < MIN_NATIVE_CHARACTERS:
                    continue
                score = self._page_score(text, normalized)
                if score < MIN_SELECTED_PAGE_SCORE:
                    continue
                candidates.append(
                    _CandidatePage(
                        page=index + 1,
                        text=text,
                        confidence=min(1.0, 0.8 + len(text) / 1_000),
                        score=score,
                    )
                )
            candidates.sort(key=lambda item: (-item.score, item.page))
            # MAX_PAGES remains the hard parser ceiling; this mapper deliberately selects a much
            # smaller review set from an admitted document of up to 500 pages.
            limit = min(MAX_SELECTED_PAGES, MAX_PAGES)
            selected = candidates[:limit]
            if normalized.issuer:
                identity = next(
                    (item for item in candidates if _label(normalized.issuer) in _label(item.text)),
                    None,
                )
                if identity is not None and identity not in selected:
                    selected = [*selected[: limit - 1], identity]
            return tuple(selected)
        except PdfExtractionError as error:
            raise AnnualReportMappingError(str(error)) from error
        finally:
            document.close()

    @staticmethod
    def _check_discovery_time(started: float) -> None:
        if time.monotonic() - started > MAX_DISCOVERY_SECONDS:
            raise AnnualReportMappingError("PDF discovery exceeded the processing time limit")

    def _page_score(self, text: str, normalized: NormalizationResult) -> int:
        label = _label(text)
        score = 0
        score += 3 * sum(title in label for title in _STATEMENT_TITLES)
        score += 2 * sum(
            any(alias in label for alias in aliases) for aliases in _CONCEPT_LABELS.values()
        )
        years = {fact.observation.period.end.year for fact in normalized.facts}
        score += sum(str(year) in label for year in years)
        if normalized.issuer and _label(normalized.issuer) in label:
            score += 4
        if normalized.currency and self._expected_currency_present(text, normalized.currency):
            score += 2
        if " group " in f" {label} " or "consolidated" in label:
            score += 1
        return score

    def _map_candidates(
        self,
        pages: Sequence[_CandidatePage],
        document_id: str,
        normalized: NormalizationResult,
        *,
        inherited_warnings: tuple[str, ...],
    ) -> AnnualReportMapping:
        if not normalized.issuer or not normalized.entity_scope or not normalized.currency:
            raise AnnualReportMappingError("workbook identity metadata is incomplete")
        if not pages:
            raise AnnualReportMappingError("no relevant annual-report pages met the evidence gate")
        issuer_label = _label(normalized.issuer)
        searchable = " ".join(_label(page.text) for page in pages)
        identity_pages = [
            page
            for page in pages
            if issuer_label in _label(page.text)
            and any(
                title in _label(page.text)
                for title in ("annual report", "financial report", "financial statements")
            )
        ]
        if not identity_pages:
            raise AnnualReportMappingError("PDF issuer does not match workbook issuer metadata")
        declared_issuers = {
            _label(match.group("issuer"))
            for page in pages
            for match in _DECLARED_ISSUER_PATTERN.finditer(page.text)
        }
        if declared_issuers and any(issuer_label not in declared for declared in declared_issuers):
            raise AnnualReportMappingError("PDF issuer identity is ambiguous")
        if self._looks_like_bank(searchable):
            raise AnnualReportMappingError(
                "Tier 0 operating-company metrics are not applicable to this bank-style report"
            )
        declared_currencies = {
            currency for page in pages for currency in self._declared_currencies(page.text)
        }
        if normalized.currency not in declared_currencies:
            raise AnnualReportMappingError("PDF currency does not match workbook currency metadata")
        if declared_currencies != {normalized.currency}:
            raise AnnualReportMappingError("PDF currency declarations are ambiguous")
        scope = _label(normalized.entity_scope)
        if ("consolidated" in scope or "group" in scope) and not any(
            "consolidated" in _label(page.text) or " group " in f" {_label(page.text)} "
            for page in pages
        ):
            raise AnnualReportMappingError("PDF entity scope does not match workbook entity scope")

        metric_inputs = {item.plan.metric_id: item for item in normalized.metric_inputs}
        observations = {fact.observation.id: fact.observation for fact in normalized.facts}
        mapped_pages: list[ExtractedPage] = []
        claims: list[FinancialClaim] = []
        for metric_id, metric_input in metric_inputs.items():
            plan = metric_input.plan
            narrative = self._narrative_candidate(metric_id, metric_input.period.end.year, pages)
            if narrative is not None:
                page, text, asserted_value = narrative
                claim_page = self._claim_page(page, document_id, text)
                claims.append(
                    self._claim(
                        metric_id,
                        metric_input.period,
                        asserted_value,
                        text,
                        claim_page,
                        normalized,
                        inherited_warnings,
                    )
                )
                mapped_pages.append(claim_page)
                continue

            input_observations = [
                observations[item.observation_id]
                for item in plan.inputs
                if item.observation_id in observations
            ]
            if len(input_observations) != len(plan.inputs):
                continue
            matches = [
                page
                for page in pages
                if self._table_page_matches(page, input_observations, normalized.currency)
            ]
            if not matches:
                continue
            matches.sort(key=lambda item: (-item.score, item.page))
            page = matches[0]
            result = calculate_metric("annual-report-mapping", plan, observations)
            if result.result is None or result.exceptional_state is not None:
                continue
            quote = self._table_anchor(page.text, input_observations)
            claim_page = self._claim_page(page, document_id, quote)
            display_name = REGISTRY[metric_id].display_name
            text = (
                f"Financial statement tables imply {display_name} of {result.result} "
                f"for {metric_input.period.end.year}."
            )
            claims.append(
                self._claim(
                    metric_id,
                    metric_input.period,
                    result.result,
                    text,
                    claim_page,
                    normalized,
                    inherited_warnings,
                )
            )
            mapped_pages.append(claim_page)

        if not claims:
            raise AnnualReportMappingError(
                "no unambiguous report page corroborated a compatible workbook metric plan"
            )
        return AnnualReportMapping(pages=tuple(mapped_pages), claims=tuple(claims))

    @staticmethod
    def _looks_like_bank(searchable: str) -> bool:
        return sum(indicator in searchable for indicator in _BANK_INDICATORS) >= 3

    @staticmethod
    def _expected_currency_present(text: str, currency: str) -> bool:
        return AnnualReportMapper._declared_currencies(text) == {currency}

    @staticmethod
    def _declared_currencies(text: str) -> set[str]:
        found = {
            match.group("currency").casefold() for match in _CURRENCY_UNIT_PATTERN.finditer(text)
        }
        return {
            "MYR" if marker == "rm" else marker.upper().replace("US$", "USD") for marker in found
        }

    def _narrative_candidate(
        self, metric_id: MetricId, expected_year: int, pages: Sequence[_CandidatePage]
    ) -> tuple[_CandidatePage, str, Decimal] | None:
        pattern, factor = next(
            (pattern, factor)
            for candidate_metric, pattern, factor in _NARRATIVE_PATTERNS
            if candidate_metric == metric_id
        )
        found: dict[tuple[str, Decimal], tuple[_CandidatePage, str]] = {}
        values: set[Decimal] = set()
        wrong_years: set[int] = set()
        for page in pages:
            for match in pattern.finditer(" ".join(page.text.split())):
                year = match.group("year")
                if year is not None and int(year) != expected_year:
                    wrong_years.add(int(year))
                    continue
                try:
                    value = Decimal(match.group("value")) * factor
                except (InvalidOperation, TypeError):
                    continue
                if not value.is_finite():
                    continue
                text = match.group(0).strip()
                found.setdefault((_label(text), value), (page, text))
                values.add(value)
        if len(values) > 1:
            raise AnnualReportMappingError(f"conflicting {metric_id.value} claim candidates")
        if not found:
            if wrong_years:
                raise AnnualReportMappingError(
                    f"{metric_id.value} claim period does not match the workbook period"
                )
            return None
        (_, value), (page, text) = sorted(
            found.items(), key=lambda item: (-item[1][0].score, item[1][0].page)
        )[0]
        return page, text, value

    def _table_page_matches(
        self, page: _CandidatePage, observations: Sequence, currency: str
    ) -> bool:
        if page.confidence < MIN_MAPPING_CONFIDENCE:
            return False
        if not self._expected_currency_present(page.text, currency):
            return False
        lines = [" ".join(line.split()) for line in page.text.splitlines() if line.strip()]
        available_years = set(_label(page.text).split())
        by_concept: dict[str, list] = {}
        for observation in observations:
            by_concept.setdefault(observation.concept, []).append(observation)
        return all(
            self._concept_block_matches(lines, available_years, concept, concept_observations)
            for concept, concept_observations in by_concept.items()
        )

    @staticmethod
    def _concept_block_matches(
        lines: Sequence[str],
        available_years: set[str],
        concept: str,
        observations: Sequence,
    ) -> bool:
        aliases = _CONCEPT_LABELS.get(concept, ())
        if not aliases:
            return False
        expected_values = {_number_key(item.display_value) for item in observations}
        expected_years = {str(item.period.end.year) for item in observations}
        if "" in expected_values:
            return False
        for index, line in enumerate(lines):
            label = _label(line)
            if not any(label == alias or label.startswith(f"{alias} ") for alias in aliases):
                continue
            end = min(len(lines), index + 12)
            for following in range(index + 1, end):
                if re.search(r"[A-Za-z]{2}", lines[following]):
                    end = following
                    break
            block = " ".join(lines[index:end])
            value_sequence = [_number_key(value) for value in _number_tokens(block)]
            values = set(value_sequence)
            ordered_observations = sorted(
                observations, key=lambda item: item.period.end, reverse=True
            )
            ordered_keys = [_number_key(item.display_value) for item in ordered_observations]
            positions = [
                value_sequence.index(key) if value_sequence.count(key) == 1 else -1
                for key in ordered_keys
            ]
            roles_are_ordered = all(
                position >= 0 for position in positions
            ) and positions == sorted(positions)
            if (
                expected_values <= values
                and expected_years <= available_years
                and roles_are_ordered
            ):
                return True
        return False

    def _claim_page(
        self,
        page: _CandidatePage,
        document_id: str,
        quote: str,
    ) -> ExtractedPage:
        warnings = page.warnings
        if page.confidence < REVIEW_CONFIDENCE and not any(
            warning.code == "ocr_low_confidence" for warning in warnings
        ):
            warnings = (
                *warnings,
                ExtractionWarning(
                    code="ocr_low_confidence",
                    message="Selected report evidence is below the decisive confidence threshold.",
                ),
            )
        bounded_quote = " ".join(quote.split())[:MAX_PAGE_TEXT]
        digest = hashlib.sha256(bounded_quote.encode("utf-8")).hexdigest()[:16]
        method = "ocr" if page.warnings or page.confidence < REVIEW_CONFIDENCE else "native"
        span = SourceSpan(
            id=f"span:{document_id}:pdf:{page.page}:{method}:{digest}",
            document_version_id=document_id,
            source=PdfSourceRef(
                document_id=document_id,
                page=page.page,
                quote=bounded_quote,
            ),
        )
        return ExtractedPage(
            span=span,
            page=page.page,
            method=(ExtractionMethod.OCR if method == "ocr" else ExtractionMethod.NATIVE_PDF),
            confidence=page.confidence,
            warnings=warnings,
        )

    @staticmethod
    def _claim(
        metric_id,
        period,
        asserted_value,
        text,
        page: ExtractedPage,
        normalized: NormalizationResult,
        inherited_warnings: tuple[str, ...],
    ) -> FinancialClaim:
        assert page.span is not None
        return FinancialClaim(
            id=f"claim:{page.span.document_version_id}:{metric_id.value}",
            text=text,
            entity=normalized.entity_scope,
            metric_id=metric_id,
            period=period,
            asserted_value=asserted_value,
            unit="ratio",
            currency=normalized.currency,
            source_span_id=page.span.id,
            extraction_warnings=tuple(
                dict.fromkeys(
                    [*(warning.message for warning in page.warnings), *inherited_warnings]
                )
            ),
        )

    @staticmethod
    def _table_anchor(text: str, observations: Sequence) -> str:
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        selected: list[str] = []
        for observation in observations:
            aliases = _CONCEPT_LABELS.get(observation.concept, ())
            display_key = _number_key(observation.display_value)
            for index, line in enumerate(lines):
                line_label = _label(line)
                if any(alias in line_label for alias in aliases):
                    selected.extend(lines[max(0, index - 3) : min(len(lines), index + 8)])
                    break
            for index, line in enumerate(lines):
                if display_key and display_key in {
                    _number_key(value) for value in _number_tokens(line)
                }:
                    selected.extend(lines[max(0, index - 2) : min(len(lines), index + 3)])
                    break
        return " […] ".join(dict.fromkeys(selected))[:MAX_PAGE_TEXT]


def _label(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9€£$]+", " ", value).split())


def _number_tokens(value: str) -> Iterable[str]:
    return re.findall(r"(?<![A-Za-z0-9])\(?[+-]?\d[\d,]*(?:\.\d+)?\)?(?![A-Za-z0-9])", value)


def _number_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace(" ", "")
    text = re.sub(r"^[€£$¥]", "", text)
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", text):
        return ""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return ""
    if negative:
        number = -number
    return format(number.normalize(), "f")
