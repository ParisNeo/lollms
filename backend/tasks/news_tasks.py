import datetime
import time
from ascii_colors import trace_exception
import feedparser

from backend.db.models.news import RSSFeedSource, NewsArticle
from backend.db.models.user import User as DBUser
from backend.session import build_lollms_client_from_params
from backend.settings import settings
from backend.task_manager import Task

try:
    from scrapemaster import ScrapeMaster
except ImportError:
    ScrapeMaster = None

def _scrape_rss_feeds_task(task: Task):
    """
    The main function for the background task to fetch and process RSS feeds.
    """
    db = task.db_session_factory()
    try:
        if not settings.get("rss_feed_enabled"):
            task.log("RSS feed processing is disabled in settings.", "WARNING")
            return {"status": "disabled"}

        task.log("--- Starting RSS Feed Check ---")
        
        sources = db.query(RSSFeedSource).filter(RSSFeedSource.is_active == True).all()
        if not sources:
            task.log("No active RSS feed sources found.", "INFO")
            return {"status": "no_sources"}
            
        admin_user = db.query(DBUser).filter(DBUser.is_admin == True).order_by(DBUser.id).first()
        if not admin_user:
            task.log("No admin user found to run LLM processing for RSS feeds.", "ERROR")
            raise Exception("Admin user not found.")
        
        if not ScrapeMaster:
            task.log("ScrapeMaster library is not installed. Cannot process RSS feeds.", "ERROR")
            raise ImportError("ScrapeMaster library is not installed.")
            
        lc = build_lollms_client_from_params(username=admin_user.username)

        total_new_articles = 0
        for i, source in enumerate(sources):
            task.log(f"Processing feed: {source.name} ({source.url})")
            feed = feedparser.parse(source.url)
            
            for entry in feed.entries:
                if task.cancellation_event.is_set():
                    task.log("Task cancelled by user.", "WARNING")
                    return {"status": "cancelled"}

                article_url = entry.link
                article_exists = db.query(NewsArticle).filter(NewsArticle.url == article_url).first()
                
                if not article_exists:
                    task.log(f"  - New article found: {entry.title}")
                    try:
                        scraper = ScrapeMaster(article_url)
                        scraped_content = scraper.scrape_markdown()
                        if not scraped_content or len(scraped_content) < 100:
                            task.log(f"    - Scraping failed or content too short for {article_url}", "WARNING")
                            continue
                        
                        reformat_prompt = f"Reformat the following article into a well-structured news entry, using markdown for formatting. Keep the key information and make it easy to read:\n\n{scraped_content}"
                        reformatted_content = lc.generate_text(reformat_prompt, max_new_tokens=2048)

                        fun_fact_prompt = f"Based on the following article, generate a single, short, interesting 'fun fact' style summary. The fact must be a single sentence.\n\nArticle:\n{scraped_content}"
                        fun_fact_content = lc.generate_text(fun_fact_prompt, max_new_tokens=100).strip()

                        pub_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))

                        new_article = NewsArticle(
                            source_id=source.id,
                            title=entry.title,
                            url=article_url,
                            content=reformatted_content,
                            fun_fact=fun_fact_content,
                            publication_date=pub_date,
                        )
                        db.add(new_article)
                        db.commit()
                        total_new_articles += 1
                        task.log(f"    - Processed and saved: {entry.title}")

                    except Exception as e:
                        task.log(f"    - ERROR processing article {entry.title}: {e}", "ERROR")
                        trace_exception(e)
                        db.rollback()
            
            task.set_progress(int(100 * (i + 1) / len(sources)))

        task.log("--- RSS Feed Check Finished ---")
        return {"status": "success", "new_articles_found": total_new_articles}
    except Exception as e:
        task.log(f"CRITICAL ERROR in RSS feed processing task: {e}", "CRITICAL")
        trace_exception(e)
        raise e
    finally:
        db.close()