"""Logging functionality with dual file and console output."""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict


class Logger:
    """Dual-output logger: writes to file and colored console."""

    COLORS: Dict[str, str] = {
        'cyan': '\033[96m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'gray': '\033[90m',
        'white': '\033[97m',
        'reset': '\033[0m',
    }

    def __init__(self, log_file: Path) -> None:
        """Initialize logger with output file path."""
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str, color: Optional[str] = None) -> None:
        """Write message to log file and print to console with optional color."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f"{timestamp} {msg}"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        if color and color in self.COLORS:
            print(f"{self.COLORS[color]}{line}{self.COLORS['reset']}")
        else:
            print(line)
