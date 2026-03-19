from google import genai
client = genai.Client(api_key="GOOGLE_API_KEY")
for m in client.models.list():
    if "embedContent" in m.supported_actions:
        print(m.name)