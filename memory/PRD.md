# LLM Council - Windows Installer PRD

## Problem Statement
Le workflow GitHub Actions produisait un `LLM-Council.exe` via PyInstaller (exécutable portable) au lieu d'un vrai installeur Windows. Le fichier `workflows/innobuild.yml` était ignoré car mal placé (GitHub n'exécute que `.github/workflows/`).

## What's Been Implemented (Jan 2026)

### Correction 1 : `.github/workflows/build.yml` - REMPLACÉ
Workflow complet Inno Setup (copié de la branche OCR qui fonctionne) :
- Build frontend React/Vite → `frontend/dist/`
- Télécharge Python 3.11 embeddable + pip + packages
- Prune des fichiers inutiles (tests, __pycache__)
- Génère icône placeholder si absente
- Installe Inno Setup 6.7.1
- Patch le .iss (supprime disk spanning)
- Compile → `installer/output/LLMCouncil-Setup-2.1.0.exe`
- Upload artifact + release GitHub sur tag v*

### Correction 2 : `installer/inno-setup/llm-council-installer.iss` - CORRIGÉ
- ✅ Raccourcis pointent vers `launch.bat` (pas de launcher PyInstaller)
- ✅ Raccourci bureau **coché par défaut** (sans `Flags: unchecked`)
- ✅ Chemin frontend corrigé : `frontend/dist`
- ✅ Support multilingue (anglais + français)

### Fichiers supprimés (nettoyage)
- `workflows/innobuild.yml` - Mauvais emplacement, ignoré par GitHub
- `launcher/launcher.py` - Plus nécessaire (launch.bat suffit)

## Architecture installée
```
C:\Program Files\LLM Council\
├── scripts/
│   ├── launch.bat          ← Raccourci bureau pointe ici
│   ├── setup.bat
│   └── stop_services.bat
├── backend/                # FastAPI code
├── frontend/dist/          # React built files
├── python/                 # Embedded Python 3.11
│   ├── python.exe
│   ├── Lib/site-packages/
│   └── Scripts/
├── config/
└── docs/
```

## Flux utilisateur
1. Double-clic sur `LLMCouncil-Setup-2.1.0.exe`
2. Wizard d'installation → `C:\Program Files\LLM Council\`
3. Raccourci "LLM Council" créé sur le bureau (coché par défaut)
4. Double-clic raccourci → `launch.bat` démarre uvicorn + ouvre navigateur

## Next Action Items
- [x] Remplacer `.github/workflows/build.yml`
- [x] Corriger `.iss` (raccourcis vers launch.bat)
- [x] Supprimer fichiers inutiles
- [ ] Pousser sur GitHub via "Save to Github"
- [ ] Vérifier exécution du workflow sur `master_innosetup_lmstudioserver`

## Backlog
- P1: Ajouter vraie icône personnalisée
- P2: Auto-update depuis GitHub Releases
