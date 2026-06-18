import hmac


def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'",
    )
    return response


def request_api_token(request_obj):
    auth_header = request_obj.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request_obj.headers.get("X-API-Token", "").strip()


def is_authorized_api_request(request_obj, api_auth_token):
    if not api_auth_token:
        return True
    if request_obj.method == "OPTIONS":
        return True
    if not request_obj.path.startswith("/api/"):
        return True
    if request_obj.path == "/api/auth/status":
        return True

    supplied_token = request_api_token(request_obj)
    return bool(supplied_token and hmac.compare_digest(supplied_token, api_auth_token))
