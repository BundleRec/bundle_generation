import backoff
import openai
import requests
import json


class OpenAI:
    def __init__(self, model, api_key, temperature=0):

        openai.api_key = api_key
        self.model = model
        self.temperature = temperature

    @backoff.on_exception(backoff.expo, (openai.error.RateLimitError, openai.error.APIError, openai.error.APIConnectionError, openai.error.Timeout), max_tries=5, factor=2, max_time=60)
    def create_chat_completion(self, messages):

        completion = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )

        return completion.choices[0].message.content
    
class Claude:
    def __init__(self, model, api_key, temperature=0):

        self.Claude_url = "https://api.anthropic.com/v1"
        self.Claude_api_key = api_key
        self.model = model
        self.temperature = temperature

    @backoff.on_exception(backoff.expo, (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.RequestException), max_tries=5, factor=2, max_time=60)
    def create_chat_completion(self, messages):
        # convert messages to string
        formatted_string = "\n\n{}: {}\n\nAssistant: ".format("Human" if messages[0]["role"] == "user" else "Assistant", messages[0]["content"])
        url = f"{self.Claude_url}/complete"
        headers = {
            "accept": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.Claude_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "prompt": formatted_string,
            "max_tokens_to_sample": 256,
            "temperature": self.temperature
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=30)
        response_json = response.json()

        return response_json['completion'].strip()