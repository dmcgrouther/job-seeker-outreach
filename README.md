# Job Seeker Outreach Tool

A two-script toolkit that can help find someone's email address and and can generate a personalized outreach email using AI.

---

## Scripts

| File | Description |
|---|---|
| `find_email.py` | Finds and SMTP-verifies a person's work email address |
| `outreach.py` | Scrapes a job page and generates a personalized outreach email via Claude AI |

---

## Setup

### 1. Install dependencies

```bash
pip install selenium webdriver-manager dnspython requests beautifulsoup4 anthropic
```

### 2. Set your Anthropic API key

`outreach.py` uses Claude AI to write the email. You need an API key from [console.anthropic.com](https://console.anthropic.com).

As an example, you could do enter this command when using powershell (just swap in your API key):
```powershell
$env:ANTHROPIC_API_KEY='sk-ant-...'
```

### 3. Edit your background blurb

In `outreach.py`, update the blurb at the top of the file so Claude can personalize the email to you:

```python
MY_BLURB = """
I'm a solutions engineer with a background in sales and software development...
"""
```

### 4. Install Google Chrome

Make sure Google Chrome is installed. The script will automatically download the matching ChromeDriver.

---

## Script 1 — find_email.py

Searches Google for a company's email format, infers the most likely email address for a given person, and verifies it exists via SMTP.

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

1. Opens Chrome and searches Google for `[Company] email format`
2. Scrapes the results to detect the company domain and email pattern
3. Generates a list of candidate email addresses based on common formats
4. Probes the mail server via SMTP to verify which address exists

### SMTP Verification Results

| Status | Meaning |
|---|---|
| Verified | Mailbox confirmed by the mail server |
| Inconclusive | Server could not confirm or deny (catch-all or port blocked) |
| Invalid | Mailbox rejected by the mail server |

---

## Script 2 — outreach.py

Scrapes a job posting page and uses Claude AI to write a concise, personalized outreach email based on the role and your background blurb.

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
3. Sends your background blurb + the job content to Claude AI
4. Claude writes a tailored email under 250 words with a subject line and call to action
5. Prints the email to the terminal and saves it as a `.txt` file

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
- **Site compatibility** — `outreach.py` does not work with every job site. Sites like LinkedIn require authentication to view job postings and will block the scraper. For best results use direct company careers pages (e.g. `careers.acmecorp.com`) rather than third-party job boards.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install selenium webdriver-manager dnspython requests beautifulsoup4 anthropic` |
| Chrome crash / backtrace symbols | Run `pip install --upgrade webdriver-manager` |
| `ANTHROPIC_API_KEY not set` | Export the key in your terminal (see Setup step 2) |
| Wrong email domain returned | The blocklist in `find_email.py` may need updating — check `BLOCKED_DOMAINS` |
| Google returns aggregator sites | Try a more specific search by adding the company's website domain to the query |
