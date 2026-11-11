import os
import ast
import math
import operator
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

API = f"https://chat.gde.wtf/botapi/{TOKEN}"

calculations = {}

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def api(method, data):
    r = requests.post(
        f"{API}/{method}",
        json=data,
        timeout=15
    )
    r.raise_for_status()
    result = r.json()

    if not result.get("ok"):
        raise RuntimeError(str(result))

    return result


def calculate(expression):
    if not expression or len(expression) > 100:
        raise ValueError("Некорректное выражение")

    tree = ast.parse(expression, mode="eval")

    def calc(node):
        if isinstance(node, ast.Expression):
            return calc(node.body)

        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float):
                raise ValueError()
            return node.value

        if isinstance(node, ast.BinOp):
            op = OPS.get(type(node.op))
            if op is None:
                raise ValueError()
            return op(calc(node.left), calc(node.right))

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.UAdd):
                return calc(node.operand)
            if isinstance(node.op, ast.USub):
                return -calc(node.operand)
            raise ValueError()

        raise ValueError()

    result = calc(tree)

    if not math.isfinite(result) or abs(result) > 1e100:
        raise ValueError()

    return result


def keyboard():
    rows = [
        ["7", "8", "9", "÷"],
        ["4", "5", "6", "×"],
        ["1", "2", "3", "−"],
        ["0", ".", "⌫", "+"],
        ["C", "=", "Закрыть"]
    ]

    return {
        "inline_keyboard": [
            [{"text": b, "data": "calc:" + b} for b in row]
            for row in rows
        ]
    }


def show(chat_id, message_id=None):
    expression = calculations.get(chat_id, "")

    data = {
        "chat_id": chat_id,
        "text": (
            "🧮 КАЛЬКУЛЯТОР\n\n"
            f"Выражение: {expression or '0'}"
        ),
        "reply_markup": keyboard()
    }

    if message_id is None:
        api("sendMessage", data)
    else:
        data["message_id"] = message_id
        api("editMessageText", data)


def handle_message(message):
    chat_id = str(message["chat"]["id"])

    if message.get("command") in ("start", "calc"):
        calculations[chat_id] = ""
        show(chat_id)


def handle_callback(cb):
    api("answerCallbackQuery", {
        "callback_query_id": cb["id"]
    })

    message = cb["message"]
    chat_id = str(message["chat"]["id"])
    message_id = message["message_id"]

    button = cb.get("data", "")

    if not button.startswith("calc:"):
        return

    button = button[5:]
    expression = calculations.get(chat_id, "")

    if button == "Закрыть":
        calculations.pop(chat_id, None)
        api("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Калькулятор закрыт."
        })
        return

    if button == "C":
        expression = ""

    elif button == "⌫":
        expression = expression[:-1]

    elif button == "=":
        try:
            result = calculate(expression)
            expression = format(result, ".10g")
        except ZeroDivisionError:
            expression = ""
            calculations[chat_id] = ""
            api("editMessageText", {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "❌ На ноль делить нельзя."
            })
            return
        except Exception:
            expression = ""
            calculations[chat_id] = ""
            api("editMessageText", {
                "chat_id": chat_id,
"message_id": message_id,
                "text": "❌ Ошибка вычисления."
            })
            return

    else:
        symbols = {
            "÷": "/",
            "×": "*",
            "−": "-"
        }
        if len(expression) < 100:
            expression += symbols.get(button, button)

    calculations[chat_id] = expression
    show(chat_id, message_id)


@app.route("/", methods=["GET"])
def home():
    return "GDE Calculator is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get(
        "X-Bot-Api-Secret-Token"
    ) != SECRET:
        return jsonify({"ok": False}), 403

    update = request.get_json(silent=True) or {}

    try:
        if "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception as error:
        print("Bot error:", error)

    return jsonify({"ok": True}), 200


@app.route("/register", methods=["GET"])
def register():
    result = api("setWebhook", {
        "url": WEBHOOK_URL,
        "secret_token": SECRET
    })
    return jsonify(result)
