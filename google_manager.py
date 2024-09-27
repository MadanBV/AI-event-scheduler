import os.path
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import datetime
import pytz

CALENDAR_ID = 'primary'

def authenticate_google_calendar():
    """Authenticate and return a Google Calendar service object."""
    # Define the scope needed for the calendar API
    SCOPESC = ['https://www.googleapis.com/auth/calendar']
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPESC)
    creds = flow.run_local_server(port=0)
    service = build('calendar', 'v3', credentials=creds)
    return service

def get_credentials(token_file='token.json', creds_file='credentials.json'):
    """Retrieve or create credentials based on token and credentials files."""
    SCOPESD = ['https://www.googleapis.com/auth/drive']
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPESD)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPESD)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    return creds

def download_office_hours_doc(creds):
    """Download content of the 'office_hours' document as plain text."""
    try:
        service = build("drive", "v3", credentials=creds)
        results = service.files().list(q="name = 'office_hours'", fields="files(id, name, mimeType)").execute()
        items = results.get("files", [])

        if not items:
            print("No file named 'office_hours' found.")
            return None

        file_id = items[0]['id']
        request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        content = fh.read().decode('utf-8')
        return content
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def check_availability(service, day, time_str, office_hours):
    if day not in office_hours:
        print(f"Day '{day}' is not a valid office day.")
        return False, None

    # Define timezone
    timezone = 'America/Los_Angeles'

    # Get the current datetime in the specified timezone.
    current_datetime = datetime.datetime.now(pytz.timezone(timezone))
    current_date = current_datetime.date()
    current_weekday_str = current_datetime.strftime('%a')  # e.g., "Mon"

    # Find index for current and target days of the week
    days_of_week = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    current_weekday_index = days_of_week.index(current_weekday_str)  # Current weekday index
    target_weekday_index = days_of_week.index(day)  # Target weekday index

    # Calculate how many days to add to current date to reach the next occurrence of 'day'
    days_ahead = (target_weekday_index - current_weekday_index) % 7
    if days_ahead == 0 and current_datetime.strftime('%I:%M%p') >= time_str:
        # If today is the target day but the time has already passed, schedule for next week
        days_ahead += 7

    next_target_date = current_date + datetime.timedelta(days=days_ahead)

    # Convert the appointment time into datetime object
    appointment_start = datetime.datetime.strptime(f'{next_target_date} {time_str}', '%Y-%m-%d %I:%M%p')
    appointment_start = pytz.timezone(timezone).localize(appointment_start)  # Localize to specified timezone
    appointment_end = appointment_start + datetime.timedelta(minutes=30)  # Assuming a 30-minute slot

    # Debug print to check the calculated times
    print(f"Debug: Checking availability from {appointment_start.isoformat()} to {appointment_end.isoformat()}")

    # Ensure the appointment time is within office hours
    office_start_time_str, office_end_time_str = office_hours[day]
    office_start = datetime.datetime.strptime(f'{next_target_date} {office_start_time_str}', '%Y-%m-%d %I:%M%p')
    office_end = datetime.datetime.strptime(f'{next_target_date} {office_end_time_str}', '%Y-%m-%d %I:%M%p')
    office_start = pytz.timezone(timezone).localize(office_start)
    office_end = pytz.timezone(timezone).localize(office_end)

    if not (office_start <= appointment_start < office_end):
        print("The specified time is not within office hours.")
        return False, None

    # Query the calendar for events in the specified time range
    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=appointment_start.isoformat(),
            timeMax=appointment_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        is_free = len(events) == 0
        return is_free, f'{appointment_start.isoformat()}/{appointment_end.isoformat()}'
    except Exception as e:
        print(f"An error occurred while checking availability: {str(e)}")
        return False, None

def create_event(service, start_time, end_time, summary, description=''):
    """Create a calendar event."""
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/Los_Angeles',
        },
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    event_id = created_event.get('id')
    return f'Event created: {event.get("htmlLink")}', event_id

def delete_event(service, event_id):
    """Delete an event from the calendar."""
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        return f'Event with ID {event_id} deleted successfully.'
    except Exception as e:
        print(f"An error occurred while deleting event: {str(e)}")
        return None

def update_event(service, event_id, start_time, end_time, summary, description=''):
    """Update an existing calendar event."""
    try:
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'America/Los_Angeles',
            },
        }
        updated_event = service.events().update(
            calendarId=CALENDAR_ID,
            eventId=event_id,
            body=event
        ).execute()
        return f'Event updated: {updated_event.get("htmlLink")}'
    except Exception as e:
        print(f"An error occurred while updating event: {str(e)}")
        return None

def get_events_for_date(service, date):
    try:
        # Define start and end datetime objects for the specified date
        start_datetime = f"{date}T00:00:00Z"  # Start of the day
        end_datetime = f"{date}T23:59:59Z"    # End of the day

        # Call the Google Calendar API to retrieve events for the specified date
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_datetime,
            timeMax=end_datetime,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        # Extract events from the response
        events = events_result.get('items', [])
        
        # Return the list of events
        return events
    
    except Exception as e:
        print(f"An error occurred while retrieving events: {str(e)}")
        return None
