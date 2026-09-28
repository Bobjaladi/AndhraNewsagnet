"""
fetch_telugu_news.py

Fetches RSS news (NTV Telugu, V6 Telugu, 10tv Telugu),
filters for current affairs, and saves headline + short description 
directly to telugunewsoutput.html.

Install once:
    pip install feedparser requests deep-translator
"""

import feedparser
import re
import requests
import time
import html
import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Dict

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

# ==============================================================================
# 🎛️ CONTROL DESCRIPTION LENGTH HERE:
# 30-50  -> SHORT descriptions | 100-150 -> LONG descriptions (45-60 sec audio)
# ==============================================================================
MAX_DESCRIPTION_WORDS = 50
# ==============================================================================

HTML_FILE = "telugunewsoutput.html"

# ===== TEXT CLEANUP & TRUNCATION =====

def clean_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    text = re.sub(r'([.!?])\1{2,}', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def truncate_to_short_description(text: str, max_words: int) -> str:
    if not text:
        return ""
    text = clean_text(text)
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    last_punct = max(truncated.rfind('.'), truncated.rfind('।'), truncated.rfind('?'), truncated.rfind('!'))
    if last_punct > len(truncated) * 0.6:
        return truncated[:last_punct+1].strip()
    return truncated.strip() + "..."

def contains_telugu(text: str) -> bool:
    return bool(re.search(r'[\u0C00-\u0C7F]', text))

def translate_if_needed(text: str, translate_flag: bool) -> str:
    if not translate_flag or not text:
        return text
    if contains_telugu(text):
        return text
    if GoogleTranslator:
        try:
            return GoogleTranslator(source='auto', target='te').translate(text[:4500])
        except Exception:
            pass
    return text

# ===== FILTERING & SCORING =====

def score_article_for_current_affairs(title: str, description: str) -> int:
    text = f"{title} {description}".lower()
    score = 0
    current_affairs_keywords = [
        'ప్రభుత్వం', 'మంత్రి', 'పార్లమెంట్', 'ఎన్నికలు', 'ఆర్థిక', 'బడ్జెట్',
        'అంతర్జాతీయ', 'విదేశీ', 'కోర్టు', 'సుప్రీం', 'ఉద్యోగ', 'విద్య',
        'ఆరోగ్య', 'వైద్య', 'రాజధాని', 'పాలన', 'విధానం', 'నిర్ణయం', 'కేంద్రం', 'రాష్ట్రం',
        'government', 'minister', 'parliament', 'election', 'economy', 'budget',
        'international', 'foreign', 'court', 'supreme', 'job', 'education', 'health'
    ]
    skip_keywords = [
        'horoscope', 'astrology', 'zodiac', 'రాశి', 'జాతక', 'దినఫలం', 'వార ఫలం', 'మాస ఫలం',
        'temple', 'దేవాలయం', 'ఆలయం', 'గుడి', 'devasthanam', 'tirupati', 'స్వామి', 'దర్శనం', 'puja', 'పూజ',
        'promotion', 'ప్రమోషన్', 'ప్రకటన', 'advertisement', 'subscribe', 'follow us', 'మా ఛానల్', 'సబ్స్క్రైబ్',
        'సినిమా', 'సినీ', 'నటుడు', 'నటి', 'హీరో', 'హీరోయిన్', 'క్రికెట్', 'ఐపీఎల్', 'సిరీస్', 'match', 'movie'
    ]
    for kw in skip_keywords:
        if kw in text:
            score -= 20
    for kw in current_affairs_keywords:
        if kw in text:
            score += 15
    return score

# ==============================================================================
# 🚫 IMAGE GENERATION/DOWNLOAD CODE COMMENTED OUT / REMOVED AS REQUESTED
# ==============================================================================

# ===== NEWS RSS AGENT =====

class NewsRSSAgent:
    def __init__(self):
        self.today_date = datetime.now().strftime("%d-%m-%Y")

    def format_date(self, entry: dict) -> str:
        parsed_time = entry.get('published_parsed') or entry.get('updated_parsed')
        if parsed_time:
            try: return time.strftime("%d-%m-%Y", parsed_time)
            except Exception: pass
        raw_date = entry.get('published') or entry.get('pubDate') or ''
        if not raw_date: return self.today_date
        try: return parsedate_to_datetime(raw_date).strftime("%d-%m-%Y")
        except Exception:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', raw_date)
            if match:
                y, m, d = match.group(1).split('-')
                return f"{d}-{m}-{y}"
            return self.today_date

    def fetch_rss_feeds(self, rss_sources: List[dict]) -> List[Dict]:
        all_candidates = []
        print("📰 Starting RSS Feed Aggregation for Current Affairs...")
        print("=" * 60)

        for source in rss_sources:
            url, name = source["url"], source["name"]
            max_articles = source.get("max_articles", 10)
            translate_flag = source.get("translate_to_telugu", False)
            print(f"\n🔄 Fetching from: {name} - Target: {max_articles} articles")

            try:
                headers = {'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'}
                fetch_url = f"{url}{'&' if '?' in url else '?'}_cb={int(time.time())}"
                response = requests.get(fetch_url, headers=headers, timeout=15)
                response.raise_for_status()
                feed = feedparser.parse(response.content)

                if not feed.entries:
                    print(f"⚠️ No entries found for {name}")
                    continue

                for entry in feed.entries[:max_articles]:
                    try:
                        original_link = entry.get('link', '').strip()
                        raw_title = clean_text(entry.get('title', 'No Title'))
                        raw_desc = entry.get('summary') or entry.get('description', '')
                        if not raw_desc or len(clean_text(raw_desc)) < 100:
                            if 'content' in entry and entry['content']:
                                raw_desc = entry['content'][0].get('value', '')

                        description = clean_text(raw_desc)
                        if len(description) < 20:
                            description = "ఈ వార్త గురించి పూర్తి వివరాల కోసం లింక్ క్లిక్ చేయండి."

                        score = score_article_for_current_affairs(raw_title, description)
                        all_candidates.append({
                            'title': raw_title, 'description': description, 'link': original_link,
                            'source': name, 'date': self.format_date(entry), 'score': score, 'translate': translate_flag
                        })
                    except Exception as e:
                        print(f"   ⚠️ Error processing entry: {e}")
                        continue
            except Exception as e:
                print(f"❌ Error fetching {name}: {e}")

        all_candidates.sort(key=lambda x: x['score'], reverse=True)
        top_articles = all_candidates[:10]
        print(f"\n✅ Selected top {len(top_articles)} current affairs articles.")

        final_results = []
        for idx, article in enumerate(top_articles, 1):
            print(f"\n[{idx}] Processing: {article['title'][:50]}...")
            final_title = translate_if_needed(article['title'], article['translate'])
            final_desc = translate_if_needed(article['description'], article['translate'])
            short_desc = truncate_to_short_description(final_desc, max_words=MAX_DESCRIPTION_WORDS)

            final_results.append({
                "headline": final_title,
                "short_description": short_desc,
                "link": article['link'],
                "date": article['date'],
                "source": article['source']
            })
        return final_results

    def save_output_as_html(self, results: List[Dict], filename: str = HTML_FILE):
        parts = [
            "<!DOCTYPE html>",
            "<html lang='te'>",
            "<head>",
            "  <meta charset='utf-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "  <title>Telugu Current Affairs News</title>",
            "  <style>",
            "    body { font-family: 'Nirmala UI', 'Noto Sans Telugu', Gautami, sans-serif; margin: 40px; background-color: #f4f6f8; color: #333; }",
            "    .container { max-width: 800px; margin: 0 auto; background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }",
            "    h1 { text-align: center; color: #2c3e50; margin-bottom: 5px; }",
            "    .date { text-align: center; color: #7f8c8d; margin-bottom: 40px; font-size: 16px; }",
            "    .article { page-break-inside: avoid; margin-bottom: 40px; border-bottom: 1px solid #eee; padding-bottom: 30px; }",
            "    .article:last-child { border-bottom: none; margin-bottom: 0; }",
            "    .article-number { color: #e74c3c; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }",
            "    .headline { font-size: 26px; margin: 10px 0 15px 0; color: #2c3e50; line-height: 1.4; }",
            "    .description { font-size: 18px; line-height: 1.7; color: #34495e; }",
            "    .meta { font-size: 14px; color: #95a5a6; margin-top: 15px; }",
            "    .meta a { color: #3498db; text-decoration: none; font-weight: bold; }",
            "    .meta a:hover { text-decoration: underline; }",
            "    @media print {",
            "      body { background: #fff; margin: 0; }",
            "      .container { box-shadow: none; padding: 20px; max-width: 100%; }",
            "      .article { page-break-after: always; border-bottom: none; }",
            "    }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='container'>",
            "    <h1>తెలుగు ప్రస్తుత వ్యవహారాలు (Current Affairs)</h1>",
            f"    <div class='date'>{datetime.now().strftime('%d-%m-%Y')}</div>"
        ]
        
        for i, a in enumerate(results, 1):
            parts.append(f"    <div class='article'>")
            parts.append(f"      <div class='article-number'>Article {i} &bull; {html.escape(a.get('source', ''))}</div>")
            parts.append(f"      <h2 class='headline'>{html.escape(a.get('headline', ''))}</h2>")
            parts.append(f"      <p class='description'>{html.escape(a.get('short_description', ''))}</p>")
            parts.append(f"      <div class='meta'>📅 {html.escape(a.get('date', ''))} &nbsp;|&nbsp; <a href='{html.escape(a.get('link', ''))}' target='_blank'>Read Full Article →</a></div>")
            parts.append(f"    </div>")
            
        parts.append("  </div>")
        parts.append("</body>")
        parts.append("</html>")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(parts))
        print(f"\n💾 Successfully saved {len(results)} articles to {filename}")

def main():
    agent = NewsRSSAgent()
    rss_sources = [
        {"url": "https://ntvtelugu.com/feed", "name": "NTV Telugu", "max_articles": 8, "translate_to_telugu": False},
        {"url": "https://www.v6velugu.com/feed", "name": "V6 Telugu", "max_articles": 8, "translate_to_telugu": False},
        {"url": "https://10tv.in/feed", "name": "10tv Telugu", "max_articles": 8, "translate_to_telugu": False},
    ]
    results = agent.fetch_rss_feeds(rss_sources)
    if not results:
        print("⚠️ No articles fetched.")
        return
    agent.save_output_as_html(results)

if __name__ == "__main__":
    main()
