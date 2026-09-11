import re
from typing import Optional

# Zambian mobile numbers: 9 digits after the country code, e.g. 977123456.
_ZM_LOCAL_RE = re.compile(r"^0(\d{9})$")
_ZM_INTL_RE = re.compile(r"^(?:\+?260)(\d{9})$")


def normalize_phone_number(phone: Optional[str]) -> Optional[str]:
    """Normalize a Zambian phone number to E.164 form (+260XXXXXXXXX).

    Accepts local (0XXXXXXXXX), international (+260XXXXXXXXX / 260XXXXXXXXX)
    formats, with optional spaces/dashes. Returns None if it doesn't match.
    """
    if not phone:
        return None

    cleaned = re.sub(r"[\s-]", "", phone.strip())

    match = _ZM_LOCAL_RE.match(cleaned) or _ZM_INTL_RE.match(cleaned)
    if not match:
        return None

    return f"+260{match.group(1)}"
