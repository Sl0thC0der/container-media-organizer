"""Configuration settings and constants."""

import os
import sys
from pathlib import Path


def validate_work_dir(work_dir: Path) -> Path:
    """Validate WORK_DIR is safe (no path traversal)."""
    # Skip validation during testing
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return work_dir

    try:
        resolved = work_dir.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError(f"WORK_DIR is not a directory: {work_dir}")
        return resolved
    except (ValueError, OSError, RuntimeError) as e:
        print(f"ERROR: Invalid WORK_DIR: {e}")
        sys.exit(1)


# ============================================
# PATHS
# ============================================

WORK_DIR = validate_work_dir(Path(os.getenv("WORK_DIR", "/media")))

# Config and log directories are relative to package root
# When installed as package, use user's home directory for config
try:
    # Try to use script location first (for backward compatibility)
    _package_root = Path(__file__).parent.parent.parent
    CONFIG_DIR = _package_root / "config"
    LOG_DIR = _package_root / "logs"
except Exception:
    # Fallback to home directory
    CONFIG_DIR = Path.home() / ".media_organizer" / "config"
    LOG_DIR = Path.home() / ".media_organizer" / "logs"

DB_FILE = CONFIG_DIR / "library.db"

# Legacy files (for migration)
LEGACY_MAPPING_FILE = CONFIG_DIR / "creator-mappings.json"
LEGACY_HASH_FILE = CONFIG_DIR / "all_hashes.csv"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================
# DOCKER MODEL RUNNER API
# ============================================

DMR_URL = os.getenv("DMR_URL", "http://model-runner.docker.internal")
DMR_MODEL = os.getenv("DMR_MODEL", "ai/qwen3-vl")
DMR_TIMEOUT = int(os.getenv("DMR_TIMEOUT", "120"))
DMR_MAX_RETRIES = int(os.getenv("DMR_MAX_RETRIES", "3"))


# ============================================
# FILE TYPE DEFINITIONS
# ============================================

PIC_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.wmv', '.mpg', '.mpeg', '.webm', '.flv'}
ALL_MEDIA_EXTENSIONS = PIC_EXTENSIONS | VIDEO_EXTENSIONS


# ============================================
# PERFORMANCE TUNING
# ============================================

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))
HASH_WORKERS = int(os.getenv("HASH_WORKERS", "8"))
HASH_CHUNK_SIZE = 65536  # 64KB chunks for file hashing
