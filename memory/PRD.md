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

## Data Structures

### Advanced Config
```json
{
  "mode": "openrouter" | "lmstudio" | "hybrid",
  "openrouter": { "apiKey": "" },
  "models": { "model-id": { "source": "...", "endpointUrl": "...", "localModelName": "" } },
  "chairman": { "source": "...", "endpointUrl": "...", "localModelName": "" },
  "throttle": { "maxConcurrent": 1, "delayBetweenRequests": 1.0, "requestTimeout": 300 }
}
```

### Throttle Presets
- **Safe**: maxConcurrent=1, delay=2s, timeout=300s (recommandé pour laptops)
- **Balanced**: maxConcurrent=2, delay=0.5s, timeout=180s
- **Fast**: maxConcurrent=4, delay=0s, timeout=120s (risque de freeze)

## What's Been Implemented

### 2026-04-04 - Load Balancer & Throttling

#### New Module: `backend/load_balancer.py`
- `ThrottleConfig` dataclass avec max_concurrent, delay_between_requests, request_timeout
- `get_throttle_config()` extrait la config throttle selon le mode
- `execute_with_throttle()` utilise semaphore + delays au lieu de asyncio.gather

#### Modifications Backend
- `openrouter.py`: `query_models_parallel()` utilise `execute_with_throttle()`
- Timeout LM Studio augmenté à 300s (modèles locaux lents)
- `config_manager.py`: ajout `throttle` dans DEFAULT_CONFIG et allowed_keys

#### Modifications Frontend
- `AdvancedPanel.jsx`: Section "Performance & Throttling" (visible en lmstudio/hybrid)
- Presets: Safe, Balanced, Fast
- Sliders: Concurrent requests (1-4), Delay (0-5s), Timeout (30s-10min)
- Messages d'aide contextuels selon les valeurs

### Previous Implementations
- Bug fixes: guard API key, generate_conversation_title, title_task isolation
- Feature: storage_paths dynamiques
- Refactoring: URL par modèle, persistance backend advanced config
- Panneau Advanced avec 3 modes

## Prioritized Backlog

### P0 (Bloquant)
- Aucun

### P1 (Important)
- Indicateur throttle pendant les stages (ex: "Stage 1: 1/4 modèles")
- Auto-complétion des modèles LM Studio après Test réussi

### P2 (Nice to have)
- Monitoring CPU/RAM en temps réel
- Import/export configuration

## Next Tasks
- Tester avec serveurs LM Studio réels
- Documenter les modes et presets dans le README
