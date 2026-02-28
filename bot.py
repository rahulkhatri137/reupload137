# Telegram ReUploader Bot
# Powered by @Bots137

import time
import os
import asyncio
import subprocess
import json
import logging
import aiohttp
import glob
import re
from datetime import timedelta
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# --- CONFIGURATION ---
API_ID = 123456
API_HASH = "API_HASH"
BOT_TOKEN = "BOT_TOKEN"
OWNER_ID = 123456789
# ---------------------

logging.getLogger("hydrogram").setLevel(logging.CRITICAL)

def log_stage(stage, source, filename, extra=""):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{timestamp} | {stage:<10} | {source:<5} | {filename} {extra}")

def cleanup_dir():
    extensions = ['*.mp4', ['*.mkv'], '*.zip', '*.jpg', '*.webm', '*.aria2', '*.parts']
    for ext in extensions:
        for file in glob.glob(str(ext)):
            try: os.remove(file)
            except: pass

app = Client("reupload137_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
task_queue = asyncio.Queue()
active_tasks = {}  
waiting_list = []  

# --- UTILITIES ---

async def get_url_info(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=10) as resp:
                name = os.path.basename(resp.url.path).split('?')[0] or "file.mp4"
                size = int(resp.headers.get("Content-Length", 0))
                return name, size
    except: return "file.mp4", 0

def get_metadata(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json", file_path]
        output = subprocess.check_output(cmd).decode('utf-8')
        data = json.loads(output)
        duration = int(float(data['format'].get('duration', 0)))
        w, h = 0, 0
        for s in data.get('streams', []):
            if s.get('width'):
                w, h = int(s['width']), int(s['height'])
                break
        return duration, w, h
    except: return 0, 0, 0

def humanbytes(size):
    if not size: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

async def progress_ui(current, total, message, start_time, action, user_id):
    if active_tasks.get(user_id, {}).get("is_cancelled"):
        raise StopIteration("USER_CANCELLED")
    now = time.time()
    diff = now - start_time
    if round(diff % 5.00) == 0 or current == total:
        percentage = (current * 100 / total) if total > 0 else 0
        speed = current / (diff if diff > 0 else 1)
        eta = (total - current) / speed if speed > 0 and total > 0 else 0
        bar = "▰" * int(percentage / 10) + "▱" * (10 - int(percentage / 10))
        src_tag = "🌐 Aria2" if active_tasks[user_id]['source'] == "Aria2" else "🔹 TG"
        status_text = (f"🚀 **{action}** | {src_tag}\n📄 `{active_tasks[user_id]['filename']}`\n\n"
                       f"┌ {bar} **{percentage:.1f}%**\n├ 🚀 **Speed:** {humanbytes(speed)}/s\n"
                       f"├ ⏳ **ETA:** {str(timedelta(seconds=int(eta)))}\n└ 📂 **Size:** {humanbytes(current)} / {humanbytes(total)}")
        try: await message.edit_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Terminate", callback_data=f"cancel_{user_id}")]]))
        except: pass

async def aria2_download(url, filename, message, user_id):
    start_time = time.time()
    cmd = ["aria2c", "-x", "12", "-s", "12", "-k", "1M", "--summary-interval=1", "--console-log-level=notice", "-d", ".", "-o", filename, url]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        line = await process.stdout.readline()
        if not line: break
        line = line.decode().strip()
        if active_tasks.get(user_id, {}).get("is_cancelled"):
            process.terminate()
            raise StopIteration("USER_CANCELLED")
        match = re.search(r'\((\d+)%\)', line)
        if match:
            perc = int(match.group(1))
            total = active_tasks[user_id]['total_size']
            current = int((perc / 100) * total)
            await progress_ui(current, total, message, start_time, "Downloading", user_id)
    await process.wait()
    return filename

# --- WORKER ---

async def worker():
    while True:
        user_id, cmd_msg, status_msg, custom_name, url, queue_name = await task_queue.get()
        cleanup_dir()
        source = "Aria2" if url else "TG"
        
        if url:
            orig_name, total_size = await get_url_info(url)
        else:
            replied = cmd_msg.reply_to_message
            orig_name = getattr(replied.document or replied.video or replied.audio, "file_name", "file.mp4")
            total_size = getattr(replied.document or replied.video or replied.audio, "file_size", 0)

        final_filename = custom_name if custom_name else orig_name
        active_tasks[user_id] = {"is_cancelled": False, "filename": final_filename, "total_size": total_size, "source": source, "queue_ref": queue_name}
        
        file_path = thumb_path = temp_path = None

        try:
            log_stage("DOWNLOAD", source, final_filename, "started")
            await status_msg.edit_text(f"🚀 **Processing {source}...**\n`{final_filename}`")
            
            if url:
                file_path = await aria2_download(url, final_filename, status_msg, user_id)
            else:
                temp_path = await app.download_media(cmd_msg.reply_to_message, progress=progress_ui, progress_args=(status_msg, time.time(), "Downloading", user_id))
                file_path = os.path.join(os.path.dirname(temp_path), final_filename)
                os.rename(temp_path, file_path)

            if active_tasks.get(user_id, {}).get("is_cancelled"): raise StopIteration("USER_CANCELLED")

            duration, width, height = get_metadata(file_path)
            thumb_path = f"{file_path}.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(duration / 2), "-i", file_path, "-vframes", "1", "-q:v", "2", thumb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            log_stage("UPLOAD", source, final_filename, "started")
            await app.send_video(chat_id=cmd_msg.chat.id, video=file_path, duration=duration, width=width, height=height, thumb=thumb_path if os.path.exists(thumb_path) else None, caption=f"`{final_filename}`", supports_streaming=True, progress=progress_ui, progress_args=(status_msg, time.time(), "Uploading", user_id))
            
            log_stage("COMPLETE", source, final_filename)
            try: await cmd_msg.delete()
            except: pass

        except StopIteration:
            log_stage("CANCELLED", source, final_filename)
            try: await app.send_message(cmd_msg.chat.id, f"🚫 **Task Terminated:** `{final_filename}`")
            except: pass
        except Exception as e:
            log_stage("ERROR", source, final_filename, f"!! {str(e)}")
            try: await app.send_message(cmd_msg.chat.id, f"❌ **Error:** `{e}`")
            except: pass
        finally:
            if queue_name in waiting_list: waiting_list.remove(queue_name)
            if temp_path and os.path.exists(temp_path): os.remove(temp_path)
            if file_path and os.path.exists(file_path): os.remove(file_path)
            if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
            try: await status_msg.delete()
            except: pass
            active_tasks.pop(user_id, None)
            task_queue.task_done()

# --- COMMAND HANDLER ---

@app.on_message(filters.command(["download", "dl"]) & filters.private)
async def unified_download(client, message):
    if message.from_user.id != OWNER_ID: return
    
    url = None
    custom_name = None
    queue_display_name = ""
    parts = message.text.split(" ", 2)
    
    # 1. Check for URL Download
    if len(parts) > 1 and (parts[1].startswith("http://") or parts[1].startswith("https://")):
        url = parts[1].strip()
        queue_display_name = url
        if len(parts) > 2:
            custom_name = parts[2].strip()
            queue_display_name = custom_name

    # 2. Check for Telegram File Download
    elif message.reply_to_message:
        replied = message.reply_to_message
        if not (replied.document or replied.video or replied.audio):
            return await message.reply_text("❌ Reply to a valid file or provide a URL.")
        queue_display_name = getattr(replied.document or replied.video or replied.audio, "file_name", "Telegram_File")
        if len(parts) > 1:
            custom_name = message.text.split(None, 1)[1].strip()
            queue_display_name = custom_name
            
    else:
        return await message.reply_text("❓ **Usage:**\n• Reply to file: `/dl [custom name]`\n• Send URL: `/dl [url] [custom name]`")

    waiting_list.append(queue_display_name)
    pos = len(waiting_list)
    
    status_text = f"📥 **Queued** (Pos #{pos})\n`{queue_display_name}`" if (pos > 1 or active_tasks) else "🔎 **Initializing...**"
    status_msg = await message.reply_text(status_text)
    
    log_stage("QUEUED", "SYS", custom_name or queue_display_name)
    await task_queue.put((message.from_user.id, message, status_msg, custom_name, url, queue_display_name))

@app.on_message(filters.command("queue"))
async def cmd_queue(client, message):
    if message.from_user.id != OWNER_ID: return
    text = "📊 **Bot Status**\n\n**🔄 Processing:**\n"
    text += "\n".join([f"• `{v['filename']}`" for v in active_tasks.values()]) if active_tasks else "• _Idle_"
    text += "\n\n**⌛ Queue:**\n"
    text += "\n".join([f"#{i+1}: `{f}`" for i, f in enumerate(waiting_list)]) if waiting_list else "• _Empty_"
    await message.reply_text(text)
    await message.delete()

@app.on_message(filters.command("cancel"))
async def cmd_cancel(client, message):
    if message.from_user.id == OWNER_ID and active_tasks:
        user_id = next(iter(active_tasks))
        active_tasks[user_id]["is_cancelled"] = True
    await message.delete()

@app.on_callback_query(filters.regex("^cancel_"))
async def cb_cancel(client, callback):
    if callback.from_user.id == OWNER_ID:
        uid = int(callback.data.split("_")[1])
        if uid in active_tasks:
            active_tasks[uid]["is_cancelled"] = True
            await callback.answer("Cancelling task...", show_alert=True)

if __name__ == "__main__":
    print("-" * 35 + "\n🚀 REUPLOAD137 BOT STARTED\n" + "-" * 35)
    loop = asyncio.get_event_loop()
    loop.create_task(worker())
    app.run()
