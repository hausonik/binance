from flask import Flask, jsonify
import os
from balances import get_balances
from open_trades import get_open_trades
from strategy import scan_signals
from utils import load_env

load_env()

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "ok", "msg": "Binance trading bot server running"})

@app.route("/balances")
def balances():
    return jsonify(get_balances())

@app.route("/open_trades")
def open_trades():
    return jsonify(get_open_trades())

@app.route("/scan_signals")
def scan():
    results = scan_signals()
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
