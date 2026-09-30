from celery import shared_task


@shared_task(name="sml.reports.generate", ignore_result=True, acks_late=True)
def generate_report(report_id: str) -> None:
    from .models import Report
    from .services import generate

    report = Report.objects.select_related("job", "job__media").filter(pk=report_id).first()
    if report is not None and report.status in (Report.Status.QUEUED, Report.Status.RUNNING):
        generate(report)
