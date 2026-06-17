from openai import OpenAI
import os
import time

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

_translation_cache = {}


def has_cyrillic(text):
    text = text or ""
    return any("а" <= ch.lower() <= "я" for ch in text)


def translate_to_english(text):
    text = (text or "").strip()

    if not text:
        return ""

    if not has_cyrillic(text):
        return text

    if text in _translation_cache:
        return _translation_cache[text]

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional translator for restaurants, bars, cafes and food businesses. "
                            "Translate Bulgarian text to natural English. "
                            "Keep food names natural and short. "
                            "Return ONLY the translated text."
                        )
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ]
            )

            translated = response.choices[0].message.content.strip()

            if translated and not has_cyrillic(translated):
                _translation_cache[text] = translated
                return translated

        except Exception as e:
            print("TRANSLATOR ERROR:", e)

            if attempt == 0:
                time.sleep(1)

    return text