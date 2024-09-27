from pynput.mouse import Controller, Button
import socket
import mss
from screeninfo import get_monitors
from threading import Thread
from signal import pthread_kill, SIGTSTP
from math import ceil
import zlib
from time import sleep

mouse = Controller()
mouse_state = False

addr = ("", 6789)
s = socket.create_server(addr)

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240

d = get_monitors()[0]
dx, dy = d.width, d.height
x, y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
scale = 100

PACKET_LEN = 5
SCREEN_PACKET_SIZE = 512

DEPTH = 3
SIZE = SCREEN_WIDTH * SCREEN_HEIGHT * DEPTH

lock = False

def send_thread(conn: socket.socket):
    global lock, x, y, SCREEN_WIDTH, SCREEN_HEIGHT, DEPTH
    with mss.mss() as sct:
        while True:
            while lock:
                sleep(0.001)
            print("lock released!")
            scale_fl = scale / 100
            left = x - int(scale_fl * (SCREEN_WIDTH // 2))
            top = y - int(scale_fl * (SCREEN_HEIGHT // 2))
            width = int(SCREEN_WIDTH * scale_fl)
            height = int(SCREEN_HEIGHT * scale_fl)
            monitor = { "top": top, "left": left, "width": width, "height": height }
            img = sct.grab(monitor)
            conn.send(b"\x00\x00\x00")

            pixels = list(zip(*[iter(img.rgb)] * 3))
            out = bytearray()
            for tx in range(SCREEN_WIDTH):
                for ty in range(SCREEN_HEIGHT):
                    out.extend(bytearray(pixels[int(height - ty * scale_fl - 1) * width + int(tx * scale_fl)][::-1]))
            out_z = zlib.compress(bytes(out))
            conn.send(bytes([(len(out_z) >> 16) & 0xff, (len(out_z) >> 8) & 0xff, (len(out_z) >> 0) & 0xff])
                + out_z)
            lock = True
            print("sent screen and set lock!")

print("Started up, please use ipconfig/ifconfig for IP")

while True:
    conn, c_addr = s.accept()
    print(f"New client {c_addr}!")
    frame_dim = bytearray()
    frame_dim.append((dx >> 8) & 0xff)
    frame_dim.append((dx >> 0) & 0xff)
    frame_dim.append((dy >> 8) & 0xff)
    frame_dim.append((dy >> 0) & 0xff)
    conn.send(frame_dim)
    print("Sent screen dimensions!")
    t = Thread(target=send_thread, args=[conn])
    t.start()
    while True:
        data = conn.recv(PACKET_LEN)
        if not data:
            break
        data_t = data[0]
        data_x = data[1] << 8 | data[2]
        data_y = data[3] << 8 | data[4]
        print(f"Raw packet data: t = {data_t}; x = {data_x}; y = {data_y}")
        scale_fl = scale / 100
        if data_t == 0x00:
            pass # just update screen
        elif data_t == 0x01:
            px = x - int((SCREEN_WIDTH // 2) * scale_fl) + int(data_x * scale_fl)
            py = y - int((SCREEN_HEIGHT // 2) * scale_fl) + int(data_y * scale_fl)
            mouse.position = (px, py)
            if not mouse_state:
                mouse.press(Button.left)
                mouse_state = True
        elif data_t == 0x02:
            mouse.release(Button.left)
            mouse_state = False
        elif data_t == 0x03:
            x = max(min(data_x, dx - ceil((SCREEN_WIDTH // 2) * scale_fl) - 1), int((SCREEN_WIDTH // 2) * scale_fl))
            y = max(min(data_y, dy - ceil((SCREEN_HEIGHT // 2) * scale_fl) - 1), int((SCREEN_HEIGHT // 2) * scale_fl))
        elif data_t == 0x04:
            scale = max(50, scale - 1)
        elif data_t == 0x05:
            st = (scale + 1) / 100
            if ((x >= int((SCREEN_WIDTH // 2) * st) and x < dx - ceil((SCREEN_WIDTH // 2) * st) - 1)
                    and (y >= int((SCREEN_HEIGHT // 2) * st) and y < dy - ceil((SCREEN_HEIGHT // 2) * st) - 1)):
                scale = min(300, scale + 1)
        elif data_t == 0x06:
            lock = False
        else:
            print("Invalid packet!!!")
    pthread_kill(t.ident, SIGTSTP)
        
