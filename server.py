from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import google.generativeai as genai
import os
from dotenv import load_dotenv
from pysondb import db as pysondb
import random
import string
import re

db = pysondb.getDb("recipe-quickie.json")
app = Flask(__name__)
cors = CORS(app)  # allow CORS for all domains on all routes.
app.config["CORS_HEADERS"] = "Content-Type"

# Load env
load_dotenv()


GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY environment variable is not set.  Please set it in a .env file."
    )
genai.configure(api_key=GOOGLE_API_KEY)


model = genai.GenerativeModel("gemini-2.0-flash-lite")


def generate_recipe(ingredients):
    try:
        prompt = f"Generate a possible recipe using only the following ingredients: {', '.join(ingredients)}.  "
        prompt += "Provide the recipe in a clear and concise format, including:\n"
        prompt += "- Title of the recipe\n"
        prompt += "- List of ingredients with quantities\n"
        prompt += "- Step-by-step instructions\n"
        prompt += "- Estimated preparation and cooking time\n"
        prompt += "- Serving size"  # Added serving size
        prompt += "Do not include any personal opinions or commentary.  Just the facts."

        response = model.generate_content(prompt)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            print("Prompt feedback:", response.prompt_feedback.block_reason)

        if response.text:
            return response.text
        else:
            return "No recipe generated."

    except Exception as e:
        print(f"Error generating recipe: {e}")


def generate_id(length=8):
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choices(characters, k=length))


@app.route("/recipes", methods=["GET"])
def get_all_recipes():
    try:
        recipes = db.getAll()
        return jsonify(recipes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/recipes/<recipe_id>", methods=["GET"])
def get_specific_recipe(recipe_id):
    try:
        recipe = db.getBy({"recipe_id": recipe_id})
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404
        return jsonify(recipe), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate_recipe", methods=["POST"])
@cross_origin()
def get_recipe():
    try:
        data = request.get_json()
        if not data or "ingredients" not in data:
            return jsonify({"error": "Invalid request"}), 400

        ingredients = data["ingredients"]
        if not isinstance(ingredients, list) or not all(
            isinstance(item, str) for item in ingredients
        ):
            return jsonify({"error": "Invalid request"}), 400

        if not ingredients:
            return jsonify({"error": "Invalid request"}), 400

        # generate
        recipe = generate_recipe(ingredients)
        if recipe:
            # Save to DB
            info = {
                "ingredients": ingredients,
                "recipe": recipe,
                "title": re.sub(r"^[#\*\s]+|[\*\s]+$", "", recipe.split("\n")[0]),
                "recipe_id": generate_id(),
            }
            db.add(info)
            return jsonify({"data": info}), 200
        else:
            return (
                jsonify(
                    {
                        "error": "Failed to generate recipe.  Please check the ingredients and try again."
                    }
                ),
                500,
            )  # changed to 500

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


def validate_ingredients(ingredients):
    # validate
    if not ingredients:
        return False
    if not isinstance(ingredients, list):
        return False
    if not all(isinstance(item, str) for item in ingredients):
        return False
    return True


if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 8080)))
