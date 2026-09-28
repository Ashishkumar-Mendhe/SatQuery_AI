"""Unit tests for AI/VLM provider interfaces, mock providers, and fallback registry."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from satquery.api.schemas.analysis import (
    AnalysisMode,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceType,
    WarningCode,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderMode,
    ProviderStatus,
)
from satquery.providers.ai.base import (
    AIInterpretationRequest,
    AIProviderNotConfiguredError,
    AIProviderUnavailableError,
)
from satquery.providers.ai.mock import MockAIProvider
from satquery.providers.ai.real_adapter import GeminiAIProviderAdapter
from satquery.providers.ai.registry import AIProviderRegistry, DisabledAIProvider


@pytest.fixture
def sample_evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id="evd-ndvi-01",
            type=EvidenceType.SPECTRAL_MEASUREMENT,
            title="NDVI Vegetation Index",
            description="Mean NDVI of 0.62 indicates dense healthy vegetation canopy.",
            source_scene_ids=["mock-scene-optical-01"],
            confidence=0.92,
            provenance=EvidenceProvenance(
                computation="NDVI Formula (B08 - B04)/(B08 + B04)",
                processed_at=datetime.now(UTC),
            ),
        ),
        EvidenceItem(
            id="evd-ndwi-01",
            type=EvidenceType.SPECTRAL_MEASUREMENT,
            title="NDWI Water Index",
            description="Mean NDWI of -0.21 confirms lack of surface water saturation.",
            source_scene_ids=["mock-scene-optical-01"],
            confidence=0.88,
            provenance=EvidenceProvenance(
                computation="NDWI Formula (B03 - B08)/(B03 + B08)",
                processed_at=datetime.now(UTC),
            ),
        ),
    ]


def test_mock_ai_provider_health_check() -> None:
    provider = MockAIProvider()
    info = asyncio.run(provider.health_check())

    assert info.provider_id == "mock"
    assert info.mode == ProviderMode.MOCK
    assert info.status == ProviderStatus.READY
    assert info.configured is True
    assert info.healthy is True
    assert info.data_origin == DataOrigin.MOCK


def test_mock_ai_provider_with_evidence(sample_evidence: list[EvidenceItem]) -> None:
    provider = MockAIProvider()
    req = AIInterpretationRequest(
        question="What is the vegetation health status in this area?",
        mode=AnalysisMode.SPECTRAL_ANALYSIS,
        evidence=sample_evidence,
    )
    res = asyncio.run(provider.generate_interpretation(req))

    assert "NDVI Vegetation Index" in res.answer
    assert "0.62" in res.answer
    assert len(res.evidence_ids) == 2
    assert "evd-ndvi-01" in res.evidence_ids
    assert "evd-ndwi-01" in res.evidence_ids
    assert len(res.findings) == 2
    assert res.findings[0].evidence_ids == ["evd-ndvi-01"]
    assert res.findings[1].evidence_ids == ["evd-ndwi-01"]
    assert res.confidence >= 0.85
    assert res.execution_metadata.data_origin == DataOrigin.MOCK
    assert res.execution_metadata.fallback_used is False


def test_mock_ai_provider_without_evidence_refuses_hallucination() -> None:
    provider = MockAIProvider()
    req = AIInterpretationRequest(
        question="Is there flooding in this area?",
        mode=AnalysisMode.VISUAL_QUESTION_ANSWERING,
        evidence=[],  # Empty evidence
    )
    res = asyncio.run(provider.generate_interpretation(req))

    assert "Unable to answer" in res.answer or "no quantitative evidence" in res.answer
    assert len(res.findings) == 0
    assert res.confidence <= 0.20
    assert len(res.warnings) >= 1
    assert any(w.code == WarningCode.INSUFFICIENT_EVIDENCE for w in res.warnings)


def test_gemini_ai_adapter_unconfigured() -> None:
    adapter = GeminiAIProviderAdapter(api_key=None)
    assert adapter.is_configured() is False
    info = asyncio.run(adapter.health_check())
    assert info.status == ProviderStatus.NOT_CONFIGURED
    assert info.configured is False

    req = AIInterpretationRequest(
        question="Analyze this area",
        mode=AnalysisMode.VISUAL_QUESTION_ANSWERING,
        evidence=[],
    )
    with pytest.raises(AIProviderNotConfiguredError):
        asyncio.run(adapter.generate_interpretation(req))


def test_ai_provider_registry_fallback(sample_evidence: list[EvidenceItem]) -> None:
    # Unconfigured Gemini primary provider with fallback enabled
    unconfigured_primary = GeminiAIProviderAdapter(api_key=None)
    registry = AIProviderRegistry(
        primary_provider=unconfigured_primary,
        mock_provider=MockAIProvider(),
        allow_fallback=True,
    )

    req = AIInterpretationRequest(
        question="Analyze crop vigor",
        mode=AnalysisMode.SPECTRAL_ANALYSIS,
        evidence=sample_evidence,
    )
    res = asyncio.run(registry.generate_interpretation(req))

    assert res.execution_metadata.data_origin == DataOrigin.FALLBACK
    assert res.execution_metadata.fallback_used is True
    assert "gemini" in (res.execution_metadata.fallback_reason or "").lower()
    assert len(res.warnings) >= 1
    assert any(w.code == WarningCode.MOCK_DATA_USED for w in res.warnings)


def test_disabled_ai_provider() -> None:
    disabled = DisabledAIProvider()
    info = asyncio.run(disabled.health_check())
    assert info.status == ProviderStatus.DISABLED

    req = AIInterpretationRequest(
        question="Analyze scene",
        mode=AnalysisMode.VISUAL_QUESTION_ANSWERING,
        evidence=[],
    )
    with pytest.raises(AIProviderUnavailableError):
        asyncio.run(disabled.generate_interpretation(req))
