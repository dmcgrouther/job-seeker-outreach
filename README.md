# Job Seeker Outreach Tool

A two-script toolkit that can help find someone's email address and generate a personalized outreach email using AI.

---

## Scripts

| File | Description |
|---|---|
| `find_email.py` | Finds and SMTP-verifies a person's work email address |
| `outreach.py` | Scrapes a job page and generates a personalized outreach email via Claude AI |
| `logger.py` | Logging utility |

---

## Setup

### 1. Install dependencies

```bash
pip install selenium webdriver-manager dnspython requests beautifulsoup4 anthropic ddgs google-genai groq
```

### 2. Set your Hunter API key

`find_email.py` uses Hunter to find email formats. To use this option, you need an API key from [hunter.io](https://hunter.io).

As an example, you could enter this command when using powershell (just swap in your API key):
```powershell
$env:HUNTER_API_KEY='...'
```

### 3. Set your AI API key

`outreach.py` supports multiple AI engines. Set the keys for the ones you want to use. At least one AI API key is needed.

```bash
# Required for outreach.py — at least one AI engine key is needed
export ANTHROPIC_API_KEY="sk-ant-..."   # console.anthropic.com (pay-as-you-go)
export GROQ_API_KEY="..."               # console.groq.com (free tier)
export GEMINI_API_KEY="..."             # aistudio.google.com (free tier)
```

### 4. Edit your background blurb

In `outreach.py`, update the blurb at the top of the file so the AI can personalize the email to you:

```python
MY_BLURB = """
I'm a solutions engineer with a background in sales and software development...
"""
```

### 5. Install Google Chrome

`find_email.py` uses Google/Selenium only if Hunter fails to find an email format. If you want this fallback available, install Chromium:

```bash
# Ubuntu / Debian
sudo apt install -y chromium-browser
```

On Ubuntu with snap, Selenium Manager will automatically detect and use the correct ChromeDriver version (no manual driver installation needed.

---

## Script 1 — find_email.py

Finds the most likely work email address for a given person by detecting the company's email format, and verifies it exists via SMTP.

### Usage

```bash
python find_email.py "Full Name" "Company Name"
```

### Example

```bash
python find_email.py "Jane Smith" "Acme Corp"
```

### Example Output

```
  Detected domain: acmecorp.com
  Detected format: firstname.lastname

  Name:         Jane Smith
  Company:      Acme Corp
  Domain:       acmecorp.com
  Email:        jane.smith@acmecorp.com
  Format:       firstname.lastname
  SMTP status:  Verified - mailbox exists

  Other likely formats:
    - jsmith@acmecorp.com
    - janes@acmecorp.com
    - jacob@acmecorp.com
    ...
```

### How It Works

1. Email format lookup uses a cascading fallback across few sources, stopping at the first success:

| Priority | Source | Notes |
|---|---|---|
| 1 | Hunter.io API | Most accurate — requires `HUNTER_API_KEY` |
| 2 | Google (Selenium) | requires Chromium installed |
| 3 | DuckDuckGo (`ddgs`) | Last resort — Free, unlimited |

2. Infers the company domain and email pattern, and generates a list of candidate email addresses based on common formats
3. Probes the mail server via SMTP to verify which address exists

### SMTP Verification Results

| Status | Meaning |
|---|---|
| Verified | Mailbox confirmed by the mail server |
| Inconclusive | Server could not confirm or deny (catch-all or port blocked) |
| Invalid | Mailbox rejected by the mail server |

---

## Script 2 — outreach.py

Scrapes a job posting page and uses AI to write a concise, personalized outreach email based on the role and your background blurb.

### Usage

```bash
python outreach.py "job_url"
```

### Example

```bash
python outreach.py "https://careers.acmecorp.com/en/jobs/123"
```

### Example Output

```
  Fetching job page ...
  Generating personalized email with Claude ...

  Subject: Exploring Solutions Engineer Opportunities at Acme Corp

  Hi [Hiring Team],

  I came across your Solutions Engineer opening at Acme Corp and wanted
  to reach out directly ...

  Email saved to: outreach_Acme Corp_20240315_142301.txt
```

### How It Works

1. Fetches and parses the job posting URL
2. Extracts the role title, company name, and job description
3. Sends your background blurb + the job content to AI
4. AI writes a tailored email under 250 words with a subject line and call to action
5. Prints the email to the terminal and saves it as a `.txt` file

AI engine selection uses a cascading fallback, stopping at the first success:

| Priority | Engine | Notes |
|---|---|---|
| 1 | Claude (Anthropic) | Pay-as-you-go, highest quality |
| 2 | Gemini (Google) | Free tier, region-dependent |
| 3 | Groq (Llama 3.3) | Free, fast |

---

## Recommended Workflow

Run the two scripts in order:

```bash
# Step 1 — find the recruiter's email
python find_email.py "Jane Smith" "Acme Corp"

# Step 2 — generate the outreach email for the role
python outreach.py "https://careers.acmecorp.com/en/jobs/..."
```

Then copy the email from `outreach.py`'s output and send it to the address found by `find_email.py`.

---

## Notes & Limitations

- **SMTP catch-alls** — Large companies using Google Workspace or Microsoft 365 often accept any address. In these cases the SMTP status will show as inconclusive rather than verified, but the email guess is still likely correct.
- **Port 25 blocking** — Some ISPs block outbound port 25 used for SMTP probing. If verification times out, proceed with the guessed address.
- **Google CAPTCHA** — `find_email.py` scrapes Google search results. If a CAPTCHA appears, wait a few minutes and try again.
- **Claude API costs** — Each run of `outreach.py` makes one API call to Claude, billed to your Anthropic account.
- **Hunter.io quota** — The free tier provides 50 searches/month. Results for well-known companies are often cached and do not consume quota.
- **Gemini free tier** — The Gemini API free tier is not available in all regions. Canadian IPs may experience quota issues. Groq is the recommended free alternative.
- **Site compatibility** — `outreach.py` does not work with every job site. Sites like LinkedIn require authentication to view job postings and will block the scraper. For best results use direct company careers pages (e.g. `careers.acmecorp.com`) rather than third-party job boards.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install selenium webdriver-manager dnspython requests beautifulsoup4 anthropic ddgs google-genai groq` |
| Chrome crash / backtrace symbols | Run `pip install --upgrade webdriver-manager` |
| `ANTHROPIC_API_KEY not set` | Export the key in your terminal (see Setup step 3) |
| `GROQ_API_KEY not set` | Sign up at [console.groq.com](https://console.groq.com) and export the key |
| Wrong email domain returned | The blocklist in `find_email.py` may need updating — check `BLOCKED_DOMAINS` |
| Google returns aggregator sites | Try a more specific search by adding the company's website domain to the query |
| Selenium / Chrome errors | Install Chromium (`sudo apt install chromium-browser`) — only needed for Google fallback |
| Gemini quota errors (`limit: 0`) | Free tier not available in your region — use Groq instead |
