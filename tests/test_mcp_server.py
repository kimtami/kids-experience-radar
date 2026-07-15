from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tomllib

import pytest

from kids_experience_radar import mcp_server
from kids_experience_radar.models import CrawlResult, Event
from kids_experience_radar.normalizers import KST
from kids_experience_radar.store import EventStore


def _event(external_id: str, *, hour: int) -> Event:
    start = (datetime.now(KST) + timedelta(days=7)).replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    return Event(
        source_id="test_official_source",
        source_name="테스트 공식기관",
        external_id=external_id,
        title=f"초등 과학 체험 {external_id}",
        detail_url=f"https://example.go.kr/events/{external_id}",
        provider_name="테스트 공식기관",
        category="과학 체험",
        event_start=start,
        event_end=start + timedelta(hours=1),
        apply_end=start - timedelta(days=1),
        status="접수중",
        age_text="초등학생",
        age_min=7,
        age_max=13,
        price_text="무료",
        price_min=0,
        venue_name="수원 테스트관",
        address="경기도 수원시 팔달구 테스트로 1",
        region="경기도 수원시",
        latitude=37.2636,
        longitude=127.0286,
        child_relevance_score=0.95,
        fetched_at=datetime.now(KST),
        raw={"private_source_payload": "must never leave MCP"},
    )


def _seed_database(path: Path) -> list[Event]:
    events = [_event("one", hour=10), _event("two", hour=14)]
    with EventStore(path) as store:
        store.upsert_events(events)
    return events


def test_read_tools_do_not_create_a_missing_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "missing" / "radar.sqlite3"
    monkeypatch.setenv("KIDS_RADAR_DB", str(database))

    result = mcp_server.search_nearby_service(
        latitude=37.2636,
        longitude=127.0286,
    )
    status = mcp_server.status_service()

    assert result == {"count": 0, "next_cursor": None, "events": []}
    assert status["database_initialized"] is False
    assert not database.exists()
    assert not database.parent.exists()


def test_search_cursor_and_get_event_never_return_raw_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "radar.sqlite3"
    events = _seed_database(database)
    monkeypatch.setenv("KIDS_RADAR_DB", str(database))

    first = mcp_server.search_nearby_service(
        latitude=37.2636,
        longitude=127.0286,
        free_only=True,
        limit=1,
    )
    assert first["count"] == 1
    assert first["next_cursor"] is not None
    first_event = first["events"][0]  # type: ignore[index]
    assert "raw" not in first_event
    assert "private_source_payload" not in repr(first)

    second = mcp_server.search_nearby_service(
        latitude=37.2636,
        longitude=127.0286,
        free_only=True,
        limit=1,
        cursor=str(first["next_cursor"]),
    )
    assert second["count"] == 1
    assert second["next_cursor"] is None

    detail = mcp_server.get_event_service(events[0].uid)
    assert detail["found"] is True
    assert "raw" not in detail["event"]  # type: ignore[operator]
    assert "private_source_payload" not in repr(detail)


def test_cursor_is_bound_to_the_search_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "radar.sqlite3"
    _seed_database(database)
    monkeypatch.setenv("KIDS_RADAR_DB", str(database))
    first = mcp_server.search_nearby_service(
        latitude=37.2636,
        longitude=127.0286,
        limit=1,
    )

    with pytest.raises(ValueError, match="does not match"):
        mcp_server.search_nearby_service(
            latitude=37.2636,
            longitude=127.0286,
            radius_km=30,
            limit=1,
            cursor=str(first["next_cursor"]),
        )


def test_digest_is_returned_in_memory_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "radar.sqlite3"
    _seed_database(database)
    monkeypatch.setenv("KIDS_RADAR_DB", str(database))

    result = mcp_server.digest_service(
        latitude=37.2636,
        longitude=127.0286,
        new_within_hours=26,
        format="markdown",
    )

    assert result["count"] == 2
    assert result["mime_type"] == "text/markdown"
    assert "초등 과학 체험" in str(result["content"])
    assert "https://example.go.kr/events/" in str(result["content"])
    assert all(path.name.startswith("radar.sqlite3") for path in tmp_path.iterdir())


def test_refresh_is_disabled_and_exact_source_allowlisted_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KIDS_RADAR_MCP_ALLOW_CRAWL", raising=False)
    monkeypatch.delenv("KIDS_RADAR_MCP_CRAWL_SOURCES", raising=False)

    with pytest.raises(PermissionError, match="disabled"):
        mcp_server.refresh_service(source_ids=["suwon_library_child_programs"])

    monkeypatch.setenv("KIDS_RADAR_MCP_ALLOW_CRAWL", "1")
    monkeypatch.setenv(
        "KIDS_RADAR_MCP_CRAWL_SOURCES",
        "suwon_library_child_programs",
    )
    with pytest.raises(PermissionError, match="not MCP-allowlisted"):
        mcp_server.refresh_service(source_ids=["gyeonggi_library_programs"])


def test_mcp_errors_redact_keys_and_query_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "very-secret-service-key")

    redacted = mcp_server._redact_error(  # noqa: SLF001 - security contract
        "failed very-secret-service-key at ?serviceKey=other-secret&x=1"
    )

    assert "very-secret" not in str(redacted)
    assert "other-secret" not in str(redacted)
    assert str(redacted).count("[REDACTED]") == 2


def test_refresh_passes_only_validated_registry_sources_to_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "radar.sqlite3"
    captured: dict[str, object] = {}

    def fake_crawl_sources(
        sources: object,
        *,
        database: str | Path,
        window: object,
    ) -> list[CrawlResult]:
        selected = list(sources)  # type: ignore[arg-type]
        captured.update(
            {
                "source_ids": [source.info.source_id for source in selected],
                "database": database,
                "window": window,
            }
        )
        return [
            CrawlResult(
                source_id=selected[0].info.source_id,
                fetched=3,
                stored=3,
                changed=1,
                started_at=datetime.now(KST),
                finished_at=datetime.now(KST),
            )
        ]

    monkeypatch.setenv("KIDS_RADAR_DB", str(database))
    monkeypatch.setenv("KIDS_RADAR_MCP_ALLOW_CRAWL", "true")
    monkeypatch.setenv(
        "KIDS_RADAR_MCP_CRAWL_SOURCES",
        "suwon_library_child_programs",
    )
    monkeypatch.setattr(mcp_server, "crawl_sources", fake_crawl_sources)

    result = mcp_server.refresh_service(
        source_ids=["suwon_library_child_programs"],
        from_date="2026-07-15",
        to_date="2026-08-31",
        max_pages=10,
    )

    assert result["ok"] is True
    assert result["totals"] == {
        "fetched": 3,
        "stored": 3,
        "changed": 1,
        "skipped": 0,
        "errors": 0,
    }
    assert captured["source_ids"] == ["suwon_library_child_programs"]
    assert captured["database"] == database
    window = captured["window"]
    assert window.max_pages == 10  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"latitude": 91, "longitude": 127}, "latitude"),
        ({"latitude": 37, "longitude": 181}, "longitude"),
        ({"latitude": 37, "longitude": 127, "radius_km": 0}, "radius_km"),
        ({"latitude": 37, "longitude": 127, "limit": 101}, "limit"),
    ],
)
def test_search_rejects_unbounded_inputs(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        mcp_server.search_nearby_service(**kwargs)  # type: ignore[arg-type]


def test_in_memory_mcp_protocol_exposes_bounded_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp.shared.memory import create_connected_server_and_client_session

    database = tmp_path / "radar.sqlite3"
    _seed_database(database)
    monkeypatch.setenv("KIDS_RADAR_DB", str(database))
    monkeypatch.setenv("KIDS_RADAR_MCP_ALLOW_CRAWL", "0")

    async def check() -> None:
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.name == "Kids Experience Radar"
            assert initialized.serverInfo.version == "0.1.0"
            assert (
                str(initialized.serverInfo.websiteUrl)
                == "https://github.com/kimtami/kids-experience-radar"
            )
            listed = await session.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == {
                "get_experience",
                "get_radar_status",
                "list_experience_sources",
                "refresh_experience_sources",
                "render_nearby_digest",
                "search_nearby_experiences",
            }
            assert tools["search_nearby_experiences"].annotations.readOnlyHint
            assert not tools["refresh_experience_sources"].annotations.readOnlyHint
            search_schema = tools["search_nearby_experiences"].inputSchema
            assert search_schema["properties"]["latitude"]["minimum"] == -90
            assert search_schema["properties"]["latitude"]["maximum"] == 90
            assert search_schema["properties"]["limit"]["maximum"] == 100
            refresh_schema = tools["refresh_experience_sources"].inputSchema
            assert refresh_schema["properties"]["source_ids"]["maxItems"] == 25
            assert refresh_schema["properties"]["max_pages"]["maximum"] == 25

            resources = await session.list_resources()
            assert {str(resource.uri) for resource in resources.resources} == {
                "kidradar://sources",
                "kidradar://stats",
            }
            resource = await session.read_resource("kidradar://stats")
            assert '"database_initialized": true' in resource.contents[0].text
            prompts = await session.list_prompts()
            assert {prompt.name for prompt in prompts.prompts} == {
                "find_family_experiences"
            }

            result = await session.call_tool(
                "search_nearby_experiences",
                {
                    "latitude": 37.2636,
                    "longitude": 127.0286,
                    "limit": 1,
                },
            )
            assert result.isError is False
            assert result.structuredContent is not None
            assert result.structuredContent["count"] == 1

    asyncio.run(check())


def test_real_stdio_protocol_initializes_without_stdout_noise(
    tmp_path: Path,
) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    database = tmp_path / "radar.sqlite3"
    _seed_database(database)
    environment = dict(os.environ)
    environment.update(
        {
            "KIDS_RADAR_DB": str(database),
            "KIDS_RADAR_MCP_ALLOW_CRAWL": "0",
        }
    )

    async def check() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "kids_experience_radar.mcp_server"],
            env=environment,
            cwd=Path(__file__).parents[1],
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert "get_radar_status" in {tool.name for tool in listed.tools}
                result = await session.call_tool("get_radar_status", {})
                assert result.isError is False
                assert result.structuredContent is not None
                assert result.structuredContent["database_initialized"] is True

    asyncio.run(check())


def test_mcp_configs_use_current_wrappers_and_read_only_defaults() -> None:
    root = Path(__file__).parents[1]
    project_config = json.loads((root / ".mcp.json").read_text())
    desktop_config = json.loads(
        (root / "config/claude-desktop-mcp.example.json").read_text()
    )
    generic_config = json.loads(
        (root / "config/mcp-stdio-server.example.json").read_text()
    )
    codex_config = tomllib.loads(
        (root / "config/codex-mcp.example.toml").read_text()
    )
    pyproject = tomllib.loads((root / "pyproject.toml").read_text())

    for config in (project_config, desktop_config):
        server = config["mcpServers"]["kids_experience_radar"]
        assert server["type"] == "stdio"
        assert server["command"] == "uv"
        assert "kidradar-mcp" in server["args"]
        assert server["env"]["KIDS_RADAR_MCP_ALLOW_CRAWL"] == "0"

    project_server = project_config["mcpServers"]["kids_experience_radar"]
    assert "${CLAUDE_PROJECT_DIR:-.}" in project_server["args"]
    assert project_server["env"]["KIDS_RADAR_DB"].startswith(
        "${CLAUDE_PROJECT_DIR:-.}/"
    )

    assert generic_config["type"] == "stdio"
    assert generic_config["command"] == "uvx"
    assert generic_config["args"] == [
        "--from",
        "git+https://github.com/kimtami/kids-experience-radar.git@v0.1.0",
        "kidradar-mcp",
    ]
    assert generic_config["env"]["KIDS_RADAR_MCP_ALLOW_CRAWL"] == "0"

    codex = codex_config["mcp_servers"]["kids_experience_radar"]
    assert codex["command"] == "uv"
    assert codex["tool_timeout_sec"] >= 900
    assert codex["env"]["KIDS_RADAR_MCP_ALLOW_CRAWL"] == "0"
    assert (
        pyproject["project"]["scripts"]["kidradar-mcp"]
        == "kids_experience_radar.mcp_server:main"
    )
    assert "mcp>=1.28.1,<2" in pyproject["project"]["dependencies"]
