import chainlit as cl
import json
from dotenv import load_dotenv
from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
from movie_functions import get_now_playing_movies, get_showtimes, buy_ticket, confirm_ticket_purchase, get_reviews
from prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_REVIEWS

load_dotenv()

# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable
# client = wrap_openai(openai.AsyncClient())
 
client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 500
}



@observe
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

@observe
async def generate_reviews_response(client, message_history, gen_kwargs):
    response = await client.chat.completions.create(
        messages=message_history + [{"role": "system", "content": SYSTEM_PROMPT_REVIEWS}],
        **gen_kwargs
    )
    response_message = response.choices[0].message
    print(f"Reviews response message: {response_message}")
    return response_message

@cl.on_message
@observe
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})

    while True:
        print("\n\n\n----------------loop----------------\n\n\n")
        reviews_response_message = await generate_reviews_response(client, message_history + [{"role": "system", "content": SYSTEM_PROMPT_REVIEWS}], gen_kwargs)
        print(f"Reviews response message: {reviews_response_message.content}")
        
        response_message = await generate_response(client, message_history, gen_kwargs)
        print(f"Response message: {response_message.content}")

        # Extract JSON from the response message
        json_start = response_message.content.find('{')
        json_end = response_message.content.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = response_message.content[json_start:json_end]
            try:
                # Parse the JSON object
                json_object = json.loads(json_str)
                print(f"Function call json: {json_object}")

                # Check if the we should fetch reviews based on the response message
                print("\n\n\n====Checking if we should fetch reviews====\n\n\n")
                if "fetch_reviews" in json_object and json_object["fetch_reviews"]:
                    # Fetch reviews for the movie
                    reviews = get_reviews(json_object["id"])
                    message_history.append({"role": "system", "content": f"Reviews for {json_object['movie']}:\n\n{reviews}\n\nRationale: {json_object['rationale']}"})
                else:
                    print("Reviews not fetched as per user's request.")

                print("\n\n\n====Checking if it's a valid function call====\n\n\n")
                # Check if it's a valid function call
                if "function_name" in json_object and "rationale" in json_object:
                    function_name = json_object["function_name"]
                    rationale = json_object["rationale"]
                   
                    
                    # Handle the function call
                    if function_name == "get_now_playing_movies":
                        print("\n\n\n====Calling get_now_playing_movies====\n\n\n")
                        movies = get_now_playing_movies()
                        message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{movies}"})
                    elif function_name == "get_showtimes":
                        print("\n\n\n====Calling get_showtimes====\n\n\n")
                        if "parameters" in json_object and "title" in json_object["parameters"] and "location" in json_object["parameters"]:
                            showtimes = get_showtimes(json_object["parameters"]["title"], json_object["parameters"]["location"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{showtimes}"})   
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                            await cl.Message(content=error_message).send()
                            print("BREAK LOOP: Invalid function call format. Breaking out of loop.")
                            break
                    elif function_name == "buy_ticket":
                        print("\n\n\n====Calling buy_ticket====\n\n\n")
                        if "parameters" in json_object and "theater" in json_object["parameters"] and "movie" in json_object["parameters"] and "showtime" in json_object["parameters"]:
                            confirmation = buy_ticket(json_object["parameters"]["theater"], json_object["parameters"]["movie"], json_object["parameters"]["showtime"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{confirmation}.\n\nbuying a ticket for {json_object['parameters']['movie']} at {json_object['parameters']['theater']} for {json_object['parameters']['showtime']}. Confirm these details with the user and ask if they want to proceed before confirming ticket purchase."})   
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                            await cl.Message(content=error_message).send()
                            print("BREAK LOOP: Invalid function call format. Breaking out of loop.")
                            break
                    elif function_name == "confirm_ticket_purchase":
                        print("\n\n\n====Calling confirm_ticket_purchase====\n\n\n")
                        if "parameters" in json_object and "theater" in json_object["parameters"] and "movie" in json_object["parameters"] and "showtime" in json_object["parameters"]:
                            confirmation = confirm_ticket_purchase(json_object["parameters"]["theater"], json_object["parameters"]["movie"], json_object["parameters"]["showtime"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{confirmation}"})   
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                        await cl.Message(content=error_message).send()
                    elif function_name == "get_reviews":
                        print("\n\n\n====Calling get_reviews====\n\n\n")
                        if "parameters" in json_object and "movie_id" in json_object["parameters"]:
                            reviews = get_reviews(json_object["parameters"]["movie_id"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{reviews}"})
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                            await cl.Message(content=error_message).send()
                            print("BREAK LOOP: Invalid function call format. Breaking out of loop.")
                            break
                    else:
                        # Handle unknown function calls
                        error_message = f"Unknown function: {function_name}"
                        message_history.append({"role": "system", "content": error_message})
                        await cl.Message(content=error_message).send()
                        print("BREAK LOOP: Unknown function. Breaking out of loop.")
                        break
                else:
                    # Handle invalid function call format
                    error_message = "Invalid function call format"
                    message_history.append({"role": "system", "content": error_message})
                    await cl.Message(content=error_message).send()
                    print("BREAK LOOP:Invalid function call format. Breaking out of loop.")
                    break
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as a normal message
                message_history.append({"role": "assistant", "content": response_message.content})
                print("BREAK LOOP: No JSON found in response message. Breaking out of loop.")
                break
        else:
            # If no JSON is found, treat it as a normal message
            message_history.append({"role": "assistant", "content": response_message.content})
            print("BREAK LOOP:No JSON found in response message. Breaking out of loop.")
            break

    cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()