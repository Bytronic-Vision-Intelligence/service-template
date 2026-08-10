from dependencies.mqtt_functions import *

from dependencies import loadConfig
import time
import threading
from queue import Empty, Queue
from mqtt_client import MQTTClient, MQTTConfig
#
IP = loadConfig.return_config_value("ip")
PORT = loadConfig.return_config_value("port")
TRIGGER_TOPIC = loadConfig.return_config_value("trigger_topic")
OUTPUT_TOPIC = loadConfig.return_config_value("output_topic") #this should be adjusted to suit your worker requirements

def worker_process_function():
    print("insert your program here")

def main():
    config = MQTTConfig(host=IP, port=PORT)
    client = MQTTClient(config)
    client.connect()

    event_queue = Queue()
    stop_event = threading.Event()
    subscribe_thread = start_subscribe_thread(IP, PORT, TRIGGER_TOPIC, event_queue, stop_event)

    try:
        while True:
            time.sleep(0.1)

            try:
                msg = event_queue.get_nowait()
            except Empty:
                continue

            if msg is None:
                print("Received invalid trigger payload; ignoring.")
                continue

            worker_process_function()

    except KeyboardInterrupt:
        print("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        if subscribe_thread.is_alive():
            subscribe_thread.join(timeout=2)

if __name__ == "__main__":
    main()