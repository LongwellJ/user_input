import json

# Load existing responses
output_file = "responses.json"
try:
    with open(output_file, "r", encoding="utf-8") as f:
        responses = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("Error: responses.json is missing or corrupted.")
    exit()

# Define mapping of string values to numeric values
value_mapping = {
    "Very Plain": 1, "Somewhat Plain": 2, "Balanced": 3, "Somewhat Stylistic": 4, "Very Stylistic": 5,
    "Strongly Fact-Based": 1, "Somewhat Fact-Based": 2, "Balanced": 3, "Somewhat Opinion-Based": 4, "Strongly Opinion-Based": 5,
    "Strong Critique": 1, "Somewhat Critique": 2, "Balanced": 3, "Somewhat Affirmation": 4, "Strong Affirmation": 5,
    "Highly Complex": 1, "Somewhat Complex": 2, "Balanced": 3, "Somewhat Simple": 4, "Highly Simple": 5,
    "Highly General": 1, "Somewhat General": 2, "Balanced": 3, "Somewhat Detailed": 4, "Highly Detailed": 5,
    "Highly Informative": 1, "Somewhat Informative": 2, "Balanced": 3, "Somewhat Entertaining": 4, "Highly Entertaining": 5,
    "Strongly Upside": 1, "Somewhat Upside": 2, "Balanced": 3, "Somewhat Downside": 4, "Strongly Downside": 5,
    "Strong Agreement": 1, "Some Agreement": 2, "Balanced": 3, "Some Counterargument": 4, "Strong Counterargument": 5,
    "Very Dry": 1, "Somewhat Dry": 2, "Balanced": 3, "Somewhat Emotionally Charged": 4, "Very Emotionally Charged": 5,
    "Strongly Data-Driven": 1, "Somewhat Data-Driven": 2, "Balanced": 3, "Somewhat Narrative-Driven": 4, "Strongly Narrative-Driven": 5,
    "Purely Quoted Statements": 1, "Mixed Quoted Statements and Authorial Narrative": 2, "Purely Authorial Narrative": 3
}

# Fix numeric_response for each document
for response in responses:
    model_response = response.get("model_response", {})

    if not model_response:
        print(f"Skipping story {response.get('story_number', 'Unknown')}: No model response.")
        continue

    # Extract model response content
    content = model_response.get("content", [])
    if content and isinstance(content, list):
        text_content = content[0].get("text", "{}")  # Ensure it's a valid JSON string

        try:
            parsed_analysis = json.loads(text_content)  # Convert JSON string to dictionary
            numeric_response = {
                key: value_mapping.get(value, None) for key, value in parsed_analysis.items()
            }
            response["numeric_response"] = numeric_response  # Update the document
        except json.JSONDecodeError as e:
            print(f"JSON decoding error for story {response.get('story_number', 'Unknown')}: {e}")
            response["numeric_response"] = {}  # Set empty dict if parsing fails
    else:
        print(f"Unexpected response format for story {response.get('story_number', 'Unknown')}")
        response["numeric_response"] = {}  # Set empty dict if structure is incorrect

# Save the fixed responses back to responses.json
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(responses, f, indent=2)

print("responses.json has been updated with correct numeric_response values.")
