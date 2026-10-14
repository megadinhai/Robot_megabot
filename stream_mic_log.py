import serial
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def format_bar(val, max_val=32767, width=30):
    ratio = min(1.0, max(0.0, val / max_val))
    filled = int(ratio * width)
    return "[" + "=" * filled + " " * (width - filled) + "]"

try:
    ser = serial.Serial('COM8', 115200, timeout=0.2)
    print("==================================================================")
    print("  DANG KET NOI COM8 - HAY NOI VAO MIC DE THEO DOI LOG (30s)")
    print("==================================================================")
    t0 = time.time()
    while time.time() - t0 < 30:
        line = ser.readline()
        if line:
            try:
                decoded = line.decode('utf-8', errors='ignore').strip()
                if decoded:
                    if "MIC Diagnostic" in decoded:
                        parts = decoded.split("=")
                        if len(parts) > 1:
                            val_str = parts[-1].strip().split()[0]
                            try:
                                val = int(val_str)
                                bar = format_bar(val)
                                print(f"MIC LEVEL {bar} Peak: {val:5d} / 32767")
                            except:
                                print(f"MIC: {decoded}")
                        else:
                            print(f"MIC: {decoded}")
                    else:
                        print(f"LOG: {decoded}")
            except Exception as e:
                pass
    ser.close()
    print("==================================================================")
    print("  KET THUC THEO DOI LOG COM8")
    print("==================================================================")
except Exception as e:
    print(f"Loi cong COM8: {e}")

