import requests
import os

api_key = os.getenv("GROQ_API_KEY")

response = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": "Say: Groq working"}]
    }
)

print("Status:", response.status_code)
if response.ok:
    print("Response:", response.json()["choices"][0]["message"]["content"])
else:
    print("Error:", response.text)
