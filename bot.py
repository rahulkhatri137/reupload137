# Telegram ReUploader Bot
# Powered by @Bots137

import os
import random
import asyncio
import subprocess
import logging
import sys
import time
from collections import deque
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# ========= CONFIG =========
API_ID = 123456
API_HASH = "API_HASH"
BOT_TOKEN = "BOT_TOKEN"
OWNER_ID = 123456789

WORKERS = 12
MAX_QUEUE = 5
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ========= LOGGING =========
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger()
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)

def log(tag, message):
    logger.info(f"[{tag}] {message}")

def sanitize_filename(name):
    name = name.strip()
    name = name.replace("/", "_").replace("\\", "_")
    return name
    
app = Client(
    "reupload137_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=WORKERS
)

queue = deque()
processing = False
current_task = None
progress_msg = None
aria2_process = None

# ========= FLOODWAIT =========
async def safe_api_call(func, *args, **kwargs):
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWait as e:
            wait_time = int(e.value)
            log("FLOODWAIT", f"Sleeping {wait_time}s")
            await asyncio.sleep(wait_time)

# ========= METADATA =========
def get_video_metadata(video_path):
    try:
        result = subprocess.run(
            ["ffprobe","-v","error","-select_streams","v:0",
             "-show_entries","stream=width,height,duration",
             "-of","default=noprint_wrappers=1",video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        width = height = duration = 0
        for line in result.stdout.splitlines():
            if line.startswith("width="):
                width = int(line.split("=")[1])
            elif line.startswith("height="):
                height = int(line.split("=")[1])
            elif line.startswith("duration="):
                duration = float(line.split("=")[1])
        return width, height, int(duration)
    except:
        return 0, 0, 0

def random_thumbnail(video_path, thumb_path):
    _, _, duration = get_video_metadata(video_path)
    timestamp = int(duration) / 2
    subprocess.run(
        ["ffmpeg","-ss",str(timestamp),"-i",video_path,
         "-vframes","1","-q:v","2",thumb_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# ========= QUEUE =========
async def process_queue():
    global processing, current_task, progress_msg

    if processing:
        return

    processing = True

    while queue:
        task_type, message, queue_msg, file_name = queue[0]

        log("PROCESS", f"Started: {file_name} | Type: {task_type.upper()}")
        try:
            await queue_msg.delete()
        except:
            pass
        try:
            if task_type == "telegram":
                current_task = asyncio.create_task(handle_download(message, file_name))
            else:
                current_task = asyncio.create_task(handle_url_download(message, file_name))

            await current_task
            log("COMPLETE", f"Done: {file_name}")
            try:
                await message.delete()
            except: pass

        except asyncio.CancelledError:
            log("CANCEL", f"Cancelled: {file_name}")
            try:
                await message.reply_text(f"Cancelled: {file_name}")
                await progress_msg.delete()
            except: pass
        except Exception as e:
            log("ERROR", f"{file_name} -> {str(e)}")

        if queue:
           queue.popleft()

    processing = False
    current_task = None

# ========= TELEGRAM DOWNLOAD =========
async def handle_download(message: Message, file_name):
    replied = message.reply_to_message
    media = replied.document or replied.video or replied.audio or replied.photo
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    global progress_msg
    progress_msg = await message.reply_text(f"Downloading: {file_name}")
    last_percent = 0
    start_time = time.time()

    log("DOWNLOAD", f"Starting: {file_name}")

    async def progress(current, total):
        nonlocal last_percent
        percent = int(current * 100 / total)
        if percent - last_percent >= 5:
            last_percent = percent
            elapsed = time.time() - start_time
            speed = current / elapsed if elapsed > 0 else 0
            speed_mb = speed / (1024 * 1024)

            await safe_api_call(
                progress_msg.edit_text,
                f"{file_name}\nDownloading: {percent}%\nSpeed: {speed_mb:.2f} MB/s"
            )

    try:
        file_path = await safe_api_call(
        app.download_media,
        media,
        file_name=file_path,
        progress=progress
    )
    except Exception as e:
        log("ERROR", f"Download failed: {file_name}")
        try:
            await progress_msg.delete()
            await message.reply_text(f"Download failed: {file_name}")
        except:
            pass

    log("DOWNLOAD", f"Completed: {file_name}")
    await upload_file(message, file_path, file_name, progress_msg)

# ========= URL DOWNLOAD =========
async def handle_url_download(message: Message, file_name):
    url = message.text.split(" ",1)[1].strip()
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    global progress_msg, aria2_process
    progress_msg = await message.reply_text(f"Downloading: {file_name}")

    log("DOWNLOAD", f"Starting: {file_name} (URL)")

    await download_with_aria2(url, file_path, progress_msg, message, file_name)

    log("DOWNLOAD", f"Completed: {file_name}")
    await upload_file(message, file_path, file_name, progress_msg)

async def download_with_aria2(url, file_path, progress_msg, message, file_name):

    global aria2_process
    command = [
        "aria2c",
        "-x", "8",                # connections
        "-s", "8",                # split
        "-k", "1M",               # chunk size
        "--summary-interval=1",   # update every second
        "--download-result=full",
        "--console-log-level=notice",
        "--dir", os.path.dirname(file_path),
        "--out", os.path.basename(file_path),
        url
    ]

    aria2_process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    last_percent = 0

    while True:
        line = await aria2_process.stdout.readline()
        if not line:
            break

        line = line.decode().strip()

        if "DL:" in line and "%" in line:
            try:
                percent_part = line.split("%")[0]
                percent = float(percent_part.split()[-1])
                speed_part = line.split("DL:")[1].split()[0]

                if speed_part.endswith("MiB/s"):
                    speed = float(speed_part.replace("MiB/s", "")) * 1024 * 1024
                elif speed_part.endswith("KiB/s"):
                    speed = float(speed_part.replace("KiB/s", "")) * 1024
                elif speed_part.endswith("B/s"):
                    speed = float(speed_part.replace("B/s", ""))
                else:
                    speed = 0
            
                if percent - last_percent >= 5:
                    last_percent = percent
                    try:
                        await progress_msg.edit(
                            f"{os.path.basename(file_path)}\n"
                            f"Downloading: {percent:.1f}%\n"
                            f"Speed: {speed/1024/1024:.2f} MB/s"
                        )
                    except:
                        pass

            except:
                pass

    await aria2_process.wait()

    if aria2_process.returncode != 0:
        try:
            await message.reply_text(f"Download failed: {file_name}")
            await progress_msg.delete()
        except: pass
        raise Exception("aria2 download failed")
        
# ========= UPLOAD =========
async def upload_file(message, file_path, file_name, progress_msg):

    await safe_api_call(progress_msg.edit_text, f"Uploading: {file_name}")
    last_percent = 0
    start_time = time.time()

    log("UPLOAD", f"Starting: {file_name}")

    async def progress(current, total):
        nonlocal last_percent
        percent = int(current * 100 / total)
        if percent - last_percent >= 5:
            last_percent = percent
            elapsed = time.time() - start_time
            speed = current / elapsed if elapsed > 0 else 0
            speed_mb = speed / (1024 * 1024)

            await safe_api_call(
                progress_msg.edit_text,
                f"{file_name}\nUploading: {percent}%\nSpeed: {speed_mb:.2f} MB/s"
            )

    width, height, duration = get_video_metadata(file_path)
    thumb = os.path.join(DOWNLOAD_DIR, "thumb.jpg")
    random_thumbnail(file_path, thumb)

    await safe_api_call(
        app.send_video,
        message.chat.id,
        file_path,
        thumb=thumb if os.path.exists(thumb) else None,
        caption=file_name,
        supports_streaming=True,
        duration=duration,
        width=width,
        height=height,
        progress=progress
    )

    log("UPLOAD", f"Completed: {file_name}")

    if os.path.exists(file_path):
        os.remove(file_path)
        log("CLEANUP", f"Removed file: {file_name}")
    if os.path.exists(thumb):
        os.remove(thumb)

    try:
        await progress_msg.delete()
    except:
        pass

# ========= COMMANDS =========
@app.on_message(filters.command("download") & filters.reply)
async def download_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Unauthorized.")
    if len(queue) >= MAX_QUEUE:
        return await message.reply_text("Queue full (max 5 items).")

    replied = message.reply_to_message
    media = replied.document or replied.video or replied.audio or replied.photo

    file_name = getattr(media, "file_name", None)

    if not file_name:
       if replied.photo:
          file_name = f"photo_{int(time.time())}.jpg"
       elif replied.video:
          file_name = f"video_{int(time.time())}.mp4"
       elif replied.audio:
          file_name = f"audio_{int(time.time())}.mp3"
       else:
          file_name = f"file_{int(time.time())}"

    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        custom_name = sanitize_filename(parts[1])
        file_name = custom_name
    else:
        file_name = file_name
        
    queue_msg = await message.reply_text(f"Added to queue. Position: {len(queue)+1}")
    log("QUEUE", f"Added: {file_name} | Position: {len(queue)+1}")

    queue.append(("telegram", message, queue_msg, file_name))
    await process_queue()

@app.on_message(filters.command("url"))
async def url_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Unauthorized.")
    if len(queue) >= MAX_QUEUE:
        return await message.reply_text("Queue full (max 5 items).")

    text = message.text.split(" ", 1)
    if "|" in text[1]:
        url_part, name_part = text[1].split("|", 1)
        url = url_part.strip()
        file_name = sanitize_filename(name_part.strip())
    else:
        url = text[1].strip()
        file_name = url.split("/")[-1].split("?")[0] or f"file_{int(time.time())}"

    queue_msg = await message.reply_text(f"Added to queue. Position: {len(queue)+1}")
    log("QUEUE", f"Added: {file_name} | Position: {len(queue)+1}")

    queue.append(("url", message, queue_msg, file_name))
    await process_queue()

queue = deque()
@app.on_message(filters.command("queue"))
async def queue_handler(client, message):

    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Unauthorized.")

    if not queue:
        return await message.reply_text("Queue: {len(queue)}/{MAX_QUEUE}")

    text = ""
    if queue:
        text += "Queue:\n"
        for i, item in enumerate(queue, start=1):
            file_name = item[3]
            text += f"{i}. {file_name}\n"

    text += f"\nTotal: {len(queue)}/{MAX_QUEUE}"

    await message.reply_text(text)

@app.on_message(filters.command("cancel"))
async def cancel_handler(client, message):
    global current_task, queue, aria2_process
    if message.from_user.id != OWNER_ID:
        return
    if current_task and not current_task.done():
        current_task.cancel()
        log("CANCEL", "Active task cancelled")
    if aria2_process:
        aria2_process.kill()
    queue.clear()
    await message.delete()

log("INFO", "Bot started and ready")
app.run()
