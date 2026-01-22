"""
Kafka Producer for Lance Streaming Pipeline
============================================
Generates product data and sends to Kafka for the Lance embedding pipeline.

Usage:
    python scripts/kafka-lance-producer.py

    # With custom settings
    KAFKA_BOOTSTRAP=localhost:9092 KAFKA_TOPIC=products python scripts/kafka-lance-producer.py
"""

import json
import time
import random
from datetime import datetime
import os

# Configuration
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "products")
RATE_LIMIT = float(os.environ.get("RATE_LIMIT", "1.0"))  # messages per second

# Product catalog for realistic data generation
CATEGORIES = {
    "electronics": {
        "products": [
            ("Wireless Bluetooth Headphones", "Premium noise-canceling headphones with 30-hour battery life and crystal-clear audio quality"),
            ("Smart Watch Pro", "Advanced fitness tracker with heart rate monitoring, GPS, and sleep analysis"),
            ("USB-C Hub Adapter", "7-in-1 multiport hub with HDMI, USB 3.0, SD card reader, and PD charging"),
            ("Mechanical Keyboard", "RGB backlit mechanical keyboard with Cherry MX switches for gaming and typing"),
            ("Portable Power Bank", "20000mAh high-capacity power bank with fast charging support"),
            ("Wireless Earbuds", "True wireless earbuds with active noise cancellation and transparency mode"),
            ("4K Webcam", "Ultra HD webcam with autofocus, built-in microphone, and privacy shutter"),
            ("Smart Home Speaker", "Voice-controlled speaker with premium audio and smart home integration"),
        ],
        "price_range": (29.99, 299.99),
    },
    "clothing": {
        "products": [
            ("Cotton T-Shirt", "Soft 100% organic cotton t-shirt with comfortable fit and breathable fabric"),
            ("Denim Jeans", "Classic straight-fit jeans made from premium stretch denim"),
            ("Running Shoes", "Lightweight athletic shoes with responsive cushioning and breathable mesh"),
            ("Winter Jacket", "Waterproof insulated jacket with removable hood and multiple pockets"),
            ("Yoga Pants", "High-waisted yoga pants with four-way stretch and moisture-wicking fabric"),
            ("Casual Sneakers", "Versatile everyday sneakers with memory foam insoles"),
            ("Wool Sweater", "Cozy merino wool sweater with classic cable knit pattern"),
            ("Athletic Shorts", "Quick-dry performance shorts with built-in liner and zip pocket"),
        ],
        "price_range": (19.99, 149.99),
    },
    "home": {
        "products": [
            ("Memory Foam Pillow", "Ergonomic cooling memory foam pillow for optimal neck support"),
            ("Robot Vacuum", "Smart robot vacuum with mapping technology and app control"),
            ("Air Purifier", "HEPA air purifier with real-time air quality monitoring"),
            ("Coffee Maker", "Programmable drip coffee maker with thermal carafe and brew strength control"),
            ("LED Desk Lamp", "Adjustable LED desk lamp with multiple brightness levels and USB charging"),
            ("Weighted Blanket", "Premium weighted blanket with glass beads for better sleep"),
            ("Stand Mixer", "Professional stand mixer with multiple attachments for baking"),
            ("Smart Thermostat", "Wi-Fi enabled thermostat with energy saving features and voice control"),
        ],
        "price_range": (39.99, 399.99),
    },
    "sports": {
        "products": [
            ("Yoga Mat", "Non-slip eco-friendly yoga mat with alignment guides"),
            ("Resistance Bands Set", "Set of 5 resistance bands with different tension levels"),
            ("Foam Roller", "High-density foam roller for muscle recovery and deep tissue massage"),
            ("Jump Rope", "Speed jump rope with ball bearings and adjustable length"),
            ("Dumbbell Set", "Adjustable dumbbell set with quick-change weight system"),
            ("Exercise Ball", "Anti-burst stability ball for core workouts and stretching"),
            ("Pull-Up Bar", "Doorway pull-up bar with multiple grip positions"),
            ("Fitness Tracker Band", "Waterproof activity tracker with heart rate and sleep monitoring"),
        ],
        "price_range": (14.99, 199.99),
    },
    "books": {
        "products": [
            ("Python Programming Guide", "Comprehensive guide to Python programming from beginner to advanced"),
            ("Data Science Handbook", "Essential handbook covering statistics, machine learning, and data visualization"),
            ("Clean Code Principles", "Best practices for writing maintainable and efficient code"),
            ("System Design Interview", "In-depth preparation guide for system design interviews"),
            ("Machine Learning Fundamentals", "Introduction to machine learning algorithms and applications"),
            ("Cloud Architecture Patterns", "Design patterns for building scalable cloud applications"),
            ("DevOps Practices", "Modern DevOps practices for continuous integration and deployment"),
            ("Database Internals", "Deep dive into database storage engines and distributed systems"),
        ],
        "price_range": (24.99, 59.99),
    },
}


def generate_product():
    """Generate a random product."""
    category = random.choice(list(CATEGORIES.keys()))
    cat_data = CATEGORIES[category]
    name, description = random.choice(cat_data["products"])
    min_price, max_price = cat_data["price_range"]

    return {
        "id": f"prod_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
        "name": name,
        "description": description,
        "category": category,
        "price": round(random.uniform(min_price, max_price), 2),
        "timestamp": datetime.now().isoformat(),
    }


def main():
    print("=" * 60)
    print("KAFKA PRODUCER FOR LANCE PIPELINE")
    print("=" * 60)
    print(f"Bootstrap servers: {KAFKA_BOOTSTRAP}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Rate limit: {RATE_LIMIT} msg/sec")
    print("=" * 60)

    try:
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        print("\nConnected to Kafka")
    except Exception as e:
        print(f"\nFailed to connect to Kafka: {e}")
        print("Make sure Kafka is running: docker compose -f docker-compose-kafka.yml up -d")
        return

    print(f"\nSending products to '{KAFKA_TOPIC}' topic...")
    print("Press Ctrl+C to stop\n")

    counter = 0
    try:
        while True:
            product = generate_product()
            producer.send(KAFKA_TOPIC, value=product)
            counter += 1

            print(
                f"[{counter}] {product['category']:12} | "
                f"{product['name'][:35]:35} | "
                f"${product['price']:>7.2f}"
            )

            time.sleep(1.0 / RATE_LIMIT)

    except KeyboardInterrupt:
        print(f"\n\nStopping producer after {counter} messages...")
    finally:
        producer.close()
        print("Producer closed.")


if __name__ == "__main__":
    main()
