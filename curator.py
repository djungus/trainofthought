import json
import os
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
import email.utils

# =====================================================================
# Utilities
# =====================================================================

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def parse_date(date_str):
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except Exception:
        pass
    
    try:
        cleaned_str = date_str.strip()
        if cleaned_str.endswith('Z'):
            cleaned_str = cleaned_str[:-1] + '+00:00'
        return datetime.fromisoformat(cleaned_str)
    except Exception:
        pass
    
    return datetime.now(timezone.utc)

def fetch_feed(url):
    log(f"Fetching: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/xml, text/xml, */*'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read()
    except Exception as e:
        log(f"Error fetching {url}: {e}")
        return None

def parse_feed_xml(xml_content, source_name):
    if not xml_content:
        return []
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        log(f"XML parse error for {source_name}: {e}")
        return []

    items = []
    
    # Check if standard RSS
    for channel in root.findall('channel'):
        for item in channel.findall('item'):
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            desc = item.findtext('description', '').strip()
            pub_date_str = item.findtext('pubDate', '').strip()
            
            items.append({
                'source': source_name,
                'title': title,
                'link': link,
                'description': html.unescape(desc),
                'pub_date': parse_date(pub_date_str)
            })

    # Check if Atom feed
    if not items:
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        if not entries:
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')
        if not entries:
            entries = root.findall('.//entry')

        for entry in entries:
            title_node = entry.find('{http://www.w3.org/2005/Atom}title') or entry.find('title')
            title = title_node.text.strip() if title_node is not None and title_node.text else ''

            link_node = entry.find('{http://www.w3.org/2005/Atom}link') or entry.find('link')
            link = ''
            if link_node is not None:
                link = link_node.get('href', '').strip() or link_node.text.strip() if link_node.text else ''

            summary_node = (entry.find('{http://www.w3.org/2005/Atom}summary') or 
                            entry.find('summary') or 
                            entry.find('{http://www.w3.org/2005/Atom}content') or 
                            entry.find('content'))
            desc = summary_node.text.strip() if summary_node is not None and summary_node.text else ''

            pub_node = (entry.find('{http://www.w3.org/2005/Atom}published') or 
                        entry.find('published') or 
                        entry.find('{http://www.w3.org/2005/Atom}updated') or 
                        entry.find('updated'))
            pub_date_str = pub_node.text.strip() if pub_node is not None and pub_node.text else ''

            items.append({
                'source': source_name,
                'title': title,
                'link': link,
                'description': html.unescape(desc) if desc else '',
                'pub_date': parse_date(pub_date_str)
            })
            
    return items

def filter_recent(items, days=4.5):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [item for item in items if item['pub_date'] >= cutoff]

# =====================================================================
# Dealforager & Sidequest Dynamic Fetchers
# =====================================================================

def fetch_dealforager_deals(interests, weights, exclude_kw, limit=6):
    log("Querying Dealforager API for custom deals...")
    deals = []
    seen_asins = set()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.dealforager.com/'
    }
    
    # We query Dealforager for interests that correspond to product searches
    deal_keywords = ["skincare", "volleyball", "rock climbing", "pokemon", "boston celtics", "electronics", "software"]
    
    for kw in deal_keywords:
        weight = weights.get(kw, 1.0)
        
        search_term = kw
        if kw == "boston celtics":
            search_term = "celtics"
        elif kw == "rock climbing":
            search_term = "climbing"
            
        url = f"https://www.dealforager.com/api/products?search={urllib.parse.quote(search_term)}&sort=0"
        log(f"Fetching Dealforager for '{search_term}' (weight: {weight:.1f})")
        
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                items = json.loads(response.read().decode('utf-8'))
                for item in items:
                    asin = item.get('asin')
                    if not asin or asin in seen_asins:
                        continue
                        
                    title = item.get('title', '')
                    
                    # Apply keyword exclusions
                    title_lower = title.lower()
                    excluded = False
                    for ex in exclude_kw:
                        if ex.lower() in title_lower:
                            excluded = True
                            break
                    if excluded:
                        continue
                        
                    dealscore = item.get('dealscore', 0)
                    savings = (item.get('savingspercent', 0)) / 100.0
                    
                    # Compute custom weighted score to prioritize preferred categories
                    score = dealscore * weight
                    
                    deals.append({
                        'asin': asin,
                        'title': title,
                        'newprice': item.get('newprice', 0),
                        'usedprice': item.get('usedprice', 0),
                        'savingspercent': savings,
                        'dealscore': dealscore,
                        'source': 'Dealforager',
                        'category': kw,
                        'score': score,
                        'link': f"https://www.amazon.com/dp/{asin}?tag=dealforager-20"
                    })
                    seen_asins.add(asin)
        except Exception as e:
            log(f"Error querying Dealforager API for '{search_term}': {e}")
            
    # Sort deals by our weighted score
    deals.sort(key=lambda x: x['score'], reverse=True)
    return deals[:limit]

def fetch_sidequest_leads(query):
    log(f"Fetching Sidequest search hits for query: '{query}'")
    leads = []
    
    # 1. Fetch Google News RSS for this query
    gn_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    gn_xml = fetch_feed(gn_url)
    gn_items = parse_feed_xml(gn_xml, "Google News")
    recent_gn = filter_recent(gn_items, days=7)
    leads.extend(recent_gn[:4])
    
    # 2. Fetch Reddit Search RSS for this query
    reddit_url = f"https://www.reddit.com/search.rss?q={urllib.parse.quote(query)}&sort=new"
    reddit_xml = fetch_feed(reddit_url)
    reddit_items = parse_feed_xml(reddit_xml, "Reddit Search")
    recent_reddit = filter_recent(reddit_items, days=7)
    leads.extend(recent_reddit[:4])
    
    return leads

# =====================================================================
# Content Aggregator
# =====================================================================

def process_sources(config):
    curated_data = {
        "discovery_candidates": [],
        "local_news": [],
        "medicine": [],
        "tech_finance": [],
        "deals": [],
        "sidequest_leads": []
    }
    
    # Weights and profile configuration
    user_conf = config.get("user", {})
    interests = user_conf.get("noted_interests", [])
    weights = user_conf.get("weights", {}).get("interests", {})
    exclude_kw = config["filters"]["exclude_keywords"]
    
    # 1. Fetch Suggested Reading discovery candidates (AC10, Paul Graham, Google News Book releases)
    for source in config["sources"].get("discovery_newsletters", []):
        xml = fetch_feed(source["url"])
        items = parse_feed_xml(xml, source["name"])
        recent = filter_recent(items, days=7)
        curated_data["discovery_candidates"].extend(recent)
        
    for source in config["sources"].get("discovery_books", []):
        xml = fetch_feed(source["url"])
        items = parse_feed_xml(xml, source["name"])
        recent = filter_recent(items, days=7)
        curated_data["discovery_candidates"].extend(recent)

    # 2. Fetch Local News
    for source in config["sources"].get("local_news", []):
        xml = fetch_feed(source["url"])
        items = parse_feed_xml(xml, source["name"])
        recent = filter_recent(items, days=4)
        curated_data["local_news"].extend(recent[:3])
        
    # 3. Fetch Medicine News
    for source in config["sources"].get("medicine", []):
        xml = fetch_feed(source["url"])
        items = parse_feed_xml(xml, source["name"])
        recent = filter_recent(items, days=6)
        curated_data["medicine"].extend(recent[:3])
        
    # 4. Fetch Tech & Finance News
    for source in config["sources"].get("tech_finance", []):
        xml = fetch_feed(source["url"])
        items = parse_feed_xml(xml, source["name"])
        recent = filter_recent(items, days=4)
        curated_data["tech_finance"].extend(recent[:3])

    # 5. Fetch Custom Dealforager Deals
    df_deals = fetch_dealforager_deals(interests, weights, exclude_kw, limit=6)
    curated_data["deals"].extend(df_deals)
    
    # 6. Fetch Fallback Deals (RSS) if needed
    if len(curated_data["deals"]) < 3:
        log("Insufficient Dealforager deals. Fetching fallback RSS deals...")
        fallback_deals = []
        for source in config["sources"].get("fallback_deals", []):
            xml = fetch_feed(source["url"])
            items = parse_feed_xml(xml, source["name"])
            fallback_deals.extend(items)
        
        seen_links = set()
        for deal in fallback_deals:
            if deal['link'] in seen_links:
                continue
            title_lower = deal['title'].lower()
            if any(ex.lower() in title_lower for ex in exclude_kw):
                continue
            if any(inc.lower() in title_lower for inc in config["filters"]["deal_keywords"]):
                curated_data["deals"].append({
                    'asin': '',
                    'title': deal['title'],
                    'newprice': 0,
                    'usedprice': 0,
                    'savingspercent': 0,
                    'dealscore': 0,
                    'source': deal['source'],
                    'category': 'general',
                    'score': 1.0,
                    'link': deal['link']
                })
                seen_links.add(deal['link'])
                if len(curated_data["deals"]) >= 6:
                    break

    # 7. Sidequest leads (if active)
    sidequest_conf = config.get("sidequest", {})
    if sidequest_conf.get("enabled") and sidequest_conf.get("query"):
        leads = fetch_sidequest_leads(sidequest_conf["query"])
        curated_data["sidequest_leads"].extend(leads)

    return curated_data

# =====================================================================
# AI Curation (Gemini API)
# =====================================================================

def call_gemini(prompt, api_key):
    if not api_key:
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode("utf-8"), 
        headers=headers, 
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log(f"Gemini API call failed: {e}")
        return None

def parse_json_from_gemini(text):
    if not text:
        return []
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except Exception as e:
        log(f"Failed to parse JSON from Gemini: {e}")
        return []

def run_ai_curation(curated_data, config, api_key):
    user_profile = config.get("user", {})
    liked_authors = user_profile.get("liked_authors", [])
    interests = user_profile.get("noted_interests", [])
    weights = user_conf_weights = user_profile.get("weights", {})
    
    # 1. Warm Greeting Curation
    greeting_prompt = f"""
    You are a professional personal assistant curating a biweekly newsletter for a Boston native who is currently a pre-med junior at Cornell University.
    Their interests include: {', '.join(interests)}.
    Write a warm, personalized greeting paragraph (3-4 sentences max) referencing Cornell, studies, Boston, or physical books. Keep it premium, engaging, and friendly.
    """
    greeting = None
    if api_key:
        greeting = call_gemini(greeting_prompt, api_key)
    if not greeting:
        greeting = "Good morning! Welcome to your twice-weekly TrainOfThought. We've compiled the latest updates in medicine, local Boston/Ithaca news, tech developments, and custom hobby deals."
    else:
        greeting = greeting.strip()
        
    # 2. Suggested Reading AI Curation
    recommendations = []
    if api_key and curated_data["discovery_candidates"]:
        # Prepare candidate list for prompt
        candidates_list = []
        for i, item in enumerate(curated_data["discovery_candidates"]):
            candidates_list.append({
                "index": i,
                "title": item["title"],
                "source": item["source"],
                "link": item["link"]
            })
            
        rec_prompt = f"""
        You are a highly intellectual personal curator. The user has requested a discovery reading list.
        They ALREADY receive newsletters from their subscribed authors: {', '.join(liked_authors)}.
        DO NOT recommend articles published directly by these authors. Instead, select exactly 3 articles from the candidate list below that are SIMILARLY themed in tone, writing style, or subject matter to these authors, matching the user's interests:
        
        User Interests (with current preference weights):
        {json.dumps(weights.get("interests", {}))}
        
        Candidate Articles:
        {json.dumps(candidates_list[:40])}
        
        For each of the 3 articles you select:
        - Determine which interest or author style it maps to.
        - Provide a 1-sentence personalized recommendation reason (e.g. 'If you like Henrik Karlsson's essays on education, you will find this deep-dive on learning frameworks fascinating.').
        - Categorize it as feedback_type "interest" or "author", and feedback_target (matching the interest keyword or the liked author's name).
        
        Output your response ONLY as a raw JSON array of objects, and DO NOT wrap it in markdown code blocks. The JSON format must look exactly like this:
        [
          {{
            "title": "Selected Article Title",
            "url": "https://example.com/link",
            "source": "Source Name",
            "reason": "1-sentence personalized reason matching their liked authors/interests.",
            "feedback_type": "interest" or "author",
            "feedback_target": "name of interest or liked author"
          }},
          ...
        ]
        """
        rec_text = call_gemini(rec_prompt, api_key)
        recommendations = parse_json_from_gemini(rec_text)
        
    # Fallback Suggested Reading
    if not recommendations:
        log("Curation recommendations fallback triggered.")
        # Pick top 3 from candidates
        candidates = curated_data["discovery_candidates"][:3]
        for c in candidates:
            # Map randomly or to generic interest
            recommendations.append({
                "title": c["title"],
                "url": c["link"],
                "source": c["source"],
                "reason": "Recommended based on your discovery feed matches.",
                "feedback_type": "interest",
                "feedback_target": "physical books"
            })
            
    # 3. Sidequest Curation (if enabled)
    sidequest_summary = ""
    sidequest_conf = config.get("sidequest", {})
    if sidequest_conf.get("enabled") and sidequest_conf.get("query"):
        query = sidequest_conf["query"]
        desc = sidequest_conf.get("description", "")
        leads = curated_data["sidequest_leads"]
        
        if api_key and leads:
            leads_list = [{"title": l["title"], "source": l["source"], "link": l["link"]} for l in leads]
            sq_prompt = f"""
            The user is currently running a custom "Sidequest": "{query}" ({desc}).
            We performed web searches and found the following hits:
            {json.dumps(leads_list[:8])}
            
            Summarize the most relevant details, leads, or resale alerts from these matches into 2-3 concrete bullet points. Keep it brief.
            If none of these links contain concrete ticket sales or leads, generate a polite note stating we are still monitoring for listings.
            DO NOT wrap your response in markdown code blocks.
            """
            sq_summary_text = call_gemini(sq_prompt, api_key)
            if sq_summary_text:
                sidequest_summary = sq_summary_text.strip()
        
        if not sidequest_summary:
            sidequest_summary = f"No new active alerts or ticket postings for '{query}' found this week. Curation engine is still monitoring Google News and Reddit searches."
            
    return greeting, recommendations, sidequest_summary

# =====================================================================
# Email Generation & Sending
# =====================================================================

def build_feedback_urls(config, title, f_type, f_target):
    user_conf = config.get("user", {})
    gh_user = user_conf.get("github_username", "username")
    gh_repo = user_conf.get("github_repo", "trainofthought")
    
    base_url = f"https://{gh_user}.github.io/{gh_repo}/feedback.html"
    
    params_yes = {
        "item": title,
        "type": f_type,
        "target": f_target,
        "feedback": "yes",
        "owner": gh_user,
        "repo": gh_repo
    }
    params_no = {
        "item": title,
        "type": f_type,
        "target": f_target,
        "feedback": "no",
        "owner": gh_user,
        "repo": gh_repo
    }
    
    yes_url = f"{base_url}?{urllib.parse.urlencode(params_yes)}"
    no_url = f"{base_url}?{urllib.parse.urlencode(params_no)}"
    
    return yes_url, no_url

def build_html_email(config, greeting, recommendations, sidequest_summary, data):
    # Load template
    template_path = os.path.join(os.path.dirname(__file__), "template.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        template = "<html><body><h1>TrainOfThought</h1><p>{greeting}</p></body></html>"

    today_str = datetime.now().strftime("%B %d, %Y")
    
    # 1. Format Sidequest Section
    sidequest_html = ""
    sidequest_conf = config.get("sidequest", {})
    if sidequest_conf.get("enabled") and sidequest_conf.get("query"):
        # Format sidequest summary as bullets
        summary_bullets = ""
        for line in sidequest_summary.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Remove existing list markers
            if line.startswith('*') or line.startswith('-') or line.startswith('•'):
                line = line[1:].strip()
            summary_bullets += f"<li>{line}</li>"
            
        sidequest_html = f"""
        <div class="sidequest-card">
            <div class="sidequest-header">
                <span class="sidequest-icon">🎯</span>
                <span class="sidequest-title">Active Sidequest</span>
            </div>
            <div class="sidequest-query">{sidequest_conf['query']}</div>
            <ul class="sidequest-leads">
                {summary_bullets}
            </ul>
        </div>
        """

    # 2. Format Suggested Reading Section (AI Curated)
    nl_html = ""
    if recommendations:
        for item in recommendations:
            yes_url, no_url = build_feedback_urls(config, item['title'], item['feedback_type'], item['feedback_target'])
            nl_html += f"""
            <div class="article">
                <span class="tag tag-read">{item.get('source', 'Discovery')}</span>
                <h3><a href="{item['url']}">{item['title']}</a></h3>
                <p>{item['reason']}</p>
                <div class="article-meta">
                    <span>Feedback:</span>
                    <div class="feedback-container">
                        <a href="{yes_url}" class="feedback-btn" target="_blank">👍 Yes</a>
                        <a href="{no_url}" class="feedback-btn" target="_blank">👎 No</a>
                    </div>
                </div>
            </div>
            """
    else:
        nl_html = "<p class='empty-state'>No new reading suggestions this week.</p>"

    # 3. Format Local News Section
    local_html = ""
    if data["local_news"]:
        for item in data["local_news"]:
            desc = item['description'][:140] + "..." if len(item['description']) > 140 else item['description']
            local_html += f"""
            <div class="article">
                <span class="tag tag-local">{item['source']}</span>
                <h3><a href="{item['link']}">{item['title']}</a></h3>
                <p>{desc}</p>
                <span class="article-meta">{item['pub_date'].strftime('%b %d')}</span>
            </div>
            """
    else:
        local_html = "<p class='empty-state'>No new local news found.</p>"

    # 4. Format Medicine Section
    med_html = ""
    if data["medicine"]:
        for item in data["medicine"]:
            med_html += f"""
            <div class="article">
                <span class="tag tag-medicine">{item['source']}</span>
                <h3><a href="{item['link']}">{item['title']}</a></h3>
                <span class="article-meta">{item['pub_date'].strftime('%b %d')}</span>
            </div>
            """
    else:
        med_html = "<p class='empty-state'>No new medical papers published recently.</p>"

    # 5. Format Tech & Finance Section
    tech_html = ""
    if data["tech_finance"]:
        for item in data["tech_finance"]:
            tech_html += f"""
            <div class="article">
                <span class="tag tag-tech">{item['source']}</span>
                <h3><a href="{item['link']}">{item['title']}</a></h3>
                <span class="article-meta">{item['pub_date'].strftime('%b %d')}</span>
            </div>
            """
    else:
        tech_html = "<p class='empty-state'>No major tech or finance news.</p>"

    # 6. Format Deals Section
    deals_html = ""
    if data["deals"]:
        for item in data["deals"]:
            yes_url, no_url = build_feedback_urls(config, item['title'], "interest", item['category'])
            
            # Format price and badge
            price_str = ""
            if item['usedprice'] > 0:
                price_str += f'<span class="price-used">Used: ${item["usedprice"]/100:.2f}</span>'
            if item['newprice'] > 0:
                price_str += f'<span class="price-new">New: ${item["newprice"]/100:.2f}</span>'
                
            badge_str = ""
            if item['savingspercent'] > 0:
                badge_str = f'<span class="deal-badge">{item["savingspercent"]*100:.0f}% OFF</span>'
                
            deals_html += f"""
            <div class="deal-item">
                <div class="deal-header">
                    <span class="deal-title"><a href="{item['link']}">{item['title'][:70]}...</a></span>
                    {badge_str}
                </div>
                <div class="deal-prices">
                    {price_str} | <span style="font-size: 10px; color:#64748b;">Category: {item['category']}</span>
                </div>
                <div class="feedback-container">
                    <span>Feedback:</span>
                    <a href="{yes_url}" class="feedback-btn" target="_blank">👍 Yes</a>
                    <a href="{no_url}" class="feedback-btn" target="_blank">👎 No</a>
                </div>
            </div>
            """
    else:
        deals_html = "<p class='empty-state'>No curated deals matching your keywords today.</p>"

    # Substitute tags
    html_content = template
    html_content = html_content.replace("{{ date }}", today_str)
    html_content = html_content.replace("{{ greeting }}", greeting.replace("\n", "<br>"))
    html_content = html_content.replace("{{ sidequest_section }}", sidequest_html)
    html_content = html_content.replace("{{ newsletters_section }}", nl_html)
    html_content = html_content.replace("{{ local_news_section }}", local_html)
    html_content = html_content.replace("{{ medicine_section }}", med_html)
    html_content = html_content.replace("{{ tech_finance_section }}", tech_html)
    html_content = html_content.replace("{{ deals_section }}", deals_html)

    return html_content

def send_email(html_content, to_email):
    subject = f"📬 TrainOfThought — {datetime.now().strftime('%b %d, %Y')}"
    
    # 1. Try Resend if API key is present
    resend_api_key = os.environ.get("RESEND_API_KEY")
    if resend_api_key:
        log("Attempting to send email via Resend API...")
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": "TrainOfThought <digest@trainofthought.app>" if "trainofthought.app" in os.environ.get("RESEND_DOMAIN", "") else "onboarding@resend.dev",
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as r:
                res = json.loads(r.read().decode("utf-8"))
                log(f"Email sent via Resend. ID: {res.get('id')}")
                return True
        except Exception as e:
            log(f"Resend dispatch failed: {e}")
            
    # 2. Try SMTP if variables are present
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT", "465")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    
    if smtp_server and smtp_user and smtp_pass:
        log("Attempting to send email via SMTP...")
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg.attach(MIMEText(html_content, 'html'))
        
        try:
            with smtplib.SMTP_SSL(smtp_server, int(smtp_port)) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, to_email, msg.as_string())
            log("Email sent successfully via SMTP.")
            return True
        except Exception as e:
            log(f"SMTP dispatch failed: {e}")
            
    log("Email sending skipped. (Set RESEND_API_KEY or SMTP_SERVER variables to dispatch emails).")
    return False

# =====================================================================
# Main Pipeline Executable
# =====================================================================

def main():
    log("TrainOfThought Curation Engine Starting...")
    
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        log(f"Config file not found at {config_path}")
        sys.exit(1)
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    # Get aggregated data
    curated_data = process_sources(config)
    
    # AI personalization & Suggested Reading
    gemini_key = os.environ.get("GEMINI_API_KEY")
    greeting, recommendations, sidequest_summary = run_ai_curation(curated_data, config, gemini_key)
    
    # Compile HTML
    html_content = build_html_email(config, greeting, recommendations, sidequest_summary, curated_data)
    
    # Write output file for local review/dry run
    output_path = os.path.join(os.path.dirname(__file__), "digest_preview.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    log(f"Dry run preview compiled to {output_path}")
    
    # Send email
    to_email = config["user"]["email"]
    send_email(html_content, to_email)
    
    log("TrainOfThought Run Complete!")

if __name__ == "__main__":
    main()
