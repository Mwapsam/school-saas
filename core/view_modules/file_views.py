"""
Reference views for the public/private storage architecture.

These are intentionally small, copy-pasteable examples that show the correct
pattern for each case. Real features (logo upload, report download, etc.) should
follow the same shapes.

    PublicFileUploadView   -> writes to the public bucket, returns a plain CDN URL
    PrivateFileUploadView  -> writes to the private bucket (default storage)
    private_file_download  -> issues a short-lived CloudFront signed URL + 302
    private_prefix_cookies -> sets CloudFront signed cookies for a whole prefix
"""

import os

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage, storages
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View

from core.services.cloudfront_service import get_cloudfront_signer
from core.services.logging_service import ServiceLogger

# ── Upload constraints ────────────────────────────────────────────────────────
_MAX_PUBLIC_BYTES = 5 * 1024 * 1024     # 5 MB  — images / branding
_MAX_PRIVATE_BYTES = 20 * 1024 * 1024   # 20 MB — PDFs / documents

_PUBLIC_CONTENT_TYPES = frozenset({
    "image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp",
})

_PRIVATE_CONTENT_TYPES = frozenset({
    "application/pdf",
    "image/png", "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _tenant_prefix(request) -> str:
    """Per-tenant key prefix so one school can never read another's files."""
    tenant = getattr(request, "tenant", None)
    return getattr(tenant, "schema_name", "public")


def _file_logger(request) -> ServiceLogger:
    return ServiceLogger("file_storage", getattr(request, "tenant", None))


def _validate_upload(f, allowed_types: frozenset, max_bytes: int):
    """Return a JsonResponse error, or None if the file passes validation."""
    if f.size > max_bytes:
        mb = max_bytes // (1024 * 1024)
        return JsonResponse({"error": f"File exceeds the {mb} MB limit."}, status=413)
    ct = getattr(f, "content_type", "").split(";")[0].strip().lower()
    if ct not in allowed_types:
        return JsonResponse({"error": f"File type '{ct}' is not permitted."}, status=415)
    return None


# ── Public uploads ────────────────────────────────────────────────────────────
@method_decorator(login_required, name="dispatch")
class PublicFileUploadView(View):
    """Upload a non-sensitive asset (e.g. a logo) to the public bucket."""

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return JsonResponse({"error": "No file provided"}, status=400)

        err = _validate_upload(f, _PUBLIC_CONTENT_TYPES, _MAX_PUBLIC_BYTES)
        if err:
            return err

        public = storages["public"]
        key = f"public-docs/{_tenant_prefix(request)}/{os.path.basename(f.name)}"
        saved = public.save(key, f)
        url = public.url(saved)

        _file_logger(request).log_action(
            "upload", "public_file",
            resource_id=saved,
            user=request.user,
            request=request,
            details={"size": f.size, "content_type": f.content_type},
        )
        return JsonResponse({"key": saved, "url": url})


# ── Private uploads ───────────────────────────────────────────────────────────
@method_decorator(login_required, name="dispatch")
class PrivateFileUploadView(View):
    """Upload a confidential file (e.g. an admission document) to the private bucket.

    ``default_storage`` is the PrivateMediaStorage in staging/production.
    """

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return JsonResponse({"error": "No file provided"}, status=400)

        err = _validate_upload(f, _PRIVATE_CONTENT_TYPES, _MAX_PRIVATE_BYTES)
        if err:
            return err

        key = f"uploads/{_tenant_prefix(request)}/{os.path.basename(f.name)}"
        saved = default_storage.save(key, f)

        _file_logger(request).log_action(
            "upload", "private_file",
            resource_id=saved,
            user=request.user,
            request=request,
            details={"size": f.size, "content_type": f.content_type},
        )
        # Return the key only — never a long-lived URL. Callers fetch a signed
        # URL on demand via the download endpoint below.
        return JsonResponse({"key": saved}, status=201)


# ── Private download (signed URL) ─────────────────────────────────────────────
@login_required
def private_file_download(request):
    """Redirect to a short-lived CloudFront signed URL for a private object.

    GET /files/private/download/?key=uploads/<schema>/doc.pdf&ttl=120
    """
    key = request.GET.get("key")
    if not key:
        return JsonResponse({"error": "key is required"}, status=400)

    # Authorisation: key must start with a known prefix owned by the caller's tenant.
    prefix = _tenant_prefix(request)
    allowed_prefixes = (
        f"uploads/{prefix}/",
        f"media/uploads/{prefix}/",
        f"reports/{prefix}/",
        f"media/reports/{prefix}/",
    )
    if not any(key.startswith(p) for p in allowed_prefixes):
        _file_logger(request).log_action(
            "access_denied", "private_file",
            resource_id=key,
            user=request.user,
            request=request,
            level="WARNING",
        )
        return HttpResponseForbidden("Not allowed")

    try:
        ttl = min(int(request.GET.get("ttl", 0)) or 0, 3600) or None
    except ValueError:
        ttl = None

    signer = get_cloudfront_signer()
    # The private storage stores objects under the 'media/' location; the signed
    # URL must reference the full key. Accept either a bare key or a media/ key.
    object_key = key if key.startswith("media/") else f"media/{key}"
    url = signer.signed_url(object_key, expire_seconds=ttl)

    _file_logger(request).log_action(
        "download", "private_file",
        resource_id=key,
        user=request.user,
        request=request,
        details={"ttl": ttl},
    )
    return HttpResponseRedirect(url)


# ── Private prefix access via signed cookies ──────────────────────────────────
@login_required
def private_prefix_cookies(request):
    """Set CloudFront signed cookies granting access to the tenant's report prefix.

    Useful when a page references many private objects (e.g. a gallery of
    reports) — sign once, the browser sends cookies for each object.
    """
    signer = get_cloudfront_signer()
    prefix = _tenant_prefix(request)
    domain = signer.domain
    resource = f"https://{domain}/media/reports/{prefix}/*"

    cookies = signer.signed_cookies(resource, expire_seconds=3600)

    _file_logger(request).log_action(
        "issue_signed_cookies", "private_prefix",
        resource_id=resource,
        user=request.user,
        request=request,
    )
    resp = JsonResponse({"ok": True, "resource": resource})
    for name, value in cookies.items():
        resp.set_cookie(
            name, value, domain=domain, secure=True, httponly=True, samesite="None", path="/"
        )
    return resp
