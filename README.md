# Lead to CRM Sync

A proof of concept for Maple Comfort HVAC, a sample home services company. New leads from the website form land in HubSpot automatically, without duplicates, and the sales team gets a Slack alert for each one.

## The problem
Leads came in through a web form and were copied into the CRM by hand. Some got missed, some were entered twice, and nobody knew a hot lead had arrived until hours later.

## What it does
1. Reads new leads from a CSV export of the web form
2. Skips any lead without an email address
3. Checks HubSpot for an existing contact with the same email, and skips duplicates
4. Creates a contact and a linked deal for each new lead
5. Posts an alert to a Slack channel for each new lead, plus a summary

## Built with
Python, HubSpot CRM API, Slack incoming webhooks

## Run it
1. Copy `.env.example` to `.env` and add your HubSpot service key and Slack webhook URL
2. `pip install requests python-dotenv`
3. `python3 sync_leads.py`

## What it doesn't handle yet
- Leads only arrive as a CSV file, not live from the form
- Duplicates are matched by email only, not by phone or name
- It doesn't update an existing contact when a lead returns with new details
