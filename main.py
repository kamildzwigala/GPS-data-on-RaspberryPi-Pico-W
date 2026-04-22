import network
import urequests
import time
import math
import machine
import neopixel
import json
from sh1106 import SH1106_I2C

print("You have 3 seconds to STOP in Thonny...")
time.sleep(3)

# --- EQUIPMENT INITIALIZATION ---
status_led = machine.Pin("LED", machine.Pin.OUT) # Built-in diode Pico W
status_led.value(0)

# Button to change the goal (GP15 to GND)
btn_switch = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)

i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=400000)
oled = SH1106_I2C(128, 64, i2c)

NUM_LEDS = 64
np = neopixel.NeoPixel(machine.Pin(2), NUM_LEDS)

# --- PIXEL ART (Matrix 8x8) ---
COLOR_MAP = { 0: (0,0,0), 1: (255,255,255), 2: (0,255,0), 3: (0,0,40), 4: (40,0,0), 5: (40,40,0) }

ICON_WIFI = [
    0,0,0,0,0,0,0,0,  0,3,3,3,3,3,3,0,  3,0,0,0,0,0,0,3,  0,0,3,3,3,3,0,0,
    0,3,0,0,0,0,3,0,  0,0,0,3,3,0,0,0,  0,0,0,3,3,0,0,0,  0,0,0,0,0,0,0,0
]
ICON_ERROR = [
    4,0,0,0,0,0,0,4,  0,4,0,0,0,0,4,0,  0,0,4,0,0,4,0,0,  0,0,0,4,4,0,0,0,
    0,0,0,4,4,0,0,0,  0,0,4,0,0,4,0,0,  0,4,0,0,0,0,4,0,  4,0,0,0,0,0,0,4
]
ICON_TARGET = [
    0,0,0,5,5,0,0,0,  0,0,0,5,5,0,0,0,  0,0,0,0,0,0,0,0,  5,5,0,4,4,0,5,5,
    5,5,0,4,4,0,5,5,  0,0,0,0,0,0,0,0,  0,0,0,5,5,0,0,0,  0,0,0,5,5,0,0,0
]

def show_frame(frame_data):
    for i in range(NUM_LEDS):
        np[i] = COLOR_MAP.get(frame_data[i], (0,0,0))
    np.write()

# --- LOADING CONFIGURATION ---
try:
    with open('config.json', 'r') as f: config = json.load(f)
    WIFI_SSID = config.get('ssid', '')
    WIFI_PASS = config.get('password', '')
    BASE_API_URL = config.get('api_url', '').rsplit('/', 1)[0] # Cuting end /1
    HOME_LAT = float(config.get('home_lat', 0.0))
    HOME_LON = float(config.get('home_lon', 0.0))
except Exception as e:
    WIFI_SSID = ""
    BASE_API_URL = ""

# --- OLED GRAPHICS (Shortened for code readability) ---
def draw_circle(x0, y0, r, c=1):
    f = 1 - r; ddf_x = 1; ddf_y = -2 * r; x = 0; y = r
    oled.pixel(x0, y0+r, c); oled.pixel(x0, y0-r, c); oled.pixel(x0+r, y0, c); oled.pixel(x0-r, y0, c)
    while x < y:
        if f >= 0: y -= 1; ddf_y += 2; f += ddf_y
        x += 1; ddf_x += 2; f += ddf_x
        oled.pixel(x0+x, y0+y, c); oled.pixel(x0-x, y0+y, c); oled.pixel(x0+x, y0-y, c); oled.pixel(x0-x, y0-y, c)
        oled.pixel(x0+y, y0+x, c); oled.pixel(x0-y, y0+x, c); oled.pixel(x0+y, y0-x, c); oled.pixel(x0-y, y0-x, c)

def draw_globe(cx, cy, r, offset):
    draw_circle(cx, cy, r, 1)
    oled.hline(cx - int(r*0.86), cy - r//2, int(r*1.72), 1)
    oled.hline(cx - r, cy, 2*r, 1)
    oled.hline(cx - int(r*0.86), cy + r//2, int(r*1.72), 1)
    spacing = r // 2
    for i in range(5):
        lx = cx - r + ((offset + i * spacing) % (2 * r))
        dx = abs(lx - cx)
        if dx < r:
            dy = int(math.sqrt(r*r - dx*dx))
            oled.vline(lx, cy - dy, dy * 2, 1)

def play_cinematic(lat_val, lon_val, target_name):
    show_frame(ICON_TARGET)
    for offset in range(0, 40, 4):
        oled.fill(0)
        oled.text(f"SZUKAM: {target_name}", 0, 0)
        draw_globe(64, 32, 22, offset)
        oled.show()
        time.sleep(0.1)
    time.sleep(1)

# --- MATHEMATICS GPS ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371; dLat = math.radians(lat2 - lat1); dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def calculate_azimuth(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dLon))
    return (math.degrees(math.atan2(x, y)) + 360) % 360

# --- CONNECTION WI-FI ---
def connect_wifi_or_setup():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not WIFI_SSID:
        show_frame(ICON_WIFI)
        oled.fill(0)
        oled.text("--- SETUP ---", 16, 0)
        oled.text("1.Connect to WiFi:", 0, 16)
        oled.text("picosetup: password", 0, 26)
        oled.text("2.Go to:", 0, 42)
        oled.text("192.168.4.1", 0, 52)
        oled.show()
        import setup_server
        setup_server.start_ap_and_server()
        return False

    wlan.connect(WIFI_SSID, WIFI_PASS)
    oled.fill(0)
    oled.text("Connecting to WiFi...", 0, 20)
    oled.show()
    
    timeout = 15
    while not wlan.isconnected() and timeout > 0:
        status_led.toggle() # Flashing when connecting
        show_frame(ICON_WIFI)
        time.sleep(0.5)
        timeout -= 0.5
        
    if wlan.isconnected():
        status_led.value(1) # Connected
        oled.fill(0); oled.text("WiFi OK!", 0, 20); oled.show()
        time.sleep(1)
        return True
    else:
        show_frame(ICON_ERROR)
        oled.fill(0)
        oled.text("CONNECTION FAILED!", 0, 0)
        oled.show()
        time.sleep(3)
        import setup_server
        setup_server.start_ap_and_server()
        return False

# --- MAIN LOOP OF THE PROGRAM ---
if connect_wifi_or_setup():
    target_id = 3 # 1 = GPS, 3 = APP
    target_names = {1: "GPS", 3: "APP"}
    
    current_distance = 0.0
    current_speed = 0.0
    lat = 0.0
    lon = 0.0
    
    last_fetch_time = 0
    last_btn_press = 0
    last_anim_time = time.ticks_ms()
    
    FETCH_INTERVAL = 10000
    ANIM_INTERVAL = 360000

    while True:
        now = time.ticks_ms()
        
        # --- OPERATION OF THE CHANGE TARGET BUTTON ---
        if not btn_switch.value(): # JIf the button is pressed (short to GND)
            if time.ticks_diff(now, last_btn_press) > 500: # Debouncing (Protection against contact vibration)
                target_id = 3 if target_id == 1 else 1 # Zmiana celu
                last_btn_press = now
                last_fetch_time = 0 # Forces immediate download of new data
                
                show_frame(ICON_TARGET)
                oled.fill(0)
                oled.text(f"Target change:", 0, 20)
                oled.text(f"--> {target_names[target_id]}", 0, 40)
                oled.show()
                time.sleep(1.5)
        
        # --- DOWNLOADING DATA FROM API ---
        if time.ticks_diff(now, last_fetch_time) > FETCH_INTERVAL:
            try:
                status_led.value(0) # Heartbeat OFF
                # Dynamic URL depending on the selected target!
                current_api_url = f"{BASE_API_URL}/{target_id}"
                
                response = urequests.get(current_api_url)
                data = response.json()
                response.close()
                
                lat = data['latitude']
                lon = data['longitude']
                current_speed = data['speed'] * 1.852
                
                current_distance = calculate_distance(HOME_LAT, HOME_LON, lat, lon)
                azimuth = calculate_azimuth(HOME_LAT, HOME_LON, lat, lon)
                
                oled.fill(0)
                oled.text(f"{target_names[target_id]} {current_distance:.1f} km", 0, 0)
                oled.text(f"Speed: {current_speed:.1f} km/h", 0, 16)
                oled.text(f"Azimuth: {int(azimuth)} st", 0, 32)
                oled.text(f"{lat:.4f} {lon:.4f}", 0, 56)
                oled.show()
                
                last_fetch_time = now
                status_led.value(1) # Heartbeat ON
            except Exception as e:
                show_frame(ICON_ERROR)
                status_led.value(0) # Dign off the LED if there is an error

        # --- Animation ---
        if time.ticks_diff(now, last_anim_time) > ANIM_INTERVAL and lat != 0.0:
            play_cinematic(lat, lon, target_names[target_id])
            last_anim_time = time.ticks_ms()
            last_fetch_time = 0 

        # --- MATRIX LED (Colors depending on distance) ---
        if current_distance <= 10.0: base_color = (0, 255, 0)
        elif current_distance <= 40.0: base_color = (255, 150, 0)
        else: base_color = (255, 0, 0)
            
        if current_speed > 2.0:
            pulse = (math.sin(now / 300) + 1) / 2
            brightness = 0.05 + (pulse * 0.5)
        else:
            brightness = 0.1
            
        r = int(base_color[0] * brightness)
        g = int(base_color[1] * brightness)
        b = int(base_color[2] * brightness)
        
        # Displays smooth color only if we do not press the button and there is no error
        if btn_switch.value(): 
            for i in range(NUM_LEDS): np[i] = (r, g, b)
            np.write()
        
        time.sleep(0.05)
