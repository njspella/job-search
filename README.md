# Job search

A personal job search tool for engineering manager, principal engineer, AI engineer,
quality director and operations manager roles paying $120,000+, either remote or within
about 50 minutes of Pella, Iowa.

- **Refresh search** pulls new postings and adds them to your saved list. Nothing is ever
  removed, so your statuses and notes stay put.
- **Status** on each job (New, Saved, Applied, Interviewing, Offer, Rejected, Not interested)
  is saved as soon as you change it.
- **Connections** shows which of your LinkedIn connections work at each company.

## The website

The hosted version is the Pella Job Tracker page on claude.ai
(https://claude.ai/artifact/LDJ4KUg9mmqvfeiqrB9G8H). Its source is `site/job-tracker.html`.
Each refresh runs the **Refresh jobs** GitHub Action, which writes `site-data/jobs.json`;
a daily Claude scheduled task (also started by the page's Refresh button) then adds new
jobs to the page without touching your statuses or notes.

Local Iowa jobs come from Adzuna, which needs a free key. To turn it on for the website, get
a key at https://developer.adzuna.com/ and add two repository secrets in GitHub
(Settings > Secrets and variables > Actions): `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
USAJOBS works the same way with `USAJOBS_API_KEY` and `USAJOBS_EMAIL`.

LinkedIn, Indeed and Glassdoor listings come through Google Jobs, which indexes those sites.
Get a key at https://serpapi.com/ and add it as the secret `SERPAPI_KEY`. Each refresh uses
8 searches, so the free plan covers roughly one refresh a day.

## Running it on your own computer instead

Everything in this mode runs on your computer and stays there (in `data/jobs.db`). It needs only
Python 3.9 or newer, with no extra packages.

## Start it

```
git clone https://github.com/njspella/job-search.git
cd job-search
python3 -m jobsearch
```

Your browser opens to the job list. Click **Refresh search** to pull postings.
Stop it with Ctrl+C. Run the same command any time to come back to your list.

## Add your LinkedIn connections

LinkedIn doesn't let other apps read your connections, so the tool uses LinkedIn's own export:

1. On LinkedIn, go to **Settings & Privacy > Data privacy > Get a copy of your data**.
2. Choose **Connections** only and request the archive. LinkedIn emails a link, usually within minutes.
3. Download and unzip it, then click **Import LinkedIn connections** on the job page and pick `Connections.csv`.

Re-import whenever you want fresher data; the new file replaces the old one. Matching uses the
company name each connection lists on their profile, so a few may not match when a company goes
by two names (for example "John Deere" and "Deere & Company").

## Where jobs come from

| Source | Covers | Setup |
| --- | --- | --- |
| Remotive, Remote OK, Himalayas, We Work Remotely | Remote jobs | None |
| Adzuna | Local and remote listings from many job boards | Free key from [developer.adzuna.com](https://developer.adzuna.com/) |
| USAJOBS | Federal jobs | Free key from [developer.usajobs.gov](https://developer.usajobs.gov/) |
| Google Jobs (SerpApi) | LinkedIn, Indeed, Glassdoor and company-site listings | Key from [serpapi.com](https://serpapi.com/) |

LinkedIn, Indeed and Glassdoor don't allow automated searching. For those, keep their email
alerts on and use **Add a job you found elsewhere** on the page to save postings into the same list.

To turn on Adzuna and USAJOBS, create `config.local.json` in this folder:

```json
{
  "adzuna_app_id": "your id",
  "adzuna_app_key": "your key",
  "usajobs_api_key": "your key",
  "usajobs_email": "you@example.com"
}
```

The same file can override any other setting in `jobsearch/config.py`, such as `titles`,
`salary_floor`, `radius_miles` or `queries`. It is git-ignored, so your keys stay private.

## Other commands

```
python3 -m jobsearch refresh                      # refresh without opening the page
python3 -m jobsearch connections Connections.csv  # import connections from the command line
python3 -m unittest discover -s tests             # run the tests
```
