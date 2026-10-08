#!/usr/bin/env python3
"""
WhatsApp Backup Downloader

Downloads WhatsApp backups from Google Drive using the Google Backup API.
Uses gpsoauth for authentication to access WhatsApp's private backup data.
"""

import sys
from src.config import Config
from src.google_auth import GoogleAuth
from src.backup_api import BackupAPI


def print_help():
    print("""
WhatsApp Backup Downloader
==========================

Downloads WhatsApp backups from Google Drive using gpsoauth authentication.

Usage: python main.py <command>

Commands:
    help     Show this help message
    setup    Configure Google account credentials
    info     Show WhatsApp backup metadata (size, file count)
    list     List all WhatsApp backup files
    sync     Download all WhatsApp backup files

Examples:
    python main.py setup    # First time setup
    python main.py info     # Show backup info
    python main.py list     # List all files in backup
    python main.py sync     # Download all backup files

Requirements:
    - Google account email and password (or App Password if 2FA enabled)
    - Android device ID (from: adb shell settings get secure android_id)
""")


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def cmd_setup(config: Config):
    """Setup credentials."""
    config.prompt_credentials()
    print("\nSetup complete! You can now run other commands.")


def cmd_info(api: BackupAPI):
    """Show backup info."""
    info = api.get_backup_info()

    if not info:
        print("No WhatsApp backup found.")
        return

    print("\n" + "=" * 60)
    print("WhatsApp Backup Info")
    print("=" * 60)

    print(f"\nBackup Name: {info['name']}")
    print(f"Total Size: {format_size(info['size_bytes'])}")
    print(f"Last Updated: {info['update_time']}")

    metadata = info.get('metadata', {})
    if metadata:
        print("\nBackup Details:")
        print("-" * 40)

        if 'numOfMessages' in metadata:
            print(f"  Messages: {metadata['numOfMessages']:,}")
        if 'numOfMediaFiles' in metadata:
            print(f"  Media Files: {metadata['numOfMediaFiles']:,}")
        if 'numOfPhotos' in metadata:
            print(f"  Photos: {metadata['numOfPhotos']:,}")
        if 'chatdbSize' in metadata:
            print(f"  Chat DB Size: {format_size(int(metadata['chatdbSize']))}")
        if 'mediaSize' in metadata:
            print(f"  Media Size: {format_size(int(metadata['mediaSize']))}")
        if 'videoSize' in metadata:
            print(f"  Video Size: {format_size(int(metadata['videoSize']))}")
        if 'versionOfAppWhenBackup' in metadata:
            print(f"  WhatsApp Version: {metadata['versionOfAppWhenBackup']}")
        if 'passwordProtectedBackupEnabled' in metadata:
            protected = "Yes" if metadata['passwordProtectedBackupEnabled'] else "No"
            print(f"  Password Protected: {protected}")

    print("=" * 60)


def cmd_list(api: BackupAPI):
    """List all backup files."""
    files = api.list_files()

    if not files:
        print("No files found in backup.")
        return

    print("\n" + "=" * 80)
    print("WhatsApp Backup Files")
    print("=" * 80)
    print(f"\n{'Filename':<60} {'Size':>15}")
    print("-" * 77)

    total_size = 0
    for file_info in files:
        name = file_info.get("name", "Unknown")
        size = int(file_info.get("sizeBytes", 0))
        total_size += size

        # Extract relative path
        parts = name.split("/files/", 1)
        relative_path = parts[1] if len(parts) > 1 else name.split("/")[-1]

        # Truncate long filenames
        if len(relative_path) > 58:
            relative_path = "..." + relative_path[-55:]

        print(f"{relative_path:<60} {format_size(size):>15}")

    print("-" * 77)
    print(f"{'Total: ' + str(len(files)) + ' files':<60} {format_size(total_size):>15}")
    print("=" * 80)


def cmd_sync(api: BackupAPI, output_dir: str):
    """Download all backup files."""
    files = api.list_files()

    if not files:
        print("No files found in backup.")
        return

    total_size = sum(int(f.get("sizeBytes", 0)) for f in files)
    print(f"\nFound {len(files)} files ({format_size(total_size)})")

    confirm = input("Proceed with download? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Download cancelled.")
        return

    stats = api.sync_all(output_dir)

    print("\n" + "=" * 40)
    print("Download Complete!")
    print("=" * 40)
    print(f"  Successfully downloaded: {stats['success']}")
    print(f"  Skipped (already exist): {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")
    print(f"\nFiles saved to: {output_dir}")


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command in ('help', '-h', '--help'):
        print_help()
        sys.exit(0)

    # Initialize configuration
    config = Config()

    # Handle setup command
    if command == 'setup':
        cmd_setup(config)
        sys.exit(0)

    # Load credentials
    if not config.is_configured():
        config.load_from_settings()

    if not config.is_configured():
        print("Credentials not configured.")
        print("Run 'python main.py setup' first, or set environment variables:")
        print("  GOOGLE_EMAIL, GOOGLE_PASSWORD, ANDROID_ID")
        sys.exit(1)

    print("WhatsApp Backup Downloader")
    print("=" * 30)

    try:
        # Initialize authentication and API
        auth = GoogleAuth(config.google_email, config.google_password, config.android_id)
        api = BackupAPI(auth)

        if command == 'info':
            cmd_info(api)
        elif command == 'list':
            cmd_list(api)
        elif command == 'sync':
            cmd_sync(api, config.backup_dir)
        else:
            print(f"Unknown command: {command}")
            print_help()
            sys.exit(1)

    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
