import os
from google.cloud import firestore

# Hardcode project ID explicitly as a string
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-7c7728dc232e"

def seed_database():
    """Seeds initial recipes and pantry items into Firestore."""
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    
    recipes = [
        {
            "id": "recipe_1",
            "title": "Mediterranean Quinoa Salad",
            "category": "Lunch",
            "prep_time_mins": 15,
            "ingredients": ["quinoa", "cucumber", "feta cheese", "olive oil", "tomatoes"],
            "instructions": "Cook quinoa. Mix with chopped cucumber, tomatoes, feta, and drizzle with olive oil."
        },
        {
            "id": "recipe_2",
            "title": "Avocado & Spinach Power Smoothie",
            "category": "Breakfast",
            "prep_time_mins": 5,
            "ingredients": ["avocado", "spinach", "banana", "almond milk"],
            "instructions": "Blend avocado, spinach, banana, and almond milk until smooth."
        },
        {
            "id": "recipe_3",
            "title": "Classic Chicken Noodle Soup",
            "category": "Dinner",
            "prep_time_mins": 30,
            "ingredients": ["chicken breast", "carrots", "celery", "egg noodles", "chicken broth"],
            "instructions": "Simmer chicken breast, carrots, and celery in broth. Add egg noodles and cook until tender."
        }
    ]

    pantry_items = [
        {"name": "quinoa", "quantity": "500g", "category": "Grains"},
        {"name": "olive oil", "quantity": "1 bottle", "category": "Oils & Condiments"},
        {"name": "avocado", "quantity": "3 items", "category": "Produce"},
        {"name": "spinach", "quantity": "1 bag", "category": "Produce"},
        {"name": "feta cheese", "quantity": "200g", "category": "Dairy"}
    ]

    print(f"Seeding database for project: {FIRESTORE_PROJECT_ID}...")

    # Seed recipes
    for recipe in recipes:
        doc_ref = db.collection("recipes").document(recipe["id"])
        doc_ref.set(recipe)
        print(f"Seeded recipe: {recipe['title']}")

    # Seed pantry items
    for item in pantry_items:
        doc_id = item["name"].lower().replace(" ", "_")
        doc_ref = db.collection("pantry_items").document(doc_id)
        doc_ref.set(item)
        print(f"Seeded pantry item: {item['name']}")

    print("Firestore database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
