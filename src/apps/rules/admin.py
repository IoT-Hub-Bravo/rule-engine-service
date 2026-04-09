import json
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from .models import Rule
from .validators.rule_validator import validate_action, validate_condition


class RuleAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_superuser:
            self.fields["device_metric_id"].queryset = self.fields[
                "device_metric_id"
            ].queryset.filter(device__user=self.user)

    class Meta:
        model = Rule
        fields = "__all__"
        help_texts = {
            "name": "A short, unique name for this rule (e.g. 'CPU Overheat Alert').",
            "description": "Optional. Describe what this rule monitors and why.",
            "device_metric_id": "The specific device+metric pair this rule applies to.",
            "is_active": "Inactive rules are stored but never evaluated.",
            "condition": "Expression or criteria that trigger this rule.",
            "action": "What happens when this rule triggers.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "condition": forms.Textarea(attrs={"rows": 5}),
            "action": forms.Textarea(attrs={"rows": 5}),
        }

    def clean(self):
        cleaned = super().clean()

        device_metric_id = cleaned.get("device_metric_id")
        is_active = cleaned.get("is_active")
        if is_active and device_metric_id is None:
            raise ValidationError("Cannot activate a rule without a device metric assigned.")
        return cleaned

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Rule name cannot be blank or whitespace only.")

        device_metric_id = self.cleaned_data.get("device_metric_id")
        if device_metric_id:
            qs = Rule.objects.filter(name__iexact=name, device_metric_id=device_metric_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    f'A rule named "{name}" already exists for this device metric.'
                )

        return name

    def clean_condition(self):
        raw = self.cleaned_data.get("condition")
        validate_condition(raw)
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def clean_action(self):
        raw = self.cleaned_data.get("action")
        validate_action(raw)
        if isinstance(raw, str):
            return json.loads(raw)
        return raw


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    form = RuleAdminForm

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)

        class FormWithUser(Form):
            def __init__(self_inner, *args, **inner_kwargs):
                inner_kwargs.setdefault("user", request.user)
                Form.__init__(self_inner, *args, **inner_kwargs)

        return FormWithUser

    list_display = (
        "id",
        "name",
        "device_metric_id",
        "rule_status",
        "condition",
        "action",
    )
    list_filter = ("is_active", "device_metric_id")
    search_fields = (
        "name",
        "description",
        "device_metric_id__device__name",
        "device_metric_id__metric__metric_type",
    )
    search_help_text = "Search by rule name, description, device name, or metric type."
    ordering = ("-id",)
    list_per_page = 25

    readonly_fields = ("id",)
    save_on_top = True  # save buttons at top and bottom of form

    fieldsets = (
        (
            "Identity",
            {"fields": ("id", "name", "description")},
        ),
        (
            "Configuration",
            {
                "fields": ("device_metric_id", "condition", "action"),
                "description": "Link this rule to a device metric and define its condition and action.",
            },
        ),
        (
            "Status",
            {
                "fields": ("is_active",),
                "classes": ("collapse",),
                "description": "Runtime state of this rule. 'Last triggered' is read-only.",
            },
        ),
    )

    def has_add_permission(self, request):
        return request.user.is_staff or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.is_staff

        return request.user.is_staff and obj.device_metric_id.device.user == request.user

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.is_staff

        return request.user.is_staff and obj.device_metric_id.device.user == request.user

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.is_staff

        return request.user.is_staff and obj.device_metric_id.device.user == request.user

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        return qs.filter(device_metric_id__device__user=request.user)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = "updated" if change else "created"
        status = "active" if obj.is_active else "inactive"
        self.message_user(
            request,
            f'Rule "{obj.name}" was {action} and is currently {status}.',
            messages.SUCCESS,
        )

    def delete_model(self, request, obj):
        name = obj.name
        super().delete_model(request, obj)
        self.message_user(
            request,
            f'Rule "{name}" and all its associated events have been deleted.',
            messages.WARNING,
        )

    @admin.display(description="Active", boolean=True, ordering="is_active")
    def rule_status(self, obj):
        return obj.is_active

    # @admin.display(description="Last Triggered")
    # def last_triggered_display(self, obj):
    #     from django.db.models import Max

    #     latest = Event.objects.filter(rule=obj.id).aggregate(Max("rule_triggered_at"))[
    #         "rule_triggered_at__max"
    #     ]
    #     if latest:
    #         local = localtime(latest)
    #         return format_html(
    #             '<span title="{}">{}</span>',
    #             local.isoformat(),
    #             local.strftime("%Y-%m-%d %H:%M"),
    #         )
    #     return format_html('<span style="color: gray;">Never</span>')
