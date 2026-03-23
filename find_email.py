"""
Email Finder Script
Usage: python find_email.py "John Doe" "Acme Corp"

Searches Google for the company's email format, infers the likely
email address for the given person, then verifies it via SMTP.

Requirements:
    pip install selenium webdriver-manager dnspython
"""

import sys
import re
import time
import socket
import smtplib
import dns.resolver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ── Common email format templates ────────────────────────────────────────────

def generate_candidates(first: str, last: str, domain: str) -> list[tuple[str, str]]:
    """Return (email, format_label) pairs for the most common patterns."""
    f, l = first.lower(), last.lower()
    fi = f[0]          # first initial
    li = l[0]          # last  initial
    return [
        (f"{f}.{l}@{domain}",   "firstname.lastname"),
        (f"{fi}{l}@{domain}",   "flastname"),
        (f"{f}{li}@{domain}",   "firstnamel"),
        (f"{f}@{domain}",       "firstname"),
        (f"{l}@{domain}",       "lastname"),
        (f"{fi}.{l}@{domain}",  "f.lastname"),
        (f"{f}_{l}@{domain}",   "firstname_lastname"),
        (f"{f}{l}@{domain}",    "firstnamelastname"),
        (f"{l}.{f}@{domain}",   "lastname.firstname"),
        (f"{l}{fi}@{domain}",   "lastnamef"),
    ]


# ── Domain extractor ──────────────────────────────────────────────────────────

# Third-party aggregator / generic domains that must never be returned
BLOCKED_DOMAINS = {
    # Email lookup tools
    'rocketreach.co', 'hunter.io', 'apollo.io', 'lusha.com', 'clearbit.com',
    'zoominfo.com', 'snov.io', 'voilanorbert.com', 'findthat.email',
    'anymailfinder.com', 'skrapp.io', 'dropcontact.com', 'leadiq.com',
    'seamless.ai', 'contactout.com', 'emailsherlock.com', 'email-format.com',
    'signalhire.com', 'adapt.io', 'swordfish.ai', 'kendo.ai',
    # Generic mail providers
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com',
    'protonmail.com', 'aol.com', 'mail.com',
    # Search / social / noise
    'google.com', 'bing.com', 'linkedin.com', 'twitter.com', 'x.com',
    'facebook.com', 'instagram.com', 'reddit.com', 'quora.com',
    'youtube.com', 'wikipedia.org', 'example.com', 'w3.org',
}

def _is_blocked(domain: str) -> bool:
    domain = domain.lower()
    return any(domain == b or domain.endswith('.' + b) for b in BLOCKED_DOMAINS)


def extract_domain(text: str, company: str = '') -> str | None:
    """
    Pull the target company's domain from Google snippet text.

    Strategy (in priority order):
      1. Find actual email addresses in the text (@ pattern) — most reliable.
      2. Find bare domains that contain a slug of the company name.
      3. Find any bare domain not on the blocklist.
    """
    # 1. Look for real email addresses → grab their domain
    email_pattern = r'[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})'
    for match in re.finditer(email_pattern, text):
        domain = match.group(1).lower()
        if not _is_blocked(domain):
            return domain

    # 2. Look for domains that contain the company name slug
    if company:
        slug = re.sub(r'[^a-z0-9]', '', company.lower())
        bare_pattern = r'\b([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})\b'
        for match in re.finditer(bare_pattern, text):
            domain = match.group(1).lower()
            domain_slug = re.sub(r'[^a-z0-9]', '', domain.split('.')[0])
            if not _is_blocked(domain) and slug in domain_slug:
                return domain

    # 3. Fallback: first non-blocked bare domain
    bare_pattern = r'\b([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})\b'
    for match in re.finditer(bare_pattern, text):
        domain = match.group(1).lower()
        if not _is_blocked(domain):
            return domain

    return None


# ── Format keyword → template ─────────────────────────────────────────────────

FORMAT_KEYWORDS = {
    r'first(?:name)?[\s._-]?last(?:name)?':   'firstname.lastname',
    r'f[\s._-]?last(?:name)?':                'flastname',
    r'first(?:name)?[\s._-]?l\b':             'firstnamel',
    r'first(?:name)?\b':                      'firstname',
    r'\blast(?:name)?\b':                     'lastname',
    r'f[\s._-]?\.[\s._-]?last(?:name)?':      'f.lastname',
    r'first_last':                             'firstname_lastname',
    r'last[\s._-]?first':                     'lastname.firstname',
    r'last[\s._-]?f\b':                       'lastnamef',
}

def detect_format_from_text(text: str) -> str | None:
    text_lower = text.lower()
    for pattern, fmt in FORMAT_KEYWORDS.items():
        if re.search(pattern, text_lower):
            return fmt
    return None


# ── Selenium search ───────────────────────────────────────────────────────────

def search_google(query: str, headless: bool = False) -> str:
    """Open Chrome, search Google, return the combined snippet text."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    try:
        driver.get('https://www.google.com')
        time.sleep(1)

        # Accept cookie banner if present (EU users)
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[contains(., 'Accept')]")
            accept_btn.click()
            time.sleep(0.5)
        except Exception:
            pass

        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'q'))
        )
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'search'))
        )
        time.sleep(1.5)

        # Grab all visible text from the results section
        results_div = driver.find_element(By.ID, 'search')
        return results_div.text

    finally:
        driver.quit()


# ── SMTP email verifier ───────────────────────────────────────────────────────

SMTP_TIMEOUT = 10          # seconds per connection attempt
FROM_ADDRESS = 'verify@example.com'   # sender used in RCPT probe (never sent)

def _get_mx(domain: str) -> str | None:
    """Return the highest-priority MX hostname for a domain, or None."""
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx = sorted(records, key=lambda r: r.preference)[0]
        return str(mx.exchange).rstrip('.')
    except Exception:
        return None


def verify_email_smtp(email: str) -> dict:
    """
    Verify an email address exists without sending a real message.

    Steps:
      1. MX lookup  — confirms the domain accepts mail at all
      2. SMTP RCPT  — asks the mail server if the mailbox exists

    Returns a dict with keys:
      valid    : bool | None   (None = inconclusive / catch-all)
      reason   : str           (human-readable explanation)
      mx_host  : str | None
    """
    domain = email.split('@')[-1]

    # Step 1: MX lookup
    mx_host = _get_mx(domain)
    if not mx_host:
        return {'valid': False, 'reason': f'No MX record for "{domain}"', 'mx_host': None}

    # Step 2: SMTP RCPT probe
    try:
        with smtplib.SMTP(timeout=SMTP_TIMEOUT) as smtp:
            smtp.connect(mx_host, 25)
            smtp.helo('example.com')
            smtp.mail(FROM_ADDRESS)
            code, message = smtp.rcpt(email)
            msg_str = message.decode(errors='replace')

            if code == 250:
                return {'valid': True,  'reason': 'Mailbox accepted (RCPT 250)', 'mx_host': mx_host}
            elif code == 550:
                return {'valid': False, 'reason': f'Mailbox rejected (RCPT 550): {msg_str}', 'mx_host': mx_host}
            elif code in (451, 452):
                return {'valid': None,  'reason': f'Server temporarily unavailable (RCPT {code})', 'mx_host': mx_host}
            else:
                return {'valid': None,  'reason': f'Inconclusive (RCPT {code}): {msg_str}', 'mx_host': mx_host}

    except smtplib.SMTPConnectError:
        return {'valid': None, 'reason': 'Could not connect on port 25 (may be blocked by your ISP)', 'mx_host': mx_host}
    except smtplib.SMTPServerDisconnected:
        return {'valid': None, 'reason': 'Server disconnected early — likely a catch-all or greylisting', 'mx_host': mx_host}
    except socket.timeout:
        return {'valid': None, 'reason': 'Connection timed out — server may be blocking probes', 'mx_host': mx_host}
    except Exception as e:
        return {'valid': None, 'reason': f'SMTP error: {e}', 'mx_host': mx_host}


def verify_candidates(candidates: list[tuple[str, str]], best_email: str) -> tuple[str, dict]:
    """
    SMTP-verify the best email first, then fall through to alternates
    if the result is definitively invalid.
    Returns (verified_email, smtp_result).
    """
    ordered = [best_email] + [e for e, _ in candidates if e != best_email]

    for email in ordered:
        print(f'  📡  SMTP probing {email} …')
        result = verify_email_smtp(email)
        if result['valid'] is True:
            return email, result          # confirmed — stop here
        elif result['valid'] is False:
            print(f'      ✗  {result["reason"]}')
            continue                      # definitely bad — try next
        else:
            print(f'      ?  {result["reason"]}')
            return email, result          # inconclusive — return with caveat

    return best_email, {'valid': False, 'reason': 'All candidates rejected by mail server', 'mx_host': None}


# ── Main logic ────────────────────────────────────────────────────────────────

def find_email(full_name: str, company: str) -> dict:
    parts = full_name.strip().split()
    if len(parts) < 2:
        raise ValueError("Please provide both first and last name.")
    first, last = parts[0], parts[-1]

    query = f'{company} email format'
    print(f'\n🔍  Searching Google: "{query}"')
    snippet_text = search_google(query)

    print('\n📄  Analysing search results …')

    # 1. Try to find the domain
    domain = extract_domain(snippet_text, company)
    if not domain:
        # Fallback: guess domain from company name
        slug = re.sub(r'[^a-z0-9]', '', company.lower())
        domain = f'{slug}.com'
        print(f'⚠️   Could not detect domain – guessing: {domain}')
    else:
        print(f'✅  Detected domain: {domain}')

    # 2. Try to detect the format
    detected_fmt = detect_format_from_text(snippet_text)

    # 3. Build all candidates and rank them
    candidates = generate_candidates(first, last, domain)
    fmt_map = {label: email for email, label in candidates}

    if detected_fmt and detected_fmt in fmt_map:
        best_email = fmt_map[detected_fmt]
        confidence = 'High'
        print(f'✅  Detected format: {detected_fmt}')
    else:
        best_email = fmt_map['firstname.lastname']
        confidence = 'Medium (defaulted to most common pattern)'
        detected_fmt = 'firstname.lastname'
        print(f'⚠️   Could not detect format – defaulting to most common pattern.')

    # 4. SMTP verification
    print('\n🔬  Verifying email via SMTP …')
    verified_email, smtp_result = verify_candidates(candidates, best_email)

    if smtp_result['valid'] is True:
        smtp_status = '✅ Verified — mailbox exists'
    elif smtp_result['valid'] is False:
        smtp_status = '❌ Invalid — mailbox rejected'
    else:
        smtp_status = '⚠️  Inconclusive — server did not confirm or deny'

    return {
        'name':         full_name,
        'company':      company,
        'domain':       domain,
        'format':       detected_fmt,
        'email':        verified_email,
        'confidence':   confidence,
        'smtp_status':  smtp_status,
        'smtp_reason':  smtp_result['reason'],
        'mx_host':      smtp_result['mx_host'],
        'alternates':   [e for e, _ in candidates if e != verified_email],
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python find_email.py "Full Name" "Company Name"')
        print('Example: python find_email.py "Jane Smith" "Acme Corp"')
        sys.exit(1)

    name    = sys.argv[1]
    company = sys.argv[2]

    result = find_email(name, company)

    print('\n' + '═' * 55)
    print(f'  👤  Name:         {result["name"]}')
    print(f'  🏢  Company:      {result["company"]}')
    print(f'  🌐  Domain:       {result["domain"]}')
    print(f'  📧  Email:        {result["email"]}')
    print(f'  📐  Format:       {result["format"]}')
    print(f'  🎯  Confidence:   {result["confidence"]}')
    print(f'  🔬  SMTP status:  {result["smtp_status"]}')
    print(f'  💬  Detail:       {result["smtp_reason"]}')
    if result["mx_host"]:
        print(f'  📮  MX host:      {result["mx_host"]}')
    print('─' * 55)
    print('  Other likely formats:')
    for alt in result['alternates'][:5]:
        print(f'    • {alt}')
    print('═' * 55)