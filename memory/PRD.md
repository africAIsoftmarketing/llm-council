# LLM Council - Product Requirements Document

## Original Problem Statement
Ajouter un onglet "Advanced" dans l'interface frontend de LLM Council pour permettre à l'utilisateur de configurer la source des appels LLM avec trois options : OpenRouter (cloud), LM Studio (local), et Hybrid (mix cloud & local). Support du mode développeur LM Studio avec plusieurs modèles simultanés.

## Architecture

### Frontend (React/Vite) - port 5173
- `App.jsx` : État global, gestion des conversations, advancedSettings
- `api.js` : Client HTTP avec support des paramètres advanced
- `ChatInterface.jsx` : Interface principale avec les 3 stages
- `AdvancedPanel.jsx` : Panneau de configuration Advanced avec multi-modèles
- `Sidebar.jsx` : Navigation avec badge du mode actif

### Backend (Python/FastAPI) - port 8001
- `main.py` : Routes FastAPI avec SSE streaming, accepte advanced config
- `openrouter.py` : Client intelligent avec routing OpenRouter/LM Studio multi-modèles
- `council.py` : Orchestration des 3 stages avec propagation advanced config
- `config.py` : Configuration COUNCIL_MODELS, CHAIRMAN_MODEL, LMSTUDIO_BASE_URL

## User Personas
- Développeur AI cherchant à comparer plusieurs LLMs
- Utilisateur souhaitant utiliser des modèles locaux (LM Studio) pour la confidentialité
- Utilisateur avancé avec LM Studio en mode développeur (plusieurs modèles chargés)
- Utilisateur voulant un mix cloud/local pour optimiser coûts et latence

## Core Requirements (Static)
1. Interface 3-stages : Réponses parallèles → Ranking par pairs → Synthèse Chairman
2. Support OpenRouter API pour les modèles cloud
3. Support LM Studio pour les modèles locaux
4. Mode Hybrid pour mixer cloud et local
5. Support multi-modèles LM Studio (mode développeur)
6. Persistance des paramètres dans localStorage

## What's Been Implemented

### 2026-04-02 - Onglet Advanced + Multi-Modèles LM Studio

#### Features Implemented
- [x] Panneau Advanced accessible depuis la sidebar (icône ⚙️)
- [x] Sélection de mode : OpenRouter / LM Studio / Hybrid
- [x] Badge visuel du mode actif dans le header
- [x] Configuration OpenRouter : Override clé API optionnel
- [x] Configuration LM Studio : URL serveur + modèle par défaut
- [x] Bouton "Test Connection" pour LM Studio
- [x] **Multi-modèles LM Studio** : Assigner un modèle LM Studio spécifique à chaque membre du conseil
- [x] **Chairman Model** : Modèle LM Studio spécifique pour le Chairman
- [x] Mode Hybrid : Assignation source + nom modèle LM Studio par modèle
- [x] Persistance localStorage avec deep merge (llm_council_advanced_settings)
- [x] Compatibilité ascendante (fonctionne sans paramètre advanced)

#### Files Modified
- `frontend/src/components/AdvancedPanel.jsx` + `.css` : Nouveau panneau avec multi-modèles
- `frontend/src/App.jsx`, `api.js`, `Sidebar.jsx` + `.css` : Intégration
- `backend/main.py` : Accepte advanced config
- `backend/openrouter.py` : Routing intelligent avec extraction nom modèle par conseil
- `backend/council.py` : Propagation advanced_config
- `backend/config.py` : LMSTUDIO_BASE_URL

## Prioritized Backlog

### P0 (Bloquant)
- Aucun

### P1 (Important)
- Afficher indicateur source dans résultats de chaque stage
- Auto-détection des modèles disponibles dans LM Studio

### P2 (Nice to have)
- Support plusieurs serveurs LM Studio en mode hybrid
- Estimation coûts/latence par source
- Import/export configuration
- Preset configurations

## Next Tasks
- Tester avec un vrai serveur LM Studio local en mode développeur
- Documenter l'utilisation dans le README
- Ajouter validation inline des noms de modèles LM Studio
