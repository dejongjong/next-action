#!/usr/bin/env python

import os
import json
import requests

from datetime import datetime
from flask import Flask, jsonify, request

from next_action import next_action

app = Flask(__name__)

@app.route('/<token>')
def index(token):
    try:
        next_action(token)
    except Exception as e:
        return str(e)
        
    return 'Magic performed!'

app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
