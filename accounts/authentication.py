from rest_framework.authentication import SessionAuthentication


class SessionAuthWith401(SessionAuthentication):
    """SessionAuthentication that returns 401 (not 403) for unauthenticated requests.

    DRF downgrades NotAuthenticated to 403 when no authenticator provides a
    WWW-Authenticate header. Returning a non-empty string from authenticate_header
    prevents that downgrade.
    """

    def authenticate_header(self, request):
        return "Session"
