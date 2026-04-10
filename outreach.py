#!/usr/bin/env python3
"""
Recruiter Outreach Automation
------------------------------
Scrapes a company/job page URL, then uses your personal blurb below
and Claude AI to generate a personalized letter of interest.

Usage:
    python outreach.py "job_url"

Example:
    python outreach.py "https://careers.example.com/job/123"
"""

import sys
import os
import time
import argparse
from datetime import datetime
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
from logger import setup_logging
log = setup_logging(__name__)

# ─────────────────────────────────────────────
# ✏️  YOUR BACKGROUND BLURB — Edit this!
# ─────────────────────────────────────────────

MY_BLURB = """
I'm a solutions engineer with a background in sales and software development. I have worked directly with clients and have direct coding experience.
"""

# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 1. Web Scraper
# ─────────────────────────────────────────────

def scrape_job_page(url: str) -> dict:
    """
    Fetch and parse a job/company page.
    Returns a dict with 'title', 'company', 'url', and 'content'.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log.error("Required libraries missing.")
        log.error("        Install them with: pip install requests beautifulsoup4")
        sys.exit(1)

    print(f"\n[→] Fetching job page: {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error("Could not fetch the page: %s", e)
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
        tag.decompose()

    # Extract page title
    page_title = soup.title.string.strip() if soup.title else "Unknown Position"

    # Try to detect company name from meta tags or OG tags
    company = "the company"
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        company = og_site["content"].strip()
    else:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        company = domain.replace("www.", "").split(".")[0].capitalize()

    # Extract main body text (limit to ~4000 chars to stay within API context)
    body_text = soup.get_text(separator="\n", strip=True)
    lines = [line for line in body_text.splitlines() if len(line.strip()) > 30]
    content = "\n".join(lines)[:4000]

    print(f"[✓] Page loaded — Title: '{page_title}' | Company: '{company}'")

    return {
        "title": page_title,
        "company": company,
        "url": url,
        "content": content,
    }


# ─────────────────────────────────────────────
# 2. Email Generator (Claude API)
# ─────────────────────────────────────────────

def build_prompt(job_info: dict, blurb: str) -> str:
    """Build the shared prompt for any AI engine."""
    return f"""You are an expert career coach helping a job seeker write a compelling,
personalized letter of interest / cold outreach email to a recruiter or hiring manager.

Here is the job posting / company page the candidate is applying to:
---
URL: {job_info['url']}
Page Title: {job_info['title']}
Company: {job_info['company']}

Page Content:
{job_info['content']}
---

Here is a short background blurb from the candidate:
---
{blurb.strip()}
---

Write a professional, warm, and concise outreach email that:
1. Opens with a strong hook referencing the specific company or role
2. Highlights 2–3 of the candidate's most relevant strengths from their blurb
3. Shows genuine interest in the company's mission or work
4. Ends with a clear, low-pressure call to action (e.g., a brief chat)
5. Stays under 500 characters total — extremely concise, every word counts
Format:
Subject: [subject line]

[email body]
"""


def call_claude(prompt: str) -> str:
    """Call Claude API and return the response text."""
    try:
        import anthropic
    except ImportError:
        log.error("anthropic SDK not found.")
        log.error("        Install it with: pip install anthropic")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY environment variable is not set.")
        log.error("        Export it with: export ANTHROPIC_API_KEY='sk-ant-...'")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def call_gemini(prompt: str) -> str:
    """Call Gemini API and return the response text."""
    try:
        from google import genai
        from google.genai import errors
    except ImportError:
        log.error("google-genai SDK not found.")
        log.error("        Install it with: pip install google-genai")
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
       log.error("GEMINI_API_KEY environment variable is not set.")
       log.error("        Export it with: export GEMINI_API_KEY='...'")
       return None

    client = genai.Client(api_key=api_key)
    """Generates content with exponential backoff to handle 429 errors."""
    max_retries = 1
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text
        except errors.ClientError as e:
            # Check if it's a Rate Limit (429) error
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                # Calculate wait time: 2^attempt
                wait_time = (2 ** attempt)
                log.warning("Rate limit hit (Attempt %d/%d). Waiting %.2f seconds...",
                            attempt + 1, max_retries, wait_time)
                time.sleep(wait_time)
            else:
                # If it's a different error (like 400 Bad Request), return immediately
                log.error("A non-rate-limit error occurred: %s", e)
                return None
    log.error("Max retries exceeded. The API might be down or your daily quota is empty.")
    return None


def call_groq(prompt: str) -> str:
    """Call Groq API and return the response text."""
    try:
        from groq import Groq
    except ImportError:
        log.error("groq SDK not found.")
        log.error("        Install it with: pip install groq")
        return none

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        log.error("GROQ_API_KEY environment variable is not set.")
        log.error("        Export it with: export GROQ_API_KEY='...'")
        return none

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )
    return response.choices[0].message.content


# Ordered list of AI engines for text generation
_AI_ENGINES = [
    ('Claude',  call_claude),
    ('Gemini',  call_gemini),
    ('Groq',   call_groq),
]


def generate_email(job_info: dict, blurb: str) -> str:
    """Generate a letter of interest using the specified AI engine."""
    prompt = build_prompt(job_info, blurb)
    """ Try each engine in order, returning the first successful result. """
    for label, fn in _AI_ENGINES:
        log.info('Trying %s', label)
        try:
            result = fn(prompt)
            if result:
                log.info('Generated personalized email with %s', label)
                return result
        except Exception as e:
            log.warning('%s failed: %s', label, e)

    log.error('All AI engines exhausted')
    sys.exit(1)


# ─────────────────────────────────────────────
# 3. Output Handler
# ─────────────────────────────────────────────

def save_and_print(email_text: str, job_info: dict, output_path: str = None):
    """Print the email to terminal and save to a .txt file."""

    print("\n" + "═" * 60)
    print("  GENERATED EMAIL")
    print("═" * 60)
    print(email_text)
    print("═" * 60)

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company = "".join(c if c.isalnum() else "_" for c in job_info["company"])
        script_dir = Path(__file__).parent
        output_path = script_dir / f"outreach_{safe_company}_{timestamp}.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Job URL:   {job_info['url']}\n")
        f.write(f"Company:   {job_info['company']}\n")
        f.write("─" * 60 + "\n\n")
        f.write(email_text)

    print(f"\n[✓] Email saved to: {output_path}")


# ─────────────────────────────────────────────
# 4. Main Entry Point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a personalized recruiter outreach email from a job URL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "url",
        help="The job posting or company careers page URL",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path for the generated email (default: auto-named .txt file)",
    )

    args = parser.parse_args()

    # Step 1: Scrape job page
    job_info = scrape_job_page(args.url)

    # Step 2: Generate email
    email_text = generate_email(job_info, MY_BLURB)

    # Step 3: Output
    save_and_print(email_text, job_info, args.output)


if __name__ == "__main__":
    main()