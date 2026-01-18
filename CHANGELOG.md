# LoLLMs Changelog

All notable changes to the LoLLMs Platform will be documented in this file.

#
- feat: overhaul UI assets and enhance backend configuration# [Unreleased]

- feat: overhaul help system and clean up UI assets

#
- feat: refactor backend imports and cleanup UI assets# [Unreleased]

- feat: overhaul UI assets and enhance backend configuration

#
- feat: add authentication dependencies to file endpoints and enhance image upload validation# [Unreleased]

- feat(core): add ImageAlbum model, admin requirement info, and extensive UI updates

#
- feat(friends): add authorization checks for responding to friend requests# [Unreleased]

- feat(files): add SSRF protection with URL validation for image downloads

#
- chore(deps): bump lollms-client from 1.9.0 to 1.9.1# [Unreleased]

- feat: overhaul UI assets and enhance backend configuration

#
- chore(deps): bump lollms-client from 1.9.1 to 1.9.2# [Unreleased]

- feat(flow-studio): add comprehensive Flow Studio UI and backend updates

#
- chore(deps): bump lollms-client to 1.9.4 and safe_store to 3.3.4# [Unreleased]

- feat(core): add video file support, extend DB schema, and overhaul UI assets

#
- feat: prune obsolete UI asset bundles and update index.html# [Unreleased]

- feat(notebook): add tab support and extend creation schema

## [2026-01-18 19:57]

- chore(build): remove obsolete dist assets

## [2026-01-18 14:58]

- refactor(discussion): update generation and service routers

## [2026-01-17 17:53]

- feat(admin): add admin & social routes, update security and UI assets

## [2026-01-17 14:28]

- feat(social,dm): add input sanitization with bleach

## [2026-01-17 14:28]

- feat(social): add missing imports and update comments

## [2026-01-17 12:55]

- refactor(config): use ASCIIColors for security logs

## [2026-01-17 09:13]

- fix(config): auto‑rotate weak or missing SECRET_KEY

## [2026-01-17 09:02]

- feat(security): auto‑rotate and generate secure SECRET_KEY

## [2026-01-15 01:16]

- chore(build): rebuild frontend assets and update deps

## [2026-01-15 01:03]

- build(frontend): rebuild production assets

## [2026-01-15 00:58]

- build(frontend): rebuild UI assets after backend changes

## [2026-01-13 01:38]

- chore(deps): update lollms-client to 1.10.1

## [2026-01-13 01:35]

- feat(admin): rebuild frontend and update bindings API

## [2026-01-12 21:18]

- build(frontend): regenerate production build assets

## [2026-01-12 02:34]

- feat(notebook): enhance notebook system with tab support

## [2026-01-12 01:55]

- feat(notebooks): implement herd mode functionality

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
