#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WSGI entry point for Gunicorn on Render
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
