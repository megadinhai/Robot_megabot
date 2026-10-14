import serial, time
ser = serial.Serial('COM8', 115200, timeout=1)
lines = []
t0 = time.time()
print('Listening to COM8 for 10 seconds. Try speaking into INMP441...')
while time.time() - t0 < 10:
    if ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        lines.append(chunk)
    time.sleep(0.05)
ser.close()

full_log = ''.join(lines)
for l in full_log.splitlines():
    if any(k in l.lower() for k in ['vad', 'webrtc', 'audio', 'voice', 'packet', 'send', 'listen', 'hear', 'speech', 'error']):
        print(l)
