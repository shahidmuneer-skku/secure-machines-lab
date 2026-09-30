"""The Django data admin must not offer a password-only way in."""

from __future__ import annotations

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db

ADMIN = "/api/django-admin/"


@pytest.fixture
def superuser(make_user):  # type: ignore[no-untyped-def]
    return make_user(roles=("super_admin",), is_superuser=True)


def test_anonymous_visitors_are_sent_to_the_app_login(client_for):
    res = client_for().get(ADMIN, follow=True)
    final = res.redirect_chain[-1][0]
    assert final.startswith(f"{settings.PUBLIC_WEB_URL}/login?next=")
    assert "%2Fapi%2Fdjango-admin%2F" in final


def test_password_login_form_is_gone(client_for, superuser):
    from conftest import PASSWORD

    client = client_for()
    res = client.post(f"{ADMIN}login/", {"username": superuser.email, "password": PASSWORD})
    assert res.status_code == 302 and res["Location"].startswith(settings.PUBLIC_WEB_URL)
    assert "_auth_user_id" not in client.session
    assert client.get(ADMIN).status_code == 302


def test_superuser_without_second_factor_is_refused(client_for, superuser):
    client = client_for(superuser)
    assert client.get(ADMIN).status_code == 302
    assert client.get(f"{ADMIN}login/").status_code == 403


def test_staff_who_are_not_superusers_are_refused(client_for, make_user):
    admin = make_user(roles=("admin",))
    assert client_for(admin, mfa=True).get(f"{ADMIN}login/").status_code == 403


def test_superuser_with_verified_session_gets_in(client_for, superuser):
    client = client_for(superuser, mfa=True)
    assert client.get(ADMIN).status_code == 200
    assert client.get(f"{ADMIN}login/?next=https://evil.example/").headers["Location"] == ADMIN
