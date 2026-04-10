import httpx
from httpx import RequestError
import logging
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from iot_hub_shared.auth_kit.middleware import login_required
# from iot_hub_shared.audit_kit import publish_audit_event

from apps.rules.serializers.rule_serializers import RuleCreateSerializer, RulePatchSerializer
from apps.rules.services.rule_service import rule_create, rule_put, rule_patch, rule_delete
from apps.rules.models.rule import Rule
# from apps.rules.audit.rules_audit import rule_created, rule_updated, rule_deleted, rule_evaluated
from apps.rules.services.rule_processor import RuleProcessor
from apps.rules.services.device_service_client import (
    get_user_device_metric_ids,
    check_device_metric_ownership,
    check_device_metric_exists,
)
from apps.rules.utils.json import parse_json_body
from apps.rules.services.telemetry_service_client import get_last_telemetries

logger = logging.getLogger("rules")


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name="dispatch")
class RuleView(View):
    @staticmethod
    def _serialize(rule) -> dict:
        return {
            "id": rule.id,
            "name": rule.name,
            "device_metric_id": rule.device_metric_id,
            "description": getattr(rule, "description", None),
            "condition": rule.condition,
            "action": rule.action,
            "is_active": rule.is_active,
        }

    def get(self, request, rule_id=None):
        user = request.user
        is_admin = user.role == "admin"

        if rule_id:
            try:
                rule = Rule.objects.get(id=rule_id)
            except Rule.DoesNotExist:
                return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)

            # permission check
            if not is_admin:
                try:
                    allowed_ids = get_user_device_metric_ids(user.id)
                except RequestError:
                    return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503)
                if rule.device_metric_id not in allowed_ids:
                    return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)

            return JsonResponse({"rule": self._serialize(rule)})

        else:
            # GET list
            try:
                limit = int(request.GET.get("limit", 20))
                offset = int(request.GET.get("offset", 0))
            except ValueError:
                return JsonResponse(
                    {"code": 400, "message": "Limit and offset must be integer type"}, status=400
                )

            if limit <= 0 or offset < 0:
                return JsonResponse(
                    {"code": 400, "message": "Limit must be > 0 and offset must be >= 0"},
                    status=400,
                )

            if is_admin:
                all_rules = Rule.objects.all()
            else:
                try:
                    allowed_ids = get_user_device_metric_ids(user.id)
                except RequestError:
                    return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503)    
                all_rules = Rule.objects.filter(device_metric_id__in=allowed_ids)

            total = all_rules.count()
            rules = all_rules[offset : offset + limit]
            return JsonResponse(
                {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "items": [self._serialize(r) for r in rules],
                }
            )

    def post(self, request):
        """Create a new rule"""
        data, error_response = parse_json_body(request.body)
        if error_response:
            return error_response

        user = request.user
        is_admin = user.role == "admin"

        serializer = RuleCreateSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse({"code": 400, "message": serializer.errors}, status=400)

        # check if user has that device_metrics and if that device_metric exists
        device_metric_id = serializer.validated_data.get("device_metric_id")
        try:
            if is_admin:
                if not check_device_metric_exists(device_metric_id):
                    return JsonResponse({"code": 404, "message": "DeviceMetric not found"}, status=404)
            else:
                if not check_device_metric_ownership(device_metric_id, user.id):
                    return JsonResponse({"code": 403, "message": "DeviceMetric does not belong to the user"}, status=403)
        except httpx.RequestError:
            return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503)        

        try:
            rule = rule_create(rule_data=serializer.validated_data)
        except IntegrityError as e:
            if "unique_rule_name_per_device_metric" in str(e):
                return JsonResponse(
                    {
                        "code": 400,
                        "message": "Rule with this name already exists for this device_metric",
                    },
                    status=400,
                )
            else:
                return JsonResponse(
                    {
                        "code": 400,
                        "message": str(e),
                    },
                    status=400,
                )
        except ValidationError as e:
            return JsonResponse(
                {
                    "code": 400,
                    "message": str(e),
                },
                status=400,
            )

        # publish_audit_event(event=rule_created(user.id, rule))
        data = {
            "id": rule.id,
            "name": rule.name,
            "device_metric_id": rule.device_metric_id,
            "description": rule.description,
            "condition": rule.condition,
            "action": rule.action,
            "is_active": rule.is_active,
        }
        return JsonResponse(data, status=201)

    def put(self, request, rule_id):
        """Full update"""
        data, error_response = parse_json_body(request.body)
        if error_response:
            return error_response

        user = request.user
        is_admin = user.role == "admin"

        try:
            rule_old = Rule.objects.get(id=rule_id)
            if not is_admin:
                try:
                    allowed_ids = get_user_device_metric_ids(user.id)
                except httpx.RequestError:
                    return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503)   
                if rule_old.device_metric_id not in allowed_ids:
                    return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)
        except Rule.DoesNotExist:
            return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)

        serializer = RuleCreateSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse({"code": 400, "message": serializer.errors}, status=400)

        new_device_metric_id = serializer.validated_data.get("device_metric_id")
        try:
            if is_admin:
                if not check_device_metric_exists(new_device_metric_id):
                    return JsonResponse({"code": 404, "message": "DeviceMetric not found"}, status=404)
            else:
                if not check_device_metric_ownership(new_device_metric_id, user.id):
                    return JsonResponse({"code": 403, "message": "DeviceMetric does not belong to the user"}, status=403)
        except httpx.RequestError:
            return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503) 

        try:
            rule_new = rule_put(rule_id=rule_id, rule_data=serializer.validated_data)
        except ValidationError as e:
            return JsonResponse(
                {
                    "code": 400,
                    "message": str(e),
                },
                status=400,
            )

        # publish_audit_event(event=rule_updated(user.id, rule_old, rule_new))
        data = {
            "id": rule_new.id,
            "name": rule_new.name,
            "device_metric_id": rule_new.device_metric_id,
            "description": rule_new.description,
            "condition": rule_new.condition,
            "action": rule_new.action,
            "is_active": rule_new.is_active,
        }
        return JsonResponse(data, status=200)

    def patch(self, request, rule_id):
        """Partial update"""
        data, error_response = parse_json_body(request.body)
        if error_response:
            return error_response

        user = request.user
        is_admin = user.role == "admin"

        try:
            rule_old = Rule.objects.get(id=rule_id)
            if not is_admin:
                try:
                    allowed_ids = get_user_device_metric_ids(user.id)
                except httpx.RequestError:
                    return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503)     
                if rule_old.device_metric_id not in allowed_ids:
                    return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)
        except Rule.DoesNotExist:
            return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)

        serializer = RulePatchSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse({"code": 400, "message": serializer.errors}, status=400)

        new_device_metric_id = serializer.validated_data.get("device_metric_id")
        try:
            if new_device_metric_id:
                if is_admin:
                    if not check_device_metric_exists(new_device_metric_id):
                        return JsonResponse({"code": 404, "message": "DeviceMetric not found"}, status=404)
                else:
                    if not check_device_metric_ownership(new_device_metric_id, user.id):
                        return JsonResponse({"code": 403, "message": "DeviceMetric does not belong to the user"}, status=403)
        except httpx.RequestError:
                    return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503) 
    
        try:
            rule_new = rule_patch(rule_id=rule_id, rule_data=serializer.validated_data)
        except ValidationError as e:
            return JsonResponse(
                {
                    "code": 400,
                    "message": str(e),
                },
                status=400,
            )

        # publish_audit_event(event=rule_updated(user.id, rule_old, rule_new))

        return JsonResponse({"status": 200, "rule_id": rule_new.id}, status=200)

    def delete(self, request, rule_id):
        """Delete rule"""
        user = request.user
        is_admin = user.role == "admin"

        try:
            rule = Rule.objects.get(id=rule_id)
            if not is_admin:
                try:
                    allowed_ids = get_user_device_metric_ids(user.id)
                except httpx.RequestError:
                    return JsonResponse({"code": 503, "message": "Device registry unavailable, try again later"}, status=503)     
                if rule.device_metric_id not in allowed_ids:
                    return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)
        except Rule.DoesNotExist:
            return JsonResponse({"code": 404, "message": "Rule not found"}, status=404)

        # publish_audit_event(event=rule_deleted(user.id, rule))
        rule_delete(rule_id=rule_id)

        return JsonResponse({}, status=204)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name="dispatch")
class RuleEvaluateView(View):
    def post(self, request):
        user = request.user
        data, error_response = parse_json_body(request.body)
        if error_response:
            return error_response

        device_id = data.get("device_id")
        device_metric_id = data.get("device_metric_id")
        is_admin = user.role == "admin"

        try:
            telemetries = get_last_telemetries(
                user_id=user.id,
                is_admin=is_admin,
                device_id=device_id,
                device_metric_id=device_metric_id,
            )
        except httpx.RequestError:
            return JsonResponse(
                {"code": 503, "message": "telemetry-service unavailable"}, status=503
            )

        results = []
        for telemetry in telemetries:
            evaluation_result = RuleProcessor.run(telemetry)
            results.append(
                {
                    "telemetry_id": telemetry["id"],
                    "device_metric_id": telemetry["device_metric_id"],
                    "result": evaluation_result,
                }
            )
            # if evaluation_result["triggered"]:
            #     publish_audit_event(
            #         event=rule_evaluated(
            #             rule_id=evaluation_result["rule_id"],
            #             details=evaluation_result["telemetry"],
            #         )
            #     )

        return JsonResponse({"status": 200, "results": results})
