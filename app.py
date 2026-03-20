import threading
from flask import Flask, jsonify, redirect, render_template, request, url_for

from config import DELETE_IMPORTED_SMS, SERIAL_BAUD, SERIAL_PORT
from listener import start_listener
from ml307 import ML307, ML307Error
from sms_db import delete_sms_by_id, init_db, list_outbox, list_sms, queue_sms, reset_outbox_to_queue

app = Flask(__name__)

_modem: ML307 = None
_modem_error: str = None
_start_lock = threading.Lock()


def get_modem_status():
    return {"started": _modem is not None, "error": _modem_error}


def init_modem():
    global _modem, _modem_error
    with _start_lock:
        if _modem is not None:
            return
        try:
            m = ML307(port=SERIAL_PORT, baud=SERIAL_BAUD)
            m.init()
            start_listener(m)
            _modem = m
            _modem_error = None
            print("🚀 Modem initialized and listener started")
        except ML307Error as e:
            _modem_error = str(e)
            print(f"❌ Modem init failed: {e}")


@app.route("/")
def index():
    outbox_rows = list_outbox(limit=100)
    sms_rows = list_sms(limit=100)
    inbox = [r for r in sms_rows if r[1] == "IN"]
    sent_log = [r for r in sms_rows if r[1] == "OUT"]
    stats = {
        "queue": sum(1 for r in outbox_rows if r[3] == "QUEUE"),
        "sent": sum(1 for r in outbox_rows if r[3] == "SENT"),
        "failed": sum(1 for r in outbox_rows if r[3] == "FAILED"),
    }
    return render_template(
        "index.html",
        outbox=outbox_rows[:30],
        inbox=inbox[:30],
        sent_log=sent_log[:30],
        stats=stats,
        modem=get_modem_status(),
        serial_port=SERIAL_PORT,
        auto_delete=DELETE_IMPORTED_SMS,
    )


@app.route("/send", methods=["POST"])
def send():
    number = request.form.get("number", "").strip()
    text = request.form.get("text", "").strip()
    if number and text:
        queue_sms(number, text)
    return redirect(url_for("index"))


@app.route("/resend/<int:outbox_id>", methods=["POST"])
def resend(outbox_id):
    reset_outbox_to_queue(outbox_id)
    return redirect(url_for("index"))


@app.route("/delete_sms", methods=["POST"])
def delete_sms():
    ids = request.form.getlist("sms_ids")
    for sid in ids:
        try:
            delete_sms_by_id(int(sid))
        except ValueError:
            pass
    return redirect(url_for("index"))


@app.route("/api/status")
def api_status():
    outbox_rows = list_outbox(limit=100)
    return jsonify({
        "modem": get_modem_status(),
        "queue": sum(1 for r in outbox_rows if r[3] == "QUEUE"),
        "sent": sum(1 for r in outbox_rows if r[3] == "SENT"),
        "failed": sum(1 for r in outbox_rows if r[3] == "FAILED"),
    })


if __name__ == "__main__":
    init_db()
    init_modem()
    app.run(host="0.0.0.0", port=5000, debug=False)
