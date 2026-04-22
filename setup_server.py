import network
import socket
import json
import machine
import time

# Pay attention to tags of type {{SSID}}, {{PWD}} itd. - Python will exchange them for real data!
HTML_PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>GPS Radar Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 400px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h2 { text-align: center; color: #0056b3; margin-top: 0; }
        label { font-weight: bold; display: block; margin-top: 15px; font-size: 14px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        input[type="submit"] { width: 100%; background-color: #28a745; color: white; padding: 12px; margin-top: 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; }
        .btn-gps { width: 100%; background-color: #007bff; color: white; padding: 10px; margin-top: 10px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .row { display: flex; gap: 10px; } .col { flex: 1; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Radar Settings</h2>
        <form action="/save" method="GET">
            <label>Sieć Wi-Fi (SSID):</label>
            <input type="text" name="ssid" value="{{SSID}}" required>
            
            <label>Hasło Wi-Fi:</label>
            <input type="password" name="pwd" value="{{PWD}}">
            
            <label>Adres URL API (końcówka /1):</label>
            <input type="text" name="api" value="{{API}}" required>
            
            <label>Home Position (Base):</label>
            <div class="row">
                <div class="col"><input type="text" id="lat" name="lat" value="{{LAT}}" required></div>
                <div class="col"><input type="text" id="lon" name="lon" value="{{LON}}" required></div>
            </div>
            
            <button type="button" class="btn-gps" onclick="getLocation()">📍 Get current location</button>
            <input type="submit" value="💾 SAVE and START">
        </form>
    </div>
    <script>
        function getLocation() {
            const btn = document.querySelector('.btn-gps');
            if (navigator.geolocation) {
                btn.innerText = "⏳ Looking for satellites...";
                navigator.geolocation.getCurrentPosition(function(position) {
                    document.getElementById('lat').value = position.coords.latitude.toFixed(6);
                    document.getElementById('lon').value = position.coords.longitude.toFixed(6);
                    btn.innerText = "✅ Location OK!";
                    btn.style.backgroundColor = "#28a745";
                }, function(error) { alert("Błąd GPS."); btn.innerText = "❌ Download error"; }, { enableHighAccuracy: true, timeout: 10000 });
            }
        }
    </script>
</body>
</html>
"""

def unquote(string):
    res = string.replace('+', ' ')
    parts = res.split('%')
    res = parts[0]
    for item in parts[1:]:
        try: res += chr(int(item[:2], 16)) + item[2:]
        except ValueError: res += '%' + item
    return res

def start_ap_and_server():
    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    time.sleep(0.5)
    ap.config(essid="picosetup", password="password")
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
    ap.active(True)
    
    while not ap.active(): pass
    print("Go to: 192.168.4.1 in web browser, picosetup: password")

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)

    while True:
        cl, addr = s.accept()
        request = cl.recv(1024).decode('utf-8')
        if not request:
            cl.close()
            continue
            
        request_line = request.split('\r\n')[0]
        
        if 'GET /save' in request_line:
            try:
                query_string = request_line.split(' ')[1].split('?')[1]
                params = dict(x.split('=') for x in query_string.split('&'))
                
                config = {
                    'ssid': unquote(params.get('ssid', '')),
                    'password': unquote(params.get('pwd', '')),
                    'api_url': unquote(params.get('api', '')),
                    'home_lat': float(unquote(params.get('lat', '0.0'))),
                    'home_lon': float(unquote(params.get('lon', '0.0')))
                }
                
                with open('config.json', 'w') as f:
                    json.dump(config, f)
                    
                response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<meta charset='UTF-8'><h2>✅ Saved successfully!</h2><p>Pico restarts.</p>"
                cl.send(response.encode('utf-8'))
                cl.close()
                time.sleep(2)
                machine.reset() 
            except Exception as e:
                cl.send("HTTP/1.1 500 ERROR\r\n\r\nERROR.".encode('utf-8'))
        else:
            # LOADING THE CURRENT CONFIGURATION INTO THE FORM
            try:
                with open('config.json', 'r') as f:
                    cfg = json.load(f)
            except:
                cfg = {}
                
            html_response = HTML_PAGE.replace('{{SSID}}', cfg.get('ssid', ''))
            html_response = html_response.replace('{{PWD}}', cfg.get('password', ''))
            html_response = html_response.replace('{{API}}', cfg.get('api_url', ''))
            html_response = html_response.replace('{{LAT}}', str(cfg.get('home_lat', '')))
            html_response = html_response.replace('{{LON}}', str(cfg.get('home_lon', '')))
            
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html_response
            cl.send(response.encode('utf-8'))
            
        cl.close()