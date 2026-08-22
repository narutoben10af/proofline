from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from proofline.report_contracts import (
    CompanyLens,
    FinancialTrendSeries,
    ResolvedEconomicContextPoint,
)


@lru_cache(maxsize=1)
def _fixture() -> dict:
    path = files("proofline").joinpath("fixtures/economic_context_fy2025.json")
    return json.loads(path.read_text(encoding="utf-8"))


def get_company_lens(company_id: str) -> CompanyLens | None:
    raw = _fixture().get("companies", {}).get(company_id)
    if raw is None:
        return None
    points = tuple(ResolvedEconomicContextPoint.model_validate(item) for item in raw["context"])
    return CompanyLens(
        company_id=company_id,
        company=raw["company"],
        reviewed_period=raw["reviewed_period"],
        trend=FinancialTrendSeries.model_validate(raw["trend"]),
        economic_context=tuple(point for point in points if point.default_visible),
        additional_context=tuple(point for point in points if not point.default_visible),
    )
