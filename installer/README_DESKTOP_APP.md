# LLM Council Desktop App

<p align="center">
  <img src="assets/logo.png" alt="LLM Council Logo" width="120">
</p>

<p align="center">
  <strong>A Multi-LLM Deliberation System for Windows</strong><br>
  Get answers from multiple AI models that debate and synthesize the best response
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

## What is LLM Council?

LLM Council is a unique AI chat application that consults **multiple Large Language Models** (like GPT-4, Claude, Gemini, Grok) simultaneously, has them **rank each other's responses**, and then **synthesizes the best answer** from their collective wisdom.

Instead of relying on a single AI's perspective, you get the combined intelligence of an entire council of AIs!

### The 3-Stage Process

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR QUESTION                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: Individual Responses                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│  │  GPT-4  │ │ Claude  │ │ Gemini  │ │  Grok   │               │
│  │ Answer  │ │ Answer  │ │ Answer  │ │ Answer  │               │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: Peer Ranking (Anonymized)                              │
│  Each model ranks the other responses without knowing who        │
│  wrote them. This eliminates bias and ensures fair evaluation.   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: Chairman Synthesis                                     │
│  A designated "Chairman" model combines all insights and         │
│  rankings to produce the final, comprehensive answer.            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FINAL ANSWER                                                    │
│  The best synthesized response from your AI council              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

### 🤖 Multi-Model Consultation
- Query **30+ AI models** from OpenAI, Anthropic, Google, Meta, xAI, and more
- Select which models participate in your council
- Add custom models as they become available

### 📄 Document Upload & Context
- Upload **PDF, Word, PowerPoint, Text files, and Images**
- Automatic text extraction from documents
- **Vision AI support** for images (charts, screenshots, diagrams)
- Include document context in your questions
- Manage multiple documents per conversation

### 🔍 Vision AI for Images
- Upload trading charts, screenshots, or any images
- Images are sent directly to vision-capable AI models
- No OCR needed - AI understands visual content directly
- Works with GPT-4V, Claude 3, Gemini Vision models

### ⚙️ Easy Configuration
- **No Python installation required** - everything is bundled
- Simple web-based settings interface
- Secure API key storage
- Customizable model selection

### 💾 Local Data Storage
- All conversations saved locally
- Documents stored securely on your machine
- Export and backup your data
- Privacy-focused - your data stays on your computer

### 🚀 One-Click Launch
- Desktop shortcut for quick access
- Automatic server startup
- Browser opens automatically
- System tray support (optional)

---

## Installation

### System Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit)
- **Disk Space:** ~500 MB
- **RAM:** 4 GB minimum
- **Internet:** Required for AI model API calls
- **Browser:** Any modern browser (Chrome, Firefox, Edge)

### Download & Install

1. **Download** the installer: `LLMCouncil-Setup-2.0.0.exe`

2. **Run** the installer (you may need to click "More info" → "Run anyway" if Windows SmartScreen appears)

3. **Follow** the installation wizard:
   - Accept the license agreement
   - Choose installation location (default: `C:\Program Files\LLM Council`)
   - Select additional options (desktop shortcut, start menu)

4. **Complete** the installation

5. **Launch** LLM Council from:
   - Desktop shortcut, or
   - Start Menu → LLM Council

---

## Quick Start

### Step 1: Get an OpenRouter API Key

LLM Council uses [OpenRouter](https://openrouter.ai) to access multiple AI models through a single API key.

1. Go to **[openrouter.ai/keys](https://openrouter.ai/keys)**
2. Sign up or log in
3. Click **"Create Key"**
4. Copy your API key (starts with `sk-or-...`)

> 💡 **Tip:** OpenRouter offers free credits for new users! You can also add credits via credit card or crypto.

### Step 2: Configure LLM Council

1. **Launch** LLM Council (double-click the desktop shortcut)
2. Wait for the browser to open (usually 3-5 seconds)
3. Click **"Go to Settings"** or the **Settings** button in the sidebar
4. In the **API Settings** tab:
   - Paste your OpenRouter API key
   - Click **"Validate"** to verify it works
   - Click **"Save API Key"**

### Step 3: Start Chatting!

1. Click **"+ New Conversation"**
2. Type your question in the text box
3. Press **Enter** or click **Send**
4. Watch as the council deliberates and provides a synthesized answer!

---

## Usage

### Asking Questions

Simply type your question and press Enter. The council will:

1. **Collect responses** from all selected models (Stage 1)
2. **Rank the responses** anonymously (Stage 2)
3. **Synthesize** the final answer (Stage 3)

Each stage is shown progressively, so you can see the deliberation process.

### Expanding Responses

Click on any stage section to expand and view:
- Individual model responses
- Ranking explanations
- The full synthesis reasoning

### Uploading Documents

Add context to your questions by uploading documents:

1. **Drag & drop** files onto the chat area, or
2. Click the **📎 upload button** next to the text input

**Supported formats:**
- 📄 PDF documents
- 📝 Word documents (.docx)
- 📊 PowerPoint presentations (.pptx)
- 📃 Text files (.txt, .md)
- 🖼️ Images (.png, .jpg, .jpeg, .gif, .webp, .bmp, .tiff) - analyzed by vision AI

**Vision AI for Images:**
When you upload an image (like a trading chart), it will be:
1. Sent directly to vision-capable AI models (GPT-4V, Claude Vision, Gemini Vision)
2. Analyzed visually - no text extraction needed
3. The AI can understand patterns, trends, indicators, and visual elements

**Tips for best results with charts:**
- Use clear, high-resolution screenshots
- Ensure important elements are visible
- Include relevant time frames in the image
- Add context in your question about what you want analyzed

**Managing documents:**
- Click the **document icon** (top right) to open the document panel
- Toggle documents **on/off** to include/exclude from context
- **Preview** document content before sending
- **Delete** documents you no longer need

### Configuring Models

#### Selecting Council Members

1. Go to **Settings** → **Council Models** tab
2. Check the models you want in your council
3. Click **"Save Model Selection"**

**Recommended combinations:**
- **Balanced Council:** GPT-4o, Claude 3.5, Gemini 2.0, Grok 2
- **Budget Council:** GPT-4o-mini, Claude Haiku, Gemini Flash
- **Research Council:** GPT-4, Claude Opus, Gemini Pro

#### Selecting the Chairman

The Chairman model synthesizes the final answer from all responses.

1. Go to **Settings** → **Chairman Model** tab
2. Select a model from the dropdown
3. Click **"Save Chairman Selection"**

**Good Chairman choices:**
- GPT-4o (excellent synthesis)
- Claude 3.5 Sonnet (nuanced analysis)
- Gemini 2.0 Flash (fast and capable)

### Managing Conversations

- **New conversation:** Click "+ New Conversation"
- **Switch conversations:** Click on any conversation in the sidebar
- **Delete conversation:** Hover over a conversation and click the X button
- **Conversation titles:** Auto-generated from your first message

---

## Settings Reference

### API Settings
| Setting | Description |
|---------|-------------|
| OpenRouter API Key | Your API key from openrouter.ai |
| Validate | Test if the key is valid and working |

### Council Models
| Setting | Description |
|---------|-------------|
| Model Selection | Check/uncheck models to include in the council |
| Custom Model | Add models not in the default list |

### Chairman Model
| Setting | Description |
|---------|-------------|
| Chairman Selection | The model that synthesizes the final response |

### Advanced
| Setting | Description |
|---------|-------------|
| Theme | Light or dark mode (coming soon) |
| Data Location | Where conversations and documents are stored |

---

## Data Storage

All your data is stored locally on your computer:

```
%APPDATA%\LLM Council\data\
├── config.json           # Your settings and API key
├── conversations\        # Saved conversations
├── documents\            # Uploaded documents
└── document_registry.json # Document metadata
```

**Location:** `C:\Users\<YourName>\AppData\Roaming\LLM Council\data\`

### Backup Your Data

To backup your LLM Council data:
1. Open File Explorer
2. Type `%APPDATA%\LLM Council` in the address bar
3. Copy the entire `data` folder to your backup location

### Reset All Data

To start fresh:
1. Close LLM Council
2. Delete the `%APPDATA%\LLM Council` folder
3. Restart LLM Council

---

## Troubleshooting

### "Cannot connect to server"

**Cause:** The backend server isn't running.

**Solution:**
1. Close any open LLM Council windows
2. Re-launch from the desktop shortcut
3. Wait for "Server is ready!" message

### "API Key not configured"

**Cause:** No OpenRouter API key has been set.

**Solution:**
1. Get a key from [openrouter.ai/keys](https://openrouter.ai/keys)
2. Go to Settings → API Settings
3. Paste and save your key

### "All models failed to respond"

**Causes:**
- Invalid API key
- No credits on OpenRouter account
- Internet connection issues

**Solutions:**
1. Validate your API key in Settings
2. Check your OpenRouter credit balance
3. Test your internet connection

### Browser doesn't open automatically

**Solution:**
1. Manually open your browser
2. Go to `http://localhost:8001`

### "Port 8001 already in use"

**Cause:** Another application is using port 8001.

**Solution:**
1. Find and close the other application, or
2. Restart your computer to free the port

### Server won't start (Permission Error)

**Cause:** Windows is blocking file creation.

**Solution:**
1. Make sure you're not running from a restricted folder
2. The app should store data in AppData (which is always writable)
3. Try running as Administrator (right-click → Run as administrator)

### Documents won't upload

**Causes:**
- File too large (max 50MB)
- Unsupported format

**Supported formats:** PDF, DOCX, TXT, RTF, PPTX, PNG, JPG, JPEG, MD

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift + Enter` | New line in message |
| Drag & Drop | Upload document |

---

## Cost & Usage

LLM Council uses **OpenRouter** for API access. Costs depend on:

- **Which models** you select (GPT-4 costs more than GPT-3.5)
- **How many models** are in your council
- **Message length** (tokens)

**Cost-saving tips:**
1. Use fewer council members for simple questions
2. Choose "mini" or "flash" model variants
3. Keep messages concise
4. Monitor usage at [openrouter.ai/usage](https://openrouter.ai/usage)

**Typical costs:**
- Simple question with 4 budget models: ~$0.01-0.02
- Complex question with 4 premium models: ~$0.10-0.30

---

## Privacy & Security

### Your Data
- All conversations stored **locally** on your computer
- Documents processed **locally** (text extraction)
- No data sent to our servers - only to AI providers via OpenRouter

### API Keys
- Stored locally in your AppData folder
- Only sent to OpenRouter for authentication
- Never logged or transmitted elsewhere

### AI Provider Privacy
- Queries are sent to AI providers (OpenAI, Anthropic, Google, etc.)
- Review each provider's privacy policy
- OpenRouter acts as a unified gateway

---

## Uninstalling

### Standard Uninstall
1. Open **Windows Settings** → **Apps**
2. Find **"LLM Council"**
3. Click **Uninstall**

### Complete Removal (including data)
1. Uninstall via Windows Settings
2. Delete `%APPDATA%\LLM Council` folder

---

## Building from Source

If you want to build the installer yourself:

### Prerequisites
- Windows 10/11 (64-bit)
- Node.js 18+
- Python 3.11+
- Inno Setup 6

### Build Steps

```powershell
# 1. Clone the repository
git clone https://github.com/YOUR_REPO/llm-council.git
cd llm-council

# 2. Setup embedded Python
cd installer/scripts
.\download_python.bat
cd ../..

# 3. Build frontend
cd frontend
npm install
npm run build
cd ..

# 4. Compile installer (requires Inno Setup)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\inno-setup\llm-council-installer.iss

# Output: installer/output/LLMCouncil-Setup-2.0.0.exe
```

See `installer/docs/BUILD_GUIDE.md` for detailed instructions.

---

## Support & Resources

- **OpenRouter Documentation:** [openrouter.ai/docs](https://openrouter.ai/docs)
- **Original LLM Council Project:** [github.com/karpathy/llm-council](https://github.com/karpathy/llm-council)
- **Report Issues:** [GitHub Issues](https://github.com/YOUR_REPO/llm-council/issues)

---

## Credits

- Original concept by [Andrej Karpathy](https://github.com/karpathy)
- Desktop app packaging and enhancements by LLM Council Contributors
- Built with Python, FastAPI, React, and Electron

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Enjoy consulting your AI Council! 🤖⚖️🤖</strong>
</p>
