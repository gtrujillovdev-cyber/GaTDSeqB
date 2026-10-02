with open("bot.py", "r") as f:
    code = f.read()

target = '''def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Error sending telegram:", e)'''

repl = '''import threading

def _send_telegram_async(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Error sending telegram:", e)

def send_telegram(msg):
    threading.Thread(target=_send_telegram_async, args=(msg,), daemon=True).start()'''

code = code.replace(target, repl)

with open("bot.py", "w") as f:
    f.write(code)
print("Patched!")
