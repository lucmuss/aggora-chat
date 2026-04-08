import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.core.mail import send_mail
from django.dispatch import receiver
from django.urls import reverse

from apps.common.celery import dispatch_task
from apps.common.image_variants import delete_optimized_image
from apps.common.tasks import generate_media_variants_task

from .models import User

logger = logging.getLogger(__name__)

@receiver(user_logged_in)
def send_login_alert(sender, user, request, **kwargs):
    if not user.email:
        return

    try:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'Unknown'))
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()

        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')

        # Determine base URL
        app_url = getattr(settings, 'APP_PUBLIC_URL', '')
        base_url = app_url if app_url else request.build_absolute_uri('/')[:-1]

        dashboard_url = f"{base_url}/"
        try:
            password_url = f"{base_url}{reverse('account_change_password')}"
        except Exception:
            password_url = f"{base_url}/accounts/password/change/"

        context = {
            'user': user,
            'ip_address': ip,
            'user_agent': user_agent,
            'dashboard_url': dashboard_url,
            'password_url': password_url,
            'app_name': getattr(settings, 'APP_NAME', 'Our Platform')
        }

        subject = f"Security Alert: New login to your {context['app_name']} account"

        # Plain text and simple HTML block to ensure success if templates not yet present
        plain_message = f"Hello,\n\nWe noticed a new login to your account.\nIP: {ip}\nDevice: {user_agent}\n\nIf this was you, you can ignore this email. If not, please change your password: {password_url}"
        html_message = f"<p>Hello,</p><p>We noticed a new login to your account.</p><ul><li>IP: {ip}</li><li>Device: {user_agent}</li></ul><p>If this was you, you can ignore this email. If not, please change your password: <a href='{password_url}'>change password</a>.</p>"

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
            html_message=html_message
        )
        logger.info(f"Login alert sent for user_id={user.id}")
    except Exception:
        logger.exception(f"Failed to send login alert for user_id={user.id}")


def _queue_user_image_optimization(user: User) -> None:
    transaction.on_commit(
        lambda: dispatch_task(
            generate_media_variants_task,
            user._meta.label_lower,
            user.pk,
            ["avatar", "banner"],
        )
    )


@receiver(pre_save, sender=User)
def cleanup_replaced_user_image_variants(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).only("avatar", "banner").first()
    if previous is None:
        return
    if previous.avatar and previous.avatar.name != getattr(instance.avatar, "name", ""):
        delete_optimized_image(previous.avatar)
    if previous.banner and previous.banner.name != getattr(instance.banner, "name", ""):
        delete_optimized_image(previous.banner)


@receiver(post_save, sender=User)
def ensure_user_image_variants(sender, instance, **kwargs):
    _queue_user_image_optimization(instance)


@receiver(post_delete, sender=User)
def cleanup_deleted_user_image_variants(sender, instance, **kwargs):
    delete_optimized_image(instance.avatar)
    delete_optimized_image(instance.banner)
