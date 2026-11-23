# Lead to CRM Sync with AI Triage

Demo video (2 min): add link

A proof of concept for a made-up company, Maple Comfort HVAC.

## Why I built it

At the startup where I work in sales, inbound website leads were tracked by hand. They got typed into the CRM late, and an urgent one looked the same as every other row. I wanted to see how much of that a small script could take over.

## What it does

When someone asks for a quote on the website, the script:

1. Skips the lead if there's no email, or if that person is already in HubSpot
2. Sends the customer's message to an IBM watsonx.ai Granite model, which marks it urgent or routine and writes a one-line summary
3. Creates the contact and a linked deal in HubSpot
4. Posts an alert in Slack, with urgent leads first

If the AI is down or gives an odd answer, the lead is marked "unknown" and still goes into HubSpot. The AI never blocks the CRM.

## What a run looks like

First run:

```
NEW    Priya Shah: URGENT | No heat with newborn in extreme cold. (AI: ok)
NEW    Marcus Lee: routine | Spring AC tune-up in April, no rush. (AI: ok)
SKIP   Dana Okafor: no email
NEW    Tom Becker: routine | Inquiry about smart thermostat brands installed. (AI: ok)
SKIP   Priya Shah: duplicate in this file

Lead sync done: 3 new (1 urgent), 2 skipped, 0 errors
```

Second run on the same file. Nothing is created twice:

```
SKIP   Priya Shah: already in CRM
SKIP   Marcus Lee: already in CRM
SKIP   Dana Okafor: no email
SKIP   Tom Becker: already in CRM
SKIP   Priya Shah: duplicate in this file

Lead sync done: 0 new (0 urgent), 5 skipped, 0 errors
```

## Questions I'd ask a real owner first

- How many web leads come in a week, and who enters them today?
- How fast do you call back an urgent one now? What does a missed one cost you?
- What counts as urgent for you? No heat, a gas smell, a CO alarm, a baby in the house?
- Which CRM and chat tools do you already pay for?

## How I'd know a pilot worked

- Every web lead with an email is in the CRM within minutes
- Running it twice never creates a duplicate
- Urgent leads show at the top of Slack
- On 20 test messages, the urgent flag matches what a person would say

## Rough value (my assumptions, not real data)

Say 15 web leads a week at 4 minutes each to type in. That's about an hour a week of typing gone. The bigger win is calling the no-heat customer back first.

## What it doesn't do yet

- Leads come from a CSV file, not live from the form
- Duplicates are matched by email only
- A follow-up from someone already in HubSpot is skipped, even an urgent one like Priya's "still no heat". Next I'd post those to Slack instead of dropping them
- The urgent flag is a hint for a person, not a decision
- It only runs on made-up data. Real customer messages would need a privacy review first

## Run it yourself

1. Copy `.env.example` to `.env` and add your HubSpot service key, Slack webhook URL, IBM Cloud API key and watsonx project ID
2. `pip install requests python-dotenv`
3. `python3 sync_leads.py --ai-test` checks the AI step only and writes nothing
4. `python3 sync_leads.py` runs the full sync

Built with Python, the HubSpot CRM API, Slack webhooks and IBM watsonx.ai
