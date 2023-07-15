import requests
import time
import json

BASE_URL = "http://localhost:8088"

total_requests = 100

request_dict = {
    "model": "gpt-3.5-turbo",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Write 10 words article on this theme: 'Paris'"}
    ]
}

start_time = time.time()

task_ids = []
for _ in range(total_requests):
    response = requests.post(f"{BASE_URL}/task/", json={"request": request_dict})
    response_data = response.json()
    task_ids.append(response_data['task_id'])

while task_ids:
    for task_id in task_ids:
        response = requests.get(f"{BASE_URL}/task/{task_id}")
        response_data = response.json()
        if response_data['status'] == 'ready':
            print(response_data["result"].replace("\n", ""))
            task_ids.remove(task_id)
            break
        time.sleep(0.001)  # Wait for 0.5 seconds before checking again
    # print(len(task_ids))

end_time = time.time()

print(f"Time taken to process {total_requests} requests: {end_time - start_time} seconds")
