import tkinter as tk
from tkinter import Canvas
import threading
import time
import pigpio

# ---------------- CONFIG ----------------
COACH_IDS = [1, 2, 3, 4]  # Known to Pi
RX_GPIO = 16  # Nano TX -> Pi RX
TX_GPIO = 12  # Pi TX -> Nano RX (optional)
BAUD = 9600
REQUEST_INTERVAL = 2  # seconds per coach
GUI_REFRESH = 500     # ms

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

        # Left neighbor
        if left_id != -1:
            if left_id not in self.nodes:
                self.nodes[left_id] = CoachNode(left_id)
            node.left = self.nodes[left_id]
            self.nodes[left_id].right = node

        # Right neighbor
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
            color = "red" if node.temp > 50 else "green"
            self.canvas.create_rectangle(x_start, y-30, x_start+width, y+30, fill=color)
            self.canvas.create_text(x_start+width/2, y-10, text=f"Coach {node.coach_id}", font=("Arial", 12, "bold"))
            self.canvas.create_text(x_start+width/2, y+10, text=f"{node.temp:.1f}°C", font=("Arial", 10))

            if node.right:
                self.canvas.create_line(x_start+width, y, x_start+width+spacing, y, arrow=tk.LAST, width=2)

            x_start += width + spacing
            node = node.right

        self.root.after(GUI_REFRESH, self.draw_train)

# ---------------- GPIO SERIAL THREAD ----------------
class SerialThread(threading.Thread):
    def __init__(self, train):
        threading.Thread.__init__(self)
        self.train = train
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Cannot connect to pigpio daemon. Run sudo pigpiod")
        # Open software serial RX on GPIO12
        self.pi.bb_serial_read_open(RX_GPIO, BAUD)
        # TX not used here, Pi only requests
        self.daemon = True

    def run(self):
        # Infinite loop to request each coach
        while True:
            for coach_id in COACH_IDS:
                # Send request
                self.pi.bb_serial_write(TX_GPIO, f"REQ,{coach_id}\n".encode())
                # Wait for response
                start = time.time()
                response = ""
                while time.time() - start < 1:  # 1 sec timeout
                    count, data = self.pi.bb_serial_read(RX_GPIO)
                    if count > 0:
                        try:
                            response += data.decode('utf-8')
                            while '\n' in response:
                                line, response = response.split('\n', 1)
                                line = line.strip()
                                if line.startswith("DATA"):
                                    parts = line.split(',')
                                    c_id = int(parts[1])
                                    temp = float(parts[2])
                                    left = int(parts[3])
                                    right = int(parts[4])
                                    self.train.add_bundle(c_id, temp, left, right)
                        except:
                            response = ""
                time.sleep(0.05)  # tiny delay between requests

# ---------------- MAIN ----------------
if __name__ == "__main__":
    train = TrainLinkedList()
    root = tk.Tk()
    root.geometry("480x320")  # 3.5" TFT resolution
    root.title("Indian Rail Linked List Temp Monitor")

    gui = TrainGUI(root, train)
    serial_thread = SerialThread(train)
    serial_thread.start()

    root.mainloop()
