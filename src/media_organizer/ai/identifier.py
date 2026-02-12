"""AI-powered creator identification."""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from ..core.logger import Logger
from .dmr_client import DMRClient


class CreatorIdentifier:
    """Identifies creators using AI and manages creator mappings."""

    def __init__(self, db: sqlite3.Connection, dmr_client: DMRClient, logger: Logger) -> None:
        """Initialize creator identifier."""
        self.db = db
        self.dmr_client = dmr_client
        self.logger = logger

    def load_mappings(self) -> Dict[str, Optional[str]]:
        """Load creator mappings from the database."""
        rows = self.db.execute("SELECT folder_name, creator_name FROM creator_mappings").fetchall()
        return {folder: creator for folder, creator in rows}

    def save_mappings(self, mappings: Dict[str, Optional[str]]) -> None:
        """Save creator mappings to the database (upsert)."""
        self.db.executemany(
            "INSERT INTO creator_mappings(folder_name, creator_name) VALUES(?,?) "
            "ON CONFLICT(folder_name) DO UPDATE SET creator_name=excluded.creator_name",
            list(mappings.items())
        )
        self.db.commit()

    def identify_creators(self, folders: List[Path], mappings: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        """
        Use Docker Model Runner to identify creator names from ambiguous folders.

        Args:
            folders: List of folder paths to identify
            mappings: Existing creator mappings

        Returns:
            Dictionary mapping folder names to creator names
        """
        folder_list = []
        for folder in folders:
            subfolders = [d.name for d in folder.iterdir() if d.is_dir()][:5]
            folder_list.append(f"- {folder.name} (contains: {', '.join(subfolders)})")

        known_creators = {v for v in mappings.values() if v and v != ""}

        prompt = f"""Identify which creators these folders belong to. Return ONLY a JSON object mapping folder names to creator names.

Known creators: {', '.join(sorted(known_creators))}

Folders:
{chr(10).join(folder_list)}

Rules:
- If a folder contains subfolders for a creator, the creator name is the subfolder name
- If a folder has a date prefix like "2026-01-02 CreatorName - ...", extract just the creator name
- Use lowercase with underscores for creator names (e.g., "fanny_targioni_tozzetti")
- Return format: {{"folder_name": "creator_name"}}
- For container folders like "Various Files", return null

Return ONLY the JSON object, no explanation.

Example: {{"Various Files": null, "2026-01-02 Avery - Bon Voyage": "avery"}}"""

        response = self.dmr_client.call_api(prompt)

        if not response:
            self.logger.log("[ERROR] AI call failed, using empty mappings", "red")
            return {}

        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                new_mappings = json.loads(json_str)
                self.logger.log(f"[AI] Identified {len(new_mappings)} folders", "green")
                return new_mappings
            else:
                self.logger.log(f"[ERROR] No JSON found in response: {response[:200]}", "red")
                return {}
        except json.JSONDecodeError as e:
            self.logger.log(f"[ERROR] Failed to parse AI response: {e}", "red")
            self.logger.log(f"[DEBUG] Response was: {response[:200]}...", "yellow")
            return {}
