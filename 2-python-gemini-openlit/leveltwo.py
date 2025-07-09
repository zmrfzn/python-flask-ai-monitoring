import openlit

import os
from flask import Flask, render_template, request
from google import genai
from google.genai import types
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openlit.init()

# genai.configure(api_key=os.environ["API_KEY"])
# Only run this block for Gemini Developer API
client = genai.Client(api_key=os.environ["API_KEY"])

GEMINI_MODEL = "gemini-1.5-flash"
# GEMINI_MODEL = "gemini-1.5-flash-8b"
# GEMINI_MODEL = "gemini-1.5-pro"
# GEMINI_MODEL = "gemini-1.0-pro"

app = Flask(__name__, template_folder="../templates",
            static_folder="../static")

# taking the input from the user and returning the response from Gemini


def chatCompletion(prompt):
    logger.info("prompt: "+prompt)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=1.0,
        ),
    )
    # model = client.GenerativeModel(GEMINI_MODEL)
    # generation_config=client.types.GenerationConfig(
    #    temperature=1.0,
    # )

    # response = model.generate_content(
    #    prompt,
    #    generation_config=generation_config,
    # )
    logger.info(response)
    responseText = ""
    if response.candidates:
        if response.candidates[0].content.parts:
            if response.candidates[0].content.parts[0].text:
                responseText = response.candidates[0].content.parts[0].text
    return responseText


@app.route("/")
def home():
    logger.info("render index.html")
    return render_template("index.html")


@app.route("/prompt", methods=["POST"])
def prompt():
    logger.info("/prompt triggered")
    input_prompt = request.form.get("input")
    output_prompt = chatCompletion(input_prompt)
    return render_template("index.html", output=output_prompt)


# make the server publicly available via port 5004
# flask --app levelsix.py run --host 0.0.0.0 --port 5004
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5004)
