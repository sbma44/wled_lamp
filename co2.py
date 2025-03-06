import sys
import time
import requests

MAX_RANGE = 255
NORMAL_FX = 37
TOO_HIGH_FX = 0
min_val, max_val = 440, 1000

def fetch_json_with_pure_python_and_configurable_timeout(url, timeout=0.5):
    import json
    import urllib.request
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(response.read())
    except:
        return False

def value_to_color(value):
    """Convert a value to an RGB color transitioning from green to red."""
    # Clamp value within bounds
    value = max(min_val, min(max_val, value))

    # Normalize to 0-1 range (0 = green, 1 = red)
    norm = (value - min_val) / (max_val - min_val)

    # Interpolate from green (0,MAX_RANGE,0) to red (MAX_RANGE,0,0)
    r = int(MAX_RANGE * norm)
    g = int(MAX_RANGE * (1 - norm))
    b = 0  # No blue component in transition

    return [r, g, b]

def send_wled_request(value):
    """Send an HTTP POST request to the WLED endpoint with the calculated color."""
    url = "http://wled-lamp.local/json"
    headers = {"Content-Type": "application/json"}

    black = [0, 0, 0]
    color = value_to_color(value)
    payload = {
        "tt": 0,
        "seg": [{"id": 0, "fx": value < max_val and NORMAL_FX or TOO_HIGH_FX, "col": [color, black, black]}]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        print("Successfully updated WLED color.")
    except requests.RequestException as e:
        print(f"Error sending request: {e}")

if __name__ == '__main__':
    while True:
        co2_data = fetch_json_with_pure_python_and_configurable_timeout('http://192.168.1.2/flask/redis/co2/office/co2_ppm')
        if (co2_data):
            send_wled_request(int(co2_data['co2/office/co2_ppm']))
        time.sleep(60)