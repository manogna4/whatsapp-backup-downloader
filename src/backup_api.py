"""
Google Backup API client for WhatsApp backup access.

Uses the backup.googleapis.com API to list and download WhatsApp backups.
"""

import json
import os
import hashlib
import base64
from urllib.parse import quote
from typing import Optional, List, Dict, Any
import requests
from tqdm import tqdm


class BackupAPI:
    """Client for Google Backup API to access WhatsApp backups."""

    BASE_URL = "https://backup.googleapis.com/v1"

    def __init__(self, auth):
        """
        Initialize the Backup API client.

        Args:
            auth: GoogleAuth instance for authentication
        """
        self.auth = auth
        self._backups_cache: Optional[List[Dict]] = None

    def _request(self, endpoint: str, stream: bool = False) -> requests.Response:
        """Make authenticated request to Backup API."""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = self.auth.get_headers()

        response = requests.get(url, headers=headers, stream=stream)
        response.raise_for_status()
        return response

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all WhatsApp backups.

        Returns:
            List of backup objects with metadata
        """
        if self._backups_cache is not None:
            return self._backups_cache

        print("Fetching WhatsApp backups...")
        backups = []
        page_token = None

        while True:
            endpoint = "clients/wa/backups"
            if page_token:
                endpoint += f"?pageToken={page_token}"

            response = self._request(endpoint)
            data = response.json()

            if "backups" in data:
                backups.extend(data["backups"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        self._backups_cache = backups
        return backups

    def get_backup_info(self) -> Optional[Dict[str, Any]]:
        """
        Get info about the most recent backup.

        Returns:
            Backup info dict or None if no backups found
        """
        backups = self.list_backups()
        if not backups:
            return None

        # Get the first (most recent) backup
        backup = backups[0]

        # Parse metadata JSON if present
        metadata = {}
        if "metadata" in backup:
            try:
                metadata = json.loads(backup["metadata"])
            except json.JSONDecodeError:
                pass

        return {
            "name": backup.get("name", "Unknown"),
            "size_bytes": int(backup.get("sizeBytes", 0)),
            "update_time": backup.get("updateTime", "Unknown"),
            "metadata": metadata
        }

    def list_files(self, backup_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all files in a backup.

        Args:
            backup_name: Backup name (uses first backup if not specified)

        Returns:
            List of file objects
        """
        if not backup_name:
            backups = self.list_backups()
            if not backups:
                return []
            backup_name = backups[0]["name"]

        print(f"Listing files in backup...")
        files = []
        page_token = None

        while True:
            endpoint = f"{backup_name}/files"
            if page_token:
                endpoint += f"?pageToken={page_token}"

            response = self._request(endpoint)
            data = response.json()

            if "files" in data:
                files.extend(data["files"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return files

    def download_file(self, file_name: str, output_path: str, expected_md5: Optional[str] = None) -> bool:
        """
        Download a file from backup.

        Args:
            file_name: Full file name/path from the API
            output_path: Local path to save file
            expected_md5: Expected MD5 hash (base64 encoded) for verification

        Returns:
            True if download successful and verified
        """
        # URL encode special characters
        encoded_name = file_name.replace("%", "%25").replace("+", "%2B")
        endpoint = f"{encoded_name}?alt=media"

        response = self._request(endpoint, stream=True)

        # Create directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Download with progress
        total_size = int(response.headers.get('content-length', 0))
        md5_hash = hashlib.md5()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    md5_hash.update(chunk)

        # Verify MD5 if provided
        if expected_md5:
            calculated_md5 = base64.b64encode(md5_hash.digest()).decode('utf-8')
            if calculated_md5 != expected_md5:
                os.remove(output_path)
                return False

        return True

    def sync_all(self, output_dir: str, skip_existing: bool = True) -> Dict[str, int]:
        """
        Download all files from the backup.

        Args:
            output_dir: Directory to save files
            skip_existing: Skip files that already exist with correct size

        Returns:
            Dict with counts: {"success": n, "skipped": n, "failed": n}
        """
        files = self.list_files()
        if not files:
            print("No files found in backup.")
            return {"success": 0, "skipped": 0, "failed": 0}

        backups = self.list_backups()
        backup_name = backups[0]["name"] if backups else ""

        print(f"\nDownloading {len(files)} files to: {output_dir}")

        stats = {"success": 0, "skipped": 0, "failed": 0}

        for file_info in tqdm(files, desc="Downloading", unit="file"):
            file_name = file_info.get("name", "")
            file_size = int(file_info.get("sizeBytes", 0))
            file_md5 = file_info.get("md5Hash", "")

            # Extract relative path from full name
            # Format: clients/wa/backups/xxx/files/path/to/file
            parts = file_name.split("/files/", 1)
            relative_path = parts[1] if len(parts) > 1 else file_name.split("/")[-1]

            output_path = os.path.join(output_dir, relative_path)

            # Skip if file exists with correct size
            if skip_existing and os.path.exists(output_path):
                existing_size = os.path.getsize(output_path)
                if existing_size == file_size:
                    stats["skipped"] += 1
                    continue

            try:
                success = self.download_file(file_name, output_path, file_md5)
                if success:
                    stats["success"] += 1
                else:
                    tqdm.write(f"MD5 mismatch: {relative_path}")
                    stats["failed"] += 1
            except Exception as e:
                tqdm.write(f"Error downloading {relative_path}: {str(e)}")
                stats["failed"] += 1

        return stats
