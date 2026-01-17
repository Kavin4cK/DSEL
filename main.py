import tkinter as tk
import serial
import threading
import time

# ===================== SERIAL CONFIG =====================
SERIAL_PORT = "/dev/ttyACM0"   # CHANGE if needed
BAUD_RATE = 9600
REQUEST_INTERVAL = 1.5         # seconds

# ===================== GLOBALS =====================
ser = None
running = True
temps = {
    "C1": "--.-",
    "C2": "--.-",
    "C3": "--.-"
}

# ===================== SERIAL THREAD =====================
def serial_worker():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Nano reset delay
    except Exception as e:
        print("Serial error:", e)
        return

    while running:
        for coach in temps.keys():
            try:
                cmd = f"GET TEMP {coach}\n"
                ser.write(cmd.encode())

                line = ser.readline().decode().strip()
                if ":" in line:
                    cid, val = line.split(":")
                    if cid in temps:
                        temps[cid] = val
            except:
                pass

            time.sleep(REQUEST_INTERVAL)

# ===================== GUI =====================
root = tk.Tk()
root.title("Train Coach Temperature")
root.attributes("-fullscreen", True)
root.configure(bg="black")

FONT_TITLE = ("Arial", 26, "bold")
FONT_LABEL = ("Arial", 22)
FONT_VALUE = ("Arial", 28, "bold")

tk.Label(
    root, text="TRAIN TEMPERATURE MONITOR",
    font=FONT_TITLE, fg="cyan", bg="black"
).pack(pady=20)

frame = tk.Frame(root, bg="black")
frame.pack(expand=True)

labels = {}

row = 0
for coach in temps:
    tk.Label(
        frame, text=f"{coach}",
        font=FONT_LABEL, fg="white", bg="black", width=6
    ).grid(row=row, column=0, padx=20, pady=15)

    val = tk.Label(
        frame, text="--.- °C",
        font=FONT_VALUE, fg="yellow", bg="black", width=10
    )
    val.grid(row=row, column=1, padx=20)
    labels[coach] = val

    row += 1

# ===================== GUI UPDATE LOOP =====================
def update_gui():
    for coach, lbl in labels.items():
        lbl.config(text=f"{temps[coach]} °C")
    root.after(500, update_gui)

# ===================== EXIT HANDLER =====================
def on_exit(event=None):
    global running
    running = False
    try:
        if ser:
            ser.close()
    except:
        pass
    root.destroy()

root.bind("<Escape>", on_exit)

# ===================== START =====================
threading.Thread(target=serial_worker, daemon=True).start()
update_gui()
root.mainloop()
