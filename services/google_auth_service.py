"""Google sign-in (OAuth 2.0 authorization-code flow). Uses only the standard library, so nothing new to install.

Flow: send the user to Google -> Google redirects back with a one-time `code` -> we exchange the code for an access
token (server to server, over HTTPS, with our client secret) -> we ask Google who the user is."""
import json
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app


class GoogleAuthError(Exception):
    """Something went wrong talking to Google. The message is safe to show to the user."""


class GoogleAuthService:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    @staticmethod
    def enabled():
        return bool(current_app.config.get("GOOGLE_ENABLED"))

    @classmethod
    def authorization_url(cls, redirect_uri, state):
        params = {"client_id": current_app.config["GOOGLE_CLIENT_ID"], "redirect_uri": redirect_uri,
                  "response_type": "code", "scope": "openid email profile", "state": state,
                  "prompt": "select_account"}
        return cls.AUTH_URL + "?" + urllib.parse.urlencode(params)

    @staticmethod
    def _read(request):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            raise GoogleAuthError("We couldn't reach Google. Check your internet connection and try again.") from None

    @classmethod
    def fetch_profile(cls, code, redirect_uri):
        """Trade the one-time code for the user's verified Google profile."""
        body = urllib.parse.urlencode({
            "code": code, "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": redirect_uri, "grant_type": "authorization_code"}).encode()
        token = cls._read(urllib.request.Request(
            cls.TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}))
        access_token = token.get("access_token")
        if not access_token:
            raise GoogleAuthError("Google did not approve the sign-in. Please try again.")
        info = cls._read(urllib.request.Request(cls.USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}))

        email = str(info.get("email", "")).strip().lower()
        if not info.get("sub") or not email:
            raise GoogleAuthError("Google did not share an email address for this account.")
        if str(info.get("email_verified")).lower() != "true":
            raise GoogleAuthError("Your Google email address is not verified, so we can't use it.")
        return {"sub": str(info["sub"]), "email": email, "name": info.get("name", ""),
                "given_name": info.get("given_name", ""), "family_name": info.get("family_name", "")}
