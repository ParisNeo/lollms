import datetime
import random
from sqlalchemy.sql.expression import func
from backend.db import get_db
from backend.db.models.email_marketing import EmailProposal, EmailTopic, EmailStatus
from backend.db.models.user import User as DBUser
from backend.settings import settings
from backend.session import build_lollms_client_from_params
from backend.task_manager import Task

def _generate_email_proposal_task(task: Task):
    """
    Background task to research a topic and draft an email for admin review.
    """
    db = next(get_db())
    try:
        task.log("Starting Email Proposal Generation...")
        
        # 1. Select a Topic
        # Prioritize admin topics, then fallback to general ideas
        topic_entry = db.query(EmailTopic).filter(EmailTopic.is_active == True).order_by(func.random()).first()
        topic = topic_entry.topic if topic_entry else "The latest advancements in AI and productivity"
        
        task.log(f"Selected Topic: {topic}")
        
        # 2. 'Research' (Simulated or using RAG if configured)
        # In a full implementation, we would use a 'search' tool via MCP or bindings.
        # Here we ask the LLM to generate research notes based on its knowledge.
        bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not bot_user: 
            task.log("Lollms user not found", "ERROR")
            return

        lc = build_lollms_client_from_params(username='lollms')
        
        research_prompt = (
            f"Research and summarize interesting facts, news, or insights about: '{topic}'. "
            "Focus on value for a tech-savvy audience. "
            "Provide 3-5 key bullet points."
        )
        
        task.log("Gathering insights...")
        research_notes = lc.generate_text(
            research_prompt, 
            system_prompt="You are a researcher gathering data for a newsletter.",
            max_new_tokens=512
        )
        
        # 3. Draft the Email
        draft_prompt = (
            f"Write an engaging newsletter email about '{topic}' based on these notes:\n{research_notes}\n\n"
            "Format:\n"
            "Subject: [Catchy Subject]\n\n"
            "[Body Content]\n\n"
            "Keep it professional yet conversational. Under 300 words."
        )
        
        task.log("Drafting email...")
        full_draft = lc.generate_text(
            draft_prompt,
            system_prompt="You are an expert email copywriter.",
            max_new_tokens=768
        )
        
        # Parse Subject and Body
        subject = "New Update from Lollms"
        body = full_draft
        
        lines = full_draft.split('\n')
        for i, line in enumerate(lines):
            if line.lower().startswith("subject:"):
                subject = line[8:].strip()
                body = "\n".join(lines[i+1:]).strip()
                break
        
        # 4. Save to DB
        new_proposal = EmailProposal(
            title=subject,
            content=body,
            source_topic=topic,
            research_notes=research_notes,
            status=EmailStatus.PENDING_REVIEW
        )
        db.add(new_proposal)
        db.commit()
        
        task.log(f"Proposal '{subject}' saved for review.", "SUCCESS")
        
    except Exception as e:
        task.log(f"Error generating proposal: {e}", "ERROR")
    finally:
        db.close()
