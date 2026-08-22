import asyncio
import json

from fastapi.testclient import TestClient

from proofline.api import app
from proofline.mcp_server import MAX_RESULTS, fetch_catalog, mcp, search_catalog


def _payload(result) -> dict:
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    return json.loads(result.content[0].text)


def test_search_and_fetch_match_company_knowledge_standard() -> None:
    search_payload = _payload(search_catalog("Apple operating margin"))

    assert search_payload["results"][0] == {
        "id": "metric:apple:fy2025:operating_margin",
        "title": "Apple Inc. FY2025 — Operating margin",
        "url": (
            "https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/"
            "c24e7a28-5254-4dfa-9447-62aaa3c24bb1.pdf"
        ),
    }

    fetched = _payload(fetch_catalog(search_payload["results"][0]["id"]))
    assert set(fetched) == {"id", "title", "text", "url", "metadata"}
    assert fetched["metadata"]["kind"] == "metric"
    assert fetched["metadata"]["calculation_status"] == "deterministic_derived_fixture"
    assert fetched["url"].startswith("https://")


def test_results_are_deterministic_bounded_and_stably_sorted() -> None:
    first = _payload(search_catalog("FY2025"))
    second = _payload(search_catalog("FY2025"))

    assert first == second
    assert len(first["results"]) == MAX_RESULTS
    assert len({result["id"] for result in first["results"]}) == MAX_RESULTS


def test_source_fetch_exposes_metadata_but_never_document_bytes() -> None:
    fetched = _payload(fetch_catalog("source:pcg-fr-2025"))

    assert fetched["metadata"]["kind"] == "source_metadata"
    assert fetched["metadata"]["document_bytes_exposed"] is False
    assert (
        "public, human-reviewed hackathon fixture"
        in fetched["metadata"]["demo_boundary"].casefold()
    )
    assert "bytes" not in fetched


def test_unknown_or_empty_inputs_fail_closed() -> None:
    for invalid_query in ("", "  --  "):
        try:
            search_catalog(invalid_query)
        except ValueError as error:
            assert "letter or number" in str(error)
        else:  # pragma: no cover - assertion helper
            raise AssertionError("invalid search query did not fail")

    try:
        fetch_catalog("source:not-real")
    except ValueError as error:
        assert "unknown id" in str(error)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("unknown fetch id did not fail")


def test_tool_descriptors_are_exact_read_only_search_and_fetch() -> None:
    tools = asyncio.run(mcp.list_tools())

    assert [tool.name for tool in tools] == ["search", "fetch"]
    assert tools[0].inputSchema["required"] == ["query"]
    assert set(tools[0].inputSchema["properties"]) == {"query"}
    assert tools[0].inputSchema["properties"]["query"]["maxLength"] == 200
    assert tools[1].inputSchema["required"] == ["id"]
    assert set(tools[1].inputSchema["properties"]) == {"id"}
    assert tools[1].inputSchema["properties"]["id"]["maxLength"] == 160
    for tool in tools:
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is False


def test_streamable_http_mcp_endpoint_initializes() -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "proofline-test", "version": "1.0"},
        },
    }

    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Host": "127.0.0.1:8000",
        }
        response = client.post(
            "/mcp",
            json=request,
            headers=headers,
        )
        listed = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=headers,
        )
        called = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "Apple operating margin"}},
            },
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert body["result"]["serverInfo"]["name"] == "MagicFin reviewed demo"
    assert listed.status_code == 200
    assert [tool["name"] for tool in listed.json()["result"]["tools"]] == ["search", "fetch"]
    assert called.status_code == 200
    call_content = called.json()["result"]["content"]
    assert len(call_content) == 1
    assert call_content[0]["type"] == "text"
    assert json.loads(call_content[0]["text"])["results"][0]["id"] == (
        "metric:apple:fy2025:operating_margin"
    )
