"""Creates the first super_admin from SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD.

The account must enroll MFA before any admin endpoint works (StaffMfaVerified).
"""

import os

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from sml.accounts.models import User
from sml.accounts.rbac import sync_staff_flag


class Command(BaseCommand):
    help = "Create the initial super_admin account from environment variables"

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        email = os.environ.get("SUPERADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("SUPERADMIN_PASSWORD", "")
        if not email or not password:
            raise CommandError("Set SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD")
        if len(password) < 12:
            raise CommandError("SUPERADMIN_PASSWORD must be at least 12 characters")
        user, created = User.objects.get_or_create(email=email)
        if created:
            user.set_password(password)
            user.save()
        EmailAddress.objects.update_or_create(
            user=user, email=email, defaults={"verified": True, "primary": True}
        )
        try:
            user.groups.add(Group.objects.get(name="super_admin"))
        except Group.DoesNotExist as exc:
            raise CommandError("Run `manage.py seed_rbac` first") from exc
        sync_staff_flag(user)
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} super_admin {email}. Enroll MFA at first login."))
