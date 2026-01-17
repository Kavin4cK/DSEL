import serial
import time
import threading
import tkinter as tk

# ---------------- CONFIG ----------------
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600
COACH_IDS = [1, 2, 3, 4]
REQUEST_DELAY = 0.15  # seconds

# ---------------- SERIAL SETUP ----------------
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # allow Arduino reset
except Exception as e:
    print("Serial open failed:", e)
    exit(1)

# ---------------- DATA STORAGE ----------------
neighbors = {}      # {id: (left, right)}
temperatures = {}   # {id: temp}

# ---------------- SERIAL HELPERS ----------------
def send(cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()

def read_response(timeout=0.5):
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            return ser.readline().decode().strip()
    return None

# ---------------- TRAIN MAPPING ----------------
def map_train():
    neighbors.clear()
    for cid in COACH_IDS:
        send(f"MAP,{cid}")
        time.sleep(REQUEST_DELAY)
        resp = read_response()
        if resp and resp.startswith("MAP"):
            _, rid, left, right = resp.split(",")
            neighbors[int(rid)] = (int(left), int(right))

# ---------------- TEMP UPDATE LOOP ----------------
def poll_temperatures():
    while True:
        for cid in COACH_IDS:
            send(f"TEMP,{cid}")
            time.sleep(REQUEST_DELAY)
            resp = read_response()
            if resp and resp.startswith("TEMP"):
                _, rid, temp = resp.split(",")
                temperatures[int(rid)] = float(temp)
        update_gui()
        time.sleep(1)

# ---------------- GUI ----------------
root = tk.Tk()
root.title("Indian Railways – Hot Axle Monitor")
root.geometry("480x320")
root.configure(bg="black")

title = tk.Label(
    root,
    text="HOT AXLE MONITOR",
    fg="white",
    bg="black",
    font=("Arial", 16, "bold")
)
title.pack(pady=8)

coach_labels = {}

def update_gui():
    for cid in COACH_IDS:
        temp = temperatures.get(cid, "--")
        left, right = neighbors.get(cid, ("-", "-"))
        text = f"Coach {cid} | Temp: {temp} °C | L:{left} R:{right}"
        coach_labels[cid].config(text=text)

for cid in COACH_IDS:
    lbl = tk.Label(
        root,
        text=f"Coach {cid} | waiting...",
        fg="cyan",
        bg="black",
        font=("Arial", 12)
    )
    lbl.pack(anchor="w", padx=10, pady=4)
    coach_labels[cid] = lbl

# ---------------- START SYSTEM ----------------
map_train()
threading.Thread(target=poll_temperatures, daemon=True).start()
root.mainloop()
