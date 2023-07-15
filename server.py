from fastapi import FastAPI
from pydantic import BaseModel, Field
import asyncio
import openai
import os
from typing import Dict
from datetime import datetime
from dotenv import load_dotenv
import uuid

from src.logger import logging

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

MAX_TOKENS_PER_MINUTE = 12 * 10**4
MAX_TOKENS_PER_REQUEST = 50
# DELAY_BETWEEN_REQUESTS = 60.0 / (MAX_TOKENS_PER_MINUTE / MAX_TOKENS_PER_REQUEST)
DELAY_BETWEEN_REQUESTS = 0.03

app = FastAPI()
queue = asyncio.Queue()
results = {}


class ApiKey:
    def __init__(self, key):
        self.key = key
        self.last_request_time = datetime.now()
        self.has_ratelimit_error = False


class ApiKeysManager:
    def __init__(self, api_keys):
        self.api_keys = [ApiKey(key) for key in api_keys]

    def get_next_key(self):
        return min([api_key for api_key in self.api_keys if not api_key.has_ratelimit_error], key=lambda k: k.last_request_time)
        

api_keys_string = os.getenv("OPENAI_API_KEYS")
api_keys_list = api_keys_string.split(', ')

api_keys_manager = ApiKeysManager(api_keys_list)


class Item(BaseModel):
    request: Dict = Field(...)
    max_waiting_time: float = 5


async def send_message_to_openai(request: Dict, task_id: str, max_waiting_time: float, api_key: ApiKey):
    asyncio.create_task(process_request(request, task_id, max_waiting_time, api_key))


async def process_request(request: Dict, task_id: str, max_waiting_time: float, api_key: ApiKey):
    try:
        logging.info("started generating")
        completion = await asyncio.wait_for(openai.ChatCompletion.acreate(**request), timeout=max_waiting_time)
        logging.info("ended generating")
        results[task_id] = completion.choices[0].message['content']
    except Exception as e:
        logging.info(f"Error: {e}")
        api_key.has_ratelimit_error = True
        queue.put_nowait({"item": Item(request=request), "task_id": task_id})
        

def task_id_generator_function():
    task_id = 0
    while True:
        yield task_id
        task_id += 1


@app.post("/task/")
async def create_task(item: Item):
    task_id = task_id_generator_function()
    queue.put_nowait({"item": item, "task_id": task_id})
    return {"task_id": task_id}


@app.get("/task/{task_id}")
async def get_task(task_id: str):
    if task_id not in results:
        return {"status": "not_ready"}
    else:
        return {"status": "ready", "result": results[task_id]}


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(worker())


async def worker():
    global last_request_time, has_ratelimit_error

    while True:
        print(DELAY_BETWEEN_REQUESTS)
        api_key = api_keys_manager.get_next_key()
        openai.api_key = api_key.key

        wait = max(DELAY_BETWEEN_REQUESTS - (datetime.now() - api_key.last_request_time).total_seconds(), 0)
        while api_key.has_ratelimit_error or wait:
            if api_key.has_ratelimit_error:
                await asyncio.sleep(3)
                api_key.has_ratelimit_error = False
            await asyncio.sleep(wait)
            wait = max(DELAY_BETWEEN_REQUESTS - (datetime.now() - api_key.last_request_time).total_seconds(), 0)

        task = await queue.get()
        item = task["item"]
        task_id = task["task_id"]
        api_key.last_request_time = datetime.now()
        await send_message_to_openai(item.request, task_id, item.max_waiting_time, api_key)
        
        if queue.empty():
            await asyncio.sleep(0.01)