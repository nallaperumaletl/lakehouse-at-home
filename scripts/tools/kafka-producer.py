import json
import time
import random
from datetime import datetime
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

# generate sample data
users = [f"user_{i}" for i in range(1, 21)]
products = ["laptop", "phone", "tablet", "monitor", "keyboard", "mouse"]
event_types = ["view", "clock", "purchase", "add_to_cart"]

print("Sending events to Kafka topic 'events' ..")

counter = 0

try:
    while True:
        event = {
            "event_id": counter,
            "timestamp": datetime.now().isoformat(),
            "user_id": random.choice(users),
            "event_type": random.choice(event_types),
            "product": random.choice(products),
            "price": round(random.uniform(50, 2000), 2),
            "quantity": random.randint(1, 5),
        }

        producer.send("events", value=event)
        print(f"Sent: {event}")

        counter += 1
        time.sleep(random.uniform(0.5, 2.0))

except KeyboardInterrupt:
    print("\nStopping producer..")
    producer.close()
