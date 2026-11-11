import os
import ast
import math
import operator
import logging
import requests
from flask import Flask, request, jsonify
=====================================
НАСТРОЙКИ
=====================================
app = Flask(name)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)
TOKEN = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
API = f"https://chat.gde.wtf/botapi/{TOKEN}"
calculations = {}
=====================================
МАТЕМАТИЧЕСКИЕ ОПЕРАЦИИ
=====================================
OPS = {
ast.Add: operator.add,
ast.Sub: operator.sub,
ast.Mult: operator.mul,
ast.Div: operator.truediv,
}
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

        return op(
            calc(node.left),
            calc(node.right)
        )

    if isinstance(node, ast.UnaryOp):

        if isinstance(node.op, ast.UAdd):
            return calc(node.operand)

        if isinstance(node.op, ast.USub):
            return -calc(node.operand)

        raise ValueError()

    raise ValueError()

result = calc(tree)

if not math.isfinite(result):
    raise ValueError()

if abs(result) > 1e100:
    raise ValueError()

return result
=====================================
API МЕССЕНДЖЕРА
=====================================
def api(method, data):
response = requests.post(
    f"{API}/{method}",
    json=data,
    timeout=15
)

response.raise_for_status()

result = response.json()

if not result.get("ok"):
    raise RuntimeError(str(result))

return result
=====================================
КНОПКИ КАЛЬКУЛЯТОРА
=====================================
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
        [
            {
                "text": button,
                "data": "calc:" + button
            }
            for button in row
        ]
        for row in rows
    ]
}
=====================================
ПОКАЗ КАЛЬКУЛЯТОРА
=====================================
def show(chat_id, message_id=None):
expression = calculations.get(chat_id, "")

data = {
    "chat_id": chat_id,
    "text": (
        "🧮 КАЛЬКУЛЯТОР SOSUN\n\n"
        f"Выражение: {expression or '0'}"
    ),
    "reply_markup": keyboard()
}

if message_id is None:

    api("sendMessage", data)

else:

    data["message_id"] = message_id

    api("editMessageText", data)
=====================================
ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ
=====================================
def handle_message(message):
chat_id = str(message["chat"]["id"])

text = message.get("text", "").strip()

command = str(message.get("command", "")).lower()

# Запуск бота

if command in ("start", "/start", "calc", "/calc") or \
   text.split("@")[0] in ("/start", "/calc"):

    calculations[chat_id] = ""

    api("sendMessage", {
        "chat_id": chat_id,
        "text": (
            "Привет! 👋\n\n"
            "Я SOSUN — твой калькулятор.\n\n"
            "Можешь отправить мне пример:\n"
            "25+35\n"
            "100/5\n"
            "12*8\n\n"
            "Или напиши /calc, чтобы открыть калькулятор с кнопками."
        )
    })

    return

if not text:
    return

# Подготовка выражения

expression = text.replace(" ", "")

expression = expression.replace("×", "*")
expression = expression.replace("÷", "/")
expression = expression.replace("−", "-")

# Вычисление

try:

    result = calculate(expression)

    answer = format(result, ".10g")

    api("sendMessage", {
        "chat_id": chat_id,
"text": f"🧮 {text} = {answer}"
    })

except ZeroDivisionError:

    api("sendMessage", {
        "chat_id": chat_id,
        "text": "❌ На ноль делить нельзя!"
    })

except Exception as error:

    logger.warning("Calculation error: %s", error)

    api("sendMessage", {
        "chat_id": chat_id,
        "text": (
            "❌ Не удалось вычислить пример.\n\n"
            "Используй числа и знаки +, -, *, /."
        )
    })
=====================================
ОБРАБОТКА НАЖАТИЙ НА КНОПКИ
=====================================
def handle_callback(callback):
api("answerCallbackQuery", {
    "callback_query_id": callback["id"]
})

message = callback["message"]

chat_id = str(message["chat"]["id"])

message_id = message["message_id"]

button = callback.get("data", "")

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

elif button == "C":

    expression = ""

elif button == "⌫":

    expression = expression[:-1]

elif button == "=":

    try:

        result = calculate(expression)

        expression = format(result, ".10g")

    except ZeroDivisionError:

        calculations[chat_id] = ""

        api("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "❌ На ноль делить нельзя!"
        })

        return

    except Exception:

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
=====================================
ГЛАВНАЯ СТРАНИЦА
=====================================
@app.route("/", methods=["GET"])
def home():
return "SOSUN Calculator is running!"
=====================================
WEBHOOK
=====================================
@app.route("/webhook", methods=["POST"])
def webhook():
if request.headers.get(
    "X-Bot-Api-Secret-Token"
) != SECRET:

    logger.warning("Invalid webhook secret")

    return jsonify({
        "ok": False
    }), 403

update = request.get_json(silent=True) or {}

logger.info("Received update: %s", list(update.keys()))

try:

    if "message" in update:

        handle_message(update["message"])

    elif "callback_query" in update:

        handle_callback(update["callback_query"])

except Exception:

    logger.exception("Bot processing error")

return jsonify({
    "ok": True
}), 200
=====================================
РЕГИСТРАЦИЯ WEBHOOK
=====================================
@app.route("/register", methods=["GET"])
def register():
result = api("setWebhook", {
    "url": WEBHOOK_URL,
    "secret_token": SECRET
})

return jsonify(result)
=====================================
ЗАПУСК
=====================================
if name == "main":
app.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 10000))
)
