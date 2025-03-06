FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests paho-mqtt

# Copy script into the container
COPY co2.py /app/co2.py

# Set environment variables (default values can be overridden at runtime)
ENV MQTT_BROKER=192.168.1.2 \
    MQTT_TOPIC=co2/office/co2_ppm \
    WLED_URL=http://wled-lamp.local/json \
    MIN_VAL=440 \
    MAX_VAL=1000 \
    NORMAL_FX=37 \
    TOO_HIGH_FX=0 \
    INTERVAL=60

# Command to run the script
CMD ["python", "/app/co2.py"]