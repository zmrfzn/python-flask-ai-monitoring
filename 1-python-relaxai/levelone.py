import os
from openai import OpenAI
from flask import Flask, render_template, request

client = OpenAI(
    base_url="https://api.relax.ai/v1/",
    # This is the default and can be omitted
    api_key=os.environ.get("RELAX_AI_API_KEY"),
)

app = Flask(__name__, template_folder="../templates",
            static_folder="../static")

# using the same function we saw back in levelthree.py
# taking the input from the user and returning the response from OpenAI


def chatCompletion(prompt):
    print("prompt: "+prompt)
    completion = client.chat.completions.create(
        model="DeepSeek-R1-0528",
        temperature=0.8,
        max_tokens=256,
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
