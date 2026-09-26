import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
print("API Key present:", bool(api_key))

client = Groq(api_key=api_key)

models_to_test = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

for model in models_to_test:
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello"}]
        )
        print(f"SUCCESS with model '{model}': {res.choices[0].message.content[:30]}")
    except Exception as e:
        print(f"FAILED with model '{model}': {e}")
