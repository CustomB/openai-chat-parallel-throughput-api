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
DELAY_BETWEEN_REQUESTS = 0.02

app = FastAPI()
queue = asyncio.Queue()
last_request_time = datetime.now()
has_ratelimit_error = False

results = {}


class Item(BaseModel):
    request: Dict = Field(...)
    max_waiting_time: float = 5


async def send_message_to_openai(request: Dict, task_id: str, max_waiting_time: float):
    global last_request_time
    last_request_time = datetime.now()
    asyncio.create_task(process_request(request, task_id))


async def process_request(request: Dict, task_id: str, max_waiting_time: float):
    global has_ratelimit_error
    try:
        logging.info("started generating")
        completion = await asyncio.wait_for(openai.ChatCompletion.acreate(**request), timeout=max_waiting_time)
        logging.info("ended generating")
        results[task_id] = completion.choices[0].message['content']
    except Exception as e:
        logging.info(f"Error: {e}")
        has_ratelimit_error = True
        queue.put_nowait({"item": Item(request=request), "task_id": task_id})
        

@app.post("/task/")
async def create_task(item: Item):
    task_id = str(uuid.uuid4())
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
    while True:
        global last_request_time, has_ratelimit_error
        print(DELAY_BETWEEN_REQUESTS)

        wait = max(DELAY_BETWEEN_REQUESTS - (datetime.now() - last_request_time).total_seconds(), 0)
        while has_ratelimit_error or wait:
            if has_ratelimit_error:
                await asyncio.sleep(3)
                has_ratelimit_error = False
            await asyncio.sleep(wait)
            wait = max(DELAY_BETWEEN_REQUESTS - (datetime.now() - last_request_time).total_seconds(), 0)

        task = await queue.get()
        item = task["item"]
        task_id = task["task_id"]
        await send_message_to_openai(item.request, task_id, item.max_waiting_time)
        
        if queue.empty():
            await asyncio.sleep(0.1)