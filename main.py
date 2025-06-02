#---Libraries---
import socket, gc, time
from time import ticks_ms, ticks_diff
from machine import Pin, I2C, TouchPad, PWM, ADC
import ssd1306, dht
import _thread
import urequests
import ujson
import time
import ubinascii
import machine
from umqtt.simple import MQTTClient
import ssl
import usocket


# --- Hardware ---
buzzer = PWM(Pin(4))
buzzer.duty(0)
led_pwm = PWM(Pin(21), freq=5000)
led_pwm.duty(0)
i2c = I2C(0, scl=Pin(6), sda=Pin(5))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
tp = TouchPad(Pin(2))
pot = ADC(Pin(1)); pot.width(ADC.WIDTH_12BIT); pot.atten(ADC.ATTN_11DB)
dht11 = dht.DHT11(Pin(3))
pir = Pin(7, Pin.IN, Pin.PULL_DOWN)

#---MQTT Settings---
MQTT_BROKER = "192.168.205.145"
CLIENT_ID = ubinascii.hexlify(machine.unique_id())
SUB_TOPIC = b"recive"        # تاپیک برای دریافت پیام
PUB_TOPIC = b"response"    # تاپیک برای ارسال پاسخ

# --- Values ---
cityName = "Isfahan"
brightness_mode = 'auto'
notes = {'C4':262,'D4':294,'E4':330,'F4':349,'G4':392,'A4':440,'B4':494}
melody = [
    ('C4', 0.5), ('C4', 0.5), ('G4', 0.5), ('G4', 0.5),
    ('A4', 0.5), ('A4', 0.5), ('G4', 1.0),
    ('F4', 0.5), ('F4', 0.5), ('E4', 0.5), ('E4', 0.5),
    ('D4', 0.5), ('D4', 0.5), ('C4', 1.0),
    ('G4', 0.5), ('G4', 0.5), ('F4', 0.5), ('F4', 0.5),
    ('E4', 0.5), ('E4', 0.5), ('D4', 1.0),
    ('G4', 0.5), ('G4', 0.5), ('F4', 0.5), ('F4', 0.5),
    ('E4', 0.5), ('E4', 0.5), ('D4', 1.0),
    ('C4', 0.5), ('C4', 0.5), ('G4', 0.5), ('G4', 0.5),
    ('A4', 0.5), ('A4', 0.5), ('G4', 1.0),
    ('F4', 0.5), ('F4', 0.5), ('E4', 0.5), ('E4', 0.5),
    ('D4', 0.5), ('D4', 0.5), ('C4', 1.0)
]
tempo = 250
PIR_BEEP = 500
PIR_CD = 4000

# --- وضعیت ---
oled_update = False; led_blinking = False; brightness_update = False; manual_brightness = False
music_playing = False; pir_enabled = False; pir_playing = False; pir_cooldown = False
latest_brightness = 100; latest_voltage = 0; latest_temp = "--"; latest_humidity = "--"
last_motion_time = None; pir_status = "Disabled"

# --- تایمرها ---
t_bl = ticks_ms(); t_br = ticks_ms(); t_nt = ticks_ms(); t_dht = ticks_ms(); t_pir = 0
melody_idx = 0

# --- سرور ---
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 80)); s.listen(5)


def web_page():
    slider_display = 'block' if brightness_mode == 'web' else 'none'
    return f"""
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Control Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
:root {{
    --bg-color: #2f2f2f;
    --text-color: #eee;
    --card-bg: #fff;
    --card-text: #333;
}}

/* تم شب */
body.night {{
    --bg-color: #121212;  /* پس‌زمینه تیره */
    --text-color: #e0e0e0;  /* متن سفید */
    --card-bg: #1e1e1e;  /* کارت‌ها نوک مدادی */
    --card-text: #ffffff;  /* متن کارت سفید */
    --button-bg: #005a8c;  /* دکمه‌ها آبی تیره */
    --button-hover: #004a70;  /* هاور دکمه */
    --input-bg: #2a2a2a;  /* پس‌زمینه input و textarea */
    --input-text: #e0e0e0;  /* متن input و textarea */
}}


body.night .card {{
    background: var(--card-bg);
    color: #ccc;
    border-color: #333;  
}}
body.night .card div {{
    color: #fff; 
}}
body.night .buttons button {{
    background: var(--button-bg);
}}

body.night .buttons button:hover {{
    background: var(--button-hover);
}}

body.night textarea,
body.night input[type="text"] {{
    background: var(--input-bg);
    color: var(--input-text);
    border-color: #444;
}}

body.night .half {{
    background: var(--card-bg);
    color: var(--card-text);
}}

body.night .tooltip-content {{
    background: #2a2a2a;
    border-color: #444;
}}

body.night .clock {{
    background: var(--card-bg);
    color: var(--card-text);
}}


body.night .card i {{
    color: #4dabff;  
}}
body.night .card.touch {{ border-color: #84d9ff; }}
body.night .card.brightness {{ border-color: #ffe084; }}
body.night .card.voltage {{ border-color: #c5ff84; }}
body.night .card.temp {{ border-color: #ff9b84; }}
body.night .card.humidity {{ border-color: #84ffd1; }}
body.night .card.motion {{ border-color: #d484ff; }}
body.night .card.pir {{ border-color: #ff84bc; }}
body.night .card::before {{
    opacity: 0.2; /* کاهش opacity برای ظاهر بهتر */
}}
body.night .card.brightness::before {{ background: #ffe084; }}
body.night .card.voltage::before {{ background: #c5ff84; }}
body.night .card.temp::before {{ background: #ff9b84; }}
body.night .card.humidity::before {{ background: #84ffd1; }}
body {{
    margin:0; padding:0;
    font-family:'Roboto',sans-serif;
    background: var(--bg-color);
    color: var(--text-color);
    transition: background 0.5s, color 0.5s;
    transition: all 0.8s ease;
}}
.clock {{
    position: absolute;
    top: 260px;
    right: 40px;
    background: #fff;
    color: #2f2f2f;
    font-family: 'Roboto', sans-serif;
    font-size: 1.5em;
    padding: 10px 20px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    backdrop-filter: blur(5px);
    z-index: 999;
}}
.container {{
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(140px,1fr));
    gap: 15px;
    padding: 20px;
}}
.card {{
    background: #fff;
    border-radius:12px;
    box-shadow:0 6px 20px rgba(0,0,0,0.2);
    padding:20px;
    text-align:center;
    transition: all 0.8s ease, transform 0.3s, box-shadow 0.3s;    position: relative;
    border: 2px solid transparent;
    color: #333;
    overflow: hidden; 

}}
.card::before {{
    content: '';
    position: absolute;
    left: 0; bottom: 0;
    width: 100%;
    height: var(--fill-height, 0%);
    z-index: 0;
    opacity: 0.3;
    transition: height 0.5s ease;
}}
.card > * {{ position: relative; z-index: 1; }}
.card.touch {{ border-color: #84d9ff; }}
.card.brightness {{ border-color: #ffe084; }}
.card.voltage {{ border-color: #c5ff84; }}
.card.temp {{ border-color: #ff9b84; }}
.card.humidity {{ border-color: #84ffd1; }}
.card.motion {{ border-color: #d484ff; }}
.card.pir {{ border-color: #ff84bc; }}
.card.brightness::before {{ background: #ffe084; }}
.card.voltage::before {{ background: #c5ff84; }}
.card.temp::before {{ background: #ff9b84; }}
.card.humidity::before {{ background: #84ffd1; }}

.card:hover {{
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
}}
.card h2 {{
    margin: 0 0 10px;
    font-size: 1em;
    color: #555;
}}
.card div {{
    font-size: 1.3em;
    font-weight: bold;
    color: #111;
}}
.card i {{
    font-size: 1.5em;
    margin-bottom: 8px;
    display: block;
    color: #4dabff;
}}
.card.touch {{ border-color: #84d9ff; }}
.card.brightness {{ border-color: #ffe084; }}
.card.voltage {{ border-color: #c5ff84; }}
.card.temp {{ border-color: #ff9b84; }}
.card.humidity {{ border-color: #84ffd1; }}
.card.motion {{ border-color: #d484ff; }}
.card.pir {{ border-color: #ff84bc; }}

.buttons {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    padding: 20px;
}}
.cmd {{
    color: #4dabff; 
    font-weight: bold;
}}
.buttons button {{
    border: none;
    background: #00b0f0;
    border-radius: 8px;
    color: white;
    padding: 10px 14px;
    font-size: 0.9em;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transition: all 0.8s ease, transform 0.2s, box-shadow 0.2s;
}}

.buttons button:hover {{
    transform: translateY(-3px);
    background-color: #0090c0;
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
}}

.half-container {{
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    padding: 20px;
    justify-content: center;
}}
.half {{
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.2);
    padding: 20px;
    flex: 1 1 320px;
    box-sizing: border-box;
    position: relative;
    min-width: 300px;
    color: #333;
}}
textarea {{
    width: 100%;
    height: 160px;
    resize: none;
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 10px;
    font-family: monospace;
    background: #fff;
    color: #333;
}}
input[type="text"] {{
    width: calc(100% - 14px);
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 8px;
    margin-top: 10px;
    background: #fff;
    color: #333;
}}
button.clear {{
    background: linear-gradient(45deg, #ff5f6d, #ff1c4c);
    color: white;
    font-weight: bold;
    border: none;
    border-radius: 10px;
    padding: 12px 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transition: transform 0.2s, box-shadow 0.2s, background 0.3s;
}}
button.clear:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
    background: linear-gradient(45deg, #e60036, #c4002e);
}}
.tooltip-icon {{
    position: absolute;
    top: 20px;
    right: 20px;
    background: #4dabff;
    color: white;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    text-align: center;
    line-height: 24px;
    font-weight: bold;
    cursor: pointer;
    font-size: 15px;
}}
.tooltip-content {{
    opacity: 0;
    visibility: hidden;
    position: absolute;
    top: 60px;
    right: 0;
    background: #333;
    border: 2px solid #555;
    padding: 15px;
    width: 300px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    z-index: 10;
    font-size: 15px;
    color: #eee;
    transition: opacity 0.4s ease, visibility 0.4s ease;
}}
.tooltip-icon:hover + .tooltip-content {{
    opacity: 1;
    visibility: visible;
}}
#slider-container {{
    display: {slider_display};
    text-align: center;
    margin: 20px;
}}
input[type="range"] {{
    width: 80%;
}}
p.slider-text {{
    font-size: 0.95em;
    color: #ccc;
}}
button.send {{
    background: linear-gradient(45deg, #00b0ff, #005eff);
    border: none;
    border-radius: 10px;
    color: white;
    font-weight: bold;
    padding: 12px 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transition: transform 0.2s, box-shadow 0.2s;
}}
button.send:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
}}
</style>
</head><body>
<div class="clock" id="clock">--:--:--</div>
<div class="container">
  <div class="card touch"><i class="fas fa-hand-pointer"></i><h2>Touch</h2><div id="v-touch">--</div></div>
  <div class="card brightness" id="c-bright"><i class="fas fa-sun"></i><h2>Brightness</h2><div id="v-bright">--%</div></div>
  <div class="card voltage" id="c-volt"><i class="fas fa-bolt"></i><h2>Voltage</h2><div id="v-volt">--V</div></div>
  <div class="card temp" id="c-temp"><i class="fas fa-thermometer-half"></i><h2>Temp</h2><div id="v-temp">--°C</div></div>
  <div class="card humidity" id="c-humid"><i class="fas fa-tint"></i><h2>Humidity</h2><div id="v-humid">--%</div></div>
  <div class="card motion"><i class="fas fa-running"></i><h2>Last Motion</h2><div id="v-motion">--</div></div>
  <div class="card pir"><i class="fas fa-eye"></i><h2>PIR Status</h2><div id="v-pir">--</div></div>
</div>

</div>
<div class="buttons">
  <div>
    <button onclick="sendCommand('/?led=on', false)"><i class="fas fa-lightbulb"></i> LED ON</button>
    <button onclick="sendCommand('/?led=off', false)"><i class="fas fa-power-off"></i> LED OFF</button>
    <button onclick="sendCommand('/?led=blink', false)"><i class="fas fa-sync-alt"></i> Blink</button>
    <button onclick="sendCommand('/?show-tv', false)"><i class="fas fa-tv"></i> Show OLED</button>
    <button onclick="sendCommand('/?music=play', false)"><i class="fas fa-play"></i> Play Music</button>
    <button onclick="sendCommand('/?music=stop', false)"><i class="fas fa-stop"></i> Stop Music</button>
    <button onclick="toggleTheme()"><i class="fas fa-moon"></i> Toggle Theme</button>
  </div>
  <div style="margin-top:10px;">
    <button onclick="sendCommand('/?led=manual', false)"><i class="fas fa-sliders-h"></i> Manual Brightness</button>
    <button onclick="sendCommand('/?led=web', true)"><i class="fas fa-globe"></i> Web Brightness</button>
    <button onclick="sendCommand('/?pir=on', false)"><i class="fas fa-eye"></i> Enable PIR</button>
    <button onclick="sendCommand('/?pir=off', false)"><i class="fas fa-eye-slash"></i> Disable PIR</button>
    <button onclick="toggleWeather(true)"><i class="fas fa-cloud-sun"></i> Show Weather</button>
    <button onclick="toggleWeather(false)"><i class="fas fa-eye-slash"></i> Hide Weather</button>
  </div>
</div>
<div class="container" id="weather-cards" style="display:none;">
  <div class="card"><i class="fas fa-temperature-high"></i><h2>Temperature</h2><div id="w-temp">--^C</div></div>
  <div class="card"><i class="fas fa-tint"></i><h2>Humidity</h2><div id="w-humidity">--%</div></div>
  <div class="card"><i class="fas fa-tachometer-alt"></i><h2>Pressure</h2><div id="w-pressure">-- hPa</div></div>
  <div class="card"><i class="fas fa-city"></i><h2>City</h2><div id="w-city">--</div></div>
  <div class="card"><i class="fas fa-cloud"></i><h2>Weather</h2><div id="w-main">--</div></div>
  <div class="card"><i class="fas fa-wind"></i><h2>Wind Speed</h2><div id="w-wind">-- m/s</div></div>
</div>
    

<!-- این بخش جدا شد -->
<div class="half-container">
  <div class="half">
    <h2>Send Shell Command
      <span class="tooltip-icon">?</span>
      <div class="tooltip-content">
        <ul style="margin:0; padding:0; list-style:none;">
          <li><b class="cmd">on</b>: Turn on the LED</li>
          <li><b class="cmd">off</b>: Turn off the LED</li>
          <li><b class="cmd">blink</b>: Make LED blink</li>
          <li><b class="cmd">music</b>: Play music</li>
          <li><b class="cmd">stop</b>: Stop music</li>
          <li><b class="cmd">show</b>: Show values on OLED</li>
          <li><b class="cmd">piron</b>: Enable PIR</li>
          <li><b class="cmd">piroff</b>: Disable PIR</li>
          <li><b class="cmd">potbri</b>: Brightness by Potentiometer</li>
          <li><b class="cmd">webbri</b>: Brightness by slider</li>
          <li><b class="cmd">num 0-100</b>: Set brightness</li>
        </ul>
      </div>
    </h2>
    <input id="shell-input" type="text" placeholder="Enter command">
    <br><br>
    <button class="send" onclick="sendShell()"><i class="fas fa-terminal"></i> Send</button>
  </div>
  <div class="half">
    <h2>Logs</h2>
    <textarea id="v-logs" readonly>--</textarea>
    <br><br>
    <button class="clear" onclick="clearLogs()"><i class="fas fa-trash-alt"></i> Clear Logs</button>
  </div>
</div>
<div id="slider-container" style="display:{slider_display};">
  <input type="range" min="0" max="100" value="100" onchange="setBrightness(this.value)">
  <p class="slider-text">Use slider to set brightness manually</p>
</div>

<script>
function updateClock() {{
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('clock').innerText = `${{h}}:${{m}}:${{s}}`;
}}
function updateCardFill(id, value, maxValue) {{
    const card = document.getElementById(id);
    if (!card) return;
    const percent = Math.max(0, Math.min(100, (value / maxValue) * 100));
    card.style.setProperty('--fill-height', percent + '%');
}}

function refreshValues() {{
    let tempText = document.getElementById('v-temp')?.innerText;
    let humidityText = document.getElementById('v-humid')?.innerText;
    let brightnessText = document.getElementById('v-bright')?.innerText;
    let voltageText = document.getElementById('v-volt')?.innerText;

    let temp = parseFloat(tempText);
    let humidity = parseFloat(humidityText);
    let brightness = parseFloat(brightnessText);
    let voltage = (voltageText === "--") ? NaN : parseFloat(voltageText);

    if (!isNaN(temp)) updateCardFill('c-temp', temp, 60);
    if (!isNaN(humidity)) updateCardFill('c-humid', humidity, 100);
    if (!isNaN(brightness)) updateCardFill('c-bright', brightness, 100);

    if (!isNaN(voltage)) {{
        updateCardFill('c-volt', voltage, 3.3);
    }} else {{
        updateCardFill('c-volt', 0, 3.3);
    }}
}}

setInterval(refreshValues, 1000);

setInterval(updateClock, 1000);
updateClock();

function updateValues() {{
    fetch('/touch').then(r=>r.text()).then(d=>{{document.getElementById('v-touch').innerText=d;}});
    fetch('/brightness').then(r=>r.text()).then(d=>{{document.getElementById('v-bright').innerText=d+'%';}});
    fetch('/voltage').then(r=>r.text()).then(d=>{{document.getElementById('v-volt').innerText=d+'V';}});
    fetch('/temperature').then(r=>r.text()).then(d=>{{document.getElementById('v-temp').innerText=d+'^C';}});
    fetch('/humidity').then(r=>r.text()).then(d=>{{document.getElementById('v-humid').innerText=d+'%';}});
    fetch('/lastmotion').then(r=>r.text()).then(d=>{{document.getElementById('v-motion').innerText=d;}});
    fetch('/pirstatus').then(r=>r.text()).then(d=>{{document.getElementById('v-pir').innerText=d;}});
}}
function updateLogs() {{
    fetch('/logs').then(r => r.text()).then(d => {{ document.getElementById('v-logs').value = d; }});
}}
function clearLogs() {{
    fetch('/clearlogs').then(r => r.text()).then(d => {{ updateLogs(); }});
}}
function setBrightness(val) {{ fetch('/setbrightness?val='+val); }}
function sendCommand(url, showSliderFlag) {{
    fetch(url);
    document.getElementById('slider-container').style.display = showSliderFlag ? 'block' : 'none';
}}
function sendShell() {{
    let cmd = document.getElementById('shell-input').value.trim();
    if(cmd !== '') {{
        fetch('/shell?cmd='+encodeURIComponent(cmd)).then(() => {{
            updateLogs();
        }});
        document.getElementById('shell-input').value = '';
    }}
}}
document.addEventListener('DOMContentLoaded', function() {{
    const input = document.getElementById('shell-input');
    input.addEventListener('keydown', function(e) {{
        if(e.key === 'Enter') {{
            e.preventDefault();
            sendShell();
        }}
    }});
}});
function toggleWeather(show) {{
  const container = document.getElementById('weather-cards');
  container.style.display = show ? 'grid' : 'none';
  if (show) fetchWeather();
}}

function fetchWeather() {{
  fetch('/weather')
    .then(r => r.json())
    .then(data => {{
      document.getElementById('w-temp').innerText = data.temp + "^C";
      document.getElementById('w-humidity').innerText = data.humidity + "%";
      document.getElementById('w-pressure').innerText = data.pressure + " hPa";
      document.getElementById('w-city').innerText = data.city;
      document.getElementById('w-main').innerText = data.description; 
      document.getElementById('w-wind').innerText = data.wind + " m/s";
    }});
}}
function sendEmail() {{
    const recipient = document.getElementById('email-recipient').value;
    const subject = document.getElementById('email-subject').value;
    const body = document.getElementById('email-body').value;
    
    if(!recipient || !subject || !body) {{
        alert('Please fill all fields');
        return;
    }}
    
    fetch('/sendemail?recipient=' + encodeURIComponent(recipient) + 
          '&subject=' + encodeURIComponent(subject) + 
          '&body=' + encodeURIComponent(body))
    .then(r => r.text())
    .then(d => {{
        alert(d);
        updateLogs();
    }});
}}
function toggleTheme() {{
    document.body.classList.toggle('night');
    const themeBtn = document.querySelector('[onclick="toggleTheme()"]');
    
    if (document.body.classList.contains('night')) {{
        themeBtn.innerHTML = '<i class="fas fa-sun"></i> Light Mode';
    }} else {{
        themeBtn.innerHTML = '<i class="fas fa-moon"></i> Dark Mode';
    }}
}}
setInterval(updateValues,1000);
setInterval(updateLogs,2000);
window.onload = function(){{ updateValues(); updateLogs(); }};
</script>

</body></html>
"""

MQTT_COMMANDS_HELP = """
on       : Turn on the LED
off      : Turn off the LED
blink    : Make LED blink
show     : Show OLED data
music    : Start music
stop     : Stop music
piron    : Enable PIR sensor
piroff   : Disable PIR sensor
0-100    : Set LED brightness (%)
city (X) : Change city to (X)
"""


phone_msg = None
last_checked_phone_msg = None  
###########

###########
#---MQTT Function---
def sub_cb(topic, msg):
    global phone_msg
    decoded_topic = topic.decode()
    decoded_msg = msg.decode()
    phone_msg=decoded_msg
    print(f"[Received] Topic: {decoded_topic}, Message: {decoded_msg}")

    # پاسخ به پیام دریافتی
    response_msg = f"Message Recived: {decoded_msg}"
    
def handle_mqtt_command(msg):
    try:
        global oled_update, led_blinking, brightness_update, manual_brightness
        global latest_brightness, latest_voltage, pir_enabled
        global music_playing, melody_idx, t_nt

        msg = msg.strip()
        if msg.startswith('city ') and len(msg) > 1:
            new_city = msg[5:].strip()
            cityName = new_city
            add_log(f"City set to: {cityName}")
            weather = fetch_weather(cityName)
            mqttClient.publish(PUB_TOPIC, f"City Changed to {cityName}.".encode())
        if msg.lower() == 'on':
            oled_update = led_blinking = brightness_update = manual_brightness = False
            led_pwm.duty(0)
            latest_brightness = 100
            latest_voltage = "--"
            display.fill(0)
            display.text("LED ON", 0, 10)
            display.show()
            add_log("LED turned on from MQTT")
            mqttClient.publish(PUB_TOPIC, b"LED has been turned ON.")

        elif msg.lower() == 'off':
            oled_update = led_blinking = brightness_update = manual_brightness = False
            led_pwm.duty(1023)
            latest_brightness = 0
            latest_voltage = "--"
            display.fill(0)
            display.text("LED OFF", 0, 10)
            display.show()
            add_log("LED turned off from MQTT")
            mqttClient.publish(PUB_TOPIC, b"LED has been turned OFF.")

        elif msg.lower() == 'blink':
            oled_update = brightness_update = manual_brightness = False
            led_blinking = True
            latest_brightness = "0/100"
            latest_voltage = "--"
            display.fill(0)
            display.text("BLINK", 0, 10)
            display.show()
            add_log("LED blinking via MQTT")
            mqttClient.publish(PUB_TOPIC, b"LED is blinking now.")

        elif msg.lower() == 'show':
            oled_update = True
            led_blinking = brightness_update = False
            latest_voltage = "--"
            display.fill(0)
            display.text("SHOW OLED", 0, 10)
            display.show()
            add_log("Show OLED via MQTT")
            mqttClient.publish(PUB_TOPIC, b"OLED is showing values.")

        elif msg.lower() == 'music':
            oled_update = led_blinking = brightness_update = False
            stop_music()
            start_music()
            latest_voltage = "--"
            display.fill(0)
            display.text("MUSIC PLAY", 0, 10)
            display.show()
            add_log("Music started via MQTT")
            mqttClient.publish(PUB_TOPIC, b"Music started.")

        elif msg.lower() == 'stop':
            oled_update = led_blinking = brightness_update = False
            stop_music()
            latest_voltage = "--"
            display.fill(0)
            display.text("MUSIC STOP", 0, 10)
            display.show()
            add_log("Music stopped via MQTT")
            mqttClient.publish(PUB_TOPIC, b"Music stopped.")
        
        elif msg.lower() == 'piron':
            pir_enabled = True
            latest_voltage = "--"
            display.fill(0)
            display.text("PIR ON", 0, 10)
            display.show()
            add_log("PIR enabled via MQTT")
            mqttClient.publish(PUB_TOPIC, b"PIR sensor enabled.")

        elif msg.lower() == 'piroff':
            pir_enabled = False
            latest_voltage = "--"
            display.fill(0)
            display.text("PIR OFF", 0, 10)
            display.show()
            add_log("PIR disabled via MQTT")
            mqttClient.publish(PUB_TOPIC, b"PIR sensor disabled.")

        elif msg.isdigit():
            bri = int(msg)
            if 0 <= bri <= 100:
                duty = int((100 - bri) * 1023 / 100)
                led_pwm.duty(duty)
                latest_brightness = bri
                brightness_mode = 'manual'
                manual_brightness = True
                oled_update = True
                add_log(f"Brightness set to {bri}% via MQTT")
                mqttClient.publish(PUB_TOPIC, f"Brightness set to {bri}%.".encode())
    except Exception as e:
        add_log(f"MQTT command error: {e}")

  
global mqttClient
mqttClient = MQTTClient(CLIENT_ID, MQTT_BROKER, keepalive=60)
mqttClient.set_callback(sub_cb)
mqttClient.connect()
mqttClient.subscribe(SUB_TOPIC)
print(f"Connected to MQTT Broker: {MQTT_BROKER}")
print(f"Subscribed to topic: {SUB_TOPIC.decode()}")

mqttClient.publish(PUB_TOPIC, MQTT_COMMANDS_HELP.encode())

def start_music():
    global music_playing, melody_idx, t_nt
    if music_playing: return
    buzzer.freq(notes[melody[0][0]]); melody_idx = 0; t_nt = ticks_ms(); music_playing = True

def stop_music():
    global music_playing
    buzzer.duty(0); music_playing = False

log_messages = []
LOG_MAX = 20

def add_log(msg):
    global log_messages
    t = time.localtime()  # گرفتن زمان محلی
    timestamp = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])  # hh:mm:ss
    log_entry = f"[{timestamp}] {msg}"
    log_messages.append(log_entry)
    if len(log_messages) > LOG_MAX:
        log_messages.pop(0)
    print(log_entry)  # به کنسول هم با زمان چاپ کنه

def read_shell_input():
    global thread_running
    while thread_running:
        try:
            msg = input("Type log message: ")
            add_log(msg)
        except (EOFError, OSError, KeyboardInterrupt):
            add_log("[Shell thread exited due to input error]")
            break


thread_running = True
def fetch_weather(city):
    global cityName
    cityName = city
    return read_map_data() 
def read_map_data():
    try:
        API_KEY = "c1aef1acd53c97a5e0db512936cc6b6b"  # API شما
        url = f"http://api.openweathermap.org/data/2.5/weather?q={cityName}&appid={API_KEY}&units=metric"

        response = urequests.get(url)
        data = response.json()
        response.close()

        temp = data.get('main', {}).get('temp', "--")
        humidity = data.get('main', {}).get('humidity', "--")
        pressure = data.get('main', {}).get('pressure', "--")
        wind_speed = data.get('wind', {}).get('speed', "--")
        description_raw = data.get('weather', [{}])[0].get('description', "unknown")

        if isinstance(description_raw, str) and len(description_raw) > 0:
            description = description_raw[0].upper() + description_raw[1:]
        else:
            description = "Unknown"

        city_name = data.get('name', "Unknown")

        add_log(f"City: {cityName}, Temp: {temp}°C, Humidity: {humidity}%, Wind: {wind_speed} m/s")
        add_log(f"Weather: {description}, Pressure: {pressure} hPa")

        return {
            "city": city_name,
            "temp": temp,
            "humidity": humidity,
            "pressure": pressure,
            "wind": wind_speed,
            "description": description
        }
    except Exception as e:
        add_log(f"Error reading weather: {e}")
        return None

weather = read_map_data()
_thread.start_new_thread(read_shell_input, ())
while True:
    try:
        if gc.mem_free() < 50000: gc.collect()

        tv = tp.read()
        try:
            mqttClient.check_msg()
        except OSError as e:
            add_log(f"[MQTT] Disconnected: {e}")
            try:
                mqttClient.connect()
                mqttClient.subscribe(SUB_TOPIC)
                add_log("[MQTT] Reconnected successfully")
            except Exception as ex:
                add_log(f"[MQTT] Reconnect failed: {ex}")

        if phone_msg and phone_msg != last_checked_phone_msg:
            handle_mqtt_command(phone_msg)
            last_checked_phone_msg = phone_msg

        # --- دما ---
        if ticks_diff(ticks_ms(), t_dht) >= 2000:
            try: dht11.measure(); latest_temp = dht11.temperature(); latest_humidity = dht11.humidity()
            except: latest_temp = latest_humidity = "--"
            t_dht = ticks_ms()

        # --- PIR وضعیت ---
        if pir_enabled:
            pir_status = "Motion Detected" if pir.value() else "No Motion"
        else: pir_status = "Disabled"

        if pir_enabled and not pir_playing and not pir_cooldown and pir.value():
            if music_playing: stop_music()
            buzzer.freq(440); buzzer.duty(512)
            pir_playing = True; t_pir = ticks_ms(); pir_cooldown = True; last_motion_time = ticks_ms()

        if pir_playing and ticks_diff(ticks_ms(), t_pir) >= PIR_BEEP:
            buzzer.duty(0); pir_playing = False

        if pir_cooldown and not pir_playing and ticks_diff(ticks_ms(), t_pir) >= PIR_BEEP + PIR_CD:
            pir_cooldown = False

        if music_playing and ticks_diff(ticks_ms(), t_nt) >= int(melody[melody_idx][1] * tempo):
            melody_idx += 1
            if melody_idx >= len(melody): stop_music()
            else:
                note, _ = melody[melody_idx]
                buzzer.freq(notes[note]); buzzer.duty(512); t_nt = ticks_ms()

        # --- OLED ---
        if oled_update:
            display.fill(0)
            if manual_brightness:
                display.text(f"Brightness:{latest_brightness}%",0,0)
            elif brightness_mode == 'web':
                display.text(f"Web Brightness:", 0, 0)
                display.text(f"{latest_brightness}%", 0, 15)
            else:
                display.text(f"Touch:{tv}",0,0)
                display.text(f"H:{latest_humidity}",0,15)
                display.text(f"T:{latest_temp}",0,30)
            display.show()


        # --- LED Blink ---
        if led_blinking and ticks_diff(ticks_ms(), t_bl) >= 500:
            led_pwm.duty(1023 if led_pwm.duty() == 0 else 0); t_bl = ticks_ms()

        # --- Manual Brightness ---
        if brightness_update and brightness_mode == 'manual' and ticks_diff(ticks_ms(), t_br) >= 1000:
            pv = pot.read()
            volt = round(pv / 4095 * 3.3, 2)
            bri = int(pv * 100 / 4095)
            duty = int((100 - bri) * 1023 / 100)
            led_pwm.duty(duty)
            latest_brightness = bri; latest_voltage = volt
            display.fill(0); display.text(f"B:{bri}%",0,0); display.text(f"V:{volt}",0,10); display.show()
            t_br = ticks_ms()

        # --- درخواست‌ها ---
        s.settimeout(0.1)
        try: conn, addr = s.accept()
        except: conn = None
        if conn:
            conn.settimeout(3); req = conn.recv(1024).decode()

            def send_txt(val): conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\n'); conn.sendall(str(val).encode()); conn.close()

            if 'GET /touch' in req: send_txt(tv); continue
            if 'GET /brightness' in req: send_txt(latest_brightness); continue
            if 'GET /voltage' in req: send_txt(latest_voltage); continue
            if 'GET /temperature' in req: send_txt(latest_temp); continue
            if 'GET /humidity' in req: send_txt(latest_humidity); continue
            if 'GET /lastmotion' in req:
                msg = "No motion detected yet" if last_motion_time is None else ("Just now" if ticks_diff(ticks_ms(), last_motion_time)//1000 == 0 else f"{ticks_diff(ticks_ms(), last_motion_time)//1000} seconds ago")
                send_txt(msg); continue
            if 'GET /pirstatus' in req: send_txt(pir_status); continue

            # --- دستورها ---
            if '/setbrightness?val=' in req:
                try:
                    val = int(req.split('/setbrightness?val=')[1].split()[0])
                    duty = int((100 - val) * 1023 / 100)
                    led_pwm.duty(duty)
                    latest_brightness = val
                    manual_brightness = True
                    brightness_mode = 'web'
                except: pass
            if 'GET /logs' in req:
                conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\n')
                conn.sendall('\n'.join(log_messages).encode())
                conn.close()
                continue
            elif 'GET /clearlogs' in req:  
                log_messages.clear()
                conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\nLogs cleared')
                conn.close()
                continue
            elif 'GET /weather' in req:
                weather = read_map_data()
                if weather:
                    conn.send('HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n')
                    conn.sendall(ujson.dumps(weather).encode())
                else:
                    conn.send('HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError fetching weather')
                conn.close()
                continue


            elif 'POST ' in req:
                try:
                    if 'Content-Length:' in req:
                       length = int(req.split('Content-Length: ')[1].split('\r\n')[0])
                    body = b''
                    while len(body) < length:
                        body += conn.recv(length - len(body))
                    msg = body.decode().strip()
                    print("Received POST message:", msg)
                    msg_lower = msg.lower()

                    
                    if 'POST /addlog' in req:
                        add_log(msg)
                        conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\nLog received')
                    else:
                        add_log(f"User message: {msg}")
                        conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\nCommand processed')
                except Exception as e:
                    conn.send('HTTP/1.1 500 Internal Server Error\n\nError occurred')
                    add_log(f"POST handling error: {e}")
                    
                conn.close()
                continue
            elif '/shell?cmd=' in req:
                try:
                    cmd = req.split('/shell?cmd=')[1].split()[0]
                    decoded_cmd = cmd.replace('%20', ' ')
                    add_log(f"[SHELL] {decoded_cmd}")
                    if decoded_cmd.startswith('city ') and len(decoded_cmd) > 1:
                        new_city = decoded_cmd[5:].strip()
                        cityName = new_city
                        add_log(f"City set to: {cityName}")
                        weather = fetch_weather(cityName)
                        conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\nCity changed to ' + cityName)
                    if decoded_cmd.lower() == 'on' :
                        oled_update = led_blinking = brightness_update = manual_brightness = False
                        led_pwm.duty(0)
                        latest_brightness = 100
                        latest_voltage = "--"
                        display.fill(0)
                        display.text("LED ON", 0, 10)
                        display.show()
                        add_log("LED has been turned on.")
                    elif decoded_cmd.lower().startswith('ask '):
                        prompt = decoded_cmd[4:].strip()
                        if prompt:
                            # ارسال وضعیت فعلی به عنوان context
                            context = f"""
                            Current system status:
                            - Temperature: {latest_temp}°C
                            - Humidity: {latest_humidity}%
                            - LED brightness: {latest_brightness}%
                            - PIR status: {pir_status}
                            """
                            full_prompt = context + "\nUser question: " + prompt
                            response = query_deepseek(full_prompt)
                            add_log(f"[DeepSeek] Q: {prompt} | A: {response}")
                            
                            # پردازش پاسخ برای انجام اقدامات خودکار
                            if "turn on the led" in response.lower():
                                led_pwm.duty(0)
                                add_log("LED turned on based on DeepSeek response.")
                            elif "turn off the led" in response.lower():
                                led_pwm.duty(1023)
                                add_log("LED turned off based on DeepSeek response.")
                            
                            conn.send('HTTP/1.1 200 OK\nContent-Type: text/plain\n\n' + response)
                        else:
                            conn.send('HTTP/1.1 400 Bad Request\nContent-Type: text/plain\n\nPlease provide a question after "ask".')
                    elif cmd.isdigit():
                        bri = int(cmd)
                        if 0 <= bri <= 100:
                             duty = int((100 - bri) * 1023 / 100)
                             led_pwm.duty(duty)
                             latest_brightness = bri
                             brightness_mode = 'manual'
                             manual_brightness = True
                             oled_update = True
                             add_log(f"Brightness set to {bri}% by shell command")
                    elif decoded_cmd.lower() == 'off':
                        oled_update = led_blinking = brightness_update = manual_brightness = False
                        led_pwm.duty(1023)
                        latest_brightness = 0
                        latest_voltage = "--"
                        display.fill(0)
                        display.text("LED OFF", 0, 10)
                        display.show()
                        add_log("LED has been turned off.")
                    elif decoded_cmd.lower() == 'blink':
                        oled_update = brightness_update = manual_brightness = False; led_blinking = True
                        latest_brightness = "0/100"; latest_voltage = "--"
                        add_log("LED is blinking now.")
                        display.fill(0); display.text("BLINK",0,10); display.show()
                    elif decoded_cmd.lower() == 'show':
                        oled_update = True; led_blinking = brightness_update = False; latest_voltage = "--"
                        display.fill(0); display.text("SHOW OLED",0,10); display.show()
                        add_log("Show touchpad value, temp and humidty on the OLED.")
                    elif decoded_cmd.lower() == 'music':
                        oled_update = led_blinking = brightness_update = False; stop_music(); start_music(); latest_voltage = "--"
                        display.fill(0); display.text("MUSIC PLAY",0,10); display.show()
                        add_log("Start playing music!")
                    elif decoded_cmd.lower() == 'stop':
                        oled_update = led_blinking = brightness_update = False; stop_music(); latest_voltage = "--"
                        display.fill(0); display.text("MUSIC STOP",0,10); display.show()
                        add_log("Music has been stopped!")
                    elif decoded_cmd.lower() == 'potbri':
                        brightness_mode = 'manual'; oled_update = led_blinking = False; brightness_update = True; manual_brightness = False
                        display.fill(0); display.text("MANUAL",0,10); display.show()
                        add_log("Brightness manual activated. Now you can adjust the brightness by Potentiometer.")
                    elif decoded_cmd.lower() == 'webbri':
                        brightness_mode = 'web'; oled_update = True; led_blinking = brightness_update = manual_brightness = False
                        latest_voltage = "--"; latest_brightness = 100
                        led_pwm.duty(int((100 - latest_brightness) * 1023 / 100))
                        display.fill(0); display.text("WEB BRIGHTNESS",0,10); display.show()
                        add_log("Brightness mode set to web. Now you can adjust the brightness by Slider.")
                    elif decoded_cmd.lower() == 'piron':
                        pir_enabled = True; latest_voltage = "--"; display.fill(0); display.text("PIR ON",0,10); display.show()
                        add_log("PIR enabled. Now motions can detect!")
                    elif decoded_cmd.lower() == 'piroff':
                        pir_enabled = False; latest_voltage = "--"; display.fill(0); display.text("PIR OFF",0,10); display.show()
                        add_log("PIR disabled. Now motions can not detect!")
                except Exception as e:
                    add_log(f"Error processing shell command: {e}")
            elif '/?led=on' in req:
                oled_update = led_blinking = brightness_update = manual_brightness = False
                led_pwm.duty(0); latest_brightness = 100; latest_voltage = "--"
                display.fill(0); display.text("LED ON",0,10); display.show()
                add_log("LED has been turned on.")
            elif '/?led=off' in req:
                oled_update = led_blinking = brightness_update = manual_brightness = False
                led_pwm.duty(1023); latest_brightness = 0; latest_voltage = "--"
                display.fill(0); display.text("LED OFF",0,10); display.show()
                add_log("LED has been turned off.")
            elif '/?led=blink' in req:
                oled_update = brightness_update = manual_brightness = False; led_blinking = True
                latest_brightness = "0/100"; latest_voltage = "--"
                display.fill(0); display.text("BLINK",0,10); display.show()
                add_log("LED is blinking now.")
            elif '/?led=manual' in req:
                brightness_mode = 'manual'; oled_update = led_blinking = False; brightness_update = True; manual_brightness = False
                display.fill(0); display.text("MANUAL",0,10); display.show()
                add_log("Brightness manual activated. Now you can adjust the brightness by Potentiometer.")
            elif '/?music=play' in req:
                oled_update = led_blinking = brightness_update = False; stop_music(); start_music(); latest_voltage = "--"
                display.fill(0); display.text("MUSIC PLAY",0,10); display.show()
                add_log("Start playing music!")
            elif '/?music=stop' in req:
                oled_update = led_blinking = brightness_update = False; stop_music(); latest_voltage = "--"
                display.fill(0); display.text("MUSIC STOP",0,10); display.show()
                add_log("Music has been stopped!")
            elif '/?show-tv' in req:
                oled_update = True; led_blinking = brightness_update = False; latest_voltage = "--"
                display.fill(0); display.text("SHOW OLED",0,10); display.show()
                add_log("Show touchpad value, temp and humidty on the OLED")
            elif '/?pir=on' in req:
                pir_enabled = True; latest_voltage = "--"; display.fill(0); display.text("PIR ON",0,10); display.show()
                add_log("PIR enabled. Now motions can detect!")
            elif '/?pir=off' in req:
                pir_enabled = False; latest_voltage = "--"; display.fill(0); display.text("PIR OFF",0,10); display.show()
                add_log("PIR disabled. Now motions can not detect!")
            elif '/?led=web' in req:
                brightness_mode = 'web'; oled_update = True; led_blinking = brightness_update = manual_brightness = False
                latest_voltage = "--"; latest_brightness = 100
                led_pwm.duty(int((100 - latest_brightness) * 1023 / 100))
                display.fill(0); display.text("WEB BRIGHTNESS",0,10); display.show()
                add_log("Brightness mode set to web. Now you can adjust the brightness by Slider.")

            conn.send('HTTP/1.1 200 OK\nContent-Type: text/html\n\n')
            conn.sendall(web_page().encode()); conn.close()

        time.sleep_ms(10)

    except KeyboardInterrupt:
        try: stop_music(); led_pwm.deinit(); buzzer.deinit(); s.close()
        except: pass
        thread_running = False
        add_log("Program stopped cleanly"); raise
    except:
        try: conn.close()
        except: pass
        time.sleep_ms(10)






