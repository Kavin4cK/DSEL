import serial
import time
import tkinter as tk
from tkinter import ttk

# ---------------- CONFIG ----------------
USB_PORT = '/dev/ttyUSB0'  # Check with `ls /dev/ttyUSB*`
BAUD_RATE = 9600
COACH_IDS = [1, 2, 3, 4]   # Known coach IDs

REFRESH_INTERVAL = 2000    # ms

# ---------------- SERIAL ----------------
try:
    ser = serial.Serial(USB_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Allow USB to settle
except Exception as e:
    print("Cannot open serial port:", e)
    exit(1)

# ---------------- DATA STRUCTURE ----------------
train_map = {}  # {coach_id: {'left':id, 'right':id, 'temp':float}}

# ---------------- GUI ----------------
root = tk.Tk()
root.title("Train Temperature Monitor")
root.geometry("480x320")  # Adapt to 3.5" TFT

canvas = tk.Canvas(root, width=480, height=320, bg='white')
canvas.pack()

def draw_train():
    canvas.delete("all")
    x = 50
    y = 150
    radius = 30

    # Build order from linked list: find engine (left=None)
    first_id = None
    for cid, info in train_map.items():
        if info['left'] in [0, None]:
            first_id = cid
            break

    order = []
    curr = first_id
    while curr and curr in train_map:
        order.append(curr)
        nxt = train_map[curr]['right']
        if nxt == 0 or nxt is None or nxt in order:
            break
        curr = nxt

    # Draw each coach
    for cid in order:
        info = train_map[cid]
        canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill="lightblue")
        canvas.create_text(x, y-10, text=f"Coach {cid}", font=("Arial", 12, "bold"))
        temp = info.get('temp', '--')
        canvas.create_text(x, y+10, text=f"Temp: {temp}", font=("Arial", 12))
        x += 100  # space between coaches

# ---------------- SERIAL FUNCTIONS ----------------
def send_command(cmd):
    ser.write((cmd + '\n').encode())

def read_response(timeout=1.0):
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            line = ser.readline().decode().strip()
            if line:
                return line
    return None

# ---------------- TRAIN MAPPING ----------------
def request_map():
    for cid in COACH_IDS:
        send_command(f"MAP,{cid}")
        resp = read_response()
        if resp and resp.startswith("MAP"):
            parts = resp.split(',')
            if len(parts) >= 4:
                coach = int(parts[1])
                left = int(parts[2])
                right = int(parts[3])
                if coach not in train_map:
                    train_map[coach] = {}
                train_map[coach]['left'] = left
                train_map[coach]['right'] = right
        else:
            print(f"No response from coach {cid}")

# ---------------- TEMPERATURE UPDATE ----------------
def update_temps():
    for cid in COACH_IDS:
        send_command(f"TEMP,{cid}")
        resp = read_response()
        if resp and resp.startswith("TEMP"):
            parts = resp.split(',')
            if len(parts) >= 3:
                coach = int(parts[1])
                temp = parts[2]
                if coach not in train_map:
                    train_map[coach] = {}
                train_map[coach]['temp'] = temp
    draw_train()
    root.after(REFRESH_INTERVAL, update_temps)

# ---------------- MAIN ----------------
request_map()
update_temps()
root.mainloop()
