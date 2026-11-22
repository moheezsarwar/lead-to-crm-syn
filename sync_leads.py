import csv
import os
import requests
from dotenv import load_dotenv

load_dotenv()
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
SLACK_URL = os.getenv("SLACK_WEBHOOK_URL")
HEADERS = {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}
API = "https://api.hubapi.com/crm/v3/objects"


def find_contact(email):
    # Ask HubSpot: is there already a contact with this email?
    body = {"filterGroups": [{"filters": [
        {"propertyName": "email", "operator": "EQ", "value": email}
    ]}]}
    r = requests.post(f"{API}/contacts/search", headers=HEADERS, json=body)
    r.raise_for_status()
    results = r.json()["results"]
    return results[0]["id"] if results else None


def create_contact(lead):
    body = {"properties": {
        "firstname": lead["first_name"],
        "lastname": lead["last_name"],
        "email": lead["email"],
        "phone": lead["phone"],
    }}
    r = requests.post(f"{API}/contacts", headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()["id"]


def create_deal(lead, contact_id):
    body = {
        "properties": {
            "dealname": f"{lead['service']} - {lead['first_name']} {lead['last_name']}",
            "amount": lead["estimated_value"],
            "pipeline": "default",
            "dealstage": "appointmentscheduled",
        },
        # Link the deal to the contact (3 = HubSpot's "deal to contact" link)
        "associations": [{
            "to": {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
        }],
    }
    r = requests.post(f"{API}/deals", headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()["id"]


def post_to_slack(text):
    requests.post(SLACK_URL, json={"text": text})


created, skipped = 0, 0
seen = set()  # emails handled in this run

with open("leads.csv") as f:
    for lead in csv.DictReader(f):
        name = f"{lead['first_name']} {lead['last_name']}"
        email = lead["email"].strip().lower()

        if not email:
            print(f"SKIP  {name}: no email")
            skipped += 1
            continue

        if email in seen or find_contact(email):
            print(f"SKIP  {name}: already in CRM")
            skipped += 1
            continue

        contact_id = create_contact(lead)
        create_deal(lead, contact_id)
        seen.add(email)
        created += 1
        print(f"NEW   {name}: contact and deal created")
        post_to_slack(f":new: New lead: *{name}*, {lead['service']}, est. ${lead['estimated_value']}")

summary = f"Lead sync done: {created} new, {skipped} skipped"
print(summary)
post_to_slack(summary)
