# Auto Converter Watcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This project watches a directory for new or modified files and converts them automatically:

- Images (`.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`, `.heic`, `.heif`) ➜ PNG
- Videos (`.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`, `.wmv`, `.flv`, `.webm`) ➜ MP4 (x264 + AAC)

Converted files are stored in `output/images` and `output/videos`, leaving the originals untouched.

---

## 1. Prepare the Environment

1. **Install Python 3.9 or newer**  
   macOS Ventura/Sequoia already ships with `python3` (verify via `python3 --version`).  
   If needed, install from [python.org](https://www.python.org/downloads/) or via a package manager such as `brew install python`.
2. **Install `ffmpeg`**  
   ```bash
   brew install ffmpeg            # macOS + Homebrew
   sudo apt install ffmpeg        # Ubuntu/Debian
   choco install ffmpeg           # Windows + Chocolatey
   ```
3. **Suggested repository layout**
   ```
   convertor/
   ├── auto_convert.py
   ├── requirements.txt
   ├── README.md          # Thai version
   ├── README_EN.md       # English version
   ├── install_launch_agent.sh
   └── launch_agent/
       └── com.alphab.autoconvert.plist
   ```

> Commit the full structure above before sharing on GitHub.

---

## 2. Project Setup (first run)

```bash
git clone https://github.com/<your-account>/convertor.git
cd convertor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- The main script `auto_convert.py` will create `input/` and `output/` on first run.
- macOS users may need to grant Full Disk Access to Terminal/launchctl if watching Desktop/Documents.

---

## 3. Manual Execution (foreground)

```bash
source .venv/bin/activate
python3 auto_convert.py
```

1. Keep the terminal window open.
2. Drop files that need conversion into the `input/` directory.
3. Converted results appear in `output/images` or `output/audio`.
4. Press `Ctrl+C` to stop the watcher.

### Command-line options

```bash
python3 auto_convert.py \
  --input-dir /path/to/watch \
  --output-dir /path/to/results \
  --video-crf 20 \
  --video-preset veryfast \
  --ffmpeg-bin /usr/local/bin/ffmpeg
```

- `--no-process-existing`: skip files that already existed before startup.
- `--image-ext` / `--video-ext`: override supported extensions (include the dot, e.g., `.jpg .png`).
- `--video-crf`: x264 CRF value (lower = better quality, larger file).
- `--video-preset`: x264 speed/quality preset (`ultrafast` … `placebo`).

---

## 4. Run Automatically on macOS (launchd agent)

Ideal when you want background conversion without keeping a terminal open.

```bash
cd ~/convertor
chmod +x install_launch_agent.sh
./install_launch_agent.sh
```

The installer script will:

1. Verify the virtualenv at `~/convertor/.venv` exists (and print instructions if missing).
2. Copy `launch_agent/com.alphab.autoconvert.plist` to `~/Library/LaunchAgents/`.
3. Run `launchctl load -w` to start the service immediately and at every login.

### Check status / logs

```bash
launchctl list | grep com.alphab.autoconvert
tail -f ~/Library/Logs/com.alphab.autoconvert.log
tail -f ~/Library/Logs/com.alphab.autoconvert.err
```

### Restart the agent after updating code

```bash
launchctl unload ~/Library/LaunchAgents/com.alphab.autoconvert.plist
launchctl load -w ~/Library/LaunchAgents/com.alphab.autoconvert.plist
```

### Stop or remove the service

```bash
launchctl unload ~/Library/LaunchAgents/com.alphab.autoconvert.plist   # temporary stop
rm ~/Library/LaunchAgents/com.alphab.autoconvert.plist                 # remove permanently
```

---

## 5. Implementation Overview

- `watchdog` monitors the filesystem for new/modified files.
- A stabilization loop waits for file copies to finish before conversion.
- Image conversions use `Pillow` plus `pillow-heif` for HEIC/HEIF support.
- Videos are transcoded to MP4 with `ffmpeg` (`libx264` + `aac`). Errors are logged.
- Logs are printed to stdout/stderr when run manually, and to `~/Library/Logs/` via launch agent.

---

## 6. Troubleshooting

| Issue | Fix |
|-------|-----|
| No output files appear | Ensure the file finished copying and uses a supported extension. |
| HEIC files stay unconverted | Confirm `pillow-heif` is installed in the virtualenv (`pip show pillow-heif`). |
| Video output is missing / still original format | Inspect the log for ffmpeg errors, verify `ffmpeg` is on PATH, and check write permissions in `output/videos`. |
| Launch agent doesn't start at login | Check `launchctl list`, log files, and macOS Full Disk Access permissions. |
| Need a different `ffmpeg` binary | Edit the plist `EnvironmentVariables` or pass `--ffmpeg-bin` when running manually. |

---

## 7. For Contributors

- Run `python3 -m py_compile auto_convert.py` to check syntax.
- Add automated tests (e.g., pytest) as needed and document them here.
- Update both README files if you change directory layout, dependencies, or default behavior.

---

Ready for GitHub distribution: include badges/screenshots if desired, link to both README versions, and invite users to open issues for feature requests or bugs.
