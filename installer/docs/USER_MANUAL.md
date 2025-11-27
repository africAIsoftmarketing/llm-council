# LLM Council User Manual

## Getting Started

Welcome to LLM Council! This application allows you to consult multiple AI models simultaneously and get a synthesized answer from their collective wisdom.

### First Launch

1. **Start the Application**
   - Double-click "LLM Council" on your desktop or Start Menu
   - The application will start the backend server automatically

2. **Configure Your API Key**
   - Click "Settings" in the sidebar
   - Get your API key from [openrouter.ai/keys](https://openrouter.ai/keys)
   - Paste your key and click "Validate"
   - Click "Save API Key"

3. **Start Chatting**
   - Click "+ New Conversation"
   - Type your question
   - Press Enter or click "Send"

---

## Features

### The 3-Stage Council Process

When you ask a question, LLM Council runs a 3-stage deliberation:

1. **Stage 1: Individual Responses**
   - Each council member (AI model) provides their answer
   - You can expand each response to see the full text

2. **Stage 2: Peer Ranking**
   - Each model reviews and ranks the other responses
   - Models don't know whose response they're ranking (anonymized)

3. **Stage 3: Chairman Synthesis**
   - The chairman model combines all insights
   - Creates a comprehensive final answer

### Document Upload

You can upload documents to provide context for your questions:

1. **Supported Formats**
   - PDF documents
   - Word documents (.docx)
   - Text files (.txt, .md)
   - PowerPoint presentations (.pptx)
   - Images (.png, .jpg, .jpeg, .gif, .webp, .bmp, .tiff)

2. **How to Upload**
   - Drag and drop files onto the chat area
   - Or click the upload button in the input area

3. **Managing Documents**
   - Click the document icon to open the document panel
   - Toggle documents on/off to include/exclude from context
   - Preview document content
   - Delete documents you no longer need

### OCR (Optical Character Recognition)

LLM Council includes built-in OCR capabilities to extract text from images:

1. **Automatic OCR**
   - When you upload an image file, OCR runs automatically
   - Text is extracted and made available for queries
   - Works with screenshots, photos of documents, scanned pages

2. **OCR Indicators**
   - Documents processed with OCR show a purple "OCR" badge
   - The preview shows "[OCR extracted from...]" header
   - You can see which OCR engine was used (EasyOCR or Tesseract)

3. **Best Practices for OCR**
   - Use clear, high-resolution images
   - Ensure text is readable and not blurry
   - Straight/flat document photos work best
   - Avoid heavy shadows or glare

4. **Supported Image Formats for OCR**
   - PNG (recommended)
   - JPEG/JPG
   - GIF
   - WebP
   - BMP
   - TIFF

### Settings

**API Settings**
- Enter and validate your OpenRouter API key
- View masked key when configured

**Council Models**
- Select which AI models participate in the council
- Choose from 30+ available models
- Add custom models if needed

**Chairman Model**
- Select which model synthesizes the final response
- Choose a model good at summarization

**Advanced Settings**
- Theme selection (light/dark)
- View storage location

---

## Tips & Best Practices

### Getting Better Results

1. **Be Specific** - Clear, detailed questions get better answers
2. **Provide Context** - Upload relevant documents or explain background
3. **Use Multiple Models** - More diverse council = more perspectives
4. **Choose Good Chairman** - GPT-4 or Claude work well as chairman

### Managing Costs

- OpenRouter charges per token used
- More models = higher cost per question
- Monitor your credits at openrouter.ai
- Use smaller models for simpler questions

---

## Troubleshooting

### "API Key Not Configured"
- Go to Settings > API Settings
- Enter and save your OpenRouter API key

### "All Models Failed to Respond"
- Check your internet connection
- Verify your API key is valid
- Check your OpenRouter credit balance

### Server Won't Start
- Check if port 8001 is already in use
- Restart the application
- Check Windows Firewall settings

### Documents Won't Upload
- Check file size (max 50MB)
- Ensure file format is supported
- Try a different file

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line in message |
| Ctrl+N | New conversation |

---

## Data & Privacy

- Conversations are stored locally in your AppData folder
- Documents are processed locally (text extraction)
- Only query text is sent to OpenRouter/AI providers
- API keys are stored locally on your machine

**Data Location:**
```
%APPDATA%\LLM Council\data\
```

---

## Getting Help

- **GitHub:** https://github.com/karpathy/llm-council
- **OpenRouter:** https://openrouter.ai/docs

---

*Version 2.0.0*
