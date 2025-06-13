import os
import time
import subprocess
import psutil
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("system.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()
configuration_complete = str(os.environ.get('DEVICE_ID_CONFIGURED'))

# Function to check if a process is already running
def is_process_running(script_name):
    for proc in psutil.process_iter(attrs=["cmdline"]):
        cmdline = proc.info["cmdline"]
        if cmdline and script_name in " ".join(cmdline):
            return True
    return False

# Function to start a script with Popen
def start_script(script_name):
    logging.info(f"Starting script: {script_name}")
    return subprocess.Popen(["python3", script_name])

if __name__ == '__main__':
    if configuration_complete != "Yes":
        load_dotenv(override=True)

    # Scripts to run and monitor
    scripts = [
        "src/mod_data_collector.py",
        "src/sort_json.py",
        "src/upload_json.py"
    ]

    # Dictionary to store process handles
    processes = {}

    for script in scripts:
        if not is_process_running(script):
            processes[script] = start_script(script)
        else:
            logging.info(f"{script} is already running. Skipping...")

    # Monitor and restart scripts if they crash
    while True:
        time.sleep(10)
        for script, process in list(processes.items()):
            if process.poll() is not None:  # Process has exited
                logging.warning(f"{script} has stopped. Restarting...")
                processes[script] = start_script(script)
