#!/usr/bin/env python

import time
import sys
import requests
import uuid
import json
import os
from flask import Flask, jsonify, request
from datetime import datetime

delay = 5
app = Flask(__name__)

def get_subitems(items, parent_item=None):
    """Search a flat item list for child items."""
    result_items = []
    found = False
    if parent_item:
        required_indent = parent_item['indent'] + 1
    else:
        required_indent = 1
    for item in items:
        if parent_item:
            if not found and item['id'] != parent_item['id']:
                continue
            else:
                found = True
            if item['indent'] == parent_item['indent'] and item['id'] != parent_item['id']:
                return result_items
            elif item['indent'] == required_indent and found:
                result_items.append(item)
        elif item['indent'] == required_indent:
            result_items.append(item)
    return result_items

def perform_magic():
    try:
        print("Running...")

        # Load data
        projects = requests.get("https://beta.todoist.com/API/v8/projects", headers={"Authorization": "Bearer %s" % api_token}).json()
        tasks = requests.get("https://beta.todoist.com/API/v8/tasks", headers={"Authorization": "Bearer %s" % api_token}).json()
        labels = requests.get("https://beta.todoist.com/API/v8/labels", headers={"Authorization": "Bearer %s" % api_token}).json()

        # Filter for projects that have either the serial or parallel sign
        projects     = filter(lambda x: x["name"][-2:] in [u"\xb7\xb7", "::"], projects)
        na_label_id  = filter(lambda x: x["name"] == "next-action", labels)[0]["id"]
        wf_label_id  = filter(lambda x: x["name"] == "waiting", labels)[0]["id"]

        # Find next actions
        old_na_tasks = filter(lambda x: na_label_id in x["label_ids"], tasks)
        new_na_tasks = []

        for project in projects:
            if project["name"][-2:] == u"\xb7\xb7":
                project_type = "serial"
            elif project["name"][-2:] == "::":
                project_type = "parallel"
                
            project_tasks = filter(lambda x: x["project_id"] == project["id"], tasks)
            open_tasks   = filter(lambda x: x["indent"] == 1 and x["completed"] == False and x["content"][-2:] != u" \xb7", project_tasks)
            
            # These are the rules:
            # - The next action is the open first task in the project that does not have
            #   the @waiting label nor is too far in the future
            # - Unless the task is a compound task (has subtasks), then the same 
            #   rules are applied to the first level of sub tasks
            for task in open_tasks:

                sub_tasks      = get_subitems(project_tasks, task)
                open_sub_tasks = filter(lambda x: x["completed"] == False, sub_tasks)

                if len(open_sub_tasks) == 0 and task["content"][0:2] == "* ":
                    continue

                elif len(open_sub_tasks) == 0:
                    if not wf_label_id in task["label_ids"]:
                        new_na_tasks.append(task)
                else:
                    if (task["content"][-1] == "::"):
                        task_type = "parallel"
                    else:
                        task_type = "serial"

                    for sub_task in open_sub_tasks:
                        if not wf_label_id in sub_task["label_ids"]:
                            new_na_tasks.append(sub_task)

                        if (task_type == "serial"):
                            break

                if project_type == "serial":
                    break

        # Update at Todoist
        remove_na_label = [task for task in old_na_tasks if task not in new_na_tasks]
        add_na_label    = [task for task in new_na_tasks if task not in old_na_tasks]

        for task in remove_na_label + add_na_label:
            if task in remove_na_label:
                task["label_ids"].remove(na_label_id)
            else:
                task["label_ids"].append(na_label_id)
            
            requests.post(
                "https://beta.todoist.com/API/v8/tasks/%d" % task["id"],
                data = json.dumps({
                    "label_ids": task["label_ids"]
                }),
                headers={
                    "Content-Type": "application/json",
                    "X-Request-Id": str(uuid.uuid4()),
                    "Authorization": "Bearer %s" % api_token
                })
        
    except:
        print("Some error occured :(...")

@app.route('/')
def index():
    perform_magic()
    return 'Magic performed!'

app.run(host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)))
