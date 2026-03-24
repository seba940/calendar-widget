import os
import os.path
import httplib2
from google_auth_httplib2 import AuthorizedHttp
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarAPI:
    def __init__(self):
        self.service = None
        self.holiday_calendar_id = 'ko.south_korea#holiday@group.v.calendar.google.com'

    def authenticate(self):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try: 
                    creds.refresh(Request())
                except Exception:
                    if os.path.exists('token.json'): os.remove('token.json')
                    creds = None
            
            if not creds:
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    client_id = os.getenv("GOOGLE_CLIENT_ID")
                    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
                    
                    if not client_id or not client_secret:
                        raise ValueError("인증 정보가 부족합니다. credentials.json 파일 또는 환경 변수가 필요합니다.")

                    client_config = {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": ["http://localhost"]
                        }
                    }
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                    creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w', encoding="utf-8") as t:
                t.write(creds.to_json())
            
        http_client = httplib2.Http(disable_ssl_certificate_validation=True)
        authed_http = AuthorizedHttp(creds, http=http_client)
        self.service = build('calendar', 'v3', http=authed_http, static_discovery=False)
        self.find_holiday_calendar()
        return self.service

    def find_holiday_calendar(self):
        if not self.service: return
        try:
            calendar_list = self.service.calendarList().list().execute()
            for entry in calendar_list.get('items', []):
                if "holiday" in entry.get('summary', '').lower() or "휴일" in entry.get('summary', ''):
                    self.holiday_calendar_id = entry['id']
                    break
        except: pass

    def fetch_events(self, year, month):
        if not self.service: return [], []
        
        s = f"{year}-{month:02d}-01T00:00:00Z"
        e = f"{year + (1 if month==12 else 0)}-{(month%12)+1:02d}-01T00:00:00Z"
        
        events_data = []
        holiday_data = []
        
        for _ in range(2):
            try:
                events_data = self.service.events().list(calendarId='primary', timeMin=s, timeMax=e, singleEvents=True, orderBy='startTime').execute().get('items', [])
                break 
            except: pass 
                
        for _ in range(2):
            try:
                holiday_data = self.service.events().list(calendarId=self.holiday_calendar_id, timeMin=s, timeMax=e, singleEvents=True, orderBy='startTime').execute().get('items', [])
                break
            except: pass 

        return events_data, holiday_data

    def patch_event(self, event_id, body):
        return self.service.events().patch(calendarId='primary', eventId=event_id, body=body).execute()

    def insert_event(self, body):
        return self.service.events().insert(calendarId='primary', body=body).execute()

    def update_event(self, event_id, body):
        return self.service.events().update(calendarId='primary', eventId=event_id, body=body).execute()

    def delete_event(self, event_id):
        return self.service.events().delete(calendarId='primary', eventId=event_id).execute()
