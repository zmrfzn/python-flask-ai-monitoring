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

# using the same function we saw back in levelthree.py
# taking the input from the user and returning the response from OpenAI


def chatCompletion(prompt):
    print("prompt: "+prompt)
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": prompt}
        ])
    return completion.choices[0].message.content


@app.route("/")
def main():
    return render_template("index.html")


@app.route("/prompt", methods=["POST"])
def prompt():
    input_prompt = request.form.get("input")
    # call the function - chatCompletion and pass the input from the user
    output_prompt = chatCompletion(input_prompt)
    return render_template("index.html", output=output_prompt)


# make the server publicly available via port 5002
# flask --app levelfive.py run --host 0.0.0.0 --port 5002
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5002)
