# LoLLMs Changelog

All notable changes to the LoLLMs Platform will be documented in this file.

#
- feat: overhaul UI assets and enhance backend configuration# [Unreleased]

- feat: overhaul help system and clean up UI assets

#
- feat: refactor backend imports and cleanup UI assets# [Unreleased]

- feat: overhaul UI assets and enhance backend configuration

## [2.1.0] - "Restart" - 2025-12-28

This version marks a complete architectural evolution from the legacy `lollms_webui` (v1.16.0 "Twins"). LoLLMs is now a full-scale, multi-user AI orchestration platform.

### Added
- **Multi-User Foundation**: High-performance SQLite/SQLAlchemy backend replacing legacy YAML files. Supports secure authentication (JWT), user registration modes, and persistent session management.
- **LoLLMs Client Integration**: Core logic moved to the unified `lollms_client` library for faster, more reliable model interactions.
- **SafeStore (RAG) Studio**: Full implementation of Retrieval Augmented Generation. Create persistent Data Stores, index massive document libraries, and perform semantic search across your local knowledge.
- **AI Social Feed**: A community-driven feed allowing users to share posts and interact. Featuring `@lollms`—an autonomous bot capable of researching topics via Google, DuckDuckGo, ArXiv, and real-time Web Scraping.
- **Messaging & Groups**: Direct messaging system between users and the ability to organize chats into nested, hierarchical groups.
- **Specialized Studios**:
    - **Notebook Studio**: Document-based writing with integrated AI editing and long-form research.
    - **Image Studio**: Advanced control over TTI (Text-to-Image) with prompt history and generation workflows.
    - **Voice Studio**: Design and test high-quality AI voices using the new TTS (Text-to-Speech) pipeline.
- **MCP Bridge**: Native support for Model Context Protocol (MCP), allowing any model to use external tools like calculators, search engines, and local file systems.
- **Admin Command Center**: Real-time hardware monitoring (GPU/CPU/RAM), user provisioning (SCIM), Single Sign-On (SSO) configuration, and global service management.
- **Multi-Worker Synchronization**: New Communication Hub (ComHub) for seamless event broadcasting across high-concurrency server clusters.
- **Auto-Posting Service**: Configurable bot scheduler that uses knowledge bases to generate engaging community content autonomously.

### Changed
- **UI Redesign**: Complete shift to a modern, responsive Vue 3 + Tailwind CSS interface with beginner to expert UI levels.
- **API Standard**: Fully compatible OpenAI v1 and Ollama v1 endpoints serving local models to external applications.

### Fixed
- Resolved many concurrency issues inherent in the single-user architecture of previous versions.
- Improved model loading performance with intelligent process caching.
