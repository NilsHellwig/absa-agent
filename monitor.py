import os
import time
import threading
import paramiko
from dotenv import load_dotenv

load_dotenv()

class GPUMonitor:
    def __init__(self):
        self.host = os.getenv("SSH_HOST")
        self.user = os.getenv("SSH_USER")
        self.password = os.getenv("SSH_PASSWORD")
        self.wattage_readings = []
        self._stop_event = threading.Event()
        self._thread = None
        self._ssh = None

    def _connect(self):
        try:
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh.connect(self.host, username=self.user, password=self.password, timeout=5)
            return True
        except Exception as e:
            print(f"  [GPU MONITOR] SSH Connection failed: {e}")
            return False

    def _monitor_loop(self):
        if not self._ssh:
            return
            
        while not self._stop_event.is_set():
            try:
                # nvidia-smi command to get current power draw in Watts
                stdin, stdout, stderr = self._ssh.exec_command("nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits")
                output = stdout.read().decode().strip()
                if output:
                    self.wattage_readings.append(float(output))
                time.sleep(0.1)
            except Exception:
                break

    def start(self):
        if self._connect():
            self._stop_event.clear()
            self.wattage_readings = []
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._ssh:
            self._ssh.close()
            
        if self.wattage_readings:
            return sum(self.wattage_readings) / len(self.wattage_readings)
        return 0.0

class TrackStep:
    def __init__(self, step_name):
        self.step_name = step_name
        self.monitor = GPUMonitor()
        self.start_time = None

    def __enter__(self):
        print(f"  [METRICS] Starting monitor for '{self.step_name}'...")
        self.monitor.start()
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        avg_wattage = self.monitor.stop()
        print(f"  [METRICS] Step '{self.step_name}' finished. Duration: {duration:.2f}s, Avg GPU Power: {avg_wattage:.2f}W")
        self.result = {
            "step": self.step_name,
            "duration": duration,
            "avg_gpu_power_watts": avg_wattage
        }
