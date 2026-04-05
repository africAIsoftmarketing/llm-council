# LLM Council - Windows Installer PRD

## Problem Statement
Le workflow GitHub Actions actuel produisait un seul fichier `LLM-Council.exe` (PyInstaller) sans installation propre. L'objectif était de créer un vrai installeur Windows avec Inno Setup.

## What's Been Implemented (Jan 2026)

### 1. `workflows/innobuild.yml` - REFACTORÉ
- **Job 1 (build-frontend)**: Build React/Vite → `frontend/dist/`
- **Job 2 (build-python)**: Python 3.11 embarqué + pip + packages (fastapi, uvicorn, pystray, etc.)
- **Job 3 (build-installer)**: Compilation `launcher.py` → `LLMCouncil.exe` + Inno Setup → `LLMCouncil-Setup-2.1.0.exe`
- **Job 4 (release)**: Création automatique de release GitHub sur tag `v*`

### 2. `installer/inno-setup/llm-council-installer.iss` - CORRIGÉ
- ✅ Chemin frontend corrigé: `frontend/dist` au lieu de `frontend`
- ✅ Raccourci bureau **coché par défaut** (retiré `Flags: unchecked`)
- ✅ Icônes pointant vers `LLMCouncil.exe` au lieu de `launch.bat`
- ✅ Support multilingue (anglais + français)
- ✅ Désinstalleur avec nettoyage

### 3. `launcher/launcher.py` - CRÉÉ
- Lanceur léger avec systray (pystray + Pillow)
- Démarre uvicorn en arrière-plan (fenêtre cachée)
- Ouvre le navigateur sur `http://localhost:8001`
- Menu systray: "Ouvrir LLM Council" / "Arrêter le serveur"
- Gestion d'erreur avec messagebox tkinter

### 4. `installer/docs/README_INSTALLER.txt` - CRÉÉ
- Page d'information affichée avant l'installation

## Architecture
```
C:\Program Files\LLM Council\
├── LLMCouncil.exe          # Launcher (systray)
├── icon.ico                # Application icon
├── backend/                # FastAPI code
├── frontend/dist/          # React built files
├── python/                 # Embedded Python 3.11
│   ├── python.exe
│   ├── Lib/site-packages/
│   └── Scripts/
├── scripts/                # Batch scripts (setup, stop)
├── config/
└── docs/
```

## Testing Status
- Workflow YAML: Syntaxe validée
- Launcher Python: Lint passé ✅
- Script Inno Setup: Syntaxe validée

## Next Action Items
- [ ] Pousser les changements sur GitHub (branche `master_innosetup_lmstudioserver`)
- [ ] Vérifier que le workflow GitHub Actions s'exécute correctement
- [ ] Tester l'installeur généré sur une machine Windows

## Backlog
- P1: Ajouter une vraie icône personnalisée (remplacer le fallback généré)
- P2: Option pour choisir le port au premier lancement
- P2: Auto-update depuis GitHub Releases
