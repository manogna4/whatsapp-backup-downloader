import os
from dotenv import load_dotenv


class Config:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Google account credentials for gpsoauth
        self.google_email = os.getenv('GOOGLE_EMAIL', '')
        self.google_password = os.getenv('GOOGLE_PASSWORD', '')
        self.android_id = os.getenv('ANDROID_ID', '')

        # WhatsApp backup settings
        self.backup_dir = os.getenv('BACKUP_DIR', 'whatsapp_backups')

        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)

        # Settings file path
        self.settings_file = os.getenv('SETTINGS_FILE', 'settings.cfg')

    def is_configured(self) -> bool:
        """Check if all required credentials are configured."""
        return bool(self.google_email and self.google_password and self.android_id)

    def load_from_settings(self) -> bool:
        """Load credentials from settings.cfg file."""
        if not os.path.exists(self.settings_file):
            return False

        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(self.settings_file)

            if 'auth' in config:
                self.google_email = config['auth'].get('gmail', self.google_email)
                self.google_password = config['auth'].get('password', self.google_password)
                self.android_id = config['auth'].get('android_id', self.android_id)
                return True
        except Exception:
            pass

        return False

    def save_to_settings(self) -> None:
        """Save credentials to settings.cfg file."""
        import configparser
        config = configparser.ConfigParser()

        config['auth'] = {
            'gmail': self.google_email,
            'password': self.google_password,
            'android_id': self.android_id
        }

        with open(self.settings_file, 'w') as f:
            config.write(f)

    def prompt_credentials(self) -> None:
        """Prompt user to enter credentials interactively."""
        import getpass

        print("\n" + "=" * 60)
        print("Google Account Configuration")
        print("=" * 60)
        print("""
To access WhatsApp backups, you need:
  1. Google account email
  2. Google account password (or App Password if 2FA enabled)
  3. Android device ID

To get your Android ID, run on your phone (via ADB):
  adb shell settings get secure android_id

If you have 2FA enabled, create an App Password at:
  https://myaccount.google.com/apppasswords
""")
        print("-" * 60)

        self.google_email = input("Google Email: ").strip()
        self.google_password = getpass.getpass("Google Password (or App Password): ")
        self.android_id = input("Android Device ID: ").strip()

        # Offer to save
        save = input("\nSave credentials to settings.cfg? (y/n): ").strip().lower()
        if save == 'y':
            self.save_to_settings()
            print(f"Credentials saved to {self.settings_file}")
            print("WARNING: Keep this file secure - it contains your password!")