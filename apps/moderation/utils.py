from django.utils import timezone

from .models import Ban


def is_user_banned(user, community):
    if not user.is_authenticated:
        return False
    ban = Ban.objects.filter(community=community, user=user).first()
    if not ban:
        return False
    if ban.is_permanent:
        return True
    if ban.expires_at and ban.expires_at > timezone.now():
        return True
    ban.delete()
    return False
