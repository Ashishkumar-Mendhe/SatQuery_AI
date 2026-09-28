"""Deterministic 10B meaning-to-tool plans; never dispatches protected tools."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal

from satquery.api.schemas.geoagent import (
    Dependency,
    GeoAgentDependencyFinding,
    GeoAgentMessageRequest,
    GeoAgentMessageResponse,
    GeoIntent,
    GeoTool,
    MissingInput,
    SelectedGeoScene,
)
from satquery.api.schemas.viewer import ViewerSceneIdentity

type Availability = Literal["available", "unavailable", "unknown"]


def _has(message: str, pattern: str) -> bool:
    return re.search(pattern, message, re.IGNORECASE) is not None


def _classify(message: str, scenes: list[SelectedGeoScene]) -> tuple[GeoIntent | None, str | None]:
    optical = sum(scene.modality == "optical" for scene in scenes)
    sar = sum(scene.modality == "sar" for scene in scenes)
    map_action: str | None = None
    if _has(message, r"\b(draw|create|outline|sketch)\b.*\b(aoi|area of interest)\b"):
        map_action = "draw_aoi"
    elif _has(message, r"\b(zoom|fly|pan|focus)\b.*\b(aoi|area of interest)\b"):
        map_action = "zoom_to_aoi"
    elif _has(message, r"\b(clear|remove|delete)\b.*\b(aoi|area of interest)\b"):
        map_action = "clear_aoi"

    change = _has(
        message, r"\b(change|changed|changes|difference|different|before|after)\b|\bover time\b"
    )
    optical_term = _has(message, r"\b(optical|sentinel[- ]?2)\b")
    sar_term = _has(message, r"\b(sar|radar|sentinel[- ]?1)\b")
    cross_sensor = optical_term and sar_term
    cross_sensor = cross_sensor or (
        _has(message, r"\b(compare|combine|together|both)\b") and optical > 0 and sar > 0
    )
    locate = _has(message, r"\b(where|locate|locali[sz]e|find|highlight|point out)\b")
    caption = _has(message, r"\b(caption|describe|description)\b")
    imagery_view = _has(message, r"\b(show|display|view|open)\b.*\b(image|imagery|scene|raster)\b")
    comparison = _has(message, r"\b(compare|comparison)\b")
    question = (
        _has(message, r"\b(what|which|is|are|does|do|can you see|identify|tell me)\b")
        or "?" in message
    )

    if map_action:
        return "map_aoi_action", map_action
    if _has(message, r"\b(how many|count|confidence|accuracy|cause|caused|new buildings)\b"):
        return None, "unsupported_measurement_or_cause"
    if _has(message, r"\b(area|percent|percentage|square met(?:re|er))\b") and not change:
        return None, "unsupported_measurement_or_cause"
    if cross_sensor and locate:
        return None, "cross_sensor_grounding"
    if change and cross_sensor:
        return None, "cross_sensor_change"
    if change:
        return "before_after_change", None
    if cross_sensor:
        return "optical_sar_observation", None
    if comparison:
        if optical == 2 and sar == 0:
            return "before_after_change", None
        if optical == 1 and sar == 1:
            return "optical_sar_observation", None
        return None, "ambiguous_comparison"
    if locate:
        return "spatial_grounding", None
    if caption:
        return "image_caption", None
    if imagery_view:
        return "imagery_view", None
    if question:
        return "single_image_question", None
    return None, "ambiguous_intent"


_TOOLS: dict[GeoIntent, GeoTool] = {
    "imagery_view": "imagery_tiles",
    "single_image_question": "inference_vqa",
    "image_caption": "inference_caption",
    "spatial_grounding": "inference_grounding",
    "before_after_change": "optical_change",
    "optical_sar_observation": "optical_sar_observation",
    "map_aoi_action": "map_aoi_control",
}

_DEPENDENCIES: dict[GeoIntent, tuple[Dependency, ...]] = {
    "imagery_view": ("provider_rasters",),
    "single_image_question": ("inference_model", "protected_jobs", "provider_rasters"),
    "image_caption": ("inference_model", "protected_jobs", "provider_rasters"),
    "spatial_grounding": ("grounding_model", "protected_jobs", "provider_rasters"),
    "before_after_change": ("protected_jobs", "provider_rasters"),
    "optical_sar_observation": ("protected_jobs", "provider_rasters", "cross_modal_alignment"),
    "map_aoi_action": ("map_control",),
}


def route_message(
    request: GeoAgentMessageRequest,
    *,
    availability: Mapping[Dependency, Availability] | None = None,
) -> GeoAgentMessageResponse:
    """Plan a supported intent. Availability is trusted host evidence, never client text."""

    message = request.message.strip()
    unsupported_scenes = [
        scene
        for scene in request.selected_scenes
        if (
            scene.modality == "optical"
            and (scene.source.provider, scene.source.collection)
            != ("earth-search", "sentinel-2-c1-l2a")
        )
        or (
            scene.modality == "sar"
            and (scene.source.provider, scene.source.collection) != ("inpe-bdc", "sentinel-1-rtc-1")
        )
    ]
    if unsupported_scenes:
        return GeoAgentMessageResponse(
            request_id=request.request_id,
            conversation_id=request.conversation_id,
            status="unsupported",
            intended_analysis=None,
            selected_aoi=request.selected_aoi,
            selected_scenes=request.selected_scenes,
            answer=(
                "The selected scene product is not supported by the current conversational "
                "analysis tools. Select Earth Search Sentinel-2 L2A, or INPE Sentinel-1 RTC "
                "for a separate-source optical/SAR observation. No analysis ran."
            ),
        )
    if _has(
        message, r"\b(ignore|disregard|override|bypass)\b.{0,80}\b(instructions|policy|rules)\b"
    ) or _has(
        message,
        r"\b(fabricate|invent|make up)\b.{0,60}\b(answer|result|evidence|measurement)\b",
    ):
        return GeoAgentMessageResponse(
            request_id=request.request_id,
            conversation_id=request.conversation_id,
            status="unsupported",
            intended_analysis=None,
            selected_aoi=request.selected_aoi,
            selected_scenes=request.selected_scenes,
            answer=(
                "A request to override analysis rules or fabricate evidence is unsupported. "
                "No tool ran."
            ),
        )
    intent, detail = _classify(message, request.selected_scenes)
    optical = sorted(
        (scene for scene in request.selected_scenes if scene.modality == "optical"),
        key=lambda scene: scene.acquired_at.isoformat() if scene.acquired_at else "",
    )
    sar = [scene for scene in request.selected_scenes if scene.modality == "sar"]
    missing: list[MissingInput] = []
    ordered: list[ViewerSceneIdentity] = []
    if intent is None:
        if detail == "unsupported_measurement_or_cause":
            return GeoAgentMessageResponse(
                request_id=request.request_id,
                conversation_id=request.conversation_id,
                status="unsupported",
                intended_analysis=None,
                selected_aoi=request.selected_aoi,
                selected_scenes=request.selected_scenes,
                answer=(
                    "This request needs a validated measurement or cause classifier that the "
                    "selected workflow does not provide. No analysis ran."
                ),
            )
        missing = ["clarify_intent"]
        if detail == "cross_sensor_change":
            answer = (
                "Optical/SAR spectral change is not supported. Choose two dated optical scenes "
                "for change, or ask for separate optical and SAR observations."
            )
        elif detail == "cross_sensor_grounding":
            answer = (
                "Cross-sensor feature grounding is not supported. Select one optical image "
                "and name the feature to locate."
            )
        else:
            answer = (
                "Do you want to inspect one image, locate a feature, compare two optical dates, "
                "or summarize optical and SAR observations?"
            )
        return _response(
            request, None, None, None, "clarification_required", missing, [], ordered, answer
        )

    if intent == "map_aoi_action":
        if detail != "draw_aoi" and request.selected_aoi is None:
            missing.append("aoi")
    else:
        if request.selected_aoi is None and intent != "imagery_view":
            missing.append("aoi")
        if intent in {
            "imagery_view",
            "single_image_question",
            "image_caption",
            "spatial_grounding",
        }:
            if len(optical) != 1:
                missing.append("optical_scene" if not optical else "clarify_intent")
            else:
                ordered = [optical[0].source]
            if sar:
                missing.append("clarify_intent")
        elif intent == "before_after_change":
            if not optical:
                missing.append("optical_scene")
            elif len(optical) == 1:
                missing.append("second_optical_scene")
            elif optical[0].acquired_at is None or optical[1].acquired_at is None:
                missing.append("acquisition_time")
            elif optical[0].acquired_at == optical[1].acquired_at:
                missing.append("clarify_intent")
            else:
                ordered = [scene.source for scene in optical]
            if sar:
                missing.append("clarify_intent")
        elif intent == "optical_sar_observation":
            if len(optical) != 1:
                missing.append("optical_scene" if not optical else "clarify_intent")
            if len(sar) != 1:
                missing.append("sar_scene")
            if len(sar) == 1 and sar[0].polarization is None:
                missing.append("sar_polarization")
            if len(optical) == 1 and len(sar) == 1:
                ordered = [optical[0].source, sar[0].source]
        if intent == "spatial_grounding" and _has(
            message, r"\b(where|find|locate)\s+(is|are)?\s*(it|this|that|there)\??$"
        ):
            missing.append("feature_to_locate")

    if missing:
        unique_missing = list(dict.fromkeys(missing))
        labels = {
            "aoi": "an AOI",
            "optical_scene": "one selected Sentinel-2 image",
            "second_optical_scene": "a second dated Sentinel-2 image",
            "sar_scene": "one selected Sentinel-1 RTC image",
            "sar_polarization": "an available SAR polarization",
            "acquisition_time": "both acquisition times",
            "feature_to_locate": "the feature to locate",
            "clarify_intent": "a more specific request or scene selection",
        }
        answer = "Please provide " + ", ".join(labels[item] for item in unique_missing) + "."
        return _response(
            request,
            intent,
            _TOOLS[intent],
            detail,
            "clarification_required",
            unique_missing,
            [],
            ordered,
            answer,
        )

    dependencies = [
        GeoAgentDependencyFinding(
            dependency=name,
            state=(availability or {}).get(name, "unknown"),
            reason=(
                "Runtime availability was not checked by the Phase 10B router."
                if (availability or {}).get(name, "unknown") == "unknown"
                else "The trusted runtime reports this dependency unavailable."
                if (availability or {}).get(name) == "unavailable"
                else None
            ),
        )
        for name in _DEPENDENCIES[intent]
    ]
    if intent == "map_aoi_action":
        dependencies = [
            GeoAgentDependencyFinding(
                dependency="map_control",
                state="unavailable",
                reason=(
                    "GeoAgent map actions are recognized but not connected to workspace "
                    "controls in 10A+B."
                ),
            )
        ]
    unavailable = [finding for finding in dependencies if finding.state == "unavailable"]
    if unavailable:
        answer = (
            "I understood the request, but "
            + ", ".join(finding.dependency.replace("_", " ") for finding in unavailable)
            + " is unavailable. No analysis or map action ran."
        )
        status: Literal["plan_ready", "unavailable"] = "unavailable"
    else:
        answer = (
            "Request understood; no analysis has run. Runtime and source quality "
            "must be checked before any result."
        )
        status = "plan_ready"
    return _response(
        request, intent, _TOOLS[intent], detail, status, [], dependencies, ordered, answer
    )


def _response(
    request: GeoAgentMessageRequest,
    intent: GeoIntent | None,
    tool: GeoTool | None,
    detail: str | None,
    status: Literal["plan_ready", "clarification_required", "unavailable"],
    missing: list[MissingInput],
    dependencies: list[GeoAgentDependencyFinding],
    ordered: list[ViewerSceneIdentity],
    answer: str,
) -> GeoAgentMessageResponse:
    map_action: Literal["draw_aoi", "zoom_to_aoi", "clear_aoi"] | None = None
    if intent == "map_aoi_action" and detail in {"draw_aoi", "zoom_to_aoi", "clear_aoi"}:
        map_action = detail  # type: ignore[assignment]
    return GeoAgentMessageResponse(
        request_id=request.request_id,
        conversation_id=request.conversation_id,
        status=status,
        intended_analysis=intent,
        selected_aoi=request.selected_aoi,
        selected_scenes=request.selected_scenes,
        ordered_source_scenes=ordered,
        proposed_tool=tool,
        map_action=map_action,
        missing_inputs=missing,
        dependencies=dependencies,
        answer=answer,
    )
