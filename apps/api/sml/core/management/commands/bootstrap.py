"""Idempotent first-run setup: roles, platform settings, prices, packs and plans.

Existing rows are never overwritten, so admin edits survive re-runs.
Seed values are the owner-approved defaults (2026-09-30); see PLAN.md.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from sml.billing.models import CreditPack, Plan
from sml.core.models import PlatformSettings
from sml.credits.models import PriceRule

PACKS = [
    {"slug": "starter", "name": {"en": "Starter", "ko": "스타터", "de": "Starter"}, "credits": 100,
     "price_krw": 15_000, "price_usd_cents": 1_200, "sort_order": 1},
    {"slug": "standard", "name": {"en": "Standard", "ko": "스탠다드", "de": "Standard"}, "credits": 500,
     "price_krw": 59_000, "price_usd_cents": 4_500, "sort_order": 2, "highlight": True},
    {"slug": "pro", "name": {"en": "Pro", "ko": "프로", "de": "Pro"}, "credits": 2_000,
     "price_krw": 199_000, "price_usd_cents": 15_000, "sort_order": 3},
]

PLANS = [
    {"slug": "basic", "name": {"en": "Basic", "ko": "베이직", "de": "Basic"}, "monthly_credits": 300,
     "price_krw": 35_000, "price_usd_cents": 2_700, "priority": 0, "retention_days": 14, "api_access": False,
     "max_inflight_tasks": 6, "sort_order": 1,
     "description": {"en": "For individuals checking media regularly.",
                     "ko": "미디어를 정기적으로 확인하는 개인용.",
                     "de": "Für Einzelpersonen, die regelmäßig Medien prüfen."},
     "features": {"en": ["300 credits every month", "Normal queue", "14-day retention", "PDF / HWP / CSV reports"],
                  "ko": ["매월 300 크레딧", "일반 대기열", "14일 보관", "PDF / HWP / CSV 보고서"],
                  "de": ["300 Credits pro Monat", "Normale Warteschlange", "14 Tage Aufbewahrung",
                         "PDF- / HWP- / CSV-Berichte"]}},
    {"slug": "pro", "name": {"en": "Pro", "ko": "프로", "de": "Pro"}, "monthly_credits": 1_000,
     "price_krw": 99_000, "price_usd_cents": 7_500, "priority": 1, "retention_days": 30, "api_access": True,
     "max_inflight_tasks": 12, "sort_order": 2, "highlight": True,
     "description": {"en": "For analysts and newsrooms.", "ko": "분석가와 뉴스룸을 위한 플랜.",
                     "de": "Für Analysten und Redaktionen."},
     "features": {"en": ["1,000 credits every month", "Priority queue", "30-day retention", "API access"],
                  "ko": ["매월 1,000 크레딧", "우선 대기열", "30일 보관", "API 이용"],
                  "de": ["1.000 Credits pro Monat", "Priorisierte Warteschlange", "30 Tage Aufbewahrung",
                         "API-Zugang"]}},
    {"slug": "business", "name": {"en": "Business", "ko": "비즈니스", "de": "Business"}, "monthly_credits": 5_000,
     "price_krw": 399_000, "price_usd_cents": 29_900, "priority": 2, "retention_days": 90, "api_access": True,
     "max_inflight_tasks": 32, "sort_order": 3,
     "description": {"en": "For teams and platforms at scale.", "ko": "대규모 팀과 플랫폼을 위한 플랜.",
                     "de": "Für Teams und Plattformen im großen Maßstab."},
     "features": {"en": ["5,000 credits every month", "Highest queue priority", "90-day retention", "API access"],
                  "ko": ["매월 5,000 크레딧", "최우선 대기열", "90일 보관", "API 이용"],
                  "de": ["5.000 Credits pro Monat", "Höchste Priorität", "90 Tage Aufbewahrung", "API-Zugang"]}},
]


class Command(BaseCommand):
    help = "Seed roles, platform settings, credit prices, packs and plans (idempotent)"

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument("--superadmin", action="store_true", help="Also create SUPERADMIN_EMAIL")

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        call_command("seed_rbac")
        PlatformSettings.objects.get_or_create(pk=1)
        created = 0
        for key, credits in PriceRule.DEFAULTS.items():
            _, was_created = PriceRule.objects.get_or_create(key=key, defaults={"credits": credits})
            created += was_created
        for spec in PACKS:
            CreditPack.objects.get_or_create(slug=spec["slug"], defaults=spec)
        for spec in PLANS:
            Plan.objects.get_or_create(slug=spec["slug"], defaults=spec)
        if options["superadmin"]:
            call_command("create_superadmin")
        self.stdout.write(self.style.SUCCESS(
            f"Bootstrap complete ({created} new price rules, {CreditPack.objects.count()} packs, "
            f"{Plan.objects.count()} plans)"))
