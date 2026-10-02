import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.95.199.1', username='raspberry', password='pi19', timeout=10)

sftp = ssh.open_sftp()
with sftp.file('/home/raspberry/GaTDSEQ/templates/lite.html', 'r') as f:
    html = f.read().decode('utf-8')

# Replace the title
html = html.replace('<h1>GaTDSEQ <span style="color: #666; font-size: 16px; font-weight: 500; letter-spacing: 2px;">// NODE ALPHA</span></h1>', 
                    '<h1>GaTDSEQ <span style="color: #666; font-size: 13px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;">// Raspberry Pi 3 Model B Rev 1.2</span></h1>')

with sftp.file('/home/raspberry/GaTDSEQ/templates/lite.html', 'w') as f:
    f.write(html.encode('utf-8'))
sftp.close()

# Restart the server to clear cache
ssh.exec_command("pkill -f server.py")
import time; time.sleep(1)
ssh.exec_command("cd /home/raspberry/GaTDSEQ && nohup .venv/bin/python server.py > server.log 2>&1 &")

ssh.close()
print("Title updated with Pi 3!")
