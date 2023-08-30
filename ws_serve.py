#!/usr/bin/env python3

import asyncio
from websockets.server import serve

async def echo(websocket):
    async for message in websocket:
        print(f"Received msg: {message}")
        await websocket.send(message)

async def main():
    async with serve(echo, "localhost", 8765):
        await asyncio.Future()

asyncio.run(main())