"""File merging and organization."""

import re
import shutil
from pathlib import Path
from typing import List, Dict

from ..config import PIC_EXTENSIONS, VIDEO_EXTENSIONS, WORK_DIR
from ..core.logger import Logger


class FileMerger:
    """Merges scattered media files into organized creator folders."""

    def __init__(self, logger: Logger) -> None:
        """Initialize file merger."""
        self.logger = logger

    def get_highest_number(self, directory: Path, pattern: str) -> int:
        """Find the highest number in filenames matching pattern."""
        max_num = 0
        if not directory.exists():
            return 0

        for file in directory.iterdir():
            if file.is_file():
                match = re.match(pattern, file.name)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num

        return max_num

    def merge_scattered_content(self, scattered_folders: List[Dict], merge_log: Path) -> None:
        """
        Merge scattered content into proper creator folders.

        Args:
            scattered_folders: List of dicts with 'creator' and 'path' keys
            merge_log: Path to log file for merge operations
        """
        for scattered in scattered_folders:
            creator_name = scattered['creator']
            source_path = scattered['path']

            creator_dir = WORK_DIR / creator_name
            pics_dir = creator_dir / "Pics"
            video_dir = creator_dir / "Video"

            if not creator_dir.exists():
                creator_dir.mkdir(parents=True)
                self.logger.log(f"  Created {creator_name}/", "green")

            pics_dir.mkdir(exist_ok=True)
            video_dir.mkdir(exist_ok=True)

            pic_pattern = rf"{re.escape(creator_name)}_pic_(\d+)\."
            vid_pattern = rf"{re.escape(creator_name)}_vid_(\d+)\."

            max_pic = self.get_highest_number(pics_dir, pic_pattern)
            max_vid = self.get_highest_number(video_dir, vid_pattern)

            pic_num = max_pic
            vid_num = max_vid

            for file in source_path.rglob('*'):
                if not file.is_file():
                    continue

                ext = file.suffix.lower()

                if ext in PIC_EXTENSIONS:
                    pic_num += 1
                    new_name = f"{creator_name}_pic_{pic_num:03d}{ext}"
                    dest_path = pics_dir / new_name
                    shutil.move(str(file), str(dest_path))

                    with open(merge_log, 'a', encoding='utf-8') as f:
                        f.write(f"{file} -> {dest_path}\n")

                elif ext in VIDEO_EXTENSIONS:
                    vid_num += 1
                    new_name = f"{creator_name}_vid_{vid_num:03d}{ext}"
                    dest_path = video_dir / new_name
                    shutil.move(str(file), str(dest_path))

                    with open(merge_log, 'a', encoding='utf-8') as f:
                        f.write(f"{file} -> {dest_path}\n")

            self.logger.log(f"  Merged {creator_name}: {pic_num - max_pic} pics, {vid_num - max_vid} videos", "green")
