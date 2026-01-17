from backend.db import get_db
from backend.db.models.social import Post, Comment
from backend.db.models.dm import DirectMessage, Conversation
from backend.security import sanitize_content
from backend.task_manager import Task

def _sanitize_database_task(task: Task):
    """
    Task to scan and sanitize all user-generated content in the database.
    This fixes retroactive XSS vulnerabilities by cleaning data that was inserted before
    sanitization logic was implemented.
    """
    task.log("Starting Database Content Sanitization...", "INFO")
    
    # Obtain a fresh database session
    db = next(get_db())
    
    try:
        # 1. Sanitize Posts
        task.log("Phase 1/4: Scanning Posts...")
        posts = db.query(Post).all()
        total_posts = len(posts)
        sanitized_posts = 0
        
        for i, post in enumerate(posts):
            if task.cancellation_event.is_set():
                task.log("Sanitization cancelled.", "WARNING")
                return
            
            if post.content:
                clean = sanitize_content(post.content)
                if clean != post.content:
                    post.content = clean
                    sanitized_posts += 1
            
            if i % 100 == 0:
                task.set_progress(int(i / total_posts * 25)) # 0-25% progress
        
        task.log(f"  - Scanned {total_posts} posts. Sanitized {sanitized_posts} items.", "INFO")

        # 2. Sanitize Comments
        task.log("Phase 2/4: Scanning Comments...")
        comments = db.query(Comment).all()
        total_comments = len(comments)
        sanitized_comments = 0
        
        for i, comment in enumerate(comments):
            if comment.content:
                clean = sanitize_content(comment.content)
                if clean != comment.content:
                    comment.content = clean
                    sanitized_comments += 1
            
            if i % 100 == 0:
                progress = 25 + int(i / total_comments * 25) # 25-50% progress
                task.set_progress(progress)

        task.log(f"  - Scanned {total_comments} comments. Sanitized {sanitized_comments} items.", "INFO")

        # 3. Sanitize Direct Messages
        task.log("Phase 3/4: Scanning Direct Messages...")
        dms = db.query(DirectMessage).all()
        total_dms = len(dms)
        sanitized_dms = 0
        
        for i, dm in enumerate(dms):
            if dm.content:
                clean = sanitize_content(dm.content)
                if clean != dm.content:
                    dm.content = clean
                    sanitized_dms += 1
            
            if i % 100 == 0:
                progress = 50 + int(i / total_dms * 25) # 50-75% progress
                task.set_progress(progress)

        task.log(f"  - Scanned {total_dms} DMs. Sanitized {sanitized_dms} items.", "INFO")

        # 4. Sanitize Group Names
        task.log("Phase 4/4: Scanning Conversation Names...")
        convs = db.query(Conversation).all()
        total_convs = len(convs)
        sanitized_convs = 0
        
        for i, conv in enumerate(convs):
            if conv.name:
                clean = sanitize_content(conv.name)
                if clean != conv.name:
                    conv.name = clean
                    sanitized_convs += 1
            
            if i % 10 == 0: # Convs are usually fewer
                progress = 75 + int(i / total_convs * 25) # 75-100% progress
                task.set_progress(progress)

        task.log(f"  - Scanned {total_convs} Conversations. Sanitized {sanitized_convs} items.", "INFO")

        db.commit()
        task.set_progress(100)
        
        total_cleaned = sanitized_posts + sanitized_comments + sanitized_dms + sanitized_convs
        return {
            "message": f"Sanitization Complete. Cleaned {total_cleaned} items.",
            "details": {
                "posts": sanitized_posts,
                "comments": sanitized_comments,
                "dms": sanitized_dms,
                "conversations": sanitized_convs
            }
        }

    except Exception as e:
        task.log(f"CRITICAL ERROR during sanitization: {str(e)}", "ERROR")
        db.rollback()
        raise e
    finally:
        db.close()
