# Telegram ReUploader Bot

Simple telegram bot to download from telegram or web and upload to telegram. 
For deployment on Termux
Powered by [@Bots137](https://t.me/Bots137)

## Features

- Owner-only access
- Reply-based /download command
- Queue system (max 5 items)
- Always uploads as media
- Auto cleanup after upload
- Clean Termux-friendly logging
- FloodWait handling
- Supports streaming for videos
- Parallel chunk upload
- No concurrent heavy processing for low CPU/RAM footprint
- Support custom file name
- **Support Web download** now

## Requirements

-   Python 3.9+
-   ffmpeg

## Bot Setup

- Download Termux from f-droid [here](https://f-droid.org/en/packages/com.termux)
- Setup termux and install dependencies 
``` bash
pkg update && pkg upgrade -y
pkg install python ffmpeg git -y
pip install --upgrade pip
pip install pyrogram tgcrypto
```

- Run bot:

``` bash
python bot.py
```

## Configure

Edit your Telegram credentials in bot.py:

    API_ID = your_id
    API_HASH = "your_hash"
    BOT_TOKEN = "your_token"
    OWNER_ID = your_user_id
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

<details>
<summary>Use custom file name</summary>

- Telegram File: `/download custom_name.ext`
- Web File: `/download URL | File_name.ext`
</details>

## Commands via [@BotFather](https://t.me/BotFather)
~~~
download - Reply to file
queue - Show queue
cancel - Cancel current task
~~~

## Performance Notes (Android)

- Workers set to 12 (balanced for mobile)
- Single file processing (no overheating)
- Queue prevents overload
- **If your phone heats**:
Reduce WORKERS from 12 → 8
