from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

from core.auth_views import StaffOnlyLoginView
from core.webhooks import QuickBooksWebhookView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Mirrors django.contrib.auth.urls, except "login/" uses StaffOnlyLoginView
    # (rejects teacher/parent accounts — see core.forms.StaffOnlyAuthenticationForm).
    # Kept as an explicit list rather than include("django.contrib.auth.urls")
    # since include() can't override a single route.
    path("accounts/login/", StaffOnlyLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_change/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("accounts/password_change/done/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    path("webhooks/quickbooks/", QuickBooksWebhookView.as_view(), name="quickbooks_webhook"),
    path("api/", include("core.api_urls")),
    path("api/portal/", include("portal.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
