import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.95.199.1', username='raspberry', password='pi19', timeout=10)

sftp = ssh.open_sftp()
sftp.put("bot.py", "/home/raspberry/GaTDSEQ/bot.py")

# Download lite.html
with sftp.file('/home/raspberry/GaTDSEQ/templates/lite.html', 'r') as f:
    html = f.read().decode('utf-8')

# Inject TD count row after Bankroll
target_row = '<div class="row"><span class="label">Bankroll</span>'
if "TD Count" not in html:
    parts = html.split(target_row)
    if len(parts) == 2:
        td_row = '''<div class="row"><span class="label">TD Count</span><span class="value ${state.td_count == 9 || state.td_count == -9 ? 'val-green' : 'val-blue'}">${state.td_count !== undefined ? state.td_count : '--'}</span></div>
                                '''
        new_html = parts[0] + target_row + parts[1].replace('<div class="row"><span class="label">Win Rate</span>', td_row + '<div class="row"><span class="label">Win Rate</span>', 1)
        
        with sftp.file('/home/raspberry/GaTDSEQ/templates/lite.html', 'w') as f:
            f.write(new_html.encode('utf-8'))

sftp.close()

# Restart the bot
ssh.exec_command("pkill -f 'bot.py'")
import time; time.sleep(1)
ssh.exec_command("cd /home/raspberry/GaTDSEQ && nohup .venv/bin/python -u bot.py > bot_unified.log 2>&1 &")
ssh.close()
print("TD Count feature deployed!")
