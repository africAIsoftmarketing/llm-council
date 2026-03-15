# LLM Council - Product Requirements Document

## Overview
LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer questions through individual responses, peer review, and chairman synthesis.

## Original Problem Statement
Add the capability to query the LM Studio CORS server URL for each LLM to run the LLM council. Each model should have its own configurable LM Studio server URL (OpenAI API compatible).

## Architecture

### Backend (FastAPI)
- **config_manager.py**: Configuration management with LM Studio URL support
- **openrouter.py**: LLM client supporting both OpenRouter and LM Studio queries
- **council.py**: 3-stage council orchestration
- **main.py**: API endpoints including LM Studio test/config endpoints

### Frontend (React + Vite)
- **Settings.jsx**: Settings page with LM Studio configuration tab
- **api.js**: API client with LM Studio endpoints

### Installer (Inno Setup)
- Windows installer with embedded Python
- default_config.json with lm_studio_urls field
- Version bumped to 2.1.0

## Core Requirements (Static)

### LM Studio Integration
1. Each council model can have an optional LM Studio server URL
2. When configured, queries go to local LM Studio instead of OpenRouter
3. OpenAI-compatible API format for LM Studio communication
4. Connection testing endpoint to verify LM Studio server accessibility

### Configuration
- lm_studio_urls: Dict[model_id, base_url] mapping
- URLs stored in config.json
- API endpoints: POST /api/lm-studio/test, GET /api/lm-studio/urls

### UI Requirements
- LM Studio tab in Settings page
- URL input for each selected council model
- Test connection button with status feedback
- Clear button to remove configured URLs
- Visual indicator (badge) when model has LM Studio URL

## What's Been Implemented (2026-03-15)

### Backend Changes
- Added `lm_studio_urls` field to DEFAULT_CONFIG
- Added `get_lm_studio_urls()` and `get_lm_studio_url_for_model()` functions
- Added `test_lm_studio_connection()` async function
- Added `query_lm_studio()` function in openrouter.py
- Modified `query_model()` to check for LM Studio URL first
- Added API endpoints: POST /api/lm-studio/test, GET /api/lm-studio/urls
- Updated ConfigUpdateRequest to include lm_studio_urls

### Frontend Changes
- Added LM Studio tab to Settings page
- Added URL input fields for each selected model
- Added Test and Clear buttons
- Added LM Studio badge indicator
- Added API methods: testLmStudioConnection(), getLmStudioUrls()
- Fixed API_BASE to use empty string for relative URLs

### Installer Changes
- Updated default_config.json with lm_studio_urls field
- Version bumped to 2.1.0 in llm-council-installer.iss
- Updated launcher.py with lm_studio_urls in default config
- Added LM Studio quick link in launcher GUI
- Updated USER_MANUAL.md with LM Studio documentation
- Updated README_INSTALLER.txt with LM Studio info
- Updated installer/README.md with v2.1.0 features

## Prioritized Backlog

### P0 (Critical)
- [x] LM Studio URL configuration per model
- [x] Test connection functionality
- [x] Backend integration with LM Studio servers

### P1 (High)
- [ ] Connection status monitoring
- [ ] Model auto-detection from LM Studio /models endpoint

### P2 (Medium)
- [ ] Multiple LM Studio servers support
- [ ] Fallback from LM Studio to OpenRouter on failure
- [ ] Request timeout configuration per model

## User Personas

### Primary: Local LLM Enthusiast
- Runs LM Studio on local machine
- Wants to use local models in council
- Values privacy and offline capability

### Secondary: Hybrid User
- Uses both OpenRouter and local models
- Wants flexibility in model selection
- Cost-conscious (local = free)

## Next Tasks
1. Add connection health monitoring
2. Implement automatic fallback to OpenRouter when LM Studio fails
3. Add model name detection from LM Studio /models endpoint
4. Consider adding batch URL configuration
