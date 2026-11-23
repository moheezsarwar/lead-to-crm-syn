"""
Lead to CRM sync with AI triage. Demo for a made-up company, Maple Comfort HVAC.

1. Reads leads from leads.csv.
2. Skips leads with no email, and duplicates (in the file or already in HubSpot).
3. Asks an IBM watsonx.ai Granite model to mark each new lead URGENT or ROUTINE
   and write a one-line summary. If the AI fails or gives an odd answer, the
   lead is marked "unknown" and still goes into HubSpot.
4. Creates a HubSpot contact and a linked deal.
5. Posts Slack alerts, urgent leads first, then a summary.

Secrets live in .env, which is not on GitHub.
"""

import csv
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------- Settings (secrets come from .env) ----------
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN", "").strip()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()

AI_PROVIDER = os.getenv("AI_PROVIDER", "watsonx").strip().lower()  # watsonx or none
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY", "").strip()
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "").strip()
WATSONX_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").strip().rstrip("/")
WATSONX_MODEL_ID = os.getenv("WATSONX_MODEL_ID", "ibm/granite-4-h-small").strip()
WATSONX_VERSION = "2024-05-31"  # IBM's API needs a version date on every call

HUBSPOT_API = "https://api.hubapi.com/crm/v3/objects"
CSV_FILE = "leads.csv"
TIMEOUT = 30  # seconds to wait for any web request

# The model must answer in this exact shape: PRIORITY | SUMMARY
SYSTEM_PROMPT = (
    "You triage service requests for an HVAC company. "
    "Reply with exactly one line in this format: PRIORITY | SUMMARY\n"
    "PRIORITY must be the single word URGENT or ROUTINE.\n"
    "URGENT means no heat or no cooling with a health or safety risk, a gas smell, "
    "a carbon monoxide alarm, a water leak, or a vulnerable person such as a baby, "
    "an elderly person, or someone with a medical condition.\n"
    "Everything else is ROUTINE.\n"
    "SUMMARY is at most 15 words in plain English.\n"
    "Do not add any other text."
)

SORT_ORDER = {"URGENT": 0, "ROUTINE": 1, "UNKNOWN": 2}


# ---------- HubSpot ----------
def hubspot_headers():
    return {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}


def contact_exists(email):
    """True if a HubSpot contact already has this email."""
    body = {
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
        "limit": 1,
    }
    r = requests.post(f"{HUBSPOT_API}/contacts/search", headers=hubspot_headers(), json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return len(r.json().get("results", [])) > 0


def create_contact(lead, email):
    body = {"properties": {
        "email": email,
        "firstname": (lead.get("first_name") or "").strip(),
        "lastname": (lead.get("last_name") or "").strip(),
        "phone": (lead.get("phone") or "").strip(),
    }}
    r = requests.post(f"{HUBSPOT_API}/contacts", headers=hubspot_headers(), json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["id"]


def create_deal(lead, name, contact_id, priority):
    deal_name = f"{(lead.get('service') or 'Service request').strip()} - {name}"
    if priority == "URGENT":
        deal_name += " [URGENT]"
    body = {
        "properties": {
            "dealname": deal_name,
            "amount": (lead.get("estimated_value") or "0").strip(),
            "pipeline": "default",
            "dealstage": "appointmentscheduled",
        },
        # Link the deal to the contact (3 = HubSpot's "deal to contact" link)
        "associations": [{
            "to": {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
        }],
    }
    r = requests.post(f"{HUBSPOT_API}/deals", headers=hubspot_headers(), json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["id"]


# ---------- AI: IBM watsonx.ai ----------
_token = {"value": None, "expires_at": 0.0}


def get_ibm_token():
    """Swap the IBM Cloud API key for a short-lived access token. Reused until it's near expiry."""
    if _token["value"] and time.time() < _token["expires_at"] - 300:
        return _token["value"]
    r = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": WATSONX_API_KEY},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires_at"] = time.time() + float(data.get("expires_in", 3600))
    return _token["value"]


def ask_watsonx(message):
    """Send one customer message to the Granite model and return its raw reply."""
    if not WATSONX_API_KEY or not WATSONX_PROJECT_ID:
        raise RuntimeError("WATSONX_API_KEY or WATSONX_PROJECT_ID is missing in .env")
    body = {
        "model_id": WATSONX_MODEL_ID,
        "project_id": WATSONX_PROJECT_ID,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": message}]},
        ],
        "max_tokens": 60,
        "temperature": 0,
    }
    r = requests.post(
        f"{WATSONX_URL}/ml/v1/text/chat?version={WATSONX_VERSION}",
        headers={"Authorization": f"Bearer {get_ibm_token()}", "Content-Type": "application/json",
                 "Accept": "application/json"},
        json=body, timeout=TIMEOUT,
    )
    if r.status_code != 200:
        raise RuntimeError(f"watsonx HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


def parse_triage(text):
    """Read 'PRIORITY | SUMMARY'. Anything else counts as UNKNOWN."""
    if not isinstance(text, str):
        return "UNKNOWN", ""
    for line in text.strip().splitlines():
        if "|" in line:
            left, right = line.split("|", 1)
            priority = left.strip().strip("*").strip().upper()
            if priority in ("URGENT", "ROUTINE"):
                return priority, right.strip()[:120]
    return "UNKNOWN", ""


def triage(message):
    """Return (priority, summary, note). Never raises, so the AI can't block the CRM write."""
    message = (message or "").strip()
    if not message:
        return "UNKNOWN", "", "no message"
    if AI_PROVIDER == "none":
        return "UNKNOWN", "", "AI turned off"
    try:
        raw = ask_watsonx(message)
        priority, summary = parse_triage(raw)
        if priority == "UNKNOWN":
            return "UNKNOWN", "", f"unexpected AI reply: {raw[:60]!r}"
        return priority, summary, "ok"
    except Exception as e:  # any AI problem: label it and move on
        return "UNKNOWN", "", f"AI error: {str(e)[:150]}"


def label(priority):
    return {"URGENT": "URGENT", "ROUTINE": "routine"}.get(priority, "unknown")


# ---------- Slack ----------
def post_to_slack(text):
    try:
        r = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  (Slack warning: HTTP {r.status_code})")
    except requests.RequestException as e:
        print(f"  (Slack warning: {e})")


# ---------- Main ----------
def read_leads():
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def full_name(lead, row_number):
    name = f"{(lead.get('first_name') or '').strip()} {(lead.get('last_name') or '').strip()}".strip()
    return name or f"row {row_number}"


def ai_test():
    """Run only the AI step on each message. Touches nothing in HubSpot or Slack."""
    print("AI test only. Nothing is written to HubSpot or Slack.\n")
    for i, lead in enumerate(read_leads(), start=1):
        priority, summary, note = triage(lead.get("message"))
        print(f"{label(priority):8} {full_name(lead, i)}: {summary or '-'} ({note})")


def main():
    missing = [n for n, v in (("HUBSPOT_TOKEN", HUBSPOT_TOKEN), ("SLACK_WEBHOOK_URL", SLACK_WEBHOOK_URL)) if not v]
    if missing:
        print(f"Missing in .env: {', '.join(missing)}")
        sys.exit(1)

    new_leads, skipped, errors, seen = [], 0, 0, set()

    for i, lead in enumerate(read_leads(), start=1):
        name = full_name(lead, i)
        email = (lead.get("email") or "").strip().lower()

        if not email:
            print(f"SKIP   {name}: no email")
            skipped += 1
            continue
        if email in seen:
            print(f"SKIP   {name}: duplicate in this file")
            skipped += 1
            continue
        seen.add(email)

        try:
            if contact_exists(email):
                print(f"SKIP   {name}: already in CRM")
                skipped += 1
                continue
        except requests.RequestException as e:
            print(f"ERROR  {name}: HubSpot search failed, so nothing was created ({e})")
            errors += 1
            continue

        priority, summary, note = triage(lead.get("message"))

        try:
            contact_id = create_contact(lead, email)
            create_deal(lead, name, contact_id, priority)
        except requests.RequestException as e:
            print(f"ERROR  {name}: HubSpot create failed ({e})")
            errors += 1
            continue

        print(f"NEW    {name}: {label(priority)} | {summary or '-'} (AI: {note})")
        new_leads.append({"name": name, "lead": lead, "priority": priority, "summary": summary})

    # Slack alerts: urgent first, then routine, then unknown
    new_leads.sort(key=lambda x: SORT_ORDER.get(x["priority"], 2))
    for n in new_leads:
        tag = ":rotating_light: *URGENT*" if n["priority"] == "URGENT" else label(n["priority"])
        service = (n["lead"].get("service") or "").strip()
        value = (n["lead"].get("estimated_value") or "").strip()
        post_to_slack(f"{tag} | New lead: *{n['name']}* | {service} | est. ${value}\n"
                      f"Summary: {n['summary'] or 'n/a'}")

    urgent = sum(1 for n in new_leads if n["priority"] == "URGENT")
    done = f"Lead sync done: {len(new_leads)} new ({urgent} urgent), {skipped} skipped, {errors} errors"
    print("\n" + done)
    post_to_slack(done)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--ai-test":
        ai_test()
    else:
        main()
