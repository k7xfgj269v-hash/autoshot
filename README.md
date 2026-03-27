# Autoshot — KI-gestützte Video-Automatisierungspipeline

Texteingabe → KI-Skript + Bildgenerierung + Sprachsynthese → fertiges Video

> Mehrere KI-Modelle koordiniert in einer vollautomatischen Pipeline: Sprachmodell, Bildgenerierung, TTS und Videorendering arbeiten nahtlos zusammen.

---

## Funktionsübersicht

| Modus | Eingabe | Pipeline |
|-------|---------|----------|
| **Modus A** (Vollautomatisch) | Textbeschreibung | LLM → Skript · Bildgenerierung (8 Szenen) · TTS-Vertonung · Videorendering |
| **Modus B** (Material-Optimierung) | Bestehendes Videomaterial | FFmpeg-Extraktion · Whisper-Transkription · Vision-LLM-Analyse · Neugenerierung |

---

## Technologie-Stack

| Komponente | Technologie |
|------------|-------------|
| Orchestrierung | Python + Gradio |
| Sprachmodell | DeepSeek API (austauschbar) |
| Bildgenerierung | Qwen Image Turbo / kompatible APIs |
| Sprachsynthese | Microsoft Edge TTS |
| Spracherkennung | OpenAI Whisper (lokal) |
| Videorendering | Remotion (React-basiert) + FFmpeg |
| Persistenz | SQLite |

---

## Architektur

```
Texteingabe
    │
    ▼
┌─────────────────────────────────────────┐
│              Pipeline-Orchestrator       │
│                                         │
│  ┌──────────┐   ┌──────────────────┐   │
│  │  LLM     │   │  Bildgenerator   │   │
│  │ (Skript) │   │  (8 Szenen,      │   │
│  └──────────┘   │   parallel)      │   │
│       │         └──────────────────┘   │
│       ▼                  │              │
│  ┌──────────┐            │              │
│  │   TTS    │◄───────────┘              │
│  │ (Audio)  │                           │
│  └──────────┘                           │
│       │                                 │
│       ▼                                 │
│  ┌──────────┐                           │
│  │ Remotion │  React-Videorendering     │
│  │ Renderer │                           │
│  └──────────┘                           │
└─────────────────────────────────────────┘
    │
    ▼
Fertiges Video (1080×1920, 30fps)
```

---

## Schnellstart

### 1. API-Schlüssel konfigurieren

```bash
cp .env.example .env
```

`.env` befüllen:

```env
LLM_API_KEY=your_key_here
IMAGE_API_KEY=your_key_here
```

### 2. Python-Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 3. Remotion-Abhängigkeiten installieren

```bash
cd remotion
npm install
```

> Voraussetzung: Node.js 18+

### 4. Starten

```bash
python main.py
```

Browser öffnet sich unter **http://localhost:7860**

---

## Videoausgabe-Spezifikationen

| Parameter | Wert |
|-----------|------|
| Auflösung | 1080 × 1920 (Hochformat 9:16) |
| Framerate | 30 fps |
| Render-Threads | 4 (parallel) |
| Rendering | SwiftShader (CPU, keine GPU erforderlich) |

---

## Abhängigkeiten

| Bibliothek | Verwendung |
|------------|------------|
| `gradio` | Web-UI |
| `openai` | LLM-API-Client (kompatibel) |
| `edge-tts` | Sprachsynthese |
| `openai-whisper` | Lokale Spracherkennung |
| `ffmpeg-python` | Video-/Audioverarbeitung |
| `Remotion` (npm) | React-Videorendering |

---

## Erweiterbarkeit

Die Pipeline ist modular aufgebaut — jede Komponente (LLM, Bildgenerator, TTS) kann durch kompatible Alternativen ersetzt werden:

- **LLM**: OpenAI, lokales Ollama, beliebige OpenAI-kompatible API
- **Bildgenerierung**: Stable Diffusion, DALL-E, Midjourney API
- **TTS**: ElevenLabs, lokale Modelle, Azure TTS

---

<details>
<summary>English</summary>

# Autoshot — AI-Powered Video Automation Pipeline

Text input → AI script + image generation + voice synthesis → finished video

A multi-model coordination pipeline: language model, image generation, TTS, and video rendering working together automatically.

**Modes:**
- **Mode A**: Full automation — text description → script → 8 scene images → voiceover → rendered video
- **Mode B**: Material enhancement — existing footage → Whisper transcription → Vision LLM analysis → regenerated video

**Stack:** Python + Gradio · DeepSeek/OpenAI-compatible LLM · Qwen Image · Edge TTS · Whisper · Remotion + FFmpeg · SQLite

See German section above for full documentation.

</details>
