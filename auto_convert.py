#!/usr/bin/env python3
"""
Directory watcher that converts new image files to PNG and video files to MP3.

Drop files into the watched input directory and the script will place converted
files into the output directory without manual interaction.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from PIL import Image, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
except ImportError:  # pillow-heif optional; warn later if missing
    register_heif_opener = None


# Default file type mappings; extend via CLI flags if needed.
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
    ".wmv",
    ".flv",
    ".webm",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a folder and convert images to PNG and videos to MP3 automatically."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("input"),
        help="Directory to watch for new files (default: ./input).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to store converted files (default: ./output).",
    )
    parser.add_argument(
        "--no-process-existing",
        action="store_true",
        help="Skip converting files that already exist in the input directory at startup.",
    )
    parser.add_argument(
        "--image-ext",
        type=str,
        nargs="*",
        default=None,
        help="Override the set of image extensions (include dot). Example: --image-ext .jpg .jpeg",
    )
    parser.add_argument(
        "--video-ext",
        type=str,
        nargs="*",
        default=None,
        help="Override the set of video extensions (include dot).",
    )
    parser.add_argument(
        "--ffmpeg-bin",
        type=str,
        default="ffmpeg",
        help="Path to ffmpeg binary (default assumes it is on PATH).",
    )
    parser.add_argument(
        "--video-crf",
        type=str,
        default="23",
        help="Constant rate factor for x264 encoding (lower is higher quality).",
    )
    parser.add_argument(
        "--video-preset",
        type=str,
        default="medium",
        help="x264 preset controlling encode speed vs quality (e.g., veryfast, faster, medium).",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def configure_image_plugins() -> None:
    if register_heif_opener is not None:
        register_heif_opener()
    else:
        logging.warning(
            "HEIC/HEIF support unavailable. Install pillow-heif to enable conversion for these formats."
        )


def ensure_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def wait_for_file_ready(path: Path, timeout: float = 300.0, stable_checks: int = 3, interval: float = 0.5) -> bool:
    """
    Poll the file until its size stays constant for a few checks.
    Returns True if the file looks stable, False if the timeout expires.
    """
    deadline = time.monotonic() + timeout
    last_size = -1
    stable_count = 0

    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            logging.debug("File %s missing while waiting; retrying.", path)
            time.sleep(interval)
            continue

        if size == last_size and size > 0:
            stable_count += 1
            if stable_count >= stable_checks:
                return True
        else:
            stable_count = 0
            last_size = size

        time.sleep(interval)

    return False


def convert_image_to_png(src: Path, dest_dir: Path) -> None:
    output_path = dest_dir / (src.stem + ".png")
    if output_path.exists():
        logging.info("Image output already exists, skipping: %s", output_path)
        return

    try:
        with Image.open(src) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.mode else "RGB")
            img.save(output_path, format="PNG")
    except UnidentifiedImageError:
        logging.error("Cannot identify image file: %s", src)
        return
    except Exception as exc:
        logging.exception("Failed to convert image %s: %s", src, exc)
        return

    logging.info("Converted image to PNG: %s -> %s", src.name, output_path.name)


def convert_video_to_mp4(src: Path, dest_dir: Path, ffmpeg_bin: str, video_crf: str, video_preset: str) -> None:
    output_path = dest_dir / (src.stem + ".mp4")
    if output_path.exists():
        logging.info("Video output already exists, skipping: %s", output_path)
        return

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(src),
        "-c:v",
        "libx264",
        "-preset",
        video_preset,
        "-crf",
        video_crf,
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path),
    ]

    logging.debug("Running ffmpeg: %s", " ".join(cmd))
    try:
        # Capture stderr only; ffmpeg writes progress to stderr.
        result = subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as exc:
        logging.error("ffmpeg failed for %s:\n%s", src, exc.stderr.strip())
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        return
    except FileNotFoundError:
        logging.error("ffmpeg binary not found. Set --ffmpeg-bin or install ffmpeg.")
        return

    logging.info("Converted video to MP4: %s -> %s", src.name, output_path.name)
    if result.stderr:
        logging.debug("ffmpeg output: %s", result.stderr.strip())


@dataclass
class ConversionConfig:
    input_dir: Path
    output_dir: Path
    image_exts: Set[str]
    video_exts: Set[str]
    ffmpeg_bin: str
    video_crf: str
    video_preset: str

    @property
    def image_output_dir(self) -> Path:
        return self.output_dir / "images"

    @property
    def video_output_dir(self) -> Path:
        return self.output_dir / "videos"


class ConversionHandler(FileSystemEventHandler):
    def __init__(self, config: ConversionConfig):
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
        self._in_progress: Set[Path] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def _schedule(self, path: Path) -> None:
        if self._should_ignore(path):
            return

        with self._lock:
            if path in self._in_progress:
                return
            self._in_progress.add(path)

        threading.Thread(target=self._process_path, args=(path,), daemon=True).start()

    def _should_ignore(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix not in self.config.image_exts and suffix not in self.config.video_exts:
            return True
        if path.name.startswith("."):
            return True
        if not path.exists():
            return True
        return False

    def _process_path(self, path: Path) -> None:
        try:
            if not wait_for_file_ready(path):
                logging.warning("File did not stabilize in time, skipping: %s", path)
                return

            suffix = path.suffix.lower()
            if suffix in self.config.image_exts:
                ensure_directory(self.config.image_output_dir)
                convert_image_to_png(path, self.config.image_output_dir)
            elif suffix in self.config.video_exts:
                ensure_directory(self.config.video_output_dir)
                convert_video_to_mp4(
                    path,
                    self.config.video_output_dir,
                    self.config.ffmpeg_bin,
                    self.config.video_crf,
                    self.config.video_preset,
                )
            else:
                logging.debug("No converter registered for %s", path)
        finally:
            with self._lock:
                self._in_progress.discard(path)


def normalise_extensions(exts: Iterable[str]) -> Set[str]:
    normalised = set()
    for ext in exts:
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalised.add(ext.lower())
    return normalised


def process_existing_files(config: ConversionConfig) -> None:
    for path in sorted(config.input_dir.iterdir()):
        if path.is_file():
            suffix = path.suffix.lower()
            if suffix in config.image_exts or suffix in config.video_exts:
                logging.info("Processing existing file: %s", path.name)
                if suffix in config.image_exts:
                    ensure_directory(config.image_output_dir)
                    convert_image_to_png(path, config.image_output_dir)
                else:
                    ensure_directory(config.video_output_dir)
                    convert_video_to_mp4(
                        path,
                        config.video_output_dir,
                        config.ffmpeg_bin,
                        config.video_crf,
                        config.video_preset,
                    )


def main() -> int:
    args = parse_args()
    configure_logging()
    configure_image_plugins()

    config = ConversionConfig(
        input_dir=args.input_dir.expanduser().resolve(),
        output_dir=args.output_dir.expanduser().resolve(),
        image_exts=normalise_extensions(args.image_ext) if args.image_ext is not None else set(IMAGE_EXTENSIONS),
        video_exts=normalise_extensions(args.video_ext) if args.video_ext is not None else set(VIDEO_EXTENSIONS),
        ffmpeg_bin=args.ffmpeg_bin,
        video_crf=args.video_crf,
        video_preset=args.video_preset,
    )

    ensure_directory(config.input_dir)
    ensure_directory(config.output_dir)

    if not args.no_process_existing:
        process_existing_files(config)

    handler = ConversionHandler(config)
    observer = Observer()
    observer.schedule(handler, str(config.input_dir), recursive=False)

    logging.info("Watching %s", config.input_dir)
    logging.info("Converted images -> %s", config.image_output_dir)
    logging.info("Converted videos -> %s", config.video_output_dir)

    try:
        observer.start()
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logging.info("Stopping watcher...")
    finally:
        observer.stop()
        observer.join()

    return 0


if __name__ == "__main__":
    sys.exit(main())
