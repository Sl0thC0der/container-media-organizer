"""Empty folder cleanup."""

from pathlib import Path

from ..core.logger import Logger


class FolderCleanup:
    """Removes empty folders from the filesystem."""

    def __init__(self, logger: Logger) -> None:
        """Initialize folder cleanup."""
        self.logger = logger

    def remove_empty_folders(self, work_dir: Path) -> int:
        """
        Remove empty folders in a single bottom-up pass (O(n), not O(n²)).

        Args:
            work_dir: Root directory to clean

        Returns:
            Number of folders removed
        """
        self.logger.log("[CLEANUP] Removing empty folders...", "cyan")

        # Collect all directories, sort deepest-first by path depth
        all_dirs = []
        for entry in work_dir.rglob('*'):
            if entry.is_dir() and '.claude' not in str(entry):
                all_dirs.append(entry)

        all_dirs.sort(key=lambda p: len(p.parts), reverse=True)

        removed = 0
        for folder in all_dirs:
            try:
                if not any(folder.iterdir()):
                    folder.rmdir()
                    self.logger.log(f"  Removed: {folder.name}", "yellow")
                    removed += 1
            except (PermissionError, OSError):
                pass

        if removed == 0:
            self.logger.log("[CLEANUP] No empty folders found", "green")
        else:
            self.logger.log(f"[CLEANUP] Removed {removed} empty folders", "green")

        return removed
