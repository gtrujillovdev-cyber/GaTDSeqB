with open("bot.py", "r") as f:
    code = f.read()

code = code.replace("global TIMEFRAME, STATE_FILE, TRADES_FILE", "# global TIMEFRAME, STATE_FILE, TRADES_FILE")

with open("bot.py", "w") as f:
    f.write(code)
print("bot.py fixed global keyword!")
