"""Account lifecycle hooks: provisioning, signup bonus, session bookkeeping, audit trail."""

from __future__ import annotations

import time

from allauth.account.signals import (
    email_confirmed,
    password_changed,
    password_reset,
    user_logged_in,
    user_logged_out,
)
from allauth.mfa.signals import authenticator_added, authenticator_removed
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from sml.core import audit

from .middleware import AUTH_AT, LAST_SEEN, REMEMBER
from .models import AccessPolicy, RoleProfile, TrainingConsent, User


@receiver(post_save, sender=User)
def provision_user(sender, instance: User, created: bool, **kwargs) -> None:  # type: ignore[no-untyped-def]
    if not created:
        return
    AccessPolicy.objects.get_or_create(user=instance)
    TrainingConsent.objects.get_or_create(user=instance)
    from sml.credits.services import ensure_wallet

    ensure_wallet(instance)
    default_roles = Group.objects.filter(role_profile__is_default=True)
    if default_roles.exists() and not instance.groups.exists():
        instance.groups.add(*default_roles)


@receiver(email_confirmed)
def grant_signup_bonus(request, email_address, **kwargs) -> None:  # type: ignore[no-untyped-def]
    user = email_address.user
    if user is None or not email_address.primary:
        return
    from sml.credits.services import grant_signup_bonus as _grant

    transaction.on_commit(lambda: _grant(user))


@receiver(user_logged_in)
def on_login(request, user, **kwargs) -> None:  # type: ignore[no-untyped-def]
    now = int(time.time())
    request.session[AUTH_AT] = now
    request.session[LAST_SEEN] = now
    request.session[REMEMBER] = not request.session.get_expire_at_browser_close()
    audit.record("auth.login", request=request, actor=user, target=user)


@receiver(user_logged_out)
def on_logout(request, user, **kwargs) -> None:  # type: ignore[no-untyped-def]
    if user is not None:
        audit.record("auth.logout", request=request, actor=user, target=user)


@receiver(password_changed)
def on_password_changed(request, user, **kwargs) -> None:  # type: ignore[no-untyped-def]
    audit.record("auth.password_changed", request=request, actor=user, target=user)


@receiver(password_reset)
def on_password_reset(request, user, **kwargs) -> None:  # type: ignore[no-untyped-def]
    # Revoke every other session after a reset.
    from allauth.usersessions.models import UserSession

    for session in UserSession.objects.filter(user=user):
        if not request or session.session_key != request.session.session_key:
            session.end()
    audit.record("auth.password_reset", request=request, actor=user, target=user)


@receiver(authenticator_added)
def on_mfa_added(sender, request, user, authenticator, **kwargs) -> None:  # type: ignore[no-untyped-def]
    audit.record("auth.mfa_added", request=request, actor=user, target=user,
                 after={"type": authenticator.type})
    request.session.cycle_key()


@receiver(authenticator_removed)
def on_mfa_removed(sender, request, user, authenticator, **kwargs) -> None:  # type: ignore[no-untyped-def]
    audit.record("auth.mfa_removed", request=request, actor=user, target=user,
                 before={"type": authenticator.type})


def role_profile_for(group: Group) -> RoleProfile:
    profile, _ = RoleProfile.objects.get_or_create(group=group)
    return profile
