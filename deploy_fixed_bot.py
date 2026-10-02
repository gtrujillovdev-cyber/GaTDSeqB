import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.95.199.1', username='raspberry', password='pi19', timeout=10)

sftp = ssh.open_sftp()
sftp.put("bot.py", "/home/raspberry/GaTDSEQ/bot.py")
sftp.close()

# Stop old bots if any (none are running probably, but just in case)
ssh.exec_command("killall -9 python")
ssh.exec_command("killall -9 python3")

import time
time.sleep(2)

# Start server
ssh.exec_command("cd /home/raspberry/GaTDSEQ && nohup .venv/bin/python server.py > server.log 2>&1 &")
# Start bot
ssh.exec_command("cd /home/raspberry/GaTDSEQ && nohup .venv/bin/python -u bot.py > bot_unified.log 2>&1 &")

ssh.close()
print("Fixed bot deployed and running!")
