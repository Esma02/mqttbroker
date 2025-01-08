import os
import sys
import subprocess

# Django projenizin dizini
os.chdir(r'C:\Users\Hp\Desktop\project\mqttbroker')

# Django sunucusunu başlat
subprocess.run([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000'])