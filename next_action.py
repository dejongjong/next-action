#!/usr/bin/env python

# Imports
import os
import time
import sys
import requests
import uuid
import json

from datetime import datetime
from pprint import pprint


# Globals
incl_tasks = []
gets_na_label = []
blocked_label_ids = []

# Methods
def next_action(td_token):
    global incl_tasks, gets_na_label, blocked_label_ids
            
    # Load data
    projects, all_tasks, labels = load_todoist(td_token)
    
    # Find the label id's for waiting, delegated, tickler and next-action
    na_label_id = get_label_id_by_name('next-action', labels)
    blocked_label_ids= [
        get_label_id_by_name(x, labels) 
        for x in ['waiting', 'delegated', 'tickler']
    ]
    
    # Filter down to incomplete, actionable, non-ignored tasks
    incl_project_ids = [
        x['id'] for x in projects
        if x['name'][-2:] != " \xb7"
            and x['name'] != 'Inbox'
    ]
    incl_tasks = [
        x for x in all_tasks
        if x['completed'] == False
            and x['content'][:2]  != "* "
            and x['content'][-2:] != " \xb7"
            and x['project_id'] in incl_project_ids
    ]
    
    # Keep a global list of next-action tasks
    gets_na_label = []
    
    # Iterate over relevant projects
    for project in [x for x in projects if x['id'] in incl_project_ids]:
        
        # Find the top-level
        matched_tasks = [
            x for x in incl_tasks
            if x['project_id'] == project['id']
                and x.get('parent_id') is None
        ]
        if len(matched_tasks) == 0:
            continue
        else:
            matched_tasks.sort(key=lambda x: x['order'])
        
        # Take only the first task if this is a serial project
        if project['name'][-2:] != "::":
            matched_tasks = matched_tasks[0:1]
            
        # Handle each task
        for task in matched_tasks:
            find_next_action(task)
        
    # Let tasks get or lose their next-action label
    has_na_label = [
        x for x in all_tasks 
        if na_label_id in x['label_ids']
    ]
    for task in has_na_label:
        if not task in gets_na_label:
            print("Removing label for %s" % task['content'])
            label_ids = [
                x for x in task['label_ids']
                if x != na_label_id
            ]
            update_task(task, {'label_ids': label_ids}, td_token)
        
    for task in gets_na_label:
        if not task in has_na_label:
            print("Adding label for %s" % task['content'])
            label_ids = [*task['label_ids'], na_label_id]
            update_task(task, {'label_ids': label_ids}, td_token)
        


def load_todoist(td_token, types=['projects', 'tasks', 'labels']):
	return tuple(
		requests.get("https://api.todoist.com/rest/v1/%s" % x, 
		             headers={"Authorization": "Bearer %s" % td_token}).json()
		            
		for x in types
	)

	
def get_label_id_by_name(name, labels):
    label_ids = [x['id'] for x in labels if x['name'] == name]
    
    if len(label_ids) == 0:
        return None
    else:
        return label_ids[0]


def find_next_action(task):
    global incl_tasks, gets_na_label, blocked_label_ids
    
    # If this is a waiting or delegated task, then this is 
    # not a next action
    if any(x in task['label_ids'] for x in blocked_label_ids):
        return False
        
    # Find any sub tasks
    sub_tasks = [
        x for x in incl_tasks 
        if x.get('parent_id') == task['id']
    ]
    sub_tasks.sort(key=lambda x: x['order'])
    
    # If there are no sub tasks, then this is a next action
    if len(sub_tasks) == 0:
        gets_na_label.append(task)
        return True
    
    # Otherwise, iterate over the sub tasks
    else:
        if task['content'][-2:] != "::":
            find_next_action(sub_tasks[0])
        
        else:
            for sub_task in sub_tasks:
                find_next_action(sub_task)
        

def update_task(task, updates, td_token):
    requests.post(   
        url="https://api.todoist.com/rest/v1/tasks/%d" % task['id'],
        data=json.dumps(updates),
        headers={
            "Content-Type": "application/json",
            "X-Request-Id": str(uuid.uuid4()),
            "Authorization": "Bearer %s" % td_token
        }
    )
    
