import os
import time
import json
import logging
import paho.mqtt.client as mqtt
import requests

log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

# Configuration from environment variables
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.2")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "co2/office/co2_ppm")
WLED_URL = os.getenv("WLED_URL", "http://wled-lamp.local/json")
MIN_VAL = int(os.getenv("MIN_VAL", 440))
MAX_VAL = int(os.getenv("MAX_VAL", 1000))
NORMAL_FX = int(os.getenv("NORMAL_FX", 37))
TOO_HIGH_FX = int(os.getenv("TOO_HIGH_FX", 0))
INTERVAL = int(os.getenv("INTERVAL", 60))
MAX_RANGE = 255

data_points = []

def on_message(client, userdata, msg):
    try:
        co2_value = int(msg.payload.decode("utf-8"))
        data_points.append(co2_value)
    except ValueError:
        logging.error("Invalid CO2 value received.")

def value_to_color(value):
    """Convert a value to an RGB color transitioning from green to red."""
    value = max(MIN_VAL, min(MAX_VAL, value))
    norm = (value - MIN_VAL) / (MAX_VAL - MIN_VAL)
    r = int(MAX_RANGE * norm)
    g = int(MAX_RANGE * (1 - norm))
    b = 0
    return [r, g, b]

def send_wled_request(value):
    """Send an HTTP POST request to the WLED endpoint with the calculated color."""
    headers = {"Content-Type": "application/json"}
    color = value_to_color(value)
    logging.debug(f'CO2 value: {value}, color: {color}')
    payload = {
        "tt": 0,
        "seg": [{"id": 0, "ps": 0, "pal": 0, "fx": value < MAX_VAL and NORMAL_FX or TOO_HIGH_FX, "col": [color, [0, 0, 0], [0, 0, 0]]}]
    }
    try:
        logging.debug(f'sending payload: {json.dumps(payload)}')
        response = requests.post(WLED_URL, json=payload, headers=headers)
        response.raise_for_status()
        logging.info("Successfully updated WLED color.")
    except requests.RequestException as e:
        logging.error(f"Error sending request: {e}")

def main():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()

    while True:
        if data_points:
            avg_value = sum(data_points) / len(data_points)
            data_points.clear()
            send_wled_request(int(avg_value))
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()