from pynput.mouse import Controller, Button
import socket
import mss
from screeninfo import get_monitors
from threading import Thread
from signal import pthread_kill, SIGTSTP
from time import sleep

mouse = Controller()
mouse_state = False

addr = ("", 6789)
s = socket.create_server(addr)

d = get_monitors()[0]
dx, dy = d.width, d.height
x, y = 0, 0

PACKET_LEN = 5
SCREEN_PACKET_SIZE = 512

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240

DEPTH = 3
SIZE = SCREEN_WIDTH * SCREEN_HEIGHT * DEPTH

def send_thread(conn: socket.socket):
    global x, y, SCREEN_WIDTH, SCREEN_HEIGHT, DEPTH
    with mss.mss() as sct:
        while True:
            screen_packet = bytearray()
            screen_packet.append(DEPTH)
            monitor = { "top": y, "left": x, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT }
            img = sct.grab(monitor)
            conn.send(b"\x00\x00\x00")

            pixels = list(zip(*[iter(img.rgb)] * 3))
            out = bytearray()
            for tx in range(SCREEN_WIDTH):
                for ty in range(SCREEN_HEIGHT):
                    out.extend(bytearray(pixels[(SCREEN_HEIGHT - ty - 1) * SCREEN_WIDTH + tx][::-1]))
            conn.send(bytes([(SIZE >> 16) & 0xff, (SIZE >> 8) & 0xff, (SIZE >> 0) & 0xff])
                + bytes(out))
            print("sent screen")

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
        if data_t == 0x00:
            pass # just update screen
        elif data_t == 0x01:
            mouse.position = (x + data_x, y + data_y)
            if not mouse_state:
                mouse.press(Button.left)
                mouse_state = True
        elif data_t == 0x02:
            mouse.release(Button.left)
            mouse_state = False
        elif data_t == 0x03:
            x, y = data_x, data_y
        else:
            print("Invalid packet!!!")
    pthread_kill(t.ident, SIGTSTP)
        
