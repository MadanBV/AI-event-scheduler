import os
import datetime
from openai import OpenAI
from google_manager import authenticate_google_calendar, check_availability, create_event, update_event, delete_event, get_events_for_date

def get_response(client, messages):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return response.choices[0].message.content

def parse_office_hours(office_hours_str):
    """Parse office hours from a multi-line string into a dictionary."""
    office_hours = {}
    lines = office_hours_str.strip().split('\n')
    for line in lines:
        clean_line = line.strip().replace('\r', '')
        if ':' in clean_line:
            day_part, times = clean_line.split(': ')
            day = day_part.split()[-1]
            start_time_str, end_time_str = times.split('-')
            office_hours[day] = (start_time_str.strip(), end_time_str.strip())
    return office_hours

def chat_with_chatgpt(office_hours_str):
    """Interact with the user to schedule appointments based on office hours using ChatGPT."""
    service = authenticate_google_calendar()
    OPENAI_API_KEY = "Your open API key"
    office_hours = parse_office_hours(office_hours_str)
    client = OpenAI(api_key=OPENAI_API_KEY)
    messages=[]
    
    # Greet the user and ask for their name
    messages.append({"role":"system","content":"Greet the user and inform that you are an appointment booking assistant. Ask the user to input their name"})
    greeting = get_response(client,messages)
    print(greeting)
    messages.append({"role":"assistant","content":greeting})
    x=input()
    messages.append({"role":"user","content":x})
    print(messages) #debug

    while True:
        # Ask for action
        messages.append({"role":"system","content":"Ask the user if they would like to schedule, update, delete or list of appointment."})
        action_prompt = get_response(client, messages)
        print(action_prompt)
        messages.append({"role":"assistant","content":action_prompt})
        action = input().lower()
        
        # Perform task based on action
        if action == "schedule":
            schedule_appointment(service, office_hours, client, messages)
        elif action == "update":
            update_appointment(service, office_hours, client, messages)
        elif action == "delete":
            delete_appointment(service, client, messages)
        elif action == "list":
            list_appointments(service, client, messages)
        else:
            print("Invalid action.")
            
        messages.append({"role":"system","content":"Ask user would he like to do any other task.(yes/no)"})
        print(get_response(client, messages))
        res=input().lower()
        if res == "no":
            messages.append({"role":"system","content":"Thank the user"})
            print(get_response(client, messages))
            break

def schedule_appointment(service, office_hours, client, messages):
    """Schedule a new appointment."""
    print("Here are our office hours:")
    for day, times in office_hours.items():
        print(f"{day}: {times[0]} to {times[1]}")
    
    while True:
        try:
            messages.append({"role":"system","content":"Ask the user to enter the day and time they would like to schedule the appointment (e.g., Tue 2:00pm):"})
            appointment_time = get_response(client,messages)
            messages.append({"role":"assistant","content":appointment_time})
            print(appointment_time)
            user_input = input()  # Input for the day and time
            messages.append({"role":"user","content":user_input})
            day, time_str = user_input.split()
            print("day",day)
            print("time_str",time_str)
            print(messages) #debug
            
            is_free, time_range = check_availability(service, day, time_str, office_hours)
            if is_appointment_valid(day, time_str, office_hours) and is_free:
                messages.append({"role":"system","content":"Generate a polite confirmation message for user with an appointment scheduled on the date they mentioned"})
                confirmation_message = get_response(client, messages)
                messages.append({"role":"assistant","content":confirmation_message})
                print(time_range)
                start_time, end_time = time_range.split('/')
                print("start_time",start_time)
                print("End_time",end_time)
                title = input("Enter the title of the meeting: ")
                event_link, event_id = create_event(service, start_time, end_time, title)
                #print(f"{confirmation_message}\nYou can view the event here: {event_link}")
                print("Event ID", event_id)
                break
            else:
                messages.append({"role":"system","content":"Sorry, the requested time slot is not available."})
                unavailable_time = get_response(client, messages)
                print(unavailable_time)
        except ValueError:
            messages.append({"role":"system","content":"Please enter a valid day followed by time in the format 'Day HH:MMam/pm'. Example: Tue 2:00pm"})
            print(get_response(client, messages))
        except Exception as e:
            error_handling = f"An error occurred: {str(e)}"
            print(get_response(client, error_handling))


def update_appointment(service, office_hours, client, messages):
    #Update an existing appointment.
    messages.append({"role":"system","content":"Ask the user to enter the event ID of the appointment they want to update."})
    print(get_response(client, messages))
    event_id = input()
    while True:
        messages.append({"role":"system","content":"Ask the user to enter the day and time to schedule new event (e.g., Tue 2:00pm):"})
        appointment_time = get_response(client,messages)
        messages.append({"role":"assistant","content":appointment_time})
        print(appointment_time)
        user_input = input()  # Input for the day and time
        messages.append({"role":"user","content":user_input})
        day, time_str = user_input.split()
        print("day",day)
        print("time_str",time_str)
        print(messages) #debug
        is_free, time_range = check_availability(service, day, time_str, office_hours)
        if is_appointment_valid(day, time_str, office_hours) and is_free:
            messages.append({"role":"system","content":"Generate a polite confirmation message for user with an appointment scheduled on the date they mentioned"})
            confirmation_message = get_response(client, messages)
            messages.append({"role":"assistant","content":confirmation_message})
            print(time_range)
            start_time, end_time = time_range.split('/')
            print("start_time",start_time)
            print("End_time",end_time)
            title = input("Enter the title of the meeting: ")
            #print(get_response(client, messages))
            update_event(service, event_id, start_time, end_time, title)
            messages.append({"role":"system","content":"Tell user thet the event is updated"})
            unavailable_time = get_response(client, messages)
            print(unavailable_time)
            break
        else:
            messages.append({"role":"system","content":"Sorry, the requested time slot is not available."})
            unavailable_time = get_response(client, messages)
            print(unavailable_time)

def delete_appointment(service, client, messages):
    """Delete an existing appointment."""
    messages.append({"role":"system","content":"Ask the user to enter the event ID of the appointment they want to delete."})
    print(get_response(client, messages))
    event_id = input()
    mes = delete_event(service, event_id)
    print(mes)

def list_appointments(service, client, messages):
    """List all appointments for a given date."""
    messages.append({"role":"system","content":"Ask the user to enter the date (YYYY-MM-DD) to list appointments for."})
    print(get_response(client, messages))
    date_str = input()
    events = get_events_for_date(service, date_str)
    if events:
        messages.append({"role":"system","content":"Tell the user events of the given date."})
        print(get_response(client, messages))
        print("Title, Event ID,                   Start time,                End Time")
        for event in events:
            print(f"{event['summary']}, {event.get('id')}, {event['start']['dateTime']}, {event['end']['dateTime']}")
    else:
        messages.append({"role":"system","content":"Tell the user no event for the given date."})
        print(get_response(client, messages))

def is_appointment_valid(day, time_str, office_hours):
    """Check if the proposed appointment time is within the office hours for a given day."""
    if day not in office_hours:
        return False
    start_time_str, end_time_str = office_hours[day]
    start_time = datetime.datetime.strptime(start_time_str, "%I:%M%p").time()
    end_time = datetime.datetime.strptime(end_time_str, "%I:%M%p").time()
    appointment_time = datetime.datetime.strptime(time_str, "%I:%M%p").time()
    return start_time <= appointment_time <= end_time
