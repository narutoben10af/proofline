"""Read-only MCP surface for the reviewed public MagicFin demo corpus."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

DEMO_BOUNDARY = (
    "Public, human-reviewed hackathon fixture. No private database, uploaded document bytes, "
    "live model output, authentication, or user-specific state is exposed through this MCP server."
)
MAX_RESULTS = 10


@dataclass(frozen=True)
class CatalogItem:
    id: str
    title: str
    text: str
    url: str
    metadata: dict[str, Any]

    @property
    def searchable_text(self) -> str:
        return " ".join((self.id, self.title, self.text, json.dumps(self.metadata)))


class SearchResult(BaseModel):
    id: str
    title: str
    url: str


class SearchOutput(BaseModel):
    results: list[SearchResult]


class FetchOutput(BaseModel):
    id: str
    title: str
    text: str
    url: str
    metadata: dict[str, Any] | None = None


APPLE_10K = (
    "https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/c24e7a28-5254-4dfa-9447-62aaa3c24bb1.pdf"
)
PCG_REPORT = (
    "https://www.petronas.com/pcg/sites/default/files/uploads/content/2026/"
    "IR%20Suite%202025/PCG%20FR2025%20%5BInteractive%20PDF%5D.pdf"
)
PCG_RELEASE = (
    "https://www.petronas.com/pcg/media/media-releases/"
    "fy2025-results-reflect-challenging-market-pcg-prioritises-operational-and"
)


def _metric_item(
    company_slug: str,
    company: str,
    metric_id: str,
    label: str,
    display_value: str,
    formula: str,
    url: str,
) -> CatalogItem:
    return CatalogItem(
        id=f"metric:{company_slug}:fy2025:{metric_id}",
        title=f"{company} FY2025 — {label}",
        text=(
            f"{label}: {display_value}. This is a deterministic calculated result using "
            f"the project formula `{formula}` and reviewed public fixture inputs."
        ),
        url=url,
        metadata={
            "kind": "metric",
            "company": company,
            "period": "FY2025",
            "metric_id": metric_id,
            "display_value": display_value,
            "formula": formula,
            "calculation_status": "deterministic_derived_fixture",
            "demo_boundary": DEMO_BOUNDARY,
        },
    )


def _source_item(
    source_id: str,
    title: str,
    issuer: str | None,
    period: str | None,
    source_type: str,
    url: str,
) -> CatalogItem:
    return CatalogItem(
        id=f"source:{source_id.casefold()}",
        title=title,
        text=(
            f"Official source metadata for {title}. MagicFin exposes this citation and reviewed "
            "provenance only; the source document bytes are not returned by MCP."
        ),
        url=url,
        metadata={
            "kind": "source_metadata",
            "source_id": source_id,
            "issuer": issuer,
            "period": period,
            "source_type": source_type,
            "document_bytes_exposed": False,
            "demo_boundary": DEMO_BOUNDARY,
        },
    )


_ITEMS = (
    CatalogItem(
        id="company:apple:fy2025",
        title="Apple Inc. FY2025 reviewed analysis",
        text=(
            "Reviewed public demo analysis for Apple Inc. FY2025. It covers revenue growth, "
            "operating margin, current ratio, project-defined free-cash-flow margin, and gross "
            "margin. Values are deterministic derivatives of attributed filing facts."
        ),
        url=APPLE_10K,
        metadata={
            "kind": "company_analysis",
            "company": "Apple Inc.",
            "period": "FY2025",
            "source_completeness": "reviewed_fixture",
            "metric_ids": [
                "revenue_growth_yoy",
                "operating_margin",
                "current_ratio",
                "fcf_margin",
                "gross_margin",
            ],
            "demo_boundary": DEMO_BOUNDARY,
        },
    ),
    CatalogItem(
        id="company:pcg:fy2025",
        title="PETRONAS Chemicals Group Berhad FY2025 reviewed analysis",
        text=(
            "Reviewed public demo analysis for PETRONAS Chemicals Group Berhad (PCG) FY2025. "
            "It covers five deterministic metrics and an operating-margin exception that needs "
            "human investigation; MagicFin does not infer its cause."
        ),
        url=PCG_REPORT,
        metadata={
            "kind": "company_analysis",
            "company": "PETRONAS Chemicals Group Berhad",
            "period": "FY2025",
            "source_completeness": "reviewed_fixture",
            "metric_ids": [
                "revenue_growth_yoy",
                "operating_margin",
                "current_ratio",
                "fcf_margin",
                "gross_margin",
            ],
            "demo_boundary": DEMO_BOUNDARY,
        },
    ),
    _metric_item(
        "apple",
        "Apple Inc.",
        "revenue_growth_yoy",
        "Revenue growth",
        "6.425512%",
        "revenue_t / revenue_t_minus_1 - 1",
        APPLE_10K,
    ),
    _metric_item(
        "apple",
        "Apple Inc.",
        "operating_margin",
        "Operating margin",
        "31.970800%",
        "operating_profit_or_loss / revenue",
        APPLE_10K,
    ),
    _metric_item(
        "apple",
        "Apple Inc.",
        "current_ratio",
        "Current ratio",
        "0.893293x",
        "current_assets / current_liabilities",
        APPLE_10K,
    ),
    _metric_item(
        "apple",
        "Apple Inc.",
        "fcf_margin",
        "Project-defined FCF margin",
        "23.732882%",
        "(operating_cash_flow - cash_purchases_of_ppe) / revenue",
        APPLE_10K,
    ),
    _metric_item(
        "apple",
        "Apple Inc.",
        "gross_margin",
        "Gross margin",
        "46.905164%",
        "gross_profit / revenue",
        APPLE_10K,
    ),
    _metric_item(
        "pcg",
        "PETRONAS Chemicals Group Berhad",
        "revenue_growth_yoy",
        "Revenue growth",
        "-10.403965%",
        "revenue_t / revenue_t_minus_1 - 1",
        PCG_REPORT,
    ),
    _metric_item(
        "pcg",
        "PETRONAS Chemicals Group Berhad",
        "operating_margin",
        "Operating margin",
        "-4.992722%",
        "operating_profit_or_loss / revenue",
        PCG_REPORT,
    ),
    _metric_item(
        "pcg",
        "PETRONAS Chemicals Group Berhad",
        "current_ratio",
        "Current ratio",
        "1.439522x",
        "current_assets / current_liabilities",
        PCG_REPORT,
    ),
    _metric_item(
        "pcg",
        "PETRONAS Chemicals Group Berhad",
        "fcf_margin",
        "Project-defined FCF margin",
        "3.875546%",
        "(operating_cash_flow - cash_purchases_of_ppe) / revenue",
        PCG_REPORT,
    ),
    _metric_item(
        "pcg",
        "PETRONAS Chemicals Group Berhad",
        "gross_margin",
        "Gross margin",
        "10.655022%",
        "gross_profit / revenue",
        PCG_REPORT,
    ),
    CatalogItem(
        id="finding:pcg:fy2025:operating-margin-swing",
        title="PCG moved from operating profit to operating loss",
        text=(
            "PCG revenue contracted while operating profit became an operating loss. The "
            "reported arithmetic supports the size and direction of the swing, but not a cause. "
            "Classification: uncertain as to cause; human investigation is required."
        ),
        url=PCG_REPORT,
        metadata={
            "kind": "finding",
            "company": "PETRONAS Chemicals Group Berhad",
            "period": "FY2025",
            "classification": "uncertain",
            "review_status": "needs_human_investigation",
            "demo_boundary": DEMO_BOUNDARY,
        },
    ),
    CatalogItem(
        id="finding:pcg:fy2025:revenue-rounding",
        title="PCG FY2025 RM27.5 billion revenue rounding check",
        text=(
            "The issuer release's RM27.5 billion revenue claim agrees with audited RM27,480 "
            "million at the claim's one-decimal-billion precision. Classification: supported."
        ),
        url=PCG_RELEASE,
        metadata={
            "kind": "finding",
            "company": "PETRONAS Chemicals Group Berhad",
            "period": "FY2025",
            "classification": "supported",
            "review_status": "reviewed_fixture",
            "demo_boundary": DEMO_BOUNDARY,
        },
    ),
    CatalogItem(
        id="report:apple:fy2025",
        title="Apple Inc. FY2025 reviewed report metadata",
        text=(
            "Reviewed demo report metadata for Apple FY2025. The current main revision exposes "
            "the fixture-backed analysis only; a server-generated PDF is not claimed by this MCP "
            "surface."
        ),
        url=APPLE_10K,
        metadata={
            "kind": "report_metadata",
            "company": "Apple Inc.",
            "period": "FY2025",
            "pdf_status": "not_exposed_by_mcp",
            "document_bytes_exposed": False,
            "demo_boundary": DEMO_BOUNDARY,
        },
    ),
    CatalogItem(
        id="report:pcg:fy2025",
        title="PCG FY2025 reviewed report metadata",
        text=(
            "Reviewed demo report metadata for PCG FY2025. The current main revision exposes "
            "the fixture-backed analysis only; a server-generated PDF is not claimed by this MCP "
            "surface."
        ),
        url=PCG_REPORT,
        metadata={
            "kind": "report_metadata",
            "company": "PETRONAS Chemicals Group Berhad",
            "period": "FY2025",
            "pdf_status": "not_exposed_by_mcp",
            "document_bytes_exposed": False,
            "demo_boundary": DEMO_BOUNDARY,
        },
    ),
    _source_item(
        "APPLE-FILING-HUB-2025",
        "Apple FY2025 official filing hub",
        "Apple Inc.",
        "FY2025",
        "official_filing_hub",
        "https://investor.apple.com/sec-filings/sec-filings-details/default.aspx?FilingId=18880179",
    ),
    _source_item(
        "APPLE-10K-2025",
        "Apple FY2025 Form 10-K PDF",
        "Apple Inc.",
        "FY2025",
        "official_form_10k_pdf",
        APPLE_10K,
    ),
    _source_item(
        "APPLE-SEC-ACCESSION-2025",
        "Apple FY2025 SEC accession directory",
        "Apple Inc.",
        "FY2025",
        "official_sec_accession_directory",
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/",
    ),
    _source_item(
        "SEC-EDGAR-API-GUIDANCE",
        "SEC EDGAR API guidance",
        None,
        None,
        "official_retrieval_guidance",
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    ),
    _source_item(
        "PCG-FR-2025",
        "PCG Financial Report 2025",
        "PETRONAS Chemicals Group Berhad",
        "FY2025",
        "official_audited_financial_report_pdf",
        PCG_REPORT,
    ),
    _source_item(
        "PCG-REPORTS-HUB",
        "PCG official reports hub",
        "PETRONAS Chemicals Group Berhad",
        "FY2025",
        "official_reports_hub",
        "https://www.petronas.com/pcg/investor-relations/reports",
    ),
    _source_item(
        "PCG-FY2025-RELEASE",
        "PCG FY2025 results release",
        "PETRONAS Chemicals Group Berhad",
        "FY2025",
        "official_media_release_html",
        PCG_RELEASE,
    ),
)
_CATALOG = {item.id: item for item in _ITEMS}


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _rank(item: CatalogItem, query_tokens: tuple[str, ...]) -> tuple[int, str]:
    haystack = item.searchable_text.casefold()
    title = item.title.casefold()
    score = sum(3 if token in title else 1 for token in query_tokens if token in haystack)
    return (-score, item.id)


def _text_result(payload: dict[str, Any]) -> CallToolResult:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return CallToolResult(
        content=[TextContent(type="text", text=encoded)],
        structuredContent=payload,
    )


def _search_payload(query: str) -> dict[str, Any]:
    query_tokens = _tokens(query)
    if not query_tokens:
        raise ValueError("query must include at least one letter or number")
    matches = [
        item
        for item in _ITEMS
        if all(token in item.searchable_text.casefold() for token in query_tokens)
    ]
    matches.sort(key=lambda item: _rank(item, query_tokens))
    return {
        "results": [
            {"id": item.id, "title": item.title, "url": item.url} for item in matches[:MAX_RESULTS]
        ]
    }


def search_catalog(query: str) -> CallToolResult:
    """Return deterministic standard search results from the reviewed demo catalog."""

    return _text_result(_search_payload(query))


def _fetch_payload(item_id: str) -> dict[str, Any]:
    item = _CATALOG.get(item_id)
    if item is None:
        raise ValueError("unknown id; call search first and pass an exact returned id")
    return {
        "id": item.id,
        "title": item.title,
        "text": item.text,
        "url": item.url,
        "metadata": item.metadata,
    }


def fetch_catalog(item_id: str) -> CallToolResult:
    """Return one deterministic standard fetch document from the reviewed demo catalog."""

    return _text_result(_fetch_payload(item_id))


READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def search(
    query: Annotated[str, Field(min_length=1, max_length=200)],
) -> SearchOutput:
    return SearchOutput.model_validate(_search_payload(query))


def fetch(
    id: Annotated[str, Field(min_length=1, max_length=160)],
) -> FetchOutput:
    return FetchOutput.model_validate(_fetch_payload(id))


def build_mcp_server() -> FastMCP:
    """Build a fresh server so repeated application lifespans remain testable."""

    server = FastMCP(
        "MagicFin reviewed demo",
        instructions=(
            "Read-only access to MagicFin's public, reviewed FY2025 demo fixtures. Use search "
            "before fetch. Never describe this server as access to private uploads, a live "
            "database, or live AI."
        ),
        json_response=True,
        stateless_http=True,
    )
    server.tool(
        name="search",
        title="Search MagicFin reviewed demo",
        description=(
            "Use this when you need to find reviewed MagicFin demo companies, analyses, metrics, "
            "findings, sources, or report metadata. This is read-only public fixture data."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
    )(search)
    server.tool(
        name="fetch",
        title="Fetch a MagicFin reviewed demo item",
        description=(
            "Use this when you have an exact id returned by search and need the reviewed text, "
            "canonical citation URL, and truthful demo metadata for that one item."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
    )(fetch)
    return server


class MCPHTTPGateway:
    """Delegate mounted requests to the MCP app owned by the current parent lifespan."""

    def __init__(self) -> None:
        self.active_app: Any | None = None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if self.active_app is None:
            raise RuntimeError("MCP server lifespan is not active")
        await self.active_app(scope, receive, send)


mcp = build_mcp_server()
mcp_http_gateway = MCPHTTPGateway()
