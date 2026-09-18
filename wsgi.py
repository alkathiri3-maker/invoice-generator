#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WSGI entry point for Render"""

from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "<h1>Hello from Invoice Generator!</h1>"

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
