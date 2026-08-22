import json
from pathlib import Path

from proofline.api import app
from proofline.contracts import (
    AnalysisRequest,
    AnalysisResponse,
    CreateSessionRequest,
    DeletionReceipt,
    EvidenceChainSnapshot,
    ExtensionContracts,
    SessionStatus,
    SourceDeletionReceipt,
    SourceFileMetadata,
    SourceSessionCreated,
    SourceSessionStatus,
)
from proofline.metrics import REGISTRY
from proofline.report_contracts import CompanyLens, ReportRenderBundle


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    target = Path("contracts/v1")
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "analysis-request.schema.json", AnalysisRequest.model_json_schema())
    write_json(target / "analysis-response.schema.json", AnalysisResponse.model_json_schema())
    write_json(target / "evidence-chain.schema.json", EvidenceChainSnapshot.model_json_schema())
    write_json(target / "session-create.schema.json", CreateSessionRequest.model_json_schema())
    write_json(target / "session-status.schema.json", SessionStatus.model_json_schema())
    write_json(target / "deletion-receipt.schema.json", DeletionReceipt.model_json_schema())
    write_json(target / "source-file.schema.json", SourceFileMetadata.model_json_schema())
    write_json(target / "source-session.schema.json", SourceSessionStatus.model_json_schema())
    write_json(
        target / "source-session-create.schema.json", SourceSessionCreated.model_json_schema()
    )
    write_json(
        target / "source-deletion-receipt.schema.json",
        SourceDeletionReceipt.model_json_schema(),
    )
    write_json(target / "extension-contracts.schema.json", ExtensionContracts.model_json_schema())
    write_json(target / "company-lens.schema.json", CompanyLens.model_json_schema())
    write_json(target / "report-render-bundle.schema.json", ReportRenderBundle.model_json_schema())
    write_json(
        target / "metric-registry.json",
        {
            "registry_version": "1.0.0",
            "metrics": [
                {
                    "metric_id": definition.metric_id,
                    "formula_id": definition.formula_id,
                    "display_name": definition.display_name,
                    "required_roles": definition.required_roles,
                    "role_concepts": definition.role_concepts,
                    "tolerance": str(definition.tolerance),
                    "applicability": definition.applicability,
                }
                for definition in REGISTRY.values()
            ],
        },
    )
    write_json(target / "openapi.json", app.openapi())


if __name__ == "__main__":
    main()
