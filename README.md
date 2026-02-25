# Telegram ReUploader Bot

Simple telegram bot to download from telegram or web and upload to telegram.

For deployment on **Termux**.

Powered by [@Bots137](https://t.me/Bots137)

---

## ✨ Key Features

* **Unified Command**: Use `/dl` for both URLs and Telegram files.
* **Minimalist Terminal**: Clean terminal logs for easy monitoring.
* **Dual Engine**: 🌐 **Aria2** or 🔹 **TG**.
* **Real-time Progress**: Precise progress bars with speed and ETA.
* **Auto-Cleanup**: Automatically wipes the download directory before every task to save storage.
* **Smart Queue**: Dynamic queue management with positional tracking.
* **Custom Naming**: Support for custom filenames.

---

## 📲 Termux Setup Guide

* Download Termux from f-droid [here](https://f-droid.org/en/packages/com.termux)

Follow these steps to get the bot running on your Android device:

### 1. Update & Install Dependencies

```bash
pkg update && pkg upgrade -y
pkg install python ffmpeg aria2 git -y

```

### 2. Clone and Install Requirements

```bash
git clone https://github.com/rahulkhatri137/reupload137
cd reupload137

pip install hydrogram aiohttp

```

### 3. Configure the Bot

Open `bot.py` using `nano` and fill in your credentials:

```python
API_ID = 1234567           
API_HASH = "your_hash"     
BOT_TOKEN = "your_token"   
OWNER_ID = 123456789  

```
<details>
<summary>Get Telegram variables</summary>
    
### Get Telegram API

1.  Go to https://my.telegram.org
2.  Login
3.  API development tools
4.  Create app
5.  Copy API_ID & API_HASH

### Bot Token

1.  Open Telegram
2.  Search @BotFather
3.  Get your bot API token 

</details>


### 4. Run the Bot

```bash
python bot.py

```

---

## 🤖 Bot Commands via [@BotFather](https://t.me/BotFather)

| Command | Usage | Description |
| --- | --- | --- |
| `/dl [url] [name]` | Direct URL download | Downloads from web using Aria2 engine. |
| `/dl [name]` | Reply to a TG file | Downloads TG file and renames it. |
| `/queue` | View status | Shows currently processing file and waiting list. |
| `/cancel` | Terminate task | Stops the current active download and cleans up. |

---

## 📊 Terminal Log Format


```text
HH:MM:SS | STAGE      | SRC   | FILENAME
12:05:01 | QUEUED     | Aria2 | movie.mkv
12:05:02 | DOWNLOAD   | Aria2 | movie.mkv started
12:08:40 | COMPLETE   | Aria2 | movie.mkv

```

---

## ⚠️ Requirements

* **Aria2**: Must be installed in your environment (`pkg install aria2`).
* **FFmpeg**: Required for generating video thumbnails and metadata.
* **Python 3.9+**: Recommended version.

---

