#!/usr/bin/env python3 

import asyncio
from websockets.sync.client import connect

def hello():
    with connect("ws://localhost:8765") as websocket:
        websocket.send("hello world11")
        message = websocket.recv()
        print(f"Received: {message}")
        websocket.send_data

hello()