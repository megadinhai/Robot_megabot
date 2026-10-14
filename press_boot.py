import serial, time
ser = serial.Serial('COM8', 115200, timeout=1)
time.sleep(1)
print('Sending chat toggle command via serial...')
# Let\'s see what happens over 10s
t0 = time.time()
while time.time() - t0 < 6:
    if ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        print(chunk, end='')
    time.sleep(0.05)
ser.close()
