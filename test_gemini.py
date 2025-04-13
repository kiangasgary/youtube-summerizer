import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
print(f"API Key (first 4 chars): {GEMINI_API_KEY[:4]}...")

# Configure genai
genai.configure(api_key=GEMINI_API_KEY)

# List available models
print("\nListing available models:")
for m in genai.list_models():
    print(m.name)

# Create model
model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')

# Simple test
print("\nTesting with a simple prompt...")
response = model.generate_content("Say hello!")
print("\nResponse:", response.text) 