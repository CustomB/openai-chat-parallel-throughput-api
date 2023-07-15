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

MAX_TOKENS_PER_MINUTE = 12 * 10**4
MAX_TOKENS_PER_REQUEST = 100.0
# DELAY_BETWEEN_REQUESTS = 60.0 / (MAX_TOKENS_PER_MINUTE / MAX_TOKENS_PER_REQUEST)
DELAY_BETWEEN_REQUESTS = 0.02

app = FastAPI()
queue = asyncio.Queue()
last_request_time = datetime.now()

results = {}


class Item(BaseModel):
    request: Dict = Field(...)

openai.api_key = os.getenv("OPENAI_API_KEY")


async def send_message_to_openai(request: Dict, task_id: str):
    global last_request_time
    logging.info("Success")
    last_request_time = datetime.now()
    try:
        asyncio.create_task(process_request(request, task_id))
    except:
        queue.put_nowait({"item": Item(request=request), "task_id": task_id})
        return


async def process_request(request: Dict, task_id: str):
    completion = await openai.ChatCompletion.acreate(**request)
    message = completion.choices[0].message['content']
    print(message)
    results[task_id] = message


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
        global last_request_time
        print(DELAY_BETWEEN_REQUESTS)

        wait = max(DELAY_BETWEEN_REQUESTS - (datetime.now() - last_request_time).total_seconds(), 0)
        while wait:
            await asyncio.sleep(wait)
            wait = max(DELAY_BETWEEN_REQUESTS - (datetime.now() - last_request_time).total_seconds(), 0)

        task = await queue.get()
        item = task["item"]
        task_id = task["task_id"]
        await send_message_to_openai(item.request, task_id)