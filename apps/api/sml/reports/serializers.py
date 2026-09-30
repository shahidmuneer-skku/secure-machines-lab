from rest_framework import serializers

from sml.accounts.models import User

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    job_title = serializers.CharField(source="job.title", read_only=True)
    filename = serializers.CharField(read_only=True)

    class Meta:
        model = Report
        fields = ["id", "job", "job_title", "format", "locale", "status", "run_number", "version", "size_bytes",
                  "error_message", "created_at", "filename", "download_url"]

    def get_download_url(self, obj: Report) -> str | None:
        return f"/api/v1/reports/{obj.pk}/download" if obj.status == Report.Status.READY else None


class ReportRequestSerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=Report.Format.choices)
    locale = serializers.ChoiceField(choices=User.Locale.choices, required=False)
