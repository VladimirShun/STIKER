# ai-server.py — запуск локально: python ai-server.py
# На Render: Build: pip install -r requirements.txt | Start: gunicorn ai-server:app
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from urllib.request import Request, urlopen

app = Flask(__name__)
CORS(app)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen3-30b-a3b:free"  # запасной: "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_EDIT = (
    "Ты — ИИ-редактор коллажа со стикерами. Пользователь даёт команду на русском. "
    "Ты возвращаешь ТОЛЬКО валидный JSON без пояснений, вида:\n"
    '{"actions": ['
    '{"op":"move","id":1,"x":100,"y":200},'
    '{"op":"resize","id":1,"w":120,"h":120},'
    '{"op":"add","type":"glasses","x":50,"y":0,"w":100,"h":80},'
    '{"op":"remove","id":2}'
    "]}\n"
    "Типы стикеров: glasses, ears, beard, belt, hat. "
    "x,y — левый верхний угол в пикселях, w,h — размер. Не выходи за холст. "
    "id нумеруются с 0 по порядку списка стикеров. "
    "Команды типа 'надень очки', 'поставь уши', 'убери ремень', 'перенеси бороду вправо', "
    "'сделай уши больше' — понятны. Непонятную команду выполняй пустым массивом: {\"actions\":[]}."
)

SYSTEM_CHAT = (
    "Ты — Босс-кактус, весёлый колючий герой сайта об оранжерее. "
    "Отвечай коротко, дружелюбно, с юмором, иногда вставляй эмодзи 🌵. Говори по-русски."
)


def call_model(messages, max_tokens=400):
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens}
    req = Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
        },
    )
    with urlopen(req, timeout=60) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def clean_json(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    return t.strip()


@app.route("/edit", methods=["POST"])
def edit():
    data = request.get_json(silent=True) or {}
    command = (data.get("command") or "").strip()
    stickers = data.get("stickers", [])
    canvas = data.get("canvas", {})
    if not command:
        return jsonify({"error": "пустая команда"}), 400
    user_msg = (
        "Холст: " + str(canvas.get("w", 800)) + "x" + str(canvas.get("h", 600)) + ". "
        "Стикеры сейчас (id по порядку): " + json.dumps(stickers, ensure_ascii=False) + ". "
        "Команда: " + command
    )
    try:
        answer = call_model(
            [{"role": "system", "content": SYSTEM_EDIT},
             {"role": "user", "content": user_msg}]
        )
        return jsonify(json.loads(clean_json(answer)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages") or []
    if not messages:
        return jsonify({"error": "пустой диалог"}), 400
    try:
        answer = call_model(
            [{"role": "system", "content": SYSTEM_CHAT}] + messages[-12:],
            max_tokens=250,
        )
        return jsonify({"reply": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
