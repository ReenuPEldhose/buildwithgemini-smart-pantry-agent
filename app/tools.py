import json
import os
import urllib.parse
import urllib.request
import uuid
from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from google.cloud import firestore, storage

# Hardcode project ID and bucket name as string constants explicitly
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-7c7728dc232e"
MEDIA_BUCKET_NAME = "smart-pantry-media-qwiklabs-gcp-02-7c7728dc232e"


def _get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with the hardcoded project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)

def search_recipes(ingredient_query: str = "", category: str = "") -> list[dict]:
    """Search for recipes in Firestore by ingredient keyword or category.
    
    Args:
        ingredient_query: Optional ingredient name or keyword (e.g. 'quinoa', 'avocado').
        category: Optional recipe category (e.g. 'Breakfast', 'Lunch', 'Dinner').
        
    Returns:
        List of matching recipe documents.
    """
    db = _get_firestore_client()
    query = db.collection("recipes")
    
    if category:
        query = query.where("category", "==", category)
        
    docs = query.stream()
    results = []
    
    ingredient_lower = ingredient_query.lower().strip() if ingredient_query else ""
    
    for doc in docs:
        data = doc.to_dict()
        if ingredient_lower:
            ingredients = [i.lower() for i in data.get("ingredients", [])]
            title = data.get("title", "").lower()
            if not any(ingredient_lower in ing for ing in ingredients) and ingredient_lower not in title:
                continue
        results.append(data)
        
    return results


def add_pantry_item(item_name: str, quantity: str, category: str = "General") -> dict:
    """Add or update an item in the user's pantry collection in Firestore.
    
    Args:
        item_name: Name of the pantry item (e.g. 'olive oil', 'eggs').
        quantity: Quantity string (e.g. '1 bottle', '12 items').
        category: Food category (e.g. 'Produce', 'Dairy', 'Grains').
        
    Returns:
        Dictionary confirming the updated pantry item.
    """
    db = _get_firestore_client()
    doc_id = item_name.lower().replace(" ", "_")
    data = {
        "name": item_name,
        "quantity": quantity,
        "category": category
    }
    db.collection("pantry_items").document(doc_id).set(data)
    return {"status": "success", "message": f"Updated pantry item: {item_name}", "item": data}


def get_pantry_items(category: str = "") -> list[dict]:
    """Retrieve items currently in the user's pantry from Firestore.
    
    Args:
        category: Optional category filter (e.g. 'Produce', 'Grains').
        
    Returns:
        List of pantry item documents.
    """
    db = _get_firestore_client()
    query = db.collection("pantry_items")
    
    if category:
        query = query.where("category", "==", category)
        
    docs = query.stream()
    return [doc.to_dict() for doc in docs]


def generate_grocery_list(recipe_title: str) -> dict:
    """Generate a grocery list of missing ingredients needed for a specific recipe.
    
    Args:
        recipe_title: The title or keyword of the recipe (e.g. 'Mediterranean Quinoa Salad').
        
    Returns:
        Dictionary containing available ingredients, missing ingredients, and recipe title.
    """
    recipes = search_recipes(ingredient_query=recipe_title)
    if not recipes:
        return {"status": "error", "message": f"Recipe '{recipe_title}' not found in database."}
        
    recipe = recipes[0]
    recipe_ingredients = recipe.get("ingredients", [])
    
    pantry_docs = get_pantry_items()
    pantry_names = [item.get("name", "").lower() for item in pantry_docs]
    
    available = []
    missing = []
    
    for ing in recipe_ingredients:
        ing_lower = ing.lower()
        if any(p_name in ing_lower or ing_lower in p_name for p_name in pantry_names if p_name):
            available.append(ing)
        else:
            missing.append(ing)
            
    return {
        "recipe_title": recipe.get("title", recipe_title),
        "available_in_pantry": available,
        "missing_ingredients": missing,
        "grocery_list": missing
    }


def search_external_recipes(query: str) -> list[dict]:
    """Search for global recipes from TheMealDB public API.
    
    Args:
        query: Search query string (e.g. 'pasta', 'chicken', 'arrabiata').
        
    Returns:
        List of matching external recipes containing title, category, area, instructions, image URL, and ingredients.
    """
    api_key = os.getenv("MEALDB_API_KEY", "1")
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={urllib.parse.quote(query)}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            meals = data.get("meals") or []
            results = []
            for meal in meals[:3]:
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f"strIngredient{i}")
                    meas = meal.get(f"strMeasure{i}")
                    if ing and ing.strip():
                        item = f"{meas.strip()} {ing.strip()}" if meas and meas.strip() else ing.strip()
                        ingredients.append(item)
                results.append({
                    "title": meal.get("strMeal"),
                    "category": meal.get("strCategory"),
                    "area": meal.get("strArea"),
                    "instructions": meal.get("strInstructions"),
                    "image_url": meal.get("strMealThumb"),
                    "ingredients": ingredients
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch external recipes: {str(e)}"}]


def geocode_address(address: str) -> dict:
    """Convert a human-readable street address or city name into latitude and longitude coordinates using Google Geocoding API.
    
    Args:
        address: The location address or city name (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'San Francisco, CA').
        
    Returns:
        Dictionary containing formatted_address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not configured."}
        
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            results = data.get("results", [])
            if not results:
                return {"error": f"No geocoding results found for address: '{address}'"}
            first = results[0]
            loc = first.get("geometry", {}).get("location", {})
            return {
                "formatted_address": first.get("formatted_address"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng")
            }
    except Exception as e:
        return {"error": f"Geocoding API call failed: {str(e)}"}


def search_nearby_places(latitude: float, longitude: float, place_type: str = "grocery_store", radius: float = 5000.0) -> list[dict]:
    """Find nearby places (e.g. grocery stores, supermarkets, bakeries) of a given type around coordinates using Google Places API (New).
    
    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g. 'grocery_store', 'supermarket', 'bakery', 'restaurant').
        radius: Radius in meters around the center location (default 5000.0 meters).
        
    Returns:
        List of matching nearby places with name, address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY environment variable is not configured."}]
        
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": radius
            }
        }
    }
    
    try:
        req_data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            places_list = data.get("places", [])
            results = []
            for place in places_list:
                display_name = place.get("displayName", {}).get("text", "")
                results.append({
                    "name": display_name,
                    "address": place.get("formattedAddress"),
                    "location": place.get("location")
                })
            return results
    except Exception as e:
        return [{"error": f"Places API call failed: {str(e)}"}]


async def generate_recipe_image(prompt: str, tool_context: ToolContext) -> dict:
    """Generate a photo or image for a recipe, dish, or culinary item using gemini-3.1-flash-lite-image model, save it as an artifact, and upload to public GCS bucket.
    
    Args:
        prompt: Detailed description of the dish or recipe image to generate (e.g. 'vibrant photo of a Mediterranean quinoa salad').
        
    Returns:
        Dictionary containing public GCS URL and image filename.
    """
    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global"
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            )
        )
        
        image_bytes = None
        mime_type = "image/jpeg"
        
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break
                    
        if not image_bytes:
            return {"error": "Failed to generate image bytes from model response."}
            
        unique_id = uuid.uuid4().hex[:8]
        filename = f"recipe_{unique_id}.jpg" if "jpeg" in mime_type or "jpg" in mime_type else f"recipe_{unique_id}.png"
        
        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=part)

        
        # 2. Upload image bytes directly to public GCS bucket (no local file write)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(MEDIA_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        
        public_url = f"https://storage.googleapis.com/{MEDIA_BUCKET_NAME}/{filename}"
        
        return {
            "status": "success",
            "prompt": prompt,
            "filename": filename,
            "public_url": public_url
        }
    except Exception as e:
        return {"error": f"Image generation failed: {str(e)}"}


async def generate_recipe_video(prompt: str, tool_context: ToolContext) -> dict:
    """Generate a short video for a recipe, cooking technique, or dish using gemini-omni-flash-preview model in global region, save it as an artifact, and upload to public GCS bucket.
    
    Args:
        prompt: Description of the recipe video to generate (e.g. 'short video of sizzling steak in a pan' or 'steam rising from fresh pasta').
        
    Returns:
        Dictionary containing public GCS URL and video filename.
    """
    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global"
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-omni-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["VIDEO"],
            )
        )
        
        video_bytes = None
        mime_type = "video/mp4"
        
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    video_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break
                    
        if not video_bytes:
            return {"error": "Failed to generate video bytes from model response."}
            
        unique_id = uuid.uuid4().hex[:8]
        extension = "mp4" if "mp4" in mime_type else "webm" if "webm" in mime_type else "mp4"
        filename = f"recipe_{unique_id}.{extension}"
        
        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=part)
        
        # 2. Upload video bytes directly to public GCS bucket (no local file write)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(MEDIA_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        
        public_url = f"https://storage.googleapis.com/{MEDIA_BUCKET_NAME}/{filename}"
        
        return {
            "status": "success",
            "prompt": prompt,
            "filename": filename,
            "public_url": public_url
        }
    except Exception as e:
        return {"error": f"Video generation failed: {str(e)}"}







