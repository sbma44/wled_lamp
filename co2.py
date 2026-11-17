import os
import time
import threading
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
# Seconds to wait on the lamp before giving up on a request.
WLED_TIMEOUT = float(os.getenv("WLED_TIMEOUT", 10))
# If no MQTT messages arrive for this many seconds, force an MQTT reconnect.
# Catches cases paho's own keepalive doesn't (e.g. lost subscription).
MQTT_STALE_AFTER = int(os.getenv("MQTT_STALE_AFTER", INTERVAL * 10))
MAX_RANGE = 255

data_points = []
data_lock = threading.Lock()
last_message_time = time.monotonic()

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        logging.error(f"MQTT connect failed: {reason_code}")
        return
    logging.info(f"Connected to MQTT broker {MQTT_BROKER}, subscribing to {MQTT_TOPIC}")
    # Subscribe here so the subscription is restored after every reconnect.
    client.subscribe(MQTT_TOPIC)

def on_disconnect(client, userdata, flags, reason_code, properties):
    logging.warning(f"Disconnected from MQTT broker ({reason_code}); paho will retry")

def on_message(client, userdata, msg):
    global last_message_time
    last_message_time = time.monotonic()
    try:
        co2_value = int(msg.payload.decode("utf-8"))
        with data_lock:
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
    """Send an HTTP POST request to the WLED endpoint with the calculated color.

    Returns True on success. Each call opens a fresh connection (no Session),
    so there's no stale keep-alive socket to the lamp after a network change.
    """
    headers = {"Content-Type": "application/json"}
    color = value_to_color(value)
    logging.debug(f'CO2 value: {value}, color: {color}')
    payload = {
        "tt": 0,
        "seg": [{"id": 0, "ps": 0, "pal": 0, "fx": value < MAX_VAL and NORMAL_FX or TOO_HIGH_FX, "col": [color, [0, 0, 0], [0, 0, 0]]}]
    }
    try:
        logging.debug(f'sending payload: {json.dumps(payload)}')
        response = requests.post(WLED_URL, json=payload, headers=headers, timeout=WLED_TIMEOUT)
        response.raise_for_status()
        logging.info("Successfully updated WLED color.")
        return True
    except requests.RequestException as e:
        logging.error(f"Error sending request: {e}")
        return False

def main():
    global last_message_time
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    # Back off gently so we don't hammer the Pi while it's unreachable.
    client.reconnect_delay_set(min_delay=5, max_delay=120)
    # connect_async + loop_start: the network thread keeps retrying the
    # connection (including the first one) instead of crashing at startup.
    client.connect_async(MQTT_BROKER, keepalive=60)
    client.loop_start()

    pending_value = None  # last value we failed to deliver to the lamp
    while True:
        time.sleep(INTERVAL)

        with data_lock:
            points = data_points[:]
            data_points.clear()
        if points:
            pending_value = int(sum(points) / len(points))

        # Retry the lamp once per interval until it accepts the latest value.
        if pending_value is not None and send_wled_request(pending_value):
            pending_value = None

        if time.monotonic() - last_message_time > MQTT_STALE_AFTER:
            logging.warning(f"No MQTT messages in {MQTT_STALE_AFTER}s; forcing reconnect")
            last_message_time = time.monotonic()  # don't retry again until another window passes
            try:
                client.reconnect()
            except Exception as e:
                # paho's loop thread will keep retrying on its own.
                logging.error(f"MQTT reconnect failed: {e}")

if __name__ == "__main__":
    main()