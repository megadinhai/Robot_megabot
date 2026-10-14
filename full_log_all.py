import serial, time
ser = serial.Serial('COM8', 115200, timeout=1)
ser.setDTR(False)
ser.setRTS(True)
time.sleep(0.1)
ser.setRTS(False)
time.sleep(0.1)

lines = []
t0 = time.time()
while time.time() - t0 < 8:
    if ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        lines.append(chunk)
    time.sleep(0.05)
ser.close()

full_log = ''.join(lines)
for l in full_log.splitlines():
    if int(l.split('(')[1].split(')')[0]) > 3900 if '(' in l and ')' in l and l.split('(')[1].split(')')[0].isdigit() else False:
        print(l)
