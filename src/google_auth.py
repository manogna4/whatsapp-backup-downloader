"""
Google Play Services OAuth authentication for WhatsApp backup access.

This module uses gpsoauth to authenticate as WhatsApp would,
allowing access to WhatsApp's private backup data in Google Drive.
"""

import gpsoauth
import requests
from typing import Optional


class GoogleAuth:
    """Handles Google authentication via Play Services OAuth."""

    # WhatsApp's package signature (certificate hash)
    WHATSAPP_PACKAGE = "com.whatsapp"
    WHATSAPP_SIGNATURE = "38a0f7d505fe18fec64fbf343ecaaaf310dbd799"

    # Google Backup API scope
    DRIVE_SCOPE = "oauth2:https://www.googleapis.com/auth/drive.appdata"

    def __init__(self, email: str, password: str, android_id: str):
        """
        Initialize authentication.

        Args:
            email: Google account email
            password: Google account password (or app password if 2FA enabled)
            android_id: Android device ID (from: adb shell settings get secure android_id)
        """
        self.email = email
        self.password = password
        self.android_id = android_id
        self._auth_token: Optional[str] = None

    def authenticate(self) -> str:
        """
        Perform authentication and return bearer token.

        Returns:
            Bearer token for API requests

        Raises:
            Exception: If authentication fails
        """
        if self._auth_token:
            return self._auth_token

        print(f"Authenticating as {self.email}...")

        # Step 1: Master login to get initial token
        try:
            master_response = gpsoauth.perform_master_login(
                self.email,
                self.password,
                self.android_id
            )
        except Exception as e:
            raise Exception(f"Master login failed: {str(e)}")

        if "Token" not in master_response:
            error = master_response.get("Error", "Unknown error")
            if "BadAuthentication" in str(error):
                raise Exception(
                    "Authentication failed. Possible causes:\n"
                    "  - Incorrect email or password\n"
                    "  - If 2FA is enabled, use an App Password\n"
                    "  - Account may require verification"
                )
            raise Exception(f"Failed to get master token: {error}")

        master_token = master_response["Token"]

        # Step 2: Exchange for WhatsApp-scoped OAuth token
        try:
            oauth_response = gpsoauth.perform_oauth(
                self.email,
                master_token,
                self.android_id,
                self.DRIVE_SCOPE,
                self.WHATSAPP_PACKAGE,
                self.WHATSAPP_SIGNATURE
            )
        except Exception as e:
            raise Exception(f"OAuth exchange failed: {str(e)}")

        if "Auth" not in oauth_response:
            error = oauth_response.get("Error", "Unknown error")
            raise Exception(f"Failed to get OAuth token: {error}")

        self._auth_token = oauth_response["Auth"]
        print("Authentication successful!")
        return self._auth_token

    def get_headers(self) -> dict:
        """Get HTTP headers with authorization."""
        token = self.authenticate()
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": "WhatsApp/2.24.25.78 Android/14"
        }
