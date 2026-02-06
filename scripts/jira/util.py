import json
from typing import TypedDict, Any, Dict, List
import requests
from dotenv import dotenv_values, load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

config = dotenv_values('.env')
base = config.get('JIRA_BASE_URL')
url = f"{base}/rest/api/2/issue"

auth = HTTPBasicAuth(config.get('JIRA_USER'),config.get('JIRA_API_TOKEN'))

headers = {
  "Accept": "application/json",
  "Content-Type": "application/json"
}

class Fields(TypedDict):
  components: List[str]
  project: str
  issuetype: str
  issue_category: str
  epic_key: str
  delivery_team: str
  cost_impact: str
  assignee: str
  summary: str # title
  description: str
  point: float


def create_issue(fields: Fields):
  data = {
    "fields": {
      "components": [{"id": comp_id} for comp_id in fields['components']],
      "project": {"id": fields['project']},
      "summary": fields['summary'],
      "issuetype": {"id": fields['issuetype']},
      "description": fields['description'],
      "assignee": { "name": fields.get('assignee', '')},
      # add custom fields start

      # add custom fields end
    }
  }
  response = requests.request(
    "POST",
    url,
    data=json.dumps(data),
    headers=headers,
    auth=auth
  )
  if response.status_code == 201:
    return json.loads(response.text)
  else:
    print(response.status_code, response.text)
    return None

def get_issue(issue_key):
  response = requests.request(
    "GET",
    f"{url}/{issue_key}?*all",
    headers=headers,
    auth=auth
  )
   
  return json.loads(response.text)
  
def update_issue(ticket_key, data: Dict[str, str]):
  print(f"start to update {ticket_key} issue")
  response = requests.request(
     "PUT",
    f"{url}/{ticket_key}",
    data=json.dumps(data),
    headers=headers,
    auth=auth
  )
  print(response.text, response.status_code)