# Lead to CRM Sync

Demo video (2 min): [your Loom link]

A proof of concept I built for a made up company, Maple Comfort HVAC.

When someone asks for a quote on the website, this script adds them to HubSpot as a contact with a deal and posts an alert in Slack. If they're already in HubSpot, it skips them.

## What a run looks like

```
NEW   Sarah Chen: contact and deal created
NEW   Mike Patel: contact and deal created
NEW   Lisa Romano: contact and deal created
SKIP  Tom Nguyen: no email
SKIP  Mike Patel: already in CRM
Lead sync done: 3 new, 2 skipped
```

## Run it yourself

1. Copy `.env.example` to `.env` and add your HubSpot service key and Slack webhook URL
2. `pip install requests python-dotenv`
3. `python3 sync_leads.py`

## What it doesn't do yet

- Leads come from a CSV file, not live from the form
- Duplicates are matched by email only
- It doesn't update a contact who comes back with new details

Built with Python, the HubSpot CRM API and Slack webhooks.
