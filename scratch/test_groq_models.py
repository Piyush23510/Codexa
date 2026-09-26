import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    res = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": "Hello, respond with OK"}]
    )
    print("Response from openai/gpt-oss-20b:", res.choices[0].message.content)
except Exception as e:
    print("Error with openai/gpt-oss-20b:", e)
