# Auto Converter Watcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

โครงการนี้ทำหน้าที่เฝ้าโฟลเดอร์สำหรับไฟล์ใหม่/แก้ไข แล้วแปลงไฟล์ที่รองรับโดยอัตโนมัติ:

- รูปภาพ (`.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`, `.heic`, `.heif`) ➜ PNG
- วิดีโอ (`.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`, `.wmv`, `.flv`, `.webm`) ➜ MP3 (ดึงเสียงออกมาเท่านั้น)

ผลลัพธ์จะถูกส่งเข้า `output/images` และ `output/audio` โดยไม่แตะไฟล์ต้นฉบับ

---

## 1. เตรียมเครื่อง

1. **ติดตั้ง Python 3.9+**  
   macOS Ventura/Sequoia มี `python3` อยู่แล้ว (ตรวจสอบด้วย `python3 --version`).  
   หากจำเป็นติดตั้งจาก [python.org](https://www.python.org/downloads/) หรือ `brew install python`.
2. **ติดตั้ง `ffmpeg`**  
   ```bash
   brew install ffmpeg            # macOS + Homebrew
   sudo apt install ffmpeg        # Ubuntu/Debian
   choco install ffmpeg           # Windows + Chocolatey
   ```
3. **โครงสร้างโฟลเดอร์ **  
   ```
   convertor/
   ├── auto_convert.py
   ├── requirements.txt
   ├── README.md
   ├── install_launch_agent.sh
   └── launch_agent/
       └── com.alphab.autoconvert.plist
   ```


---

## 2. ตั้งค่าโปรเจ็กต์ (ครั้งแรก)

```bash
git clone https://github.com/<your-account>/convertor.git
cd convertor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- สคริปต์หลัก `auto_convert.py` จะสร้างโฟลเดอร์ `input/` และ `output/` เองเมื่อรันครั้งแรก
- ถ้าใช้งานบน macOS แจ้งผู้ใช้ว่าต้องอนุญาต Full Disk Access ให้ Terminal/launchctl หากโฟลเดอร์อยู่ใน Desktop/Documents

---

## 3. รันแบบ Manual (ต้องเปิดเทอร์มินัลเอง)

```bash
source .venv/bin/activate
python3 auto_convert.py
```

1. เปิดหน้าต่างเทอร์มินัลค้างไว้
2. ลากไฟล์ที่ต้องการแปลงเข้าโฟลเดอร์ `input/`
3. สคริปต์จะแปลงไฟล์ที่รองรับและเซฟลง `output/images` หรือ `output/audio`
4. กด `Ctrl+C` เพื่อหยุด

### ปรับแต่งการรัน

```bash
python3 auto_convert.py \
  --input-dir /path/to/watch \
  --output-dir /path/to/store/results \
  --audio-bitrate 256k \
  --ffmpeg-bin /usr/local/bin/ffmpeg
```

- `--no-process-existing` ข้ามไฟล์ที่อยู่ก่อนเริ่มสคริปต์
- `--image-ext` `--video-ext` ระบุชุดนามสกุลไฟล์เอง (ใส่จุดนำหน้า เช่น `.jpg .png`)

---

## 4. รันอัตโนมัติบน macOS (Launch Agent)

ใช้ได้ดีเวลาต้องการให้เครื่องแปลงตลอดโดยไม่ต้องเปิดเทอร์มินัล

```bash
cd ~/convertor
chmod +x install_launch_agent.sh
./install_launch_agent.sh
```

สคริปต์จะ:

1. ตรวจว่ามี virtualenv `~/convertor/.venv` แล้วหรือยัง (ถ้ายัง จะบอกขั้นตอนสร้าง)
2. คัดลอก `launch_agent/com.alphab.autoconvert.plist` ไปไว้ใน `~/Library/LaunchAgents/`
3. รัน `launchctl load -w` เพื่อเริ่ม service ทันทีและตั้งให้เริ่มทุกครั้งที่ล็อกอิน

### ตรวจสอบสถานะ

```bash
launchctl list | grep com.alphab.autoconvert
tail -f ~/Library/Logs/com.alphab.autoconvert.log
tail -f ~/Library/Logs/com.alphab.autoconvert.err
```

### รีสตาร์ต launch agent หลังอัปเดตโค้ด

```bash
launchctl unload ~/Library/LaunchAgents/com.alphab.autoconvert.plist
launchctl load -w ~/Library/LaunchAgents/com.alphab.autoconvert.plist
```

### ยุติการทำงานหรือถอนการติดตั้ง

```bash
launchctl unload ~/Library/LaunchAgents/com.alphab.autoconvert.plist    # หยุดชั่วคราว
rm ~/Library/LaunchAgents/com.alphab.autoconvert.plist                  # ลบถาวร
```

---

## 5. โครงสร้างและหลักการทำงาน

- ใช้ `watchdog` สังเกตไฟล์ใหม่/แก้ไขในโฟลเดอร์
- รอให้ไฟล์คงที่ (ไม่มีการเปลี่ยนขนาด) ก่อนเริ่มแปลง เพื่อหลีกเลี่ยงไฟล์ค้าง
- แปลงภาพด้วย `Pillow` และปลั๊กอิน `pillow-heif` เพื่อรองรับ HEIC/HEIF
- แปลงวิดีโอเป็น MP3 ด้วย `ffmpeg` (ตัวเลือก `libmp3lame`)
- เก็บ log ที่ stdout/stdout หรือไฟล์ log ใน `~/Library/Logs/` เมื่อใช้ launch agent

---

## 6. Troubleshooting

- **ไม่มีไฟล์ออกมาเลย**  
  ตรวจว่าไฟล์ถูกคัดลอกสมบูรณ์ (`auto_convert.py` รอจนไฟล์นิ่ง) และนามสกุลอยู่ในรายการรองรับ
- **ไฟล์ HEIC ไม่แปลง**  
  ยืนยันว่า `pillow-heif` ติดตั้งอยู่ใน virtualenv (`pip show pillow-heif`)
- **launch agent ไม่รันตอนบูต**  
  ตรวจคำสั่ง `launchctl list | grep autoconvert` และสิทธิ์ Full Disk Access ให้ Terminal/launchctl
- **ต้องการให้ใช้ ffmpeg เวอร์ชันอื่น**  
  แก้ไข `launch_agent/com.alphab.autoconvert.plist` ส่วน `EnvironmentVariables` หรือสั่ง `--ffmpeg-bin` ตอนรัน manual

---

## 7. เพิ่มเติมสำหรับผู้พัฒนา

- รัน `python3 -m py_compile auto_convert.py` เพื่อตรวจ syntax
- เพิ่ม test script เองได้ตามต้องการ (เช่น pytest) แล้วระบุใน README
- หากเปลี่ยนรายการนามสกุลหรือโฟลเดอร์ผลลัพธ์ อย่าลืมอัปเดตคู่มือและ plist ให้ตรงกัน

---

พร้อมสำหรับแชร์บน GitHub: อัปโหลดไฟล์ทั้งหมด, ใส่คำอธิบายโปรเจ็กต์/ภาพตัวอย่าง และลิงก์ README นี้เพื่อให้ผู้ใช้ทำตามขั้นตอนได้ครบถ้วน.
