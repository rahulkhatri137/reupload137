aria2c \
  --enable-rpc \
  --rpc-listen-port=6800 \
  --rpc-listen-all=false \
  --rpc-allow-origin-all \
  --max-connection-per-server=8 \
  --split=8 \
  --min-split-size=1M \
  --daemon=true
python bot.py
