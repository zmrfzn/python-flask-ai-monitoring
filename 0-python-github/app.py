import os
from openai import OpenAI

client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)

model_id = os.environ["MODEL"] # e.g. "gpt-4o-mini"

def chatCompletion(prompt):
    #print("prompt: "+prompt)
    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "user", "content": prompt}
        ])
    return completion.choices[0].message.content

print()
print("Welcome to the OpenAI Chatbot!")
print("This is a simple chatbot that uses the OpenAI API to generate responses.")
print("You can ask it anything, and it will try to answer.")
print()
print("Please enter your question below:")
# enter prompt from user
prompt = input()
# send prompt to chatCompletion function
response = chatCompletion(prompt)
print()
print("Response:")
print("--------------------------------------------------")
# print response
print(response)
print()