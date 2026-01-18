import serial
import time
import tkinter as tk
from tkinter import messagebox

# ---------------- CONFIG ----------------
USB_PORT = '/dev/ttyUSB0'  # Check with: ls /dev/ttyUSB*
BAUD_RATE = 9600
EXPECTED_COACHES = [1, 2, 3, 4]  # Known coach IDs
REFRESH_INTERVAL = 3000  # ms
TIMEOUT = 2.0  # seconds for serial responses

# ---------------- SERIAL ----------------
try:
    ser = serial.Serial(USB_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(3)  # Allow USB and Arduino to settle
    ser.flushInput()
    print("✅ Serial port opened successfully")
except Exception as e:
    print(f"❌ Cannot open serial port: {e}")
    print("Check: ls /dev/ttyUSB*")
    exit(1)

# ---------------- DATA STRUCTURE ----------------
# Linked list representation: {coach_id: {'left':id, 'right':id, 'temp':float, 'status':str}}
train_map = {}
active_coaches = []  # Only coaches that responded

# ---------------- SERIAL FUNCTIONS ----------------
def send_command(cmd):
    """Send command to Arduino gateway"""
    ser.write((cmd + '\n').encode())
    ser.flush()
    print(f"📤 Sent: {cmd}")

def read_response(timeout=TIMEOUT):
    """Read response from Arduino with timeout"""
    start = time.time()
    buffer = ""
    
    while time.time() - start < timeout:
        if ser.in_waiting:
            try:
                char = ser.read(1).decode('utf-8', errors='ignore')
                if char == '\n':
                    buffer = buffer.strip()
                    if buffer:
                        print(f"📥 Received: {buffer}")
                        return buffer
                    buffer = ""
                else:
                    buffer += char
            except Exception as e:
                print(f"⚠️ Read error: {e}")
                continue
    
    print(f"⏱️ Timeout waiting for response")
    return None

# ---------------- TRAIN MAPPING ----------------
def request_map():
    """Request topology from all coaches"""
    print("\n🔍 === MAPPING TRAIN TOPOLOGY ===")
    global active_coaches
    active_coaches = []
    
    for cid in EXPECTED_COACHES:
        print(f"\n🔎 Requesting map from Coach {cid}...")
        send_command(f"MAP,{cid}")
        time.sleep(0.2)  # Give time for processing
        
        resp = read_response(timeout=2.0)
        
        if resp and resp.startswith("MAP"):
            try:
                parts = resp.split(',')
                if len(parts) >= 4:
                    coach = int(parts[1])
                    left = int(parts[2])
                    right = int(parts[3])
                    
                    train_map[coach] = {
                        'left': left,
                        'right': right,
                        'temp': None,
                        'status': 'unknown'
                    }
                    active_coaches.append(coach)
                    print(f"✅ Coach {coach}: LEFT={left}, RIGHT={right}")
            except Exception as e:
                print(f"❌ Parse error for Coach {cid}: {e}")
        elif resp and resp.startswith("TIMEOUT"):
            print(f"⚠️ Coach {cid} not responding (may not be connected)")
        else:
            print(f"❌ No valid response from Coach {cid}")
    
    print(f"\n✅ Active coaches: {sorted(active_coaches)}")
    print(f"📊 Train map: {train_map}\n")

# ---------------- TEMPERATURE UPDATE ----------------
def update_temps():
    """Request temperature from all active coaches"""
    for cid in active_coaches:
        send_command(f"TEMP,{cid}")
        time.sleep(0.15)
        
        resp = read_response(timeout=1.5)
        
        if resp and resp.startswith("TEMP"):
            try:
                parts = resp.split(',')
                if len(parts) >= 3:
                    coach = int(parts[1])
                    temp = float(parts[2])
                    
                    if coach in train_map:
                        train_map[coach]['temp'] = temp
                        
                        # Determine status
                        if temp < 50:
                            train_map[coach]['status'] = 'safe'
                        elif temp < 70:
                            train_map[coach]['status'] = 'warning'
                        else:
                            train_map[coach]['status'] = 'danger'
                        
                        print(f"🌡️ Coach {coach}: {temp}°C [{train_map[coach]['status']}]")
            except Exception as e:
                print(f"❌ Temperature parse error: {e}")
    
    draw_train()
    root.after(REFRESH_INTERVAL, update_temps)

# ---------------- GUI (OPTIMIZED FOR 3.5" TFT) ----------------
root = tk.Tk()
root.title("Train Monitor")
root.geometry("480x320")  # 3.5" TFT resolution
root.configure(bg='#0a0e27')

# Optional: Fullscreen mode (uncomment if needed)
# root.attributes('-fullscreen', True)
# root.bind('<Escape>', lambda e: root.destroy())

# Title bar (compact)
title = tk.Label(root, text="TRAIN MONITOR", 
                 font=("Arial", 12, "bold"), fg="#00d4ff", bg='#0a0e27')
title.pack(pady=3)

# Canvas for train visualization
canvas = tk.Canvas(root, width=480, height=240, bg='#1a1f3a', highlightthickness=0)
canvas.pack()

# Status bar (compact)
status_label = tk.Label(root, text="Initializing...", font=("Arial", 8), 
                        fg="#ffffff", bg='#0a0e27')
status_label.pack(pady=2)

# Control buttons (compact)
button_frame = tk.Frame(root, bg='#0a0e27')
button_frame.pack(pady=2)

def manual_refresh():
    request_map()
    update_temps()

def quit_app():
    ser.close()
    root.destroy()

refresh_btn = tk.Button(button_frame, text="↻ Refresh", command=manual_refresh, 
                        font=("Arial", 8), bg='#1e3a5f', fg='white', 
                        width=10, height=1, relief=tk.FLAT)
refresh_btn.pack(side=tk.LEFT, padx=3)

quit_btn = tk.Button(button_frame, text="✕ Exit", command=quit_app, 
                     font=("Arial", 8), bg='#5f1e1e', fg='white', 
                     width=10, height=1, relief=tk.FLAT)
quit_btn.pack(side=tk.LEFT, padx=3)

def draw_train():
    """Draw train as linked list (optimized for small screen)"""
    canvas.delete("all")
    
    if not active_coaches:
        canvas.create_text(240, 120, text="NO COACHES", 
                          font=("Arial", 14, "bold"), fill="#ff4444")
        status_label.config(text="❌ No active coaches")
        return
    
    # Build order from linked list (find head)
    ordered_coaches = []
    
    # Find first coach (left = 0)
    first_coach = None
    for cid, info in train_map.items():
        if info['left'] == 0:
            first_coach = cid
            break
    
    if first_coach is None and train_map:
        first_coach = min(train_map.keys())
    
    # Traverse linked list
    current = first_coach
    visited = set()
    
    while current and current in train_map and current not in visited:
        ordered_coaches.append(current)
        visited.add(current)
        next_coach = train_map[current]['right']
        if next_coach == 0:
            break
        current = next_coach
    
    # Calculate layout for small screen
    num_coaches = len(ordered_coaches)
    
    if num_coaches <= 2:
        # Large boxes for 1-2 coaches
        box_width = 100
        box_height = 80
        spacing = 130
        start_x = (480 - (num_coaches * spacing - 30)) // 2
    elif num_coaches == 3:
        # Medium boxes for 3 coaches
        box_width = 90
        box_height = 70
        spacing = 110
        start_x = 50
    else:
        # Compact boxes for 4+ coaches
        box_width = 80
        box_height = 60
        spacing = 90
        start_x = 30
    
    y = 120  # Vertical center
    
    for i, cid in enumerate(ordered_coaches):
        info = train_map[cid]
        temp = info.get('temp')
        status = info.get('status', 'unknown')
        
        # Color coding
        if status == 'safe':
            color = '#27ae60'
            text_color = 'white'
        elif status == 'warning':
            color = '#f39c12'
            text_color = 'black'
        elif status == 'danger':
            color = '#e74c3c'
            text_color = 'white'
        else:
            color = '#7f8c8d'
            text_color = 'white'
        
        # Calculate position
        x_pos = start_x + i * spacing
        
        # Draw coach box with rounded effect (using multiple rectangles)
        canvas.create_rectangle(x_pos, y - box_height//2, 
                               x_pos + box_width, y + box_height//2, 
                               fill=color, outline='#ffffff', width=2)
        
        # Coach ID
        canvas.create_text(x_pos + box_width//2, y - box_height//2 + 12, 
                          text=f"C{cid}", 
                          font=("Arial", 10, "bold"), fill=text_color)
        
        # Temperature
        if temp is not None:
            temp_text = f"{temp:.1f}°"
            font_size = 14 if num_coaches <= 3 else 12
        else:
            temp_text = "--°"
            font_size = 12
            
        canvas.create_text(x_pos + box_width//2, y + 5, 
                          text=temp_text, 
                          font=("Arial", font_size, "bold"), fill=text_color)
        
        # Status indicator (small dot)
        dot_y = y + box_height//2 - 8
        if status == 'safe':
            dot_color = '#2ecc71'
        elif status == 'warning':
            dot_color = '#f1c40f'
        elif status == 'danger':
            dot_color = '#c0392b'
        else:
            dot_color = '#95a5a6'
            
        canvas.create_oval(x_pos + box_width//2 - 4, dot_y - 4,
                          x_pos + box_width//2 + 4, dot_y + 4,
                          fill=dot_color, outline='')
        
        # Draw link arrow to next coach
        if i < num_coaches - 1:
            arrow_start_x = x_pos + box_width
            arrow_end_x = start_x + (i + 1) * spacing
            canvas.create_line(arrow_start_x + 2, y, 
                              arrow_end_x - 2, y, 
                              arrow=tk.LAST, fill='#3498db', width=2)
    
    # Legend (compact)
    legend_y = 220
    legend_items = [
        ("●", '#27ae60', "Safe"),
        ("●", '#f39c12', "Warn"),
        ("●", '#e74c3c', "Hot")
    ]
    
    legend_x = 20
    for symbol, color, label in legend_items:
        canvas.create_text(legend_x, legend_y, 
                          text=symbol, font=("Arial", 16), fill=color)
        canvas.create_text(legend_x + 15, legend_y, 
                          text=label, font=("Arial", 7), fill='#ffffff', anchor='w')
        legend_x += 70
    
    # Update status bar
    total = len(active_coaches)
    safe = sum(1 for c in train_map.values() if c.get('status') == 'safe')
    warn = sum(1 for c in train_map.values() if c.get('status') == 'warning')
    danger = sum(1 for c in train_map.values() if c.get('status') == 'danger')
    
    status_label.config(text=f"Active: {total} | Safe: {safe} | Warn: {warn} | Hot: {danger}")

# ---------------- MAIN ----------------
print("\n🚂 === STARTING TRAIN MONITORING SYSTEM ===\n")

# Initial mapping
time.sleep(1)
request_map()

if not active_coaches:
    # Show warning but continue (allows testing)
    print("⚠️ Warning: No coaches detected!")
    status_label.config(text="⚠️ No coaches - Check connections")
else:
    print(f"✅ Success: Found {len(active_coaches)} coaches: {sorted(active_coaches)}")

# Start temperature monitoring
root.after(2000, update_temps)

try:
    root.mainloop()
except KeyboardInterrupt:
    print("\n\n🛑 Shutting down...")
finally:
    ser.close()
    print("✅ Serial port closed")