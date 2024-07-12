# import the New Relic Python Agent
import newrelic.agent
import os
import requests
import urllib.parse
from flask import Flask, render_template, jsonify, request, session
import json

app = Flask(__name__)
app.secret_key = os.urandom(24) 

# initialize the New Relic Python agent
newrelic.agent.initialize('newrelic.ini')

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/activities", methods=["GET"])
def activities():
    response = requests.get(url="http://127.0.0.1:8081/activities")
    session['games'] = response.text
    return render_template("index.html", outputGames=response.text)

@app.route("/activities/search", methods=["POST"])
def activitiesSearch():
    input_prompt = request.form.get("input")
    activity = urllib.parse.quote(input_prompt.encode('UTF-8'))
    print(activity)
    response = requests.get(url="http://127.0.0.1:8081/activities/search?activity="+activity)
    json_object = json.loads(response.text)
    session['gameInput'] = input_prompt
    session['gamePrompt'] = json_object["prompt"]
    return render_template("index.html", outputGamePrompt=json_object["prompt"], outputGames=input_prompt)

@app.route("/chat", methods=["POST"])
def chat():
    input_prompt = request.form.get("inputGamePrompt")
    print(input_prompt)
    paras = {"message": input_prompt}
    response = requests.post(url="http://127.0.0.1:8081/chat",data=paras)
    json_object = json.loads(response.text)
    print(json_object)
    chatGuid = json_object["guid"]
    session['chatGuid'] = chatGuid
    chatContent = json_object["messages"][1]["content"]
    session['chatContent'] = chatContent
    return render_template("index.html", outputChatGuid=chatGuid, outputChatContent=chatContent, outputGamePrompt=input_prompt)

@app.route("/chat/guid", methods=["POST"])
def chatGuid():
    input_prompt = request.form.get("inputGameInteraction")
    print(input_prompt)
    paras = {"message": input_prompt}
    chatGuid = session['chatGuid']
    print(chatGuid)
    response = requests.put(url="http://127.0.0.1:8081/chat/"+chatGuid,data=paras)
    json_object = json.loads(response.text)
    session['chatGuid'] = chatGuid
    print(json_object)
    msgLength = len(json_object["messages"])
    chatInteractionResult = json_object["messages"][msgLength-1]["content"]
    chatContent = session['chatContent']
    gameInput = session['gameInput']
    gamePrompt = session['gamePrompt']
    return render_template("index.html", outputChatInteraction=chatInteractionResult, outputChatGuid=chatGuid, outputChatContent=chatContent, outputGamePrompt=gamePrompt, outputGames=gameInput)

# make the server publicly available via port 5004
# flask --app chat-ui.py run --host 0.0.0.0 --port 5004
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5007)