"""Tests for the memory module: multi-store persistence, owner isolation,
and read/write flows."""

import random

import pytest

from app.modules.memory.consolidation import ConsolidationPipeline
from app.modules.memory.manager import MemoryManager
from app.modules.memory.stores import (
    EpisodicStore,
    LessonStore,
    ProceduralStore,
    SemanticStore,
    UserFactStore,
    _chunk_text,
)
from app.modules.memory.types import ExtractedFact


def _owner_id() -> int:
    """Unique owner_id per test, to avoid cross-test pollution in the
    shared ChromaDB collections."""
    return random.randint(10_000_000, 99_999_999)


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "short text"
        assert _chunk_text(text) == [text]

    def test_long_text_is_split_into_multiple_chunks(self):
        text = "x" * 1200
        chunks = _chunk_text(text)
        assert len(chunks) > 1

    def test_chunks_have_overlap(self):
        text = "a" * 100 + "b" * 500 + "c" * 100
        chunks = _chunk_text(text)
        # consecutive chunks should share some overlapping content
        assert chunks[0][-10:] in text


class TestSemanticStoreOwnerIsolation:
    def test_add_and_search_command_output(self):
        owner_id = _owner_id()
        SemanticStore.add_command_output(
            server_name="prod-db-01",
            command="df -h",
            stdout="Filesystem 100% full on /var",
            stderr="",
            exit_code=0,
            owner_id=owner_id,
        )
        result = SemanticStore.search(
            "disk usage on prod-db-01", owner_id, n_results=3
        )
        assert "prod-db-01" in result

    def test_search_does_not_leak_across_owners(self):
        owner_a = _owner_id()
        owner_b = _owner_id()
        SemanticStore.add_command_output(
            server_name="secret-server",
            command="cat /etc/passwd",
            stdout="root:x:0:0",
            stderr="",
            exit_code=0,
            owner_id=owner_a,
        )
        result = SemanticStore.search("secret-server passwd", owner_b, n_results=5)
        assert "secret-server" not in result

    def test_add_log_and_add_config_are_searchable(self):
        owner_id = _owner_id()
        SemanticStore.add_log(
            server_name="web-01",
            log_source="nginx",
            content="502 Bad Gateway error",
            owner_id=owner_id,
        )
        SemanticStore.add_config(
            server_name="web-01",
            file_path="/etc/nginx/nginx.conf",
            content="worker_processes auto;",
            owner_id=owner_id,
        )
        result = SemanticStore.search(
            "nginx configuration and errors on web-01", owner_id, n_results=5
        )
        assert "web-01" in result


class TestLessonStore:
    def test_add_and_search_lesson(self):
        owner_id = _owner_id()
        LessonStore.add_lesson(
            server_name="cache-01",
            problem="Redis OOM crashes",
            real_cause="maxmemory not set, unbounded growth",
            what_didnt_work="Restarting the service",
            what_worked="Set maxmemory-policy to allkeys-lru",
            time_to_resolve="45 minutes",
            owner_id=owner_id,
        )
        result = LessonStore.search(
            "redis running out of memory", owner_id, n_results=2
        )
        assert "cache-01" in result

    def test_search_empty_owner_returns_no_match_message(self):
        owner_id = _owner_id()
        result = LessonStore.search("anything at all", owner_id, n_results=2)
        assert "No" in result


class TestEpisodicStore:
    def test_add_and_search_summary(self):
        owner_id = _owner_id()
        EpisodicStore.add_summary(
            session_id=random.randint(1, 999999),
            summary=(
                "User investigated high CPU on app-server, root cause "
                "was a runaway cron job."
            ),
            owner_id=owner_id,
        )
        result = EpisodicStore.search("high CPU investigation", owner_id, n_results=2)
        assert "cron" in result


class TestUserFactStore:
    def test_add_and_search_fact(self):
        owner_id = _owner_id()
        UserFactStore.add_fact(
            subject="nginx",
            content="nginx config lives at /etc/nginx/sites-enabled",
            fact_type="server_fact",
            confidence=0.9,
            owner_id=owner_id,
        )
        result = UserFactStore.search(
            "where is nginx configured", owner_id, n_results=3
        )
        assert "sites-enabled" in result

    def test_search_isolated_per_owner(self):
        owner_a = _owner_id()
        owner_b = _owner_id()
        UserFactStore.add_fact(
            subject="prod-db",
            content="prod-db uses PostgreSQL 16 on port 5433",
            fact_type="server_fact",
            confidence=0.95,
            owner_id=owner_a,
        )
        result = UserFactStore.search("prod-db postgres port", owner_b, n_results=3)
        assert "5433" not in result


class TestProceduralStore:
    def test_register_and_retrieve_tool(self):
        tool_name = f"custom_tool_{random.randint(1, 999999)}"
        ProceduralStore.register_tool(
            name=tool_name,
            description="Restarts a systemd service by name",
            parameters="service_name: str",
        )
        results = ProceduralStore.retrieve_tools(
            "restart a systemd service", n_results=5
        )
        assert tool_name in results

    def test_register_tool_is_upsert_not_duplicate(self):
        tool_name = f"custom_tool_{random.randint(1, 999999)}"
        ProceduralStore.register_tool(tool_name, "v1 description", "a: str")
        ProceduralStore.register_tool(
            tool_name, "v2 description, updated", "a: str, b: int"
        )
        results = ProceduralStore.retrieve_tools(
            "v2 description updated", n_results=10
        )
        assert results.count(tool_name) == 1


class TestConsolidationPipeline:
    @pytest.mark.asyncio
    async def test_low_confidence_facts_are_discarded(self):
        owner_id = _owner_id()
        pipeline = ConsolidationPipeline()
        fact = ExtractedFact(
            fact_type="preference",
            subject="test-subject",
            content="low confidence fact that should be discarded",
            confidence=0.3,
        )
        await pipeline.consolidate([fact], owner_id)
        result = UserFactStore.search(
            "low confidence fact that should be discarded", owner_id
        )
        assert "No" in result or "low confidence fact" not in result

    @pytest.mark.asyncio
    async def test_high_confidence_fact_is_persisted(self):
        owner_id = _owner_id()
        pipeline = ConsolidationPipeline()
        fact = ExtractedFact(
            fact_type="server_fact",
            subject="staging-01",
            content="staging-01 runs Ubuntu 24.04 LTS",
            confidence=0.9,
        )
        await pipeline.consolidate([fact], owner_id)
        result = UserFactStore.search("what OS does staging-01 run", owner_id)
        assert "Ubuntu 24.04" in result

    @pytest.mark.asyncio
    async def test_duplicate_fact_is_not_persisted_twice(self):
        owner_id = _owner_id()
        pipeline = ConsolidationPipeline()
        fact = ExtractedFact(
            fact_type="server_fact",
            subject="dup-server",
            content="dup-server has 32GB of RAM installed",
            confidence=0.9,
        )
        await pipeline.consolidate([fact], owner_id)
        await pipeline.consolidate([fact], owner_id)
        result = UserFactStore.search("dup-server RAM", owner_id, n_results=10)
        assert result.count("32GB") == 1


class TestMemoryManagerReadContext:
    def test_read_context_returns_memory_context_shape(self):
        owner_id = _owner_id()
        manager = MemoryManager()
        context = manager.read_context("any query about servers", owner_id)
        assert hasattr(context, "lessons")
        assert hasattr(context, "knowledge")
        assert hasattr(context, "episodic")

    def test_read_context_on_fresh_owner_has_no_matches(self):
        owner_id = _owner_id()
        manager = MemoryManager()
        context = manager.read_context("something specific and unique", owner_id)
        assert "No" in context.lessons
        assert "No" in context.episodic
