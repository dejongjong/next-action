#!/usr/bin/env python

import os
import time
import sys
import requests
import uuid
import json
import todoist
from datetime import datetime
from flask import Flask, jsonify, request

def next_action(api_token):

	# PART 1: SYNC DATA
	# -----------------

	# Connect to the sync API
	api = todoist.TodoistAPI(api_token)
	api.sync()

	# Obtain all completed tasks (used for sorting projects) via a separate api
	req             = requests.get("https://api.todoist.com/sync/v8/completed/get_all", params={'token': api_token})
	sync            = req.json()
	completed_tasks = sync['items']

	# Load projects, tasks and labels via the old rest API
	projects = requests.get("https://api.todoist.com/rest/v1/projects", headers={"Authorization": "Bearer %s" % api_token}).json()
	tasks = requests.get("https://api.todoist.com/rest/v1/tasks", headers={"Authorization": "Bearer %s" % api_token}).json()
	labels = requests.get("https://api.todoist.com/rest/v1/labels", headers={"Authorization": "Bearer %s" % api_token}).json()


	# PART 2: REORDER PROJECTS
	# ------------------------
 
  ## Add a 'last_completed' field to each project
	#for project in projects:

	#	# Get all completed project tasks (can be none), and find the last completed date
	#	project_tasks  = [x for x in completed_tasks if x['project_id']==project['id']]
	#	last_completed = '1900-01-01'

	#	for task in project_tasks:
	#		if task['completed_date'] > last_completed:
	#			last_completed = task['completed_date']
				
	#	project['last_completed'] = last_completed


	# focus_projects = [x for x in projects if x['color'] == 32]
	# child_order = 1

	#for project in sorted(focus_projects, key=lambda x: x['last_completed']):
	#	project_api = api.projects.get_by_id(project['id'])
	#	project_api.reorder(child_order=child_order)
	#	print(f"order {child_order}: {project['name']}")
	#	child_order+=1

	#api.commit()


	# PART 3: LABEL NEXT-ACTIONS
	# --------------------------

	# Filter for projects that have no exclude sign
	projects = [x for x in projects if x["name"][-2:] != " \xb7"]

	# Find the labels ids of certain important labels
	na_label_id = [x for x in labels if x["name"] == "next-action"][0]["id"]
	wf_label_id = [x for x in labels if x["name"] == "waiting"][0]["id"]
	dl_label_id = [x for x in labels if x["name"] == "delegated"][0]["id"]
	
	# Keep a list of next actions and tasks that are over 90 days old
	next_actions = []

	# Function for finding waiting or future tasks
	def is_waiting_or_future(task):
		
		# Find the number of days until the due date
		if 'due' in task.keys():
			date_diff = (datetime.strptime(task['due']['date'], '%Y-%m-%d') 
									- datetime.now())
			days_until_due = date_diff.days
		else:
			days_until_due = None
			
		# Find the waiting label and determine if tasks is far away
		has_wf_label = wf_label_id in task["label_ids"]
		has_dl_label = dl_label_id in task["label_ids"]
		is_in_future = days_until_due != None and days_until_due > 1
				
		return (has_wf_label or has_dl_label or is_in_future)

		
	# Recursive function for processing a list of tasks
	def process_tasks(tasks, project_tasks, is_parallel=False):
		
		# Iterate over the tasks in their order as presented in
		# todoist
		for task in sorted(tasks, key=lambda x: x["order"]):
			
			# Find open sub tasks 
			open_sub_tasks = [x for x in project_tasks if "parent" in x.keys() and x["parent"] == task["id"] and x["completed"] == False]
			
			# Ignore uncheckable tasks with no sub tasks
			if len(open_sub_tasks) == 0 and task["content"][0:2] == "* ":
				continue
			
			# Only handle tasks that are not waiting and not too far in the future
			if not is_waiting_or_future(task): 
				
				# Make this a next action if there are no sub tasks
				if len(open_sub_tasks) == 0:
					print("next action: " + task['content'])
					next_actions.append(task)
		
				# Handle sub tasks
				else:
					
					# Determine task type
					if (task["content"][-2:] == "::"):
						subtask_is_parallel = True
					else:
						subtask_is_parallel = False
			
					# Call this function recursively
					process_tasks(open_sub_tasks, project_tasks, subtask_is_parallel)
			
			# Only process the next task if this is a serial project
			if not is_parallel:
				break


	# Iterate over projects
	for project in projects:
		
		# Determine the project type
		if project["name"][-2:] == "::":
			project_type = "parallel"
		else:
			project_type = "serial"
			
		# Extract the open top-level tasks for this project and exclude
		# tasks that are marked exclude
		project_tasks = [x for x in tasks if x["project_id"] == project["id"]]
		open_tasks    = [x for x in project_tasks if x["completed"] == False and "parent" not in x.keys() and x["content"][-2:] != u" \xb7"]
		
		# Iterate over the tasks in their order as presented in
		# todoist
		process_tasks(open_tasks, project_tasks, project_type=="parallel")
		

	# Find out which tasks should be updated
	old_next_actions = [x for x in tasks if na_label_id in x["label_ids"]]
	remove_na_label = [x for x in old_next_actions if x not in next_actions]
	add_na_label = [x for x in next_actions if x not in old_next_actions]


	# Update the tasks
	for task in remove_na_label + add_na_label:
		if task in remove_na_label:
			task["label_ids"].remove(na_label_id)
		elif task in add_na_label:
			task["label_ids"].append(na_label_id)
		
		requests.post(
			"https://api.todoist.com/rest/v1/tasks/%d" % task["id"],
			data = json.dumps({
				"label_ids": task["label_ids"]
			}),
			headers={
				"Content-Type": "application/json",
				"X-Request-Id": str(uuid.uuid4()),
				"Authorization": "Bearer %s" % api_token
			})


app = Flask(__name__)

@app.route('/<api_token>')
def index(api_token):
  try:
    next_action(api_token)
  except Exception as e:
    return str(e)
  
  return 'Magic performed!'

app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
