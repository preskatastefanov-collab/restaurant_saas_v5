from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def translate_to_english(text):
    text = (text or "").strip()

    if not text:
        return ""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional translator."
                        " Translate Bulgarian to natural English."
                        " Return ONLY the translated text."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return text