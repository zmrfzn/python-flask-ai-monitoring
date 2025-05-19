import os
from openai import OpenAI
from flask import Flask, render_template, request
import markdown
from langsmith.wrappers import wrap_openai

client = wrap_openai(OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
))

model_id = os.environ["MODEL"] # e.g. "gpt-4o-mini"

app = Flask(__name__)

# Read prompts from the prompts.txt file
prompts = []
try:
    with open("prompts.txt", "r") as file:
        # Skip lines that are empty or comments (starting with //)
        prompts = [line.strip() for line in file if line.strip() and not line.startswith("//")]
except Exception as e:
    print(f"Error reading prompts file: {e}")

def chatCompletion(prompt):
    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "user", "content": prompt}
        ])
    return completion.choices[0].message.content

@app.route("/")
def home():
    return render_template("index.html", prompts=prompts)

@app.route("/prompt", methods=["POST"])
def prompt():
    input_prompt = request.form.get("input")
    output_prompt = chatCompletion(input_prompt)
    html_output = markdown.markdown(output_prompt)
    return render_template("index.html", input=input_prompt, output=html_output, prompts=prompts)

# make the server publicly available via port 5004
# flask --app levelsix.py run --host 0.0.0.0 --port 5004
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5004)
