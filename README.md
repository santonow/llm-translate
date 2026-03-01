# Subtitle Translator (EN ➔ PL)
A Python script to extract, translate (via local LLM), and re-insert Polish subtitles into MP4 files.

## Prerequisites
- FFmpeg installed in your system PATH.

- Local LLM Server (e.g., llama-server) running at http://localhost:8080.
  - Recommended: `llama-server -hf speakleash/Bielik-11B-v3.0-Instruct-GGUF:Q4_K_M -c 4096 --port 8080`

## Usage

```bash
uvx --from https://github.com/santonow/llm-translate.git translate --help
```

#### Help:
```
uvx --from https://github.com/santonow/llm-translate.git translate --help
usage: translate.py [-h] [--test] [--limit LIMIT] [--subtitle-track SUBTITLE_TRACK] file

Translate subtitles of MP4 file from English to Polish using a locally hosted LLM.

positional arguments:
  file                  Path to MP4 file

options:
  -h, --help            show this help message and exit
  --test                Run test
  --limit LIMIT         Number of blocks to translate in test mode
  --subtitle-track SUBTITLE_TRACK
                        Subtitle track (default=0).
```

#### Full Translation:

```bash
uvx --from https://github.com/santonow/llm-translate.git translate movie.mp4
```

#### Test Mode (Preview only):

```bash
uvx --from https://github.com/santonow/llm-translate.git translate movie.mp4 --test --limit 10
```

## How it works
- Extracts English subtitles from the MP4 using FFmpeg.

- Chunks text by sentence for better context.

- Translates using an OpenAI-compatible API.

- Muxes the new Polish track back into a new file named movie_PL.mp4.

## Limitations
- Because of the rolling 2-sentence context, no parallelism is achieved, best to parallelize over the subtitle files if possible.
- Obvious gender issues (LLM doesn't see who's on the screen).