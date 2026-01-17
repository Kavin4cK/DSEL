import RPi.GPIO as GPIO
import tkinter as tk
from tkinter import Canvas
import threading
import time

# ---------------- CONFIG ----------------
COACH_IDS = [1, 2, 3, 4]      # Known coaches
TX_GPIO = 12                  # Pi TX → Nano RX (send requests)
RX_GPIO = 16                  # Pi RX ← Nano TX (receive data)
BAUD = 9600
BIT_TIME = 1.0 / BAUD
REQUEST_INTERVAL = 2          # seconds between requests
GUI_REFRESH = 500             # ms
TEMP_THRESHOLD = 50.0         # Red if temp > threshold

# ---------------- DATA STRUCTURES ----------------
class CoachNode:
    def __init__(self, coach_id, temp=0):
        self.coach_id = coach_id
        self.temp = temp
        self.left = None
        self.right = None

class TrainLinkedList:
    def __init__(self):
        self.nodes = {}
        self.head = None

    def add_bundle(self, coach_id, temp, left_id, right_id):
        if coach_id not in self.nodes:
            self.nodes[coach_id] = CoachNode(coach_id)
        node = self.nodes[coach_id]
        node.temp = temp

        if left_id != -1:
            if left_id not in self.nodes:
                self.nodes[left_id] = CoachNode(left_id)
            node.left = self.nodes[left_id]
            self.nodes[left_id].right = node

        if right_id != -1:
            if right_id not in self.nodes:
                self.nodes[right_id] = CoachNode(right_id)
            node.right = self.nodes[right_id]
            self.nodes[right_id].left = node

        self.head = self.find_head()

    def find_head(self):
        for node in self.nodes.values():
            if node.left is None:
                return node
        return None

# ---------------- GUI ----------------
class TrainGUI:
    def __init__(self, root, train):
        self.root = root
        self.train = train
        self.canvas = Canvas(root, width=480, height=320, bg="white")
        self.canvas.pack(fill="both", expand=True)
        self.root.after(GUI_REFRESH, self.draw_train)

    def draw_train(self):
        self.canvas.delete("all")
        x_start = 20
        y = 160
        width = 80
        spacing = 10

        node = self.train.head
        while node:
            color = "red" if node.temp > TEMP_THRESHOLD else "green"
            self.canvas.create_rectangle(x_start, y-30, x_start+width, y+30, fill=color)
            self.canvas.create_text(x_start+width/2, y-10, text=f"Coach {node.coach_id}", font=("Arial", 12, "bold"))
            self.canvas.create_text(x_start+width/2, y+10, text=f"{node.temp:.1f}°C", font=("Arial", 10))

            if node.right:
                self.canvas.create_line(x_start+width, y, x_start+width+spacing, y, arrow=tk.LAST, width=2)

            x_start += width + spacing
            node = node.right

        self.root.after(GUI_REFRESH, self.draw_train)

# ---------------- SOFTWARE UART ----------------
class SoftUART(threading.Thread):
    def __init__(self, train):
        super().__init__()
        self.train = train
        self.running = True
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RX_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(TX_GPIO, GPIO.OUT)
        GPIO.output(TX_GPIO, GPIO.HIGH)
        self.daemon = True

    # Send request to Nano
    def send_request(self, coach_id):
        msg = f"REQ,{coach_id}\n"
        for ch in msg:
            for i in range(8):
                GPIO.output(TX_GPIO, (ord(ch) >> i) & 1)
                time.sleep(BIT_TIME)
            time.sleep(BIT_TIME)  # stop bit
        time.sleep(0.01)

    # Read a line from RX_GPIO
    def read_line(self, timeout=1.0):
        line = ""
        start = time.time()
        while time.time() - start < timeout:
            if GPIO.input(RX_GPIO) == 0:  # start bit
                time.sleep(BIT_TIME*1.5)
                byte = 0
                for i in range(8):
                    bit = GPIO.input(RX_GPIO)
                    byte |= bit << i
                    time.sleep(BIT_TIME)
                line += chr(byte)
                time.sleep(BIT_TIME)  # stop bit
            if '\n' in line:
                line, _ = line.split('\n', 1)
                return line.strip()
        return None

    # Thread loop
    def run(self):
        while self.running:
            for coach_id in COACH_IDS:
                self.send_request(coach_id)
                line = self.read_line(timeout=1.0)
                if line and line.startswith("DATA"):
                    try:
                        parts = line.split(',')
                        c_id = int(parts[1])
                        temp = float(parts[2])
                        left = int(parts[3])
                        right = int(parts[4])
                        self.train.add_bundle(c_id, temp, left, right)
                    except:
                        continue
                time.sleep(0.05)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    train = TrainLinkedList()
    root = tk.Tk()
    root.geometry("480x320")
    root.title("Indian Rail Linked List Temp Monitor")

    gui = TrainGUI(root, train)
    uart_thread = SoftUART(train)
    uart_thread.start()

    root.mainloop()
    uart_thread.running = False
    GPIO.cleanup()
