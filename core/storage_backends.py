from django.conf import settings
from storages.backends.s3 import S3Storage


class PublicMediaStorage(S3Storage):
    """User-uploaded public assets (logos, branding, public documents)."""

    bucket_name = settings.AWS_PUBLIC_BUCKET_NAME
    custom_domain = settings.AWS_PUBLIC_CLOUDFRONT_DOMAIN
    location = "media"
    default_acl = None              # access governed by the bucket policy + OAC
    file_overwrite = False
    querystring_auth = False        # public — no signing
    object_parameters = {"CacheControl": "public, max-age=86400"}


class StaticStorage(S3Storage):
    """Collected static files (CSS, JS, fonts)."""

    bucket_name = settings.AWS_PUBLIC_BUCKET_NAME
    custom_domain = settings.AWS_PUBLIC_CLOUDFRONT_DOMAIN
    location = "static"
    default_acl = None
    file_overwrite = True           # static assets are content-hashed; overwrite is fine
    querystring_auth = False
    object_parameters = {"CacheControl": "public, max-age=31536000, immutable"}


class PrivateMediaStorage(S3Storage):

    bucket_name = settings.AWS_PUBLIC_BUCKET_NAME
    custom_domain = settings.AWS_PUBLIC_CLOUDFRONT_DOMAIN
    location = "static"
    default_acl = None
    file_overwrite = True          
    querystring_auth = False
    object_parameters = {"CacheControl": "public, max-age=31536000, immutable"}

    def url(self, name, parameters=None, expire=None, http_method=None):
        from core.services.cloudfront_service import get_cloudfront_signer
        clean = str(name).lstrip("/")
        key = f"{self.location.rstrip('/')}/{clean}" if self.location else clean
        return get_cloudfront_signer().signed_url(key, expire_seconds=expire)
