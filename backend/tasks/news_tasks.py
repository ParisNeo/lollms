# [UPDATE] backend/tasks/news_tasks.py
import datetime
import feedparser
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.db.models.news import RSSFeedSource as DBRSSFeedSource, NewsArticle as DBNewsArticle
from backend.db.models.fun_fact import FunFact as DBFunFact, FunFactCategory as DBFunFactCategory
from backend.session import build_lollms_client_from_params
from backend.task_manager import Task
from backend.settings import settings
from ascii_colors import trace_exception
import json

def _scrape_rss_feeds_task(task: Task):
    task.log("Starting RSS feed scraping task...")
    
    with task.db_session_factory() as db:
        active_feeds = db.query(DBRSSFeedSource).filter(DBRSSFeedSource.is_active == True).all()
        if not active_feeds:
            task.log("No active RSS feeds to process.", "INFO")
            return {"message": "No active RSS feeds."}
        
        task.log(f"Found {len(active_feeds)} active feeds to process.")
        
        existing_urls = {url for url, in db.query(DBNewsArticle.url).all()}
        
        new_articles_count = 0
        new_fun_facts_count = 0
        total_feeds = len(active_feeds)
        
        # Determine if fun fact generation is enabled
        generate_fun_facts = settings.get("rss_generate_fun_facts", False)
        
        lc = None
        if generate_fun_facts:
            try:
                # Use admin user context to build the client for system tasks
                lc = build_lollms_client_from_params(username='admin')
                if not lc.llm:
                    task.log("Could not initialize LLM client for fun fact generation. Disabling for this run.", "WARNING")
                    generate_fun_facts = False
            except Exception as e:
                task.log(f"Error initializing LLM client: {e}. Disabling fun fact generation.", "WARNING")
                generate_fun_facts = False

        for i, feed in enumerate(active_feeds):
            if task.cancellation_event.is_set():
                task.log("Task cancelled.", "WARNING")
                break
            
            task.set_progress(int(100 * (i / total_feeds)))
            task.log(f"Processing feed: {feed.name} ({feed.url})")
            
            try:
                parsed_feed = feedparser.parse(feed.url)
                if parsed_feed.bozo:
                    task.log(f"Warning: Feed '{feed.name}' may be malformed. {parsed_feed.bozo_exception}", "WARNING")

                for entry in parsed_feed.entries:
                    if entry.link in existing_urls:
                        continue
                    
                    content = entry.summary if hasattr(entry, 'summary') else (entry.description if hasattr(entry, 'description') else '')
                    
                    fun_fact_content = ""
                    if generate_fun_facts and lc:
                        try:
                            prompt = f"Extract a single, interesting, and concise fun fact from the following text. The fact should be a complete sentence. If no interesting fact can be found, respond with an empty string.\n\nText:\n---\n{content}\n---\n\nFun Fact:"
                            fun_fact_content = lc.generate_text(prompt, max_new_tokens=150, stream=False)
                        except Exception as e:
                            task.log(f"Failed to generate fun fact for article '{entry.title}': {e}", "ERROR")

                    new_article = DBNewsArticle(
                        source_id=feed.id,
                        title=entry.title,
                        url=entry.link,
                        content=content,
                        fun_fact=fun_fact_content.strip(),
                        publication_date=datetime.datetime(*(entry.published_parsed[:6])) if hasattr(entry, 'published_parsed') and entry.published_parsed else datetime.datetime.now(datetime.timezone.utc)
                    )
                    db.add(new_article)
                    existing_urls.add(entry.link)
                    new_articles_count += 1
                    if fun_fact_content.strip():
                        new_fun_facts_count += 1

                db.commit() # Commit after each feed
            except Exception as e:
                task.log(f"Failed to process feed '{feed.name}': {e}", "ERROR")
                trace_exception(e)
                db.rollback()

        task.set_progress(100)
        
        # Add generated fun facts to the database
        if new_fun_facts_count > 0:
            task.log(f"Adding {new_fun_facts_count} new fun facts to the database...")
            news_category = db.query(DBFunFactCategory).filter(DBFunFactCategory.name == "News").first()
            if not news_category:
                news_category = DBFunFactCategory(name="News", is_active=True, color="#10B981")
                db.add(news_category)
                db.flush()
            
            newly_added_articles = db.query(DBNewsArticle).order_by(desc(DBNewsArticle.id)).limit(new_articles_count).all()
            for article in newly_added_articles:
                if article.fun_fact and article.fun_fact.strip():
                    db.add(DBFunFact(content=article.fun_fact, category_id=news_category.id))
            db.commit()
            task.log("Fun facts from news have been saved.")

    return {"message": f"Scraping complete. Found {new_articles_count} new articles and generated {new_fun_facts_count} fun facts."}


def _cleanup_old_news_articles_task(task: Task):
    """
    Deletes old news articles from the database based on the retention policy.
    """
    task.log("Starting daily news article cleanup task...")
    
    retention_days = settings.get("rss_news_retention_days", 1)
    if not isinstance(retention_days, int) or retention_days <= 0:
        task.log("News article cleanup is disabled (retention days is not a positive integer).", "INFO")
        return {"message": "Cleanup disabled."}
        
    task.log(f"Retention policy: {retention_days} day(s).")
    
    with task.db_session_factory() as db:
        try:
            cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
            
            # First, delete fun facts associated with the news articles to be deleted
            news_category = db.query(DBFunFactCategory).filter(DBFunFactCategory.name == "News").first()
            if news_category:
                articles_to_delete_query = db.query(DBNewsArticle.fun_fact).filter(DBNewsArticle.publication_date < cutoff_date, DBNewsArticle.fun_fact != "")
                fun_facts_to_delete = [ff[0] for ff in articles_to_delete_query.all()]
                
                if fun_facts_to_delete:
                    num_fun_facts_deleted = db.query(DBFunFact).filter(
                        DBFunFact.category_id == news_category.id,
                        DBFunFact.content.in_(fun_facts_to_delete)
                    ).delete(synchronize_session=False)
                    task.log(f"Deleted {num_fun_facts_deleted} associated fun facts from the 'News' category.")

            # Now, delete the old news articles
            num_deleted = db.query(DBNewsArticle).filter(DBNewsArticle.publication_date < cutoff_date).delete(synchronize_session=False)
            db.commit()
            
            task.log(f"Cleanup complete. Deleted {num_deleted} articles older than {cutoff_date.strftime('%Y-%m-%d')}.")
            return {"message": f"Deleted {num_deleted} old articles."}

        except Exception as e:
            task.log(f"An error occurred during news cleanup: {e}", "CRITICAL")
            db.rollback()
            raise