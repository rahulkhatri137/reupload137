# Telegram ReUploader Bot
# Powered by @Bots137

import os
import random
import asyncio
import subprocess
import logging
import sys
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

app = Client(
    "refined_media_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=WORKERS
)

queue = deque()
processing = False
current_task = None


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
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-of", "default=noprint_wrappers=1",
                video_path
            ],
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
    width, height, duration = get_video_metadata(video_path)
    timestamp = random.uniform(1, max(2, duration - 1))

    subprocess.run(
        ["ffmpeg", "-ss", str(timestamp),
         "-i", video_path,
         "-vframes", "1",
         "-q:v", "2",
         thumb_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# ========= QUEUE =========
async def process_queue():
    global processing, current_task

    if processing:
        return

    processing = True
    log("QUEUE", "Processing started")

    while queue:
        message = queue[0]
        media_msg = message.reply_to_message
        media = media_msg.document or media_msg.video or media_msg.audio or media_msg.photo
        file_name = getattr(media, "file_name", "photo")

        log("PROCESS", f"Now processing: {file_name}")

        current_task = asyncio.create_task(handle_download(message))

        try:
            await current_task
        except asyncio.CancelledError:
            log("CANCELLED", f"Task cancelled: {file_name}")
            await message.reply_text("Current task cancelled.")
        except Exception as e:
            log("ERROR", f"{file_name} -> {str(e)}")
            await message.reply_text("Error occurred. Check terminal logs.")

        queue.popleft()

    log("QUEUE", "Queue empty")
    processing = False
    current_task = None


# ========= CORE =========
async def handle_download(message: Message):
    replied = message.reply_to_message
    media = replied.document or replied.video or replied.audio or replied.photo

    file_name = getattr(media, "file_name", None) or "file"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    progress_msg = await message.reply_text("⬇ Downloading: 0%")
    last_percent = 0

    log("DOWNLOAD", f"Starting: {file_name}")

    async def download_progress(current, total):
        nonlocal last_percent
        percent = int(current * 100 / total)
        if percent - last_percent >= 5:
            last_percent = percent
            await safe_api_call(progress_msg.edit_text, f"⬇ Downloading: {percent}%")

    file_path = await safe_api_call(
        app.download_media,
        media,
        file_name=file_path,
        progress=download_progress
    )

    log("DOWNLOAD", f"Completed: {file_name}")

    await safe_api_call(progress_msg.edit_text, "⬆ Uploading: 0%")
    last_percent = 0
    caption = f"{file_name}"

    log("UPLOAD", f"Uploading: {file_name}")

    async def upload_progress(current, total):
        nonlocal last_percent
        percent = int(current * 100 / total)
        if percent - last_percent >= 5:
            last_percent = percent
            await safe_api_call(progress_msg.edit_text, f"⬆ Uploading: {percent}%")

    try:
        ext = file_name.lower().split(".")[-1]
        video_ext = ["mp4", "mkv", "mov", "webm"]
        image_ext = ["jpg", "jpeg", "png", "webp"]
        audio_ext = ["mp3", "m4a", "aac", "ogg", "wav"]

        if ext in video_ext:
            thumb = os.path.join(DOWNLOAD_DIR, "thumb.jpg")
            random_thumbnail(file_path, thumb)

            width, height, duration = get_video_metadata(file_path)

            await safe_api_call(
                app.send_video,
                message.chat.id,
                file_path,
                thumb=thumb,
                caption=caption,
                supports_streaming=True,
                duration=duration,
                width=width,
                height=height,
                progress=upload_progress
            )

            if os.path.exists(thumb):
                os.remove(thumb)

        elif ext in image_ext:
            await safe_api_call(
                app.send_photo,
                message.chat.id,
                file_path,
                caption=caption
            )

        elif ext in audio_ext:
            await safe_api_call(
                app.send_audio,
                message.chat.id,
                file_path,
                caption=caption,
                file_name=file_name
            )

        else:
            width, height, duration = get_video_metadata(file_path)

            await safe_api_call(
                app.send_video,
                message.chat.id,
                file_path,
                caption=caption,
                supports_streaming=True,
                duration=duration,
                width=width,
                height=height,
                progress=upload_progress
            )

        log("UPLOAD", f"Completed: {file_name}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            log("CLEANUP", f"Removed file: {file_name}")

    await safe_api_call(progress_msg.edit_text, "Task Done")


# ========= COMMANDS =========
@app.on_message(filters.command("download") & filters.reply)
async def download_handler(client: Client, message: Message):
    global queue

    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Unauthorized.")

    if len(queue) >= MAX_QUEUE:
        return await message.reply_text("Queue full (max 5 items).")

    media_msg = message.reply_to_message
    media = media_msg.document or media_msg.video or media_msg.audio or media_msg.photo
    file_name = getattr(media, "file_name", "photo")

    queue.append(message)
    log("QUEUE", f"Added: {file_name} (position {len(queue)})")

    await message.reply_text(f"Added to queue. Position: {len(queue)}")
    await process_queue()


@app.on_message(filters.command("queue"))
async def show_queue(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return

    if not queue:
        return await message.reply_text("Queue is empty.")

    text = "Current Queue:\n"
    for i, msg in enumerate(queue, start=1):
        media = msg.reply_to_message
        file = media.document or media.video or media.audio or media.photo
        name = getattr(file, "file_name", "photo")
        text += f"{i}. {name}\n"

    await message.reply_text(text)


@app.on_message(filters.command("cancel"))
async def cancel_handler(client: Client, message: Message):
    global current_task, queue

    if message.from_user.id != OWNER_ID:
        return

    if current_task and not current_task.done():
        current_task.cancel()

    queue.clear()
    log("CANCEL", "Cancelled current task and cleared queue")

    await message.reply_text("Current task cancelled & queue cleared.")


log("INFO", "Bot started and ready")
app.run()