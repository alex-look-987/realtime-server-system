import logging
import pandas as pd
import orjson, lz4.frame
import asyncio, websockets
from miscs.candle_manager import Candlestick

# Event to handle server availability
server_ready = asyncio.Event()

async def check_server(uri):
  while True:
    try:
      async with websockets.connect(uri):
        server_ready.set()
        return
    except (ConnectionRefusedError, websockets.ConnectionClosed, OSError, websockets.InvalidURI):
      logging.warning("Servidor no disponible, reintentando en 1s...")

      await asyncio.sleep(1)

async def wait_for_server(wait_time=None):
  await server_ready.wait()

  if wait_time is not None:
    await asyncio.sleep(wait_time)

def start_server_check(uri):
  loop = asyncio.get_event_loop()

  if loop.is_running():
    loop.create_task(check_server(uri))
  else:
    loop.run_until_complete(check_server(uri))

async def send_to_server(uri, data, use_persistent=True):
  try:
    await wait_for_server() # wait server

    json_bytes = orjson.dumps(data)
    compressed_data = lz4.frame.compress(json_bytes)

    async with websockets.connect(uri) as websocket:
      if websocket.open:
        await websocket.send(compressed_data)

  except Exception as e:
    logging.error(f"Error al enviar datos: {e}")
    
    if use_persistent: # fallback by tick
      await send_to_server(uri, data, use_persistent=False)

# --------------------------- CLIENT TO SERVER PATHS --------------------------- #

import sys
server_port = int(sys.argv[1])

async def historical_end(dataframe: pd.DataFrame, df_key):
  data_to_send = {"df_key": df_key, "dataframe": dataframe.to_json(orient='split')}
  
  await send_to_server(f"ws://localhost:{server_port}/ibapi_end", data_to_send)

async def update_candle(candle: Candlestick, timestamp: int, df_key):
  last_candle = {"candle": candle.to_dict(), "date": timestamp}

  await send_to_server(
        f"ws://localhost:{server_port}/ibapi_update_{df_key}",
        last_candle)
