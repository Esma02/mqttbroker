import os
from django.core.management import execute_from_command_line

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mqttbroker.settings")

if __name__ == "__main__":
    execute_from_command_line(["manage.py", "runserver"])
