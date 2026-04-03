# LLM Council - Product Requirements Document

## Original Problem Statement
Ajouter un onglet "Advanced" dans l'interface frontend de LLM Council pour configurer la source des appels LLM. Refactoring pour supporter des URLs par modèle au lieu d'une URL globale, et persistance backend de la configuration.

## Architecture

### Frontend (React/Vite) - port 5173
- `App.jsx` : État global, gestion des conversations, advancedSettings
- `api.js` : Client HTTP avec endpoints advanced config (GET/POST)
- `ChatInterface.jsx` : Interface principale avec les 3 stages
- `AdvancedPanel.jsx` : Configuration LLM avec URL par modèle
- `Sidebar.jsx` : Navigation avec badge du mode actif
- `Settings.jsx` : Configuration générale (sans onglet LM Studio - supprimé)

### Backend (Python/FastAPI) - port 8001
- `main.py` : Routes FastAPI incluant `/api/config/advanced` GET/POST
- `openrouter.py` : Routing intelligent avec extraction URL par modèle
- `council.py` : Orchestration des 3 stages
- `config_manager.py` : Gestion config.json avec advanced_config

## Data Structure (Advanced Config)

```json
{
  "mode": "openrouter" | "lmstudio" | "hybrid",
  "openrouter": {
    "apiKey": ""
  },
  "models": {
    "openai/gpt-4o": {
      "source": "openrouter" | "lmstudio",
      "endpointUrl": "http://localhost:1234/v1",
      "localModelName": "mistral-7b"
    }
  },
  "chairman": {
    "source": "openrouter" | "lmstudio",
    "endpointUrl": "http://localhost:1234/v1",
    "localModelName": ""
  }
}
```

## What's Been Implemented

### 2026-04-03 - Refactoring Configuration LM Studio

#### Bug Fixes
- [x] Suppression de l'onglet `lmstudio` de Settings.jsx (doublon avec AdvancedPanel)
- [x] Remplacement de l'URL globale par URL par modèle dans AdvancedPanel

#### New Features
- [x] Nouvelle structure de données avec `models[modelId]` contenant source/endpointUrl/localModelName
- [x] UI LM Studio mode : chaque modèle a son propre champ URL + Model Name + bouton Test
- [x] UI Hybrid mode : toggle source par modèle, champs URL si LM Studio sélectionné
- [x] Chairman séparé avec sa propre configuration
- [x] Persistance backend via `GET/POST /api/config/advanced`
- [x] Auto-save avec debounce (500ms)
- [x] Chargement depuis backend au mount, fallback localStorage
- [x] Backend routing intelligent dans `openrouter.py` avec nouvelle structure

#### Files Modified
- `frontend/src/components/AdvancedPanel.jsx` : Refonte complète avec URL par modèle
- `frontend/src/components/AdvancedPanel.css` : Nouveaux styles pour model cards
- `frontend/src/components/Settings.jsx` : Suppression onglet lmstudio + états associés
- `frontend/src/api.js` : Ajout getAdvancedConfig/saveAdvancedConfig
- `backend/main.py` : Ajout endpoints /api/config/advanced
- `backend/openrouter.py` : Refonte get_model_source/get_chairman_source
- `backend/config_manager.py` : Ajout advanced_config dans DEFAULT_CONFIG et allowed_keys

## Prioritized Backlog

### P0 (Bloquant)
- Aucun

### P1 (Important)
- Auto-complétion des modèles LM Studio après Test Connection réussi
- Afficher indicateur source dans résultats de chaque stage

### P2 (Nice to have)
- Import/export configuration
- Preset configurations (ex: "All Local", "Hybrid Optimal")
- Estimation coûts/latence par source

## Next Tasks
- Tester avec serveurs LM Studio réels
- Documenter les modes dans le README
