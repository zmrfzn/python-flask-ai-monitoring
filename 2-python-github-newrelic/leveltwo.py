# import the New Relic Python Agent
import newrelic.agent
import os
import sys
from openai import OpenAI
from flask import Flask, render_template, request
import markdown

# Validate required environment variables before starting the application
required_env_vars = {
    "GITHUB_TOKEN": "GitHub API token for model access",
    "NEW_RELIC_LICENSE_KEY": "New Relic license key for monitoring"
}

missing_vars = []
for var, description in required_env_vars.items():
    if not os.environ.get(var):
        missing_vars.append(f"  - {var}: {description}")

if missing_vars:
    print("ERROR: Missing required environment variables:")
    print("\n".join(missing_vars))
    print("\nPlease set these environment variables before running the application.")
    print("Example:")
    print("  export GITHUB_TOKEN='your_token_here'")
    print("  export NEW_RELIC_LICENSE_KEY='your_license_key_here'")
    sys.exit(1)

# Set MODEL with default value
model_id = os.environ.get("MODEL", "gpt-4o-mini")
print(f"Using model: {model_id}")

client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)

app = Flask(__name__, template_folder="../templates",
            static_folder="../static")

# initialize the New Relic Python agent
newrelic.agent.initialize('newrelic.ini')

# Read prompts from the prompts.txt file
prompts = []
try:
    with open("../prompts.txt", "r") as file:
        # Skip lines that are empty or comments (starting with //)
        prompts = [line.strip() for line in file if line.strip()
                   and not line.startswith("//")]
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
