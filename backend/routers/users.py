# backend/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, exists

from backend.db import get_db
from backend.db.base import FriendshipStatus
from backend.db.utils import get_friendship_record
from backend.db.base import follows_table
from backend.db.models.user import User as DBUser, Friendship as DBFriendship
from backend.models import UserAuthDetails, UserProfileResponse, UserPublic
from backend.models.admin import UserStats, UserActivityStat
from backend.session import get_current_active_user
from typing import List, Optional
import datetime
from datetime import timezone, timedelta
from collections import defaultdict
from sqlalchemy import func, desc

users_router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(get_current_active_user)]
)

def _project_user_public(user: DBUser) -> UserPublic:
    """
    Transforms a DBUser ORM object into a completely decoupled, flat UserPublic model.
    This guarantees that the JSON serializer never accesses lazy-loaded ORM relationships
    (discussions, notes, memories) that cause huge payload warning loops.
    """
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        icon=user.icon,
        is_active=user.is_active,
        is_admin=getattr(user, "is_admin", False) or False,
        is_moderator=getattr(user, "is_moderator", False) or False,
        status=user.status,
        created_at=user.created_at,
        last_activity_at=user.last_activity_at
    )

@users_router.get("/search", response_model=List[UserPublic])
def search_for_users(
    q: str = Query(..., min_length=2, max_length=50),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches for users.
    - If the query is a partial match, it returns only users who have enabled searchability.
    - If the query is an exact username match, it returns that user regardless of their searchability setting.
    - Excludes the current user from results.
    """
    search_term = f"%{q}%"

    users = db.query(DBUser).filter(
        DBUser.id != current_user.id,
        or_(
            DBUser.username == q,
            and_(
                DBUser.is_searchable == True,
                DBUser.username.ilike(search_term)
            )
        )
    ).limit(10).all()

    return [_project_user_public(u) for u in users]


@users_router.get("/mention_search", response_model=List[UserPublic])
def search_for_mentions(
    q: Optional[str] = Query(default="", max_length=50),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches for users to mention.
    Returns users whose username matches the query and are searchable.
    Excludes the current user.
    """
    query_str = (q or "").strip()
    search_term = f"{query_str}%" if query_str else "%"
    users = db.query(DBUser).filter(
        DBUser.id != current_user.id,
        DBUser.is_searchable == True,
        DBUser.username.ilike(search_term)
    ).limit(5).all()
    return [_project_user_public(u) for u in users]


@users_router.get("/me/stats", response_model=UserStats)
def get_current_user_personal_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Returns personal usage telemetry, token consumption history, and estimated CO2 footprint for the logged-in user.
    """
    from backend.db.models.generation_metric import GenerationMetric, calculate_co2_equivalents, KWH_PER_TOKEN, CO2_G_PER_KWH

    cutoff = datetime.datetime.now(timezone.utc) - timedelta(days=days)

    metrics = db.query(
        func.date(GenerationMetric.created_at).label('metric_date'),
        GenerationMetric.source,
        func.count(GenerationMetric.id).label('gen_count'),
        func.sum(GenerationMetric.total_tokens).label('tok_count'),
        func.sum(GenerationMetric.prompt_tokens).label('p_tok'),
        func.sum(GenerationMetric.completion_tokens).label('c_tok')
    ).filter(
        GenerationMetric.user_id == current_user.id,
        GenerationMetric.created_at >= cutoff
    ).group_by(func.date(GenerationMetric.created_at), GenerationMetric.source).all()

    all_dates = set()
    daily_msgs = defaultdict(int)
    daily_tokens = defaultdict(int)
    webui_tokens_per_day_dict = defaultdict(int)
    api_tokens_per_day_dict = defaultdict(int)

    total_tokens = 0
    total_prompt = 0
    total_comp = 0
    webui_tokens = 0
    api_tokens = 0
    webui_reqs = 0
    api_reqs = 0

    for date_str, src, count, tokens, p_tok, c_tok in metrics:
        if date_str:
            d_str = str(date_str)
            all_dates.add(d_str)
            cnt = count or 0
            tok = tokens or 0
            daily_msgs[d_str] += cnt
            daily_tokens[d_str] += tok
            total_tokens += tok
            total_prompt += (p_tok or 0)
            total_comp += (c_tok or 0)

            if src == "chat":
                webui_tokens += tok
                webui_reqs += cnt
                webui_tokens_per_day_dict[d_str] += tok
            else:
                api_tokens += tok
                api_reqs += cnt
                api_tokens_per_day_dict[d_str] += tok

    # Query top models used by this user
    top_models_raw = db.query(
        GenerationMetric.model_name,
        func.sum(GenerationMetric.total_tokens).label('tok_sum'),
        func.count(GenerationMetric.id).label('usage_count')
    ).filter(
        GenerationMetric.user_id == current_user.id
    ).group_by(GenerationMetric.model_name).order_by(desc('tok_sum')).limit(5).all()

    top_models = [
        {"model_name": row[0] or "unknown", "total_tokens": row[1] or 0, "count": row[2] or 0}
        for row in top_models_raw
    ]

    sorted_date_strings = sorted(list(all_dates))

    messages_per_day = [
        UserActivityStat(date=datetime.datetime.strptime(d_str, '%Y-%m-%d').date(), count=daily_msgs[d_str])
        for d_str in sorted_date_strings
    ]
    tokens_per_day = [
        UserActivityStat(date=datetime.datetime.strptime(d_str, '%Y-%m-%d').date(), count=daily_tokens[d_str])
        for d_str in sorted_date_strings
    ]
    webui_tokens_per_day = [
        UserActivityStat(date=datetime.datetime.strptime(d_str, '%Y-%m-%d').date(), count=webui_tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]
    api_tokens_per_day = [
        UserActivityStat(date=datetime.datetime.strptime(d_str, '%Y-%m-%d').date(), count=api_tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]


    # Query WebUI vs API breakdown for user
    source_rows = db.query(
        GenerationMetric.source,
        func.count(GenerationMetric.id).label('req_count'),
        func.sum(GenerationMetric.total_tokens).label('tot_tok')
    ).filter(
        GenerationMetric.user_id == current_user.id,
        GenerationMetric.created_at >= cutoff
    ).group_by(GenerationMetric.source).all()

    webui_tokens = 0
    api_tokens = 0
    webui_reqs = 0
    api_reqs = 0

    for src, req_c, tok_c in source_rows:
        t = tok_c or 0
        r = req_c or 0
        if src == "chat":
            webui_tokens += t
            webui_reqs += r
        else:
            api_tokens += t
            api_reqs += r

    total_reqs = webui_reqs + api_reqs
    sum_tokens = webui_tokens + api_tokens if (webui_tokens + api_tokens) > 0 else total_tokens

    webui_ratio = round((webui_tokens / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0
    api_ratio = round((api_tokens / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0

    webui_energy = webui_tokens * KWH_PER_TOKEN
    api_energy = api_tokens * KWH_PER_TOKEN
    webui_co2 = webui_energy * CO2_G_PER_KWH
    api_co2 = api_energy * CO2_G_PER_KWH

    from backend.models.admin import SourceConsumptionBreakdown

    source_breakdown = SourceConsumptionBreakdown(
        webui_tokens=webui_tokens,
        api_tokens=api_tokens,
        total_tokens=sum_tokens,
        webui_requests=webui_reqs,
        api_requests=api_reqs,
        total_requests=total_reqs,
        webui_ratio=webui_ratio,
        api_ratio=api_ratio,
        webui_energy_kwh=round(webui_energy, 4),
        api_energy_kwh=round(api_energy, 4),
        webui_co2_g=round(webui_co2, 2),
        api_co2_g=round(api_co2, 2)
    )


    energy_kwh = sum_tokens * KWH_PER_TOKEN
    co2_g = energy_kwh * CO2_G_PER_KWH
    equivalents = calculate_co2_equivalents(co2_g)

    return UserStats(
        tasks_per_day=[],
        messages_per_day=messages_per_day,
        tokens_per_day=tokens_per_day,
        webui_tokens_per_day=webui_tokens_per_day,
        api_tokens_per_day=api_tokens_per_day,
        total_tokens=sum_tokens,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_comp,
        total_energy_kwh=round(energy_kwh, 4),
        total_co2_g=round(co2_g, 2),
        co2_equivalents=equivalents,
        top_models=top_models,
        source_breakdown=source_breakdown
    )

@users_router.get("/{username}", response_model=UserProfileResponse)
def get_user_profile(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Fetches a user's public profile along with the relationship
    status relative to the current authenticated user.
    """
    # Resolve 'me' keyword to current user's username
    target_username = current_user.username if username == "me" else username

    target_user = db.query(DBUser).filter(DBUser.username == target_username).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    is_following = db.query(exists().where(and_(
        follows_table.c.follower_id == current_user.id,
        follows_table.c.following_id == target_user.id
    ))).scalar()

    friendship = get_friendship_record(db, current_user.id, target_user.id)
    friendship_status = friendship.status if friendship else None

    return UserProfileResponse(
        user=_project_user_public(target_user),
        relationship={
            "is_following": is_following,
            "friendship_status": friendship_status
        }
    )