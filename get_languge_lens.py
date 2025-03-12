import boto3
import json
import time
from tqdm import tqdm
import pymongo
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Bedrock runtime client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

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

# Load the data
try:
    with open('techcrunch_top_stories.json', 'r', encoding='utf-8') as file:
        techcrunch_data = json.load(file)
except Exception as e:
    print(f"Error loading or processing JSON file: {e}")
    exit(1)


#system prompt
def language_lens_highlight_system_analysis_prompt() -> str:     
    return """
        Please analyze the article and rate it using Language Assessment Criteria below. It's extremely important that you are objective with your ratings. Focus on the content of the article and its alignment with the given criteria. The goal is to precisely capture the language characteristics of the article based on the specified criteria.

        *Important: Before submitting the analysis, please make sure to double-check your ratings against the provided scale to ensure that the rating names are accurate and included for each criterion.

        OUTPUT INSTRUCTIONS:
        
        Return the results in a json format that is compatible to the following MongoDB fields. The value for each key should be the name of the chosen option. Return only the json without any other words:

            plain_poeticness = StringField(required=True)
            fact_opinion = StringField(required=True)
            critique_affirmation = StringField(required=True)
            complexity_simplicity = StringField(required=True)
            general_detailed = StringField(required=True)
            informative_entertaining = StringField(required=True)
            upside_downside = StringField(required=True)
            agreement_counterargument = StringField(required=True)
            dry_emotionally_charged = StringField(required=True)
            data_narrative = StringField(required=True)
            quoted_authorial = StringField(required=True)

        ***

        LANGUAGE LENS ASSESSMENT CRITERIA:

        Plain vs. Stylistic Quality

        1- Very Plain:
        The text is strictly utilitarian and factual with no decorative language, metaphors, or any form of poetic devices. It presents information in the most straightforward and concise manner possible, often resembling technical writing or simple instructions.

        2 - Somewhat Plain:
        While primarily straightforward, the text includes minimal stylistic elements such as basic adjectives or slight variations in sentence structure that go beyond mere functional communication but do not enhance aesthetic quality significantly.

        3 - Balanced:
        The text balances factual delivery with some stylistic or poetic enhancements. It may use metaphors, a bit of descriptive language, or varied sentence lengths and structures to make the content more engaging without compromising clarity.

        4 - Somewhat Stylistic:
        The text is rich in stylistic elements such as vivid imagery, creative metaphors, and a noticeable rhythm or lyrical quality. While it conveys information, it also prioritizes aesthetic appeal and reader engagement through its use of language.

        5 - Very Stylistic:
        The text is highly artistic, prioritizing poetic constructs and stylistic flair. It employs a range of literary techniques like alliteration, onomatopoeia, extensive metaphorical language, and complex imagery that may occasionally prioritize beauty and style over immediate clarity or directness of information.

        ***

        Fact vs. Opinion 

        1 - Strongly Fact-Based:
        The text strictly presents verifiable facts or widely accepted data. It uses objective language and avoids any subjective interpretation or emotional language.

        2 - Somewhat Fact-Based:
        The text primarily relies on factual information but may include adjectives or mild subjective terms that do not significantly alter the factual nature of the information.

        3 - Balanced:
        The text mixes factual information with opinions or interpretations. Opinions are presented alongside facts, and both are given roughly equal emphasis without overwhelming each other.

        4 - Somewhat Opinion-Based:
        The statement contains personal views or interpretations that are supported by some factual references, but the overall tone and content lean towards personal or subjective judgment.

        5 - Strongly Opinion-Based:
        The text is dominated by personal opinions, interpretations, or speculative assertions with minimal or no factual backing within the provided context. The language is heavily subjective, emphasizing personal thoughts or conjectures.

        ***

        Critique vs. Affirmation 

        1 - Strong Critique:
        The statement presents an overwhelmingly critical perspective, focusing exclusively on flaws, shortcomings, or negative aspects of the subject matter. It does not acknowledge any positive attributes, strengths, or potential for improvement. The tone is entirely disapproving, and the critique is presented without any balance or nuance.

        2 - Somewhat Critique:
        The statement primarily criticizes certain aspects of the subject matter but does so with some acknowledgment of context, complexity, or potential for improvement. While the overall tone is critical, it may include minor recognition of positive elements or suggest the possibility of addressing the identified issues. However, the emphasis remains on the critique, with limited or no specific solutions offered.

        3 - Balanced:
        The statement provides a balanced view by giving equal attention to both negative and positive aspects of the subject matter. It presents a mix of critique and affirmation, acknowledging challenges or areas for improvement while also recognizing strengths, progress, or effective elements. The overall tone is neutral, offering an impartial assessment without strongly favoring either critique or affirmation.

        4 - Somewhat Affirmation:
        The statement primarily emphasizes the positive aspects, successes, or constructive elements of the subject matter while acknowledging some challenges or areas for improvement. The overall tone is affirming and supportive, focusing more on the strengths and positive outcomes. Any mentioned critiques or issues are presented as minor or manageable, with an emphasis on maintaining or expanding the positive aspects.

        5 - Strong Affirmation:
        The statement presents an unequivocally positive and supportive view of the subject matter, focusing solely on its strengths, benefits, and effectiveness. It does not acknowledge any flaws, limitations, or potential drawbacks. The tone is entirely affirming and celebratory, emphasizing the positive impacts and outcomes without any critique or reservation.

        ***

        Complexity vs. Simplicity 
        
        1 - Highly Complex: 
        The article presents ideas or concepts that are significantly more intricate, technical, or abstract compared to the rest of the article. It may delve into nuanced details, use specialized terminology, or explore multifaceted relationships that require substantial background knowledge or mental effort to grasp fully.
        
        2 - Somewhat Complex: 
        The article introduces concepts or ideas that are moderately more complex than the overall article. It may include some technical terms, elaborate explanations, or ideas that require a bit more concentration or familiarity with the subject matter to understand. However, it doesn't reach the level of intricacy or abstraction found in the "Highly Complex" category.
        
        3 - Balanced: 
        The article presents ideas or concepts that are on par with the complexity found in the rest of the article. It maintains a similar level of detail, technicality, or abstraction as the surrounding content, neither simplifying nor complicating the overall message. The article integrates smoothly with the article's flow and doesn't require a significant shift in understanding or mental effort.
        
        4 - Somewhat Simple: 
        The article reduces the complexity of the ideas or concepts compared to the rest of the article. It may break down intricate ideas into more digestible parts, use simpler language, or provide concrete examples to clarify abstract concepts. The article aims to make the content more accessible or easier to grasp, even if the overall article tends to be more complex.
        
        5 - Highly Simple: 
        The article significantly simplifies the ideas or concepts compared to the rest of the article. It strips away technical jargon, elaborate explanations, or abstract concepts and presents the information in a very basic, easy-to-understand manner. The article may use analogies, everyday language, or straightforward examples to make the content highly accessible, even to readers with minimal background knowledge on the subject.
        
        ***

        General Information vs. Detailed Insights 

        1 - Highly General:
        Describes concepts in the broadest terms without any specifics.

        2 - Somewhat General:
        Introduces a topic with minimal specifics, offering only slight details that do not explain how something is specifically implemented or its direct impact.

        3 - Balanced:
        Provides an even mix of general information and specific details. This level outlines the concept and includes some explanatory elements about the mechanics or implications without full detail.

        4 - Somewhat Detailed:
        Provides specific details about how something works or its direct implications, but may not cover every aspect in depth or might omit complex technical specifics.

        5 - Highly Detailed:
        Delivers in-depth explanations of processes, methodologies, or technologies, including comprehensive data or step-by-step breakdowns. This level often includes technical descriptions, extensive empirical data, or detailed case studies.

        ***

        Informative vs. Entertaining 

        1 - Highly Informative:
        The text is predominantly focused on delivering factual, data-driven content. It provides detailed information, comprehensive explanations, or thorough analysis, primarily aiming to educate or inform the reader with minimal stylistic embellishments or narrative elements.

        2 - Somewhat Informative:
        The text is mainly informative, presenting facts or insights with some level of detail. However, it includes occasional use of narrative or stylistic elements that lightly enhance the engagement without overshadowing the primary goal of information delivery.

        3 - Balanced:
        The text evenly balances factual information with entertaining elements. It provides substantial information while also incorporating storytelling, humor, or other engaging techniques that make the content more enjoyable and relatable to the reader, achieving a harmony between educating and entertaining.

        4 - Somewhat Entertaining:
        While the text contains informative content, it places a stronger emphasis on engaging the reader through narrative techniques, stylistic flair, or creative elements. The information is presented in a way that prioritizes reader interest and enjoyment, often using anecdotes, expressive language, or thematic elements to maintain engagement.

        5 - Highly Entertaining:
        The text is primarily designed to entertain, captivate, or amuse the reader, with a strong focus on narrative style, humor, or dramatic elements. Informative content is present but takes a back seat to the entertainment value, which is clearly intended to be the primary appeal of the text.

        ***

        Upside vs. Downside - Pros vs Cons 

        1 - Strongly Upside:
        The article exclusively highlights positive outcomes, benefits, or favorable aspects without acknowledging any negatives. It presents an unequivocally positive view, emphasizing the advantages, successes, or desirable qualities of the subject matter. There is no mention of potential drawbacks, limitations, or challenges.

        2 - Somewhat Upside:
        The article primarily focuses on positive aspects, giving them more prominence and weight compared to any negatives mentioned. While it may briefly acknowledge potential drawbacks or limitations, these are significantly downplayed or presented as minor concerns. The overall tone and emphasis remain strongly positive, with the benefits or advantages being the central focus.

        3 - Balanced:
        The article presents a balanced view by giving equal attention and consideration to both positive and negative aspects. It acknowledges the pros and cons, benefits and drawbacks, or advantages and disadvantages of the subject matter. Neither the positive nor the negative aspects are significantly emphasized or downplayed, providing a neutral and impartial assessment.

        4 - Somewhat Downside:
        The article predominantly focuses on negatives, drawbacks, or challenges while still acknowledging some benefits or positive aspects. The negative elements are given more attention and weight, and the overall tone leans towards a critical or cautionary perspective. Any mentioned positives are presented as minor or less significant compared to the emphasized downsides.

        5 - Strongly Downside:
        The article focuses almost exclusively on the negative aspects, challenges, or harmful outcomes associated with the subject matter. It presents an unequivocally negative view, emphasizing the drawbacks, failures, or undesirable qualities. There is little to no mention of any benefits or positive aspects, and if present, they are significantly overshadowed by the highlighted negatives.

        ***

        Agreement vs Counterargument (Compared to Main Viewpoint of Article)

        1 - Strong Agreement:
        The article strongly supports or reinforces the main viewpoint or thesis of the article without introducing any diverging opinions or perspectives. It amplifies the central message explicitly stated in the article.

        2 - Some Agreement:
        The article agrees with the main viewpoint of the article but also introduces minor nuances or additional perspectives that do not fundamentally challenge the main thesis.

        3 - Balanced:
        The article presents a balanced view, mentioning both the main viewpoint of the article and counterarguments or differing perspectives with equal emphasis.

        4 - Some Counterargument:
        The article introduces perspectives or facts that begin to challenge or offer alternatives to the main viewpoint of the article, though it does not completely contradict it.

        5 - Strong Counterargument:
        The article directly opposes the main viewpoint of the article, presenting a strong, well-defined argument that challenges or refutes the central thesis.

        ***
        
        Dry vs. Emotionally Charged 
        1 - Very Dry: 
        The text is strictly factual and neutral, devoid of any emotional language, expressive content, or stylistic flourishes. It is presented in a clinical, technical, or matter-of-fact manner, focusing solely on objective information without attempting to engage the reader's emotions or imagination.
        
        2 - Somewhat Dry: 
        The text is primarily factual and straightforward, with minimal use of emotional language or expressive elements. While it may include slight variations in tone or occasional descriptive words, these do not significantly enhance the emotional engagement. The overall language remains functional and unemotional, with any expressions of feeling being subtle and infrequent.
        
        3 - Balanced: 
        The text strikes a balance between factual information and expressive language. It maintains a professional tone while occasionally incorporating elements that provide a moderate level of emotional engagement or stylistic flair. The use of descriptive language, metaphors, or rhetorical devices is noticeable but does not dominate the content, ensuring a balance between informative and engaging elements.
        
        4 - Somewhat Emotionally Charged: 
        The text frequently employs language that conveys strong emotions, be it enthusiasm, conviction, criticism, or skepticism. It includes persuasive elements, emotive expressions, vivid descriptions, or rhetorical devices that actively aim to engage the reader's emotions and create a sense of importance, urgency, or strong sentiment. The use of expressive language is prominent and contributes significantly to the overall tone of the text.
        
        5 - Very Emotionally Charged: 
        The text is characterized by a high degree of expressive, emotive, and persuasive language throughout, which can be either positive or negative in sentiment. The consistent use of vivid imagery, powerful narratives, compelling arguments, and emotionally charged language is a defining feature, aiming to captivate the reader's emotions and create a lasting impact. The emotional tone is pervasive and dominates the entire piece, whether it's through fervor, anger, inspiration, or any other intense sentiment.

        ***

        Data-driven vs Narrative-driven
        
        1 - Strongly Data-Driven: The article relies heavily on quantitative information, statistics, numbers, or concrete facts to convey its message. It prioritizes objective data and empirical evidence over anecdotes, personal experiences, or storytelling. The article may include charts, graphs, or tables to visually represent the data and emphasize the data-driven nature of the content.
        
        2 - Somewhat Data-Driven: The article leans more towards data and facts but also incorporates some narrative elements. It presents quantitative information and evidence to support its points but may include brief anecdotes or examples to provide context or illustrate the data. The article still prioritizes data but recognizes the value of limited narrative elements to engage the reader or clarify the message.
        
        3 - Balanced: The article strikes a balance between data-driven and narrative-driven content. It presents a mix of quantitative information and qualitative insights, using both facts and stories to convey its message. The article may alternate between data points and anecdotes or weave them together to create a cohesive and engaging narrative that is supported by empirical evidence.
        
        4 - Somewhat Narrative-Driven: The article leans more towards storytelling and qualitative content but still incorporates some data and facts. It primarily uses anecdotes, personal experiences, or case studies to illustrate its points but supports these narratives with relevant data or statistics. The article recognizes the persuasive power of stories but also acknowledges the importance of grounding the narrative in empirical evidence.
        
        5 - Strongly Narrative-Driven: The article relies heavily on storytelling, anecdotes, personal experiences, or qualitative insights to convey its message. It prioritizes the human element, emotions, and the power of narratives over quantitative data or empirical evidence. The article may use vivid descriptions, character development, or a strong authorial voice to create an engaging and persuasive narrative that resonates with the reader on a personal level.

        ***

        Quoted Statements vs. Authorial Narrative

        1 - Purely Quoted Statements: The text consists exclusively of direct quotes from other sources or individuals, without any additional commentary or interpretation from the author. The presence of quotation marks at the beginning and end of the text is a clear indicator that the entire document is a direct quote. Ex: "AI is awesome!"

        2 - Mixed Quoted Statements and Authorial Narrative: The text integrates direct quotes with the author's own commentary or analysis. Quotation marks are used to identify the quoted portions, while the remaining text represents the author's narrative. Example: AI is fascinating, "I very much love working with AI," said Josh.

        3 - Purely Authorial Narrative: The text is entirely the author's original content without any direct quotes. There are no quotation marks present, as any external information or ideas are paraphrased and fully integrated into the author's narrative without explicit attribution to another speaker or source. Ex: AI is revolutionary and it is a pleasure to co-create with them.

    """

# Get system prompt
system = language_lens_highlight_system_analysis_prompt()

# Output file
output_file = "responses.json"

# Load existing responses if the file exists
try:
    with open(output_file, "r", encoding="utf-8") as f:
        responses = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    responses = []  # Start fresh if file is missing or corrupted


# Track already processed links to avoid duplication
processed_links = {response["link"] for response in responses if "link" in response}

# Loop over each story with a progress bar
for i, story in enumerate(tqdm(techcrunch_data, desc="Processing stories", unit="story")):
    cleaned_html_content = story.get("cleaned_html", None)
    link = story.get("link", None)

    # Skip if "cleaned_html" is missing or if already processed
    if not cleaned_html_content or link in processed_links:
        tqdm.write(f"Skipping story {i+1}: No content or already processed.")
        continue

    # Define the request payload for the Bedrock model
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 200,
        "top_k": 250,
        "stop_sequences": [],
        "temperature": 1,
        "top_p": 0.999,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"{system}\n\n{cleaned_html_content}"  # Merge system prompt and user input
                    }
                ]
            }
        ]
    }

    # Invoke the Bedrock model using modelId
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )

        # Parse the response
        response_body = json.loads(response["body"].read().decode("utf-8"))

        # Extract model response (assuming the response contains the expected taxonomy categories)
        model_analysis = response_body.get("text", "{}")  # Ensure it's a valid JSON string
        parsed_analysis = json.loads(model_analysis)

        # Convert text values to numeric values
        numeric_analysis = {
            key: value_mapping.get(value, None) for key, value in parsed_analysis.items()
        }

        # Store response with link
        response_entry = {
            "story_number": i + 1,
            "link": link,
            "model_response": response_body,
            "numeric_response": numeric_analysis
        }
        responses.append(response_entry)

        # Save after processing each story
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(responses, f, indent=2)

        tqdm.write(f"Saved Story {i+1}: {link}")

    except Exception as e:
        tqdm.write(f"Error invoking model for Story {i+1}: {e}")

    # Enforce a 30-second delay between API calls
    if i < len(techcrunch_data) - 1:  # Avoid unnecessary sleep after the last request
        tqdm.write("Waiting 5 seconds before the next request...")
        time.sleep(5)

def update_stories_with_model_response(responses):
    """
    Updates existing MongoDB documents by adding the 'model_response' and 'numeric_response' fields based on the story 'link'.
    If 'numeric_response' is missing, it will be generated from 'model_response["content"][0]["text"]'.
    """
    # Connect to MongoDB
    MONGO_URI = os.getenv("MONGODB_URI")
    client = pymongo.MongoClient(MONGO_URI)
    db = client["techcrunch_db"]
    collection = db["top_stories"]

    updated_count = 0

    for response in responses:
        link = response.get("link")
        model_response = response.get("model_response")
        numeric_response = response.get("numeric_response")

        # If model_response is available, attempt to map it to numeric_response if missing
        if not link or not model_response:
            print(f"Skipping response update: Missing link or model_response.")
            continue

        # If numeric_response is missing, generate it from model_response["content"][0]["text"]
        if not numeric_response:
            try:
                # Extract the text content from model_response
                content = model_response.get("content", [])
                
                if content and isinstance(content, list):
                    text_content = content[0].get("text", None)

                    if text_content:
                        print(f"Processing text for link {link}.")
                        # Assuming the text is in the form of a JSON string, parse it into a dictionary
                        parsed_analysis = json.loads(text_content)

                        # Apply the value_mapping to parsed_analysis
                        numeric_response = {
                            key: value_mapping.get(value, None)
                            for key, value in parsed_analysis.items()
                        }
                    else:
                        print(f"No text content found for link {link}. Skipping numeric response generation.")
                        continue
                else:
                    print(f"Invalid content structure for link {link}. Skipping.")
                    continue

            except Exception as e:
                print(f"Error processing model_response for link {link}: {e}")
                continue

        # Find the document with the matching link
        existing_story = collection.find_one({"link": link})

        if existing_story:
            collection.update_one(
                {"link": link},
                {"$set": {
                    "model_response": model_response,
                    "numeric_response": numeric_response
                }}
            )
            print(f"Updated story with link {link}.")
            updated_count += 1
        else:
            print(f"No matching story found for link {link}. Skipping update.")

    print(f"Updated {updated_count} stories with model responses in MongoDB.")

# Call the function to update stories with model responses and numeric responses
update_stories_with_model_response(responses)

print(f"\nAll responses saved to {output_file}")
