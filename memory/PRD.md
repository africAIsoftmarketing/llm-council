# LLM Council - Product Requirements Document

## Original Problem Statement
Ajouter un onglet "Advanced" dans l'interface frontend de LLM Council pour permettre à l'utilisateur de configurer la source des appels LLM avec trois options : OpenRouter (cloud), LM Studio (local), et Hybrid (mix cloud & local).

## Architecture

### Frontend (React/Vite) - port 5173
- `App.jsx` : État global, gestion des conversations, advancedSettings
- `api.js` : Client HTTP avec support des paramètres advanced
- `ChatInterface.jsx` : Interface principale avec les 3 stages
- `AdvancedPanel.jsx` : Panneau de configuration Advanced
- `Sidebar.jsx` : Navigation avec badge du mode actif

### Backend (Python/FastAPI) - port 8001
- `main.py` : Routes FastAPI avec SSE streaming, accepte advanced config
- `openrouter.py` : Client intelligent avec routing OpenRouter/LM Studio
- `council.py` : Orchestration des 3 stages avec propagation advanced config
- `config.py` : Configuration COUNCIL_MODELS, CHAIRMAN_MODEL, LMSTUDIO_BASE_URL

## User Personas
- Développeur AI cherchant à comparer plusieurs LLMs
- Utilisateur souhaitant utiliser des modèles locaux (LM Studio) pour la confidentialité
- Utilisateur avancé voulant un mix cloud/local pour optimiser coûts et latence

## Core Requirements (Static)
1. Interface 3-stages : Réponses parallèles → Ranking par pairs → Synthèse Chairman
2. Support OpenRouter API pour les modèles cloud
3. Support LM Studio pour les modèles locaux
4. Mode Hybrid pour mixer cloud et local
5. Persistance des paramètres dans localStorage

## What's Been Implemented

### 2026-04-02 - Onglet Advanced
- **AdvancedPanel.jsx** : Nouveau composant modal avec 3 modes (OpenRouter/LM Studio/Hybrid)
- **AdvancedPanel.css** : Styles cohérents avec le design existant
- **Sidebar.jsx** : Badge du mode actif, bouton Advanced dans la navigation
- **App.jsx** : Gestion état advancedSettings, persistance localStorage
- **api.js** : Transmission paramètres advanced dans sendMessageStream
- **main.py** : SendMessageRequest accepte advanced config optionnel
- **openrouter.py** : Routing intelligent get_model_source/get_chairman_source
- **council.py** : Propagation advanced_config à toutes les fonctions
- **config.py** : Ajout LMSTUDIO_BASE_URL par défaut

### Features Implemented
- [x] Panneau Advanced accessible depuis la sidebar (icône ⚙️)
- [x] Sélection de mode : OpenRouter / LM Studio / Hybrid
- [x] Badge visuel du mode actif dans le header
- [x] Configuration OpenRouter : Override clé API optionnel
- [x] Configuration LM Studio : URL serveur + nom du modèle
- [x] Bouton "Test Connection" pour LM Studio
- [x] Mode Hybrid : Assignation source par modèle + Chairman
- [x] Persistance localStorage (llm_council_advanced_settings)
- [x] Compatibilité ascendante (fonctionne sans paramètre advanced)

## Prioritized Backlog

### P0 (Bloquant)
- Aucun

### P1 (Important)
- Sauvegarder paramètres advanced par conversation
- Afficher source utilisée dans les résultats de chaque stage

### P2 (Nice to have)
- Support plusieurs serveurs LM Studio en mode hybrid
- Estimation coûts/latence par source
- Import/export configuration

## Next Tasks
- Tester avec un vrai serveur LM Studio local
- Documenter l'utilisation dans le README
- Ajouter validation API key OpenRouter inline
