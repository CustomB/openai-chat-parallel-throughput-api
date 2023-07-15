import requests
import time
import numpy as np

BASE_URL = "http://localhost:8088"

total_requests = 3000


prompts = [
    "Describe a moment when you felt incredibly proud of someone else. How did their achievement affect your relationship with them?",
    "Imagine you wake up in a post-apocalyptic world. What's your first move?",
    "Write a letter to your future self 10 years from now. What advice would you give?",
    "You are the inventor of a new gadget that can communicate with animals. Describe your first conversation with an animal and its implications.",
    "Describe the perfect day in your dream city. What activities would you do? What sights would you see?",
    "You have been chosen to be the ambassador of Earth to a newly discovered alien civilization. Write your first speech to the extraterrestrial beings.",
    "Narrate a story where the protagonist is a sentient AI navigating human society.",
    "Imagine you are a time traveler from the year 2200. Describe the most surprising change you see in the world of 2023.",
    "You've found a hidden door in your house leading to a secret room. What's inside it?",
    "The world now runs on a barter system instead of money. How does this change your daily life?",
]


request_dict = {
    "model": "gpt-3.5-turbo",
}

start_time = time.time()

task_ids = []
for _ in range(total_requests):
    request_dict["messages"] = [
        {"role": "system", "content": "You are a helpful assistant. You answer is 10 words long maximum"},
        {"role": "user", "content": np.random.choice(prompts)}
    ]
    response = requests.post(f"{BASE_URL}/task/", json={
        "request": request_dict,
        "max_waiting_time": 5
    })
    response_data = response.json()
    task_ids.append(response_data['task_id'])

counter = 0
while task_ids:
    for task_id in task_ids:
        response = requests.get(f"{BASE_URL}/task/{task_id}")
        response_data = response.json()
        if response_data['status'] == 'ready':
            task_ids.remove(task_id)
            counter += 1
            break
        print(counter / (time.time() - start_time))
        time.sleep(0.001) 
    # print(len(task_ids))

end_time = time.time()

print(f"Time taken to process {total_requests} requests: {end_time - start_time} seconds")
