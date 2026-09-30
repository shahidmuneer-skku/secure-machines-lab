from django.core.management.base import BaseCommand

from sml.accounts.rbac import seed_roles


class Command(BaseCommand):
    help = "Create/update roles and their capabilities from config/roles.yaml"

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        names = seed_roles()
        self.stdout.write(self.style.SUCCESS(f"Seeded roles: {', '.join(names)}"))
