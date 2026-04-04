# LLM Council - Product Requirements Document

## Original Problem Statement
Application LLM Council avec panneau Advanced pour configurer les sources LLM (OpenRouter/LM Studio/Hybrid) avec URL par modèle, throttling pour éviter le freeze du laptop, et persistance backend.

## Architecture

### Frontend (React/Vite) - port 5173
- `App.jsx` : État global, advancedSettings
- `api.js` : Client HTTP avec advanced config
- `AdvancedPanel.jsx` : Configuration LLM + Performance & Throttling
- `Settings.jsx` : Configuration générale avec chemins dynamiques
- `Sidebar.jsx` : Navigation avec badge du mode actif

### Backend (Python/FastAPI) - port 8001
- `main.py` : Routes avec guard intelligent `requires_openrouter_key()`
- `openrouter.py` : Routing intelligent avec throttling via `execute_with_throttle()`
- `load_balancer.py` : Module throttling (ThrottleConfig, semaphore, delays)
- `council.py` : Orchestration 3 stages + title generation avec routing
- `config_manager.py` : Config avec `storage_paths` et `throttle`

## What's Been Implemented

### 2026-04-04 - Fix LM Studio Query Issues

#### Bug 1: Double /v1 URL suffix ✅
- `query_lm_studio` vérifie maintenant si `/v1` est déjà dans l'URL
- Évite `http://localhost:8080/v1/v1/chat/completions`

#### Bug 2: reasoning_content field ✅
- LM Studio utilise `reasoning_content` pas `reasoning_details`
- Code extrait maintenant les deux champs

#### Bug 3: Coroutines not awaited ✅
- `query_models_parallel` utilise une fonction wrapper async
- Plus de `RuntimeWarning: coroutine 'query_model' was never awaited`

#### Améliorations
- Ajout de `stream: false` dans le payload LM Studio
- Meilleurs logs de debug avec URL et model name
- Support de `local`, `default` ou vide pour auto-select du modèle

### Previous Implementations
- Load Balancer & Throttling avec presets (Safe/Balanced/Fast)
- Bug fixes: guard API key, generate_conversation_title, title_task
- Storage paths dynamiques dans Settings > Advanced
- Refactoring URL par modèle, persistance backend advanced config

## Data Structures

### Advanced Config
```json
{
  "mode": "openrouter" | "lmstudio" | "hybrid",
  "models": { "model-id": { "source": "...", "endpointUrl": "...", "localModelName": "" } },
  "chairman": { "source": "...", "endpointUrl": "...", "localModelName": "" },
  "throttle": { "maxConcurrent": 1, "delayBetweenRequests": 1.0, "requestTimeout": 300 }
}
```

## Prioritized Backlog

### P0 (Bloquant)
- Aucun

### P1 (Important)
- Indicateur de progression pendant les stages
- Auto-complétion des modèles LM Studio

### P2 (Nice to have)
- Monitoring CPU/RAM
- Import/export configuration

## Next Tasks
- Tester avec serveur LM Studio réel sur différents ports
- Documenter les modes dans le README
