# -*- coding: utf-8 -*-
__doc__ = """
A simple chat example using a CherryPy webserver.

$ pip install cherrypy

Then run it as follow:

$ python app.py

You will want to edit this file to change the
ws_addr variable used by the websocket object to connect
to your endpoint. Probably using the actual IP
address of your machine.
"""
import random
import os

import cherrypy

from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket
from ws4py.messaging import TextMessage
from openai import OpenAI

client = OpenAI(
    # This is the default and can be omitted
    #api_key=os.environ.get("OPENAI_API_KEY"),
    api_key="EMPTY",
    base_url="http://localhost:11434/v1"
)

cur_dir = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))
index_path = os.path.join(cur_dir, 'index.html')
index_page = open(index_path, 'r').read()

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

class ChatWebSocketHandler(WebSocket):
    def received_message(self, m):
        mData = str(m.data.decode("utf-8"))
        if ("entered the room" in mData):
            cherrypy.engine.publish('websocket-broadcast', m)
        else:
            print(mData)
            completion = client.chat.completions.create(
                model="deepseek-r1:latest",
                messages=[
                    {"role": "user", "content": mData}
                ],
                stream=True)

            chunks = []
            responseContent = ""
            for chunk in completion:
                chunkContent = chunk.choices[0].delta.content
                chunks.append(chunk)
                print(chunkContent)
                responseContent += chunkContent
                cherrypy.engine.publish('websocket-broadcast', chunkContent.replace("\n", "").replace("\r", ""))

    def closed(self, code, reason="A client left the room without a proper explanation."):
        cherrypy.engine.publish('websocket-broadcast', TextMessage(reason))

class ChatWebApp(object):
    @cherrypy.expose
    def index(self):
        return index_page % {'username': "User%d" % random.randint(50, 1000),
                             'ws_addr': 'wss://host-ai-monitoring-5002-ecnjz4myohph.env.play.instruqt.com/ws'}

    @cherrypy.expose
    def ws(self):
        cherrypy.log("Handler created: %s" % repr(cherrypy.request.ws_handler))

if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 5002
    })
    
    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()

    cherrypy.quickstart(ChatWebApp(), '',
                        config={
                            '/': {
                                'tools.response_headers.on': True,
                                'tools.response_headers.headers': [
                                    ('X-Frame-options', 'deny'),
                                    ('X-XSS-Protection', '1; mode=block'),
                                    ('X-Content-Type-Options', 'nosniff')
                                ]
                            },
                            '/ws': {
                                'tools.websocket.on': True,
                                'tools.websocket.handler_cls': ChatWebSocketHandler
                            },
                        })