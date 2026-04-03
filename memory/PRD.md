# LLM Council - Product Requirements Document

## Original Problem Statement
Application LLM Council avec panneau Advanced pour configurer les sources LLM (OpenRouter/LM Studio/Hybrid) avec URL par modèle et persistance backend.

## Architecture

### Frontend (React/Vite) - port 5173
- `App.jsx` : État global, advancedSettings, gestion conversations
- `api.js` : Client HTTP avec advanced config
- `AdvancedPanel.jsx` : Configuration LLM avec URL par modèle
- `Settings.jsx` : Configuration générale avec chemins de stockage dynamiques
- `Sidebar.jsx` : Navigation avec badge du mode actif

### Backend (Python/FastAPI) - port 8001
- `main.py` : Routes avec guard intelligent `requires_openrouter_key()`
- `openrouter.py` : Routing intelligent avec extraction URL par modèle
- `council.py` : Orchestration 3 stages + `generate_conversation_title` avec routing
- `config_manager.py` : Config avec `storage_paths`

## Data Structure (Advanced Config)

```json
{
  "mode": "openrouter" | "lmstudio" | "hybrid",
  "openrouter": { "apiKey": "" },
  "models": {
    "openai/gpt-4o": {
      "source": "openrouter" | "lmstudio",
      "endpointUrl": "http://localhost:1234/v1",
      "localModelName": "mistral-7b"
    }
  },
  "chairman": { "source": "...", "endpointUrl": "...", "localModelName": "" }
}
```

## What's Been Implemented

### 2026-04-03 - Bug Fixes Backend LM Studio

#### Bug 1: Guard API key ✅
- Ajout fonction `requires_openrouter_key(advanced_config)` dans `main.py`
- Modification des guards dans `send_message` et `send_message_stream`
- En mode `lmstudio`, pas besoin de clé OpenRouter
- Health check retourne `configured: true` si advanced_config présent

#### Bug 2: generate_conversation_title ✅
- Modification pour accepter `advanced_config` parameter
- En mode `lmstudio`/`hybrid`, utilise le premier modèle du conseil avec son routing
- En mode `openrouter`, continue d'utiliser gemini-2.5-flash

#### Bug 3: Title generation failure ✅
- Ajout try/except autour de `title_task` dans event_generator
- Si échec, utilise le contenu de la query comme titre fallback
- L'échec de génération de titre n'interrompt plus le stream

#### Feature: Storage paths dynamiques ✅
- Ajout `storage_paths` dans réponse `/api/config`
- Affichage des vrais chemins dans Settings > Advanced
- Montre config_file, conversations_dir, documents_dir

### Previous Implementations
- Panneau Advanced avec 3 modes (OpenRouter/LM Studio/Hybrid)
- URL par modèle au lieu d'URL globale
- Persistance backend via `/api/config/advanced`
- Badge du mode actif dans le header

## Prioritized Backlog

### P0 (Bloquant)
- Aucun

### P1 (Important)
- Auto-complétion des modèles LM Studio après Test réussi
- Indicateur source dans résultats de chaque stage

### P2 (Nice to have)
- Import/export configuration
- Preset configurations

## Next Tasks
- Tester avec serveurs LM Studio réels
- Documenter les 3 modes dans le README
