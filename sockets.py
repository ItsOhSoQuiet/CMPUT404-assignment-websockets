#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2019 Abram Hindle, Matthew Kluk
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

# Note: This takes extensively from Hazel Campbell's chat.py example
# in the CMPUT 404 notes (licensed under the Apache license):
# https://github.com/uofa-cmput404/cmput404-slides/blob/master/examples/WebSocketsExamples/chat.py

websocket_clients = []

# Send the message to every client that's connected
def send_to_all_clients(message):
    for client in websocket_clients:
        client.put(message)

def send_json_to_clients(json_object):
    message = json.dumps(json_object)
    send_to_all_clients(message)

class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()        

def set_listener( entity, data ):
    ''' do something with the update ! '''
    update_message = json.dumps({entity: data})
    send_to_all_clients( update_message )


myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return flask.redirect("/static/index.html")

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # adapted from Hazel's chat.py example:
    # https://github.com/uofa-cmput404/cmput404-slides/blob/master/examples/WebSocketsExamples/chat.py
    try:
        while True:
            message = ws.receive()
            if (message is not None):
                packet = json.loads(message)
                send_json_to_clients( packet )
            else:
                break
    except:
        pass
                

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    client = Client()
    websocket_clients.append(client)
    g = gevent.spawn( read_ws, ws, client )
    try:
        while True:
            message = client.get()
            ws.send(message)
    except Exception as e:
        print("WS Error %s" % e)
    finally:
        websocket_clients.remove(client)
        gevent.kill(g)


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    updated_json = flask_post_json()
    if request.method == 'POST':
        for key, value in updated_json.items():
            myWorld.update(entity, key, value)
    else:
        myWorld.set(entity, updated_json)
    get_updated_instance = myWorld.get(entity)
    return json.dumps(get_updated_instance)


@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    current_world = myWorld.world()
    return json.dumps(current_world)

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    get_instance = myWorld.get(entity)
    return json.dumps(get_instance)


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    clear_world = myWorld.world()
    return json.dumps(clear_world)



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
