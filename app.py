import chainlit as cl
import json
from dotenv import load_dotenv
from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
from movie_functions import get_now_playing_movies, get_showtimes, buy_ticket, confirm_ticket_purchase


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

SYSTEM_PROMPT = """\
You are a helpful assistant that can sometimes answer a with a list of movies, provide movie showtimes, or purchase movie tickets. 

The possible function names are:
    - get_now_playing_movies()
    - get_showtimes(title, location)
    - get_reviews(movie_id)
    - buy_ticket(theater, movie, showtime)
    - confirm_ticket_purchase(theater, movie, showtime)

When user wants to buy a ticket, make sure to confirm with the user on the ticket details before confirming the ticket purchase.
For example, if you need a list of movies, generate a function call, as shown below. Make sure to always include rationale for all function calls.

{
    "function_name": "get_now_playing_movies",
    "rationale": "Explain why you are calling the function",
    "parameters": {}
}

If you need additional information, generate a function call with the required parameters. If there are no required parameters, ask user for the information. 
If you encounter errors, report the issue to the user. 


"""

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

@cl.on_message
@observe
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})
    
    while True:
        print("\n\n\n----------------loop----------------\n\n\n")
        response_message = await generate_response(client, message_history, gen_kwargs)
        print(f"Response message: {response_message.content}")

        # Extract JSON from the response message
        json_start = response_message.content.find('{')
        json_end = response_message.content.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = response_message.content[json_start:json_end]
            try:
                # Parse the JSON object
                function_call_json = json.loads(json_str)
                print(f"Function call json: {function_call_json}")
                # Check if it's a valid function call
                if "function_name" in function_call_json and "rationale" in function_call_json:
                    function_name = function_call_json["function_name"]
                    rationale = function_call_json["rationale"]
                   
                    
                    # Handle the function call
                    if function_name == "get_now_playing_movies":
                        print("\n\n\n====Calling get_now_playing_movies====\n\n\n")
                        movies = get_now_playing_movies()
                        message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{movies}"})
                    elif function_name == "get_showtimes":
                        print("\n\n\n====Calling get_showtimes====\n\n\n")
                        if "parameters" in function_call_json and "title" in function_call_json["parameters"] and "location" in function_call_json["parameters"]:
                            showtimes = get_showtimes(function_call_json["parameters"]["title"], function_call_json["parameters"]["location"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{showtimes}"})   
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                            await cl.Message(content=error_message).send()
                            print("BREAK LOOP: Invalid function call format. Breaking out of loop.")
                            break
                    elif function_name == "buy_ticket":
                        print("\n\n\n====Calling buy_ticket====\n\n\n")
                        if "parameters" in function_call_json and "theater" in function_call_json["parameters"] and "movie" in function_call_json["parameters"] and "showtime" in function_call_json["parameters"]:
                            confirmation = buy_ticket(function_call_json["parameters"]["theater"], function_call_json["parameters"]["movie"], function_call_json["parameters"]["showtime"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{confirmation}.\n\nbuying a ticket for {function_call_json['parameters']['movie']} at {function_call_json['parameters']['theater']} for {function_call_json['parameters']['showtime']}. Confirm these details with the user and ask if they want to proceed before confirming ticket purchase."})   
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                            await cl.Message(content=error_message).send()
                            print("BREAK LOOP: Invalid function call format. Breaking out of loop.")
                            break
                    elif function_name == "confirm_ticket_purchase":
                        print("\n\n\n====Calling confirm_ticket_purchase====\n\n\n")
                        if "parameters" in function_call_json and "theater" in function_call_json["parameters"] and "movie" in function_call_json["parameters"] and "showtime" in function_call_json["parameters"]:
                            confirmation = confirm_ticket_purchase(function_call_json["parameters"]["theater"], function_call_json["parameters"]["movie"], function_call_json["parameters"]["showtime"])
                            message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{confirmation}"})   
                        else:
                            error_message = "Invalid function call format"
                            message_history.append({"role": "system", "content": error_message})
                            await cl.Message(content=error_message).send()
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