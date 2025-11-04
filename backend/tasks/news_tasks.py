import datetime
import time
from ascii_colors import trace_exception
import feedparser

from backend.db.models.news import RSSFeedSource, NewsArticle
from backend.db.models.user import User as DBUser
from backend.session import build_lollms_client_from_params
from backend.settings import settings
from backend.task_manager import Task



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
            
        bot_user = db.query(DBUser).filter(DBUser.username == "lollms").first()
        if not bot_user:
            task.log("ERROR: The @lollms system user was not found. Cannot process RSS feeds.", "ERROR")
            raise Exception("@lollms user not found.")
        
        if not bot_user.lollms_model_name:
            task.log("ERROR: The @lollms user has no model configured in the AI Bot settings.", "ERROR")
            raise Exception("AI Bot model not configured.")
            
        lc = build_lollms_client_from_params(username=bot_user.username)

        total_new_articles = 0
        num_sources = len(sources)
        for i, source in enumerate(sources):
            task.set_description(f"Processing feed {i+1}/{num_sources}: {source.name}")
            task.log(f"Processing feed: {source.name} ({source.url})")
            feed = feedparser.parse(source.url)
            num_entries = len(feed.entries)
            
            if num_entries == 0:
                task.log(f"  - No entries found in feed.")
                # Update progress to reflect this source is "done"
                task.set_progress(int(100 * (i + 1) / num_sources))
                continue

            for j, entry in enumerate(feed.entries):
                if task.cancellation_event.is_set():
                    task.log("Task cancelled by user.", "WARNING")
                    return {"status": "cancelled"}

                article_url = entry.link
                article_exists = db.query(NewsArticle).filter(NewsArticle.url == article_url).first()
                
                if not article_exists:
                    task.set_description(f"Article {j+1}/{num_entries}: {entry.title[:40]}...")
                    task.log(f"  - New article found: {entry.title}")
                    try:
                        # Fallback to RSS summary
                        pub_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        
                        scraped_content = entry.summary
                        if not scraped_content or len(scraped_content) < 100:
                            task.log(f"    - Scraping failed and RSS summary is too short for {article_url}", "WARNING")
                        else:
                            fun_fact_prompt = f"Based on the following article, generate a single, short, interesting 'fun fact' style summary. The fact must be a single sentence.\n\nArticle:\n{scraped_content}"
                            fun_fact_content = lc.generate_text(fun_fact_prompt, max_new_tokens=100).strip()

                            new_article = NewsArticle(
                                source_id=source.id,
                                title=entry.title,
                                url=article_url,
                                content=scraped_content, # Using summary as content
                                fun_fact=fun_fact_content,
                                publication_date=pub_date,
                            )
                            db.add(new_article)
                            db.commit()
                            total_new_articles += 1
                            task.log(f"    - Processed and saved using RSS summary: {entry.title}")                            

                    except Exception as e:
                        task.log(f"    - ERROR processing article {entry.title}: {e}", "ERROR")
                        trace_exception(e)
                        db.rollback()
                
                # Calculate and set progress after each entry (new or existing)
                base_progress = (i / num_sources) * 100
                source_chunk_progress = 100 / num_sources
                entry_progress_in_chunk = (j + 1) / num_entries
                total_progress = base_progress + (entry_progress_in_chunk * source_chunk_progress)
                task.set_progress(int(total_progress))

        task.log("--- RSS Feed Check Finished ---")
        task.set_progress(100) # Ensure it finishes at 100%
        return {"status": "success", "new_articles_found": total_new_articles}
    except Exception as e:
        task.log(f"CRITICAL ERROR in RSS feed processing task: {e}", "CRITICAL")
        trace_exception(e)
        raise e
    finally:
        db.close()
