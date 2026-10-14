import serial, time
ser = serial.Serial('COM8', 115200, timeout=1)
ser.setDTR(False); ser.setRTS(True); time.sleep(0.1); ser.setRTS(False); time.sleep(0.1)
lines = []
t0 = time.time()
while time.time() - t0 < 8:
    if ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        lines.append(chunk)
    time.sleep(0.05)
ser.close()
for l in ''.join(lines).splitlines():
    if any(k in l.lower() for k in ['pin', 'gpio', 'mic', 'spk', 'i2s', 'codec']):
        print(l)
