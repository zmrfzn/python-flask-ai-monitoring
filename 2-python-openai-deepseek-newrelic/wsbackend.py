# import the New Relic Python Agent
import newrelic.agent
import os
from bottle import request, Bottle
from wsocket import WebSocketHandler, WSocketApp, WebSocketError, logger, run
from wsgiref.simple_server import make_server
from time import sleep

logger.setLevel('DEBUG')

bottle = Bottle()

def redirect_http_to_https(callback):
    '''Bottle plugin that redirects all http requests to https'''

    def wrapper(*args, **kwargs):
        scheme = bottle.request.urlparts[0]
        if scheme == 'http':
            # request is http; redirect to https
            bottle.redirect(bottle.request.url.replace('http', 'https', 1))
        else:
            # request is already https; okay to proceed
            return callback(*args, **kwargs)
    return wrapper

bottle.install(redirect_http_to_https)

app = WSocketApp(bottle)

@bottle.route('/')
def handle_websocket():
    wsock = request.environ.get('wsgi.websocket')
    if not wsock:
        logger.info('No websocket')
        return 'Hello World!'

    logger.info('Websocket connected')
    while True:
        try:
            message = wsock.receive()
            print(message)
            wsock.send('Your message was: %r' % message)
            sleep(3)
            wsock.send('Your message was: %r' % message)
        except WebSocketError:
            break

run(app)
