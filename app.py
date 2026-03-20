"""
Flask web app - UI only.
Reads DB, queues outgoing SMS, deletes records.
Does NOT touch serial port.
"""
from flask import Flask, redirect, render_template, request, url_for

from config import DELETE_IMPORTED_SMS, SERIAL_PORT
from sms_db import delete_sms_by_id, init_db, list_outbox, list_sms, queue_sms, reset_outbox_to_queue

app = Flask(__name__)


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
    for sid in request.form.getlist("sms_ids"):
        try:
            delete_sms_by_id(int(sid))
        except ValueError:
            pass
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
