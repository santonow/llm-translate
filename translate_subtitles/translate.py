import argparse
import asyncio
import os
import re
import subprocess

import httpx
import pysrt
from tqdm.asyncio import tqdm

# --- LLM CONFIGURATION ---
API_URL = "http://localhost:8080/v1/chat/completions"
MODEL_NAME = "bielik"
MAX_LINES_PER_CHUNK = 8
HISTORY_COUNT = 2


def get_sentence_chunks(subs):
    """Groups subtitles into chunks based on punctuation."""
    chunks = []
    current_chunk = []
    for sub in subs:
        current_chunk.append(sub)
        if (
            re.search(r'[.!?]["\)]?$', sub.text.strip())
            or len(current_chunk) >= MAX_LINES_PER_CHUNK
        ):
            chunks.append(current_chunk)
            current_chunk = []
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


async def translate_chunk(client, chunk_items, history=[]):
    """Translates a chunk with awareness of the previous translations."""
    source_text = "\n".join(
        [f"L{i}: {item.text}" for i, item in enumerate(chunk_items)]
    )
    prompt = f"""LINES TO TRANSLATE:
{source_text}
"""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": """You are a professional subtitle translator. Your task is to translate from English to Polish. 
INSTRUCTIONS:
1. Please return only translated lines, starting with L0, L1 etc.
2. Don't add any additional comments or explanations besides the translated lines.
3. Keep consistent gender and style. 
""",
            },
            *history,
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }
    try:
        response = await client.post(API_URL, json=payload, timeout=60.0)
        raw = response.json()["choices"][0]["message"]["content"].strip()
        lines = []
        for elem in list(re.split(r"L\d+:\s*", raw))[1:]:
            lines.append(elem.strip())
        return [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": raw},
        ], lines[: len(chunk_items)]
    except Exception as e:
        return [f"[Error: {e}]"] * len(chunk_items)


async def process_subtitles(input_srt, is_test, limit):
    subs = pysrt.open(input_srt)
    all_chunks = get_sentence_chunks(subs)
    chunks_to_process = all_chunks[:limit] if is_test else all_chunks

    history_buffer = []
    translated_data = []

    async with httpx.AsyncClient() as client:
        desc = "Tryb Testowy" if is_test else "Tłumaczenie"
        for i, chunk in enumerate(tqdm(chunks_to_process, desc=desc)):
            messages, translated_lines = await translate_chunk(
                client, chunk, history_buffer[-4:]
            )

            if is_test:
                print(f"\n--- BLOK {i + 1} ---")
                for original, trans in zip(chunk, translated_lines):
                    print(f"EN: {original.text.replace(chr(10), ' ')}")
                    print(f"PL: {trans}")

            translated_data.extend(translated_lines)

            # Update history for gender/context continuity
            history_buffer.extend(messages)
            if len(history_buffer) > HISTORY_COUNT:
                history_buffer.pop(0)

    if not is_test:
        for i, text in enumerate(translated_data):
            if i < len(subs):
                subs[i].text = text
        return subs
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Translate subtitles of MP4 file from English to Polish using a locally hosted LLM."
    )
    parser.add_argument("file", help="Path to MP4 file")
    parser.add_argument("--test", action="store_true", help="Run test")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of blocks to translate in test mode",
    )
    parser.add_argument(
        "--subtitle-track", type=int, default=0, help="Subtitle track (default=0)."
    )
    args = parser.parse_args()

    input_file = args.file
    name, _ = os.path.splitext(input_file)
    tmp_eng = f"{name}_temp_en.srt"
    tmp_pol = f"{name}_temp_pl.srt"
    output_file = f"{name}_PL.mp4"

    if not os.path.exists(input_file):
        print(f"[-] Error: {input_file} doesn't exist.")
        return

    print(f"[*] Extracting subtitles from {input_file}...")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-map",
            f"0:s:{args.subtitle_track}",
            tmp_eng,
        ],
        capture_output=True,
    )

    translated_subs = asyncio.run(process_subtitles(tmp_eng, args.test, args.limit))

    if not args.test and translated_subs:
        translated_subs.save(tmp_pol, encoding="utf-8")
        print(f"[*] Muxing into {output_file}...")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                input_file,
                "-i",
                tmp_pol,
                "-map",
                "0:v",
                "-map",
                "0:a",
                "-map",
                "1:0",
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-c:s",
                "mov_text",
                "-metadata:s:s:0",
                "language=pol",
                output_file,
            ],
            capture_output=True,
            check=True,
        )
        print("[*] Done!")
        if os.path.exists(tmp_eng):
            os.remove(tmp_eng)
        if os.path.exists(tmp_pol):
            os.remove(tmp_pol)
    elif args.test:
        print("\n[*] Test ended. No files were created.")
        if os.path.exists(tmp_eng):
            os.remove(tmp_eng)


if __name__ == "__main__":
    main()
