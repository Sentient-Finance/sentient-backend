from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_real_client_ip(request: Request) -> str:
    """Return the real client IP, honouring X-Forwarded-For when behind a proxy.

    If a trusted proxy sets X-Forwarded-For, use the leftmost (original) IP.
    Otherwise fall back to the direct remote address.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # "client, proxy1, proxy2" — take the first (original client)
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_real_client_ip)
