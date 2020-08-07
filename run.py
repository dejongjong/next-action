#!/usr/bin/env python

import os
from nextaction import next_action
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/<api_token>')
def index(api_token):
	next_action(api_token)
	return 'Magic performed!'

app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

