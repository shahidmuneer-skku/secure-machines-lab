from celery import shared_task


@shared_task(name="sml.maintenance.renew_subscriptions", ignore_result=True)
def renew_subscriptions() -> int:
    from .services import renew_due_subscriptions

    return renew_due_subscriptions()
