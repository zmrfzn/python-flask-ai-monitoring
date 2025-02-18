# import the New Relic Python Agent
import newrelic.agent
import os
from openai import OpenAI
from flask import Flask, render_template, request
from signalpy import *
import signalpy.jslib

client = OpenAI(
    # This is the default and can be omitted
    #api_key=os.environ.get("OPENAI_API_KEY"),
    api_key="EMPTY",
    base_url="http://localhost:11434/v1"
)

app = Flask(__name__)

# initialize the New Relic Python agent
newrelic.agent.initialize('newrelic.ini')

def chatCompletion(prompt):
    completion = client.chat.completions.create(
        model="deepseek-r1:latest",
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=True)

    chunks = []
    responseContent = ""
    for chunk in completion:
        chunks.append(chunk)
        print(chunk.choices[0].delta.content)
        responseContent += chunk.choices[0].delta.content
    return responseContent

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/prompt", methods=["POST"])
def prompt():
    input_prompt = request.form.get("input")
    output_prompt = chatCompletion(input_prompt)
    return render_template("index.html", output=output_prompt)

@app.route('/signalpy.js')
def t(environ, start_response):
    status = '200 OK'
    response_headers = []
    start_response(status, response_headers)
    return[signalpy.jslib.data.encode()]

# make the server publicly available via port 5004
# flask --app levelsix.py run --host 0.0.0.0 --port 5004
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5004)
