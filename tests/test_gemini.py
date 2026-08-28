import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="You are a character named Faseelah, a friendly companion for children. Greet a 6-year-old boy named Adam with two short sentences in simple Modern Standard Arabic."
)

print(response.text)
