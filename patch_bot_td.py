with open("bot.py", "r") as f:
    code = f.read()

target = 'print(f"Precio: ${current_price:.2f} | TD Count: {count} | RSI: {rsi:.2f} | EMA200: {ema200:.2f}")'
replacement = target + '''
    
    # Save the current TD Count to state so the dashboard can display it
    state["td_count"] = int(count)
    import json
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
'''

code = code.replace(target, replacement)
with open("bot.py", "w") as f:
    f.write(code)
print("bot.py patched with TD count!")
