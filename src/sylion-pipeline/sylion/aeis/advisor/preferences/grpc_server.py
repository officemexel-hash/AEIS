"""gRPC wrapper for the advisor preferences service."""

from __future__ import annotations

from datetime import timezone

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.timestamp_pb2 import Timestamp

from sylion.aeis.advisor.preferences._models import ResolutionLevel
from sylion.aeis.advisor.preferences.service import get_preferences_service

from sylion.aeis.advisor._generated import preferences_pb2, preferences_pb2_grpc


class PreferencesServicer(preferences_pb2_grpc.PreferencesServiceServicer):
    """Generated gRPC surface backed by the sync service."""

    def __init__(self, service=None) -> None:
        self._service = service or get_preferences_service()

    def GetEffective(self, request, context):
        return _preference_message(
            self._service.get_effective(
                user_id=request.user_id,
                project_type=request.project_type or None,
                project_domain=request.project_domain or None,
                preference_key=request.preference_key,
            ),
            user_id=request.user_id,
            preference_key=request.preference_key,
        )

    def GetExplicit(self, request, context):
        row = self._service.get_explicit(
            user_id=request.user_id,
            project_type=request.project_type or None,
            project_domain=request.project_domain or None,
            preference_key=request.preference_key,
        )
        if row is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("preference_not_found")
            return preferences_pb2.PreferenceValue()
        return _explicit_message(row)

    def Set(self, request, context):
        result = self._service.set_preference(
            user_id=request.user_id,
            project_type=request.project_type or None,
            project_domain=request.project_domain or None,
            preference_key=request.preference_key,
            value=_proto_value_to_python(request.value_json),
            set_by=request.set_by or "user",
            reason=request.reason or None,
        )
        return preferences_pb2.SetResponse(**result)

    def Reset(self, request, context):
        success = self._service.reset_preference(
            user_id=request.user_id,
            project_type=request.project_type or None,
            project_domain=request.project_domain or None,
            preference_key=request.preference_key,
            reason=request.reason or None,
        )
        return preferences_pb2.ResetResponse(
            success=success,
            error_message="" if success else "preference_not_found",
        )

    def Disable(self, request, context):
        levels_cleared = self._service.disable_preference(
            user_id=request.user_id,
            preference_key=request.preference_key,
            reason=request.reason or None,
        )
        return preferences_pb2.DisableResponse(success=True, levels_cleared=levels_cleared)

    def List(self, request, context):
        rows = self._service.list_preferences(
            user_id=request.user_id,
            project_type=request.filter_project_type or None,
            project_domain=request.filter_project_domain or None,
            preference_key=request.filter_preference_key or None,
        )
        return preferences_pb2.ListResponse(
            preferences=[_explicit_message(row) for row in rows]
        )

    def GetAudit(self, request, context):
        since = request.since.ToDatetime().astimezone(timezone.utc) if request.HasField("since") else None
        rows = self._service.get_audit(
            user_id=request.user_id,
            since=since,
            limit=request.limit or 100,
            preference_key=request.filter_preference_key or None,
        )
        response = preferences_pb2.GetAuditResponse()
        for row in rows:
            entry = response.entries.add()
            entry.audit_id = row.audit_id
            entry.user_id = row.user_id
            entry.project_type = row.project_type or ""
            entry.project_domain = row.project_domain or ""
            entry.preference_key = row.preference_key
            ParseDict(_wrap_json_value(row.old_value), entry.old_value)
            ParseDict(_wrap_json_value(row.new_value), entry.new_value)
            entry.change_type = row.change_type
            entry.changed_by = row.changed_by
            entry.changed_at.FromDatetime(row.changed_at.astimezone(timezone.utc))
            entry.reason = row.reason or ""
        return response

    def SoftLearningTick(self, request, context):
        result = self._service.soft_learning_tick(user_id=request.user_id)
        response = preferences_pb2.SoftLearningTickResponse()
        response.applied_count = result["applied_count"]
        response.pending_hard_confirmations = result["pending_hard_confirmations"]
        response.applied_preference_keys.extend(result["applied_preference_keys"])
        return response

    def RequestHardChange(self, request, context):
        hard_change = self._service.request_hard_change(
            user_id=request.user_id,
            project_type=request.project_type or None,
            project_domain=request.project_domain or None,
            preference_key=request.preference_key,
            proposed_value=_proto_value_to_python(request.proposed_value),
            source_card_id=request.source_card_id or None,
            rationale=request.rationale or None,
        )
        response = preferences_pb2.RequestHardChangeResponse(request_id=hard_change.request_id)
        response.expires_at.FromDatetime(hard_change.expires_at)
        return response

    def ConfirmHardChange(self, request, context):
        success, hard_change, error = self._service.confirm_hard_change(
            request_id=request.request_id,
            operator_signature=request.operator_signature,
            confirmed=request.confirmed,
        )
        response = preferences_pb2.ConfirmHardChangeResponse(
            success=success,
            error_message=error or "",
        )
        if success and request.confirmed and hard_change is not None:
            applied = _preference_message(
                self._service.get_effective(
                    user_id=hard_change.user_id,
                    project_type=hard_change.project_type,
                    project_domain=hard_change.project_domain,
                    preference_key=hard_change.preference_key,
                ),
                user_id=hard_change.user_id,
                preference_key=hard_change.preference_key,
            )
            response.applied_value.CopyFrom(applied)
        return response

    def GetCatalog(self, request, context):
        catalog_type = _catalog_type_to_str(request.catalog_type)
        rows = self._service.get_catalog(catalog_type, include_custom=request.include_custom)
        response = preferences_pb2.GetCatalogResponse()
        for row in rows:
            item = response.entries.add()
            item.entry_id = row.entry_id
            item.display_name = row.display_name
            item.description = row.description or ""
            item.is_system = row.is_system
            item.is_immutable = row.is_immutable
            item.metadata_json.update(row.metadata)
        return response

    def AddCustomCatalogEntry(self, request, context):
        catalog_type = _catalog_type_to_str(request.catalog_type)
        entry = self._service.add_custom_catalog_entry(
            catalog_type=catalog_type,
            entry_id=request.entry_id,
            display_name=request.display_name,
            description=request.description,
            created_by=request.created_by,
        )
        response = preferences_pb2.AddCustomCatalogEntryResponse(
            success=entry is not None,
            error_message="" if entry is not None else "invalid_catalog_entry",
        )
        if entry is not None:
            response.entry.entry_id = entry.entry_id
            response.entry.display_name = entry.display_name
            response.entry.description = entry.description or ""
            response.entry.is_system = entry.is_system
            response.entry.is_immutable = entry.is_immutable
            response.entry.metadata_json.update(entry.metadata)
        return response


def register_preferences_service(server, service=None) -> bool:
    """Register the preferences servicer on a gRPC server."""
    preferences_pb2_grpc.add_PreferencesServiceServicer_to_server(
        PreferencesServicer(service), server
    )
    return True


def _preference_message(resolved, *, user_id: str, preference_key: str):
    msg = preferences_pb2.PreferenceValue(
        user_id=user_id,
        preference_key=preference_key,
        resolution_level=_resolution_level_to_proto(resolved.resolution_level),
    )
    ParseDict(_wrap_json_value(resolved.value), msg.value_json)
    if resolved.source_row is not None:
        msg.project_type = resolved.source_row.project_type or ""
        msg.project_domain = resolved.source_row.project_domain or ""
        msg.set_by = resolved.source_row.set_by
        msg.created_at.FromDatetime(resolved.source_row.created_at.astimezone(timezone.utc))
        msg.updated_at.FromDatetime(resolved.source_row.updated_at.astimezone(timezone.utc))
    return msg


def _explicit_message(row):
    msg = preferences_pb2.PreferenceValue(
        user_id=row.user_id,
        project_type=row.project_type or "",
        project_domain=row.project_domain or "",
        preference_key=row.preference_key,
        set_by=row.set_by,
        resolution_level=preferences_pb2.RESOLUTION_LEVEL_UNSPECIFIED,
    )
    ParseDict(_wrap_json_value(row.preference_value), msg.value_json)
    msg.created_at.FromDatetime(row.created_at.astimezone(timezone.utc))
    msg.updated_at.FromDatetime(row.updated_at.astimezone(timezone.utc))
    return msg


def _resolution_level_to_proto(level: ResolutionLevel) -> int:
    return {
        ResolutionLevel.SPECIFIC: preferences_pb2.RESOLUTION_LEVEL_SPECIFIC,
        ResolutionLevel.TYPE_ONLY: preferences_pb2.RESOLUTION_LEVEL_TYPE_ONLY,
        ResolutionLevel.DOMAIN_ONLY: preferences_pb2.RESOLUTION_LEVEL_DOMAIN_ONLY,
        ResolutionLevel.USER_DEFAULT: preferences_pb2.RESOLUTION_LEVEL_USER_DEFAULT,
        ResolutionLevel.SYSTEM_DEFAULT: preferences_pb2.RESOLUTION_LEVEL_SYSTEM_DEFAULT,
    }[level]


def _proto_value_to_python(message) -> Any:
    payload = MessageToDict(message)
    return payload.get("value")


def _wrap_json_value(value: Any) -> dict[str, Any]:
    return {"value": value}


def _catalog_type_to_str(value: int) -> str:
    mapping = {
        preferences_pb2.CATALOG_TYPE_PROJECT_DOMAIN: "project_domain",
        preferences_pb2.CATALOG_TYPE_PROJECT_TYPE: "project_type",
        preferences_pb2.CATALOG_TYPE_PREFERENCE_KEY: "preference_key",
    }
    return mapping.get(value, "project_domain")
