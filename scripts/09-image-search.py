"""
Image Search with CLIP Embeddings
=================================
Demonstrates multimodal image search using CLIP (Contrastive Language-Image Pre-training).

Features:
- Text-to-image search (find images matching a text description)
- Image-to-image search (find similar images)
- Hybrid search (combine visual similarity with metadata filters)

CLIP enables searching images using natural language descriptions because it
learns a shared embedding space for both images and text.

Requirements:
    pip install transformers pillow

Usage:
    python scripts/09-image-search.py

    # With real CLIP model (slower but more accurate)
    USE_MOCK_EMBEDDINGS=false python scripts/09-image-search.py
"""

import os
import sys
from typing import List, Optional
from dataclasses import dataclass

import numpy as np
import lancedb
import pandas as pd

# Configuration
LANCE_PATH = os.environ.get("LANCE_PATH", "/tmp/lance_image_search")
USE_MOCK = os.environ.get("USE_MOCK_EMBEDDINGS", "true").lower() == "true"
CLIP_MODEL = "openai/clip-vit-base-patch32"  # 512 dimensions


@dataclass
class ImageRecord:
    """Represents an image with metadata."""
    id: str
    filename: str
    description: str
    category: str
    tags: List[str]
    width: int
    height: int


# =============================================================================
# Sample Image Catalog (simulated - in production these would be real images)
# =============================================================================
SAMPLE_IMAGES = [
    # Nature
    ImageRecord("img-001", "sunset_beach.jpg", "Beautiful sunset over a tropical beach with palm trees", "nature", ["sunset", "beach", "tropical", "ocean"], 1920, 1080),
    ImageRecord("img-002", "mountain_lake.jpg", "Serene mountain lake reflecting snow-capped peaks", "nature", ["mountain", "lake", "snow", "reflection"], 2560, 1440),
    ImageRecord("img-003", "forest_path.jpg", "Winding path through an autumn forest with golden leaves", "nature", ["forest", "autumn", "path", "trees"], 1920, 1280),
    ImageRecord("img-004", "waterfall.jpg", "Majestic waterfall cascading down rocky cliffs", "nature", ["waterfall", "rocks", "water", "mist"], 1080, 1920),

    # Animals
    ImageRecord("img-005", "golden_retriever.jpg", "Happy golden retriever playing in a park", "animals", ["dog", "golden retriever", "park", "pet"], 1200, 800),
    ImageRecord("img-006", "cat_sleeping.jpg", "Fluffy orange cat sleeping on a cozy blanket", "animals", ["cat", "sleeping", "orange", "cozy"], 1600, 1200),
    ImageRecord("img-007", "bird_flight.jpg", "Eagle soaring through blue sky with wings spread", "animals", ["bird", "eagle", "flying", "sky"], 2000, 1333),
    ImageRecord("img-008", "underwater_fish.jpg", "Colorful tropical fish swimming in coral reef", "animals", ["fish", "coral", "underwater", "tropical"], 1920, 1080),

    # Food
    ImageRecord("img-009", "pizza.jpg", "Freshly baked pepperoni pizza with melted cheese", "food", ["pizza", "pepperoni", "cheese", "italian"], 1200, 1200),
    ImageRecord("img-010", "sushi_platter.jpg", "Elegant sushi platter with various rolls and sashimi", "food", ["sushi", "japanese", "seafood", "platter"], 1600, 1067),
    ImageRecord("img-011", "fruit_bowl.jpg", "Colorful bowl of fresh fruits including berries and citrus", "food", ["fruit", "healthy", "colorful", "fresh"], 1400, 1400),
    ImageRecord("img-012", "coffee_latte.jpg", "Artisan latte with beautiful leaf pattern in foam", "food", ["coffee", "latte", "art", "cafe"], 1080, 1080),

    # Architecture
    ImageRecord("img-013", "modern_building.jpg", "Sleek modern skyscraper with glass facade", "architecture", ["building", "modern", "glass", "skyscraper"], 1080, 1920),
    ImageRecord("img-014", "ancient_temple.jpg", "Ancient stone temple with intricate carvings", "architecture", ["temple", "ancient", "stone", "historic"], 2400, 1600),
    ImageRecord("img-015", "bridge_night.jpg", "Illuminated suspension bridge at night over river", "architecture", ["bridge", "night", "lights", "river"], 1920, 1080),
    ImageRecord("img-016", "cozy_interior.jpg", "Warm cozy living room with fireplace and bookshelves", "architecture", ["interior", "cozy", "fireplace", "home"], 1600, 1200),

    # Technology
    ImageRecord("img-017", "laptop_desk.jpg", "Modern laptop on minimalist desk setup", "technology", ["laptop", "desk", "workspace", "minimal"], 1920, 1280),
    ImageRecord("img-018", "robot_arm.jpg", "Industrial robot arm in manufacturing facility", "technology", ["robot", "industrial", "automation", "factory"], 1600, 1067),
    ImageRecord("img-019", "server_room.jpg", "Rows of servers in data center with blue lights", "technology", ["servers", "data center", "computing", "network"], 2000, 1333),
    ImageRecord("img-020", "smartphone.jpg", "Latest smartphone displaying colorful app icons", "technology", ["phone", "smartphone", "mobile", "apps"], 1080, 1920),
]


class CLIPEmbedding:
    """
    CLIP embedding generator for images and text.

    CLIP (Contrastive Language-Image Pre-training) creates embeddings
    in a shared space where similar images and text are close together.
    """

    def __init__(self, model_name: str = CLIP_MODEL, use_mock: bool = False):
        self.model_name = model_name
        self.use_mock = use_mock
        self.dimension = 512  # CLIP ViT-B/32 dimension
        self._model = None
        self._processor = None

    def _load_model(self):
        """Lazy load CLIP model."""
        if self._model is None and not self.use_mock:
            try:
                from transformers import CLIPProcessor, CLIPModel

                print(f"Loading CLIP model: {self.model_name}")
                self._model = CLIPModel.from_pretrained(self.model_name)
                self._processor = CLIPProcessor.from_pretrained(self.model_name)
                print("CLIP model loaded")
            except ImportError:
                print("transformers not installed, using mock embeddings")
                self.use_mock = True
            except Exception as e:
                print(f"Failed to load CLIP: {e}, using mock embeddings")
                self.use_mock = True

    def encode_text(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for text descriptions."""
        if self.use_mock:
            return self._mock_embeddings(texts)

        self._load_model()

        if self._model is None:
            return self._mock_embeddings(texts)

        import torch

        inputs = self._processor(text=texts, return_tensors="pt", padding=True, truncation=True)

        with torch.no_grad():
            text_features = self._model.get_text_features(**inputs)
            # Normalize
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        return text_features.numpy()

    def encode_image_descriptions(self, descriptions: List[str]) -> np.ndarray:
        """
        Generate embeddings for image descriptions.

        In a real system, you would encode actual images. Here we use
        descriptions as a proxy since we don't have real image files.
        """
        return self.encode_text(descriptions)

    def _mock_embeddings(self, items: List[str]) -> np.ndarray:
        """Generate deterministic mock embeddings."""
        embeddings = []
        for item in items:
            np.random.seed(hash(item) % (2**32))
            vec = np.random.randn(self.dimension).astype(np.float32)
            vec = vec / np.linalg.norm(vec)  # Normalize
            embeddings.append(vec)
        return np.array(embeddings)


def create_image_table(db, clip_model: CLIPEmbedding) -> lancedb.table.Table:
    """Create and populate the images table with CLIP embeddings."""
    print("\n[1] Creating image embeddings...")

    # Generate embeddings from descriptions (proxy for real images)
    descriptions = [img.description for img in SAMPLE_IMAGES]
    embeddings = clip_model.encode_image_descriptions(descriptions)

    # Prepare records
    records = []
    for img, embedding in zip(SAMPLE_IMAGES, embeddings):
        record = {
            "id": img.id,
            "filename": img.filename,
            "description": img.description,
            "category": img.category,
            "tags": ",".join(img.tags),
            "width": img.width,
            "height": img.height,
            "aspect_ratio": round(img.width / img.height, 2),
            "vector": embedding.tolist(),
        }
        records.append(record)

    # Create table
    table = db.create_table("images", data=records, mode="overwrite")
    print(f"    Created table with {table.count_rows()} images")

    return table


def text_to_image_search(
    table: lancedb.table.Table,
    query: str,
    clip_model: CLIPEmbedding,
    limit: int = 5,
    filter_expr: str = None,
) -> pd.DataFrame:
    """
    Search for images using natural language description.

    This is the key capability of CLIP - finding images that match
    a text description without needing exact keyword matches.
    """
    # Generate text embedding
    query_vec = clip_model.encode_text([query])[0]

    # Search
    search = table.search(query_vec.tolist())
    if filter_expr:
        search = search.where(filter_expr)

    return search.limit(limit).to_pandas()


def image_to_image_search(
    table: lancedb.table.Table,
    image_id: str,
    limit: int = 5,
) -> pd.DataFrame:
    """
    Find images similar to a given image.

    Uses the stored embedding to find visually similar images.
    """
    # Get the source image embedding
    source = table.search().where(f"id = '{image_id}'").limit(1).to_pandas()
    if len(source) == 0:
        raise ValueError(f"Image not found: {image_id}")

    source_vec = source.iloc[0]['vector']

    # Search for similar (excluding source)
    return table.search(source_vec).where(f"id != '{image_id}'").limit(limit).to_pandas()


def demo_text_to_image(table, clip_model):
    """Demonstrate text-to-image search."""
    print("\n" + "=" * 60)
    print("TEXT-TO-IMAGE SEARCH")
    print("=" * 60)
    print("Find images using natural language descriptions")

    queries = [
        # Direct descriptions
        ("a dog playing outside", None),
        ("sushi and japanese food", None),

        # Abstract/conceptual queries
        ("peaceful relaxing scene", None),
        ("something delicious to eat", None),

        # With filters
        ("beautiful scenery", "category = 'nature'"),
        ("modern design", "category = 'architecture'"),

        # Mood-based queries
        ("warm and cozy atmosphere", None),
        ("high tech futuristic", None),
    ]

    for query, filter_expr in queries:
        print(f"\n{'─' * 60}")
        print(f"Query: \"{query}\"")
        if filter_expr:
            print(f"Filter: {filter_expr}")
        print("─" * 60)

        results = text_to_image_search(table, query, clip_model, limit=3, filter_expr=filter_expr)

        for idx, row in results.iterrows():
            score = 1 - row['_distance']
            print(f"\n  [{score:.3f}] {row['filename']}")
            print(f"          {row['description'][:60]}...")
            print(f"          Category: {row['category']} | Tags: {row['tags']}")


def demo_image_to_image(table):
    """Demonstrate image-to-image similarity search."""
    print("\n" + "=" * 60)
    print("IMAGE-TO-IMAGE SEARCH")
    print("=" * 60)
    print("Find visually similar images")

    seed_images = ["img-001", "img-005", "img-009", "img-017"]

    for seed_id in seed_images:
        # Get seed image info
        seed = table.search().where(f"id = '{seed_id}'").limit(1).to_pandas()
        if len(seed) == 0:
            continue

        print(f"\n{'─' * 60}")
        print(f"Seed: {seed.iloc[0]['filename']}")
        print(f"      {seed.iloc[0]['description'][:50]}...")
        print("─" * 60)

        results = image_to_image_search(table, seed_id, limit=3)

        print("Similar images:")
        for idx, row in results.iterrows():
            score = 1 - row['_distance']
            print(f"  [{score:.3f}] {row['filename']}")
            print(f"          {row['description'][:50]}...")


def demo_hybrid_search(table, clip_model):
    """Demonstrate hybrid search combining visual and metadata filters."""
    print("\n" + "=" * 60)
    print("HYBRID SEARCH (Visual + Metadata)")
    print("=" * 60)

    # Example: Find nature photos in landscape orientation
    print("\n[Example 1] Nature photos in landscape orientation")
    print("Query: 'scenic view' + aspect_ratio > 1.2")

    results = text_to_image_search(
        table,
        "scenic landscape view",
        clip_model,
        limit=5,
        filter_expr="category = 'nature' AND aspect_ratio > 1.2"
    )

    for idx, row in results.iterrows():
        score = 1 - row['_distance']
        print(f"  [{score:.3f}] {row['filename']} ({row['width']}x{row['height']})")

    # Example: Portrait-oriented food photos
    print("\n[Example 2] Food photos in portrait/square orientation")
    print("Query: 'appetizing food' + aspect_ratio <= 1.2")

    results = text_to_image_search(
        table,
        "appetizing delicious food",
        clip_model,
        limit=5,
        filter_expr="category = 'food' AND aspect_ratio <= 1.2"
    )

    for idx, row in results.iterrows():
        score = 1 - row['_distance']
        print(f"  [{score:.3f}] {row['filename']} ({row['width']}x{row['height']})")


def demo_cross_modal(table, clip_model):
    """Demonstrate cross-modal understanding."""
    print("\n" + "=" * 60)
    print("CROSS-MODAL UNDERSTANDING")
    print("=" * 60)
    print("CLIP understands relationships between concepts")

    # Queries that require understanding relationships
    queries = [
        "something you'd see at the ocean",
        "a workspace for remote work",
        "animals in their natural habitat",
        "something you'd find in a restaurant",
    ]

    for query in queries:
        print(f"\n{'─' * 40}")
        print(f"Query: \"{query}\"")

        results = text_to_image_search(table, query, clip_model, limit=2)

        for idx, row in results.iterrows():
            score = 1 - row['_distance']
            print(f"  [{score:.3f}] {row['filename']}: {row['description'][:40]}...")


def main():
    print("=" * 60)
    print("IMAGE SEARCH WITH CLIP EMBEDDINGS")
    print("=" * 60)
    print(f"Lance path: {LANCE_PATH}")
    print(f"Mock embeddings: {USE_MOCK}")
    print(f"CLIP model: {CLIP_MODEL}")

    # Initialize
    os.makedirs(LANCE_PATH, exist_ok=True)
    db = lancedb.connect(LANCE_PATH)

    # Initialize CLIP
    clip_model = CLIPEmbedding(use_mock=USE_MOCK)
    print(f"Embedding dimension: {clip_model.dimension}")

    # Create image table
    table = create_image_table(db, clip_model)

    # Run demos
    demo_text_to_image(table, clip_model)
    demo_image_to_image(table)
    demo_hybrid_search(table, clip_model)
    demo_cross_modal(table, clip_model)

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"Data stored at: {LANCE_PATH}")
    print("\nTo use real CLIP embeddings:")
    print("  USE_MOCK_EMBEDDINGS=false python scripts/09-image-search.py")


if __name__ == "__main__":
    main()
