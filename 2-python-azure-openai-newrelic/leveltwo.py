# import the New Relic Python Agent
import newrelic.agent
import os
from openai import AzureOpenAI
from flask import Flask, render_template, request

endpoint = os.environ["AZURE_OPENAI_API_ENDPOINT"]
model_name = os.environ["AZURE_OPENAI_MODEL_NAME"]
deployment = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]

subscription_key = os.environ["AZURE_OPENAI_API_KEY"]
api_version = os.environ["AZURE_OPENAI_API_VERSION"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

app = Flask(__name__, template_folder="../templates",
            static_folder="../static")

# initialize the New Relic Python agent
newrelic.agent.initialize('newrelic.ini')


def chatCompletion(prompt):
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": prompt}
        ])
    return completion.choices[0].message.content


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/prompt", methods=["POST"])
def prompt():
    input_prompt = request.form.get("input")
    output_prompt = chatCompletion(input_prompt)
    return render_template("index.html", output=output_prompt)


# make the server publicly available via port 5004
# flask --app levelsix.py run --host 0.0.0.0 --port 5004
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5004)
