with open("bot.py", "r") as f:
    code = f.read()

# Fix the broken string
broken_str = 'send_telegram(f"🤖 <b>Bot UNIFICADO Iniciado</b>\n\nControlando 5 timeframes simultáneamente para ahorrar RAM.")'
fixed_str = 'send_telegram("🤖 <b>Bot UNIFICADO Iniciado</b>\\n\\nControlando 5 timeframes simultáneamente para ahorrar RAM.")'

code = code.replace(broken_str, fixed_str)

with open("bot.py", "w") as f:
    f.write(code)
print("bot.py fixed locally!")
