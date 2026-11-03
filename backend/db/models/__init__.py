# NOTE: Personalities are NO LONGER stored in the database.
# Source of truth: filesystem handbags under data/personalities/{global,users/}.
# Only metadata-only reference tables remain:
#   - PersonalityShareLink       (sharing ACL, read-only discovery)
#   - UserPersonalityPreference  (user -> selected (scope, handbag_name, owner_id))
# See backend/db/models/personality_share.py and backend/personalities.py.
from .user import User
from .group import Group
from .personality_share import PersonalityShareLink, UserPersonalityPreference
from .config import GlobalConfig, LLMBinding, TTIBinding, TTSBinding, STTBinding, DatabaseVersion, RAGBinding
from .service import App, MCP, AppZooRepository, MCPZooRepository, PromptZooRepository, PersonalityZooRepository
from .social import Post, Comment
from .dm import Conversation, DirectMessage, ConversationMember
from .discussion import SharedDiscussionLink
from .discussion_group import DiscussionGroup
from .memory import UserMemory
from .note import Note, NoteGroup
from .notebook import Notebook
from .image import UserImage, ImageAlbum
from .voice import UserVoice
from .fun_fact import FunFact, FunFactCategory
from .news import NewsArticle, RSSFeedSource
from .broadcast import BroadcastMessage
from .api_key import OpenAIAPIKey
from .connections import WebSocketConnection
from .datastore import DataStore, SharedDataStoreLink
from .db_task import DBTask
from .email_marketing import EmailProposal, EmailTopic

from .prompt import SavedPrompt
# Flow Studio Integration
from .saved_artefact import SavedArtefact, SharedArtefactLink
from .flow import Flow, FlowNodeDefinition
from .generation_metric import GenerationMetric, record_generation_metric, calculate_co2_equivalents, KWH_PER_TOKEN, CO2_G_PER_KWH