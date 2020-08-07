#!/usr/bin/env python

import time
import sys
import requests
import uuid
import json
import os


def next_action(api_token):
	# Use the Todoist API to find tasks that should be marked as next action
	
	# Load data
	projects = requests.get("https://api.todoist.com/rest/v1/projects", headers={"Authorization": "Bearer %s" % api_token}).json()
	tasks = requests.get("https://api.todoist.com/rest/v1/tasks", headers={"Authorization": "Bearer %s" % api_token}).json()
	labels = requests.get("https://api.todoist.com/rest/v1/labels", headers={"Authorization": "Bearer %s" % api_token}).json()
	
	# Filter for projects that have either the serial or parallel sign
	projects = [x for x in projects if x["name"][-2:] in ["\xb7\xb7", "::"]]
	na_label_id = [x for x in labels if x["name"] == "next-action"][0]["id"]
	wf_label_id = [x for x in labels if x["name"] == "waiting"][0]["id"]

	# Find next actions
	old_na_tasks = [x for x in tasks if na_label_id in x["label_ids"]]
	new_na_tasks = []

	for project in projects:
		if project["name"][-2:] == u"\xb7\xb7":
			project_type = "serial"
		elif project["name"][-2:] == "::":
			project_type = "parallel"
		
		# Extract the open top-level tasks for this project
		project_tasks = [x for x in tasks if x["project_id"] == project["id"]]
		open_tasks    = [x for x in project_tasks if x["completed"] == False and "parent" not in x.keys() and x["content"][-2:] != u" \xb7"]
		
		# Find tasks that are over 5 days old and not yet labeled '+5d
		old_tasks = [x for x in open_tasks if x["completed"] == False and (datetime.now() - datetime.strptime(x["created"], "%Y-%m-%dT%H:%M:%SZ")).days >= 2]
		
		# These are the rules:
		# - The next action is the open first task in the project that does not have
		#   the @waiting label nor is too far in the future
		# - Unless the task is a compound task (has subtasks), then the same 
		#   rules are applied to the first level of sub tasks
		for task in sorted(open_tasks, key = lambda x: x["order"]):
		
			open_sub_tasks = [x for x in tasks if "parent" in x.keys() and x["parent"] == task["id"] and x["completed"] == False]
		
			# Ignore uncheckable tasks with no sub tasks
			if len(open_sub_tasks) == 0 and task["content"][0:2] == "* ":
				continue
		
			# Handle non-compound tasks
			elif len(open_sub_tasks) == 0:
				if not wf_label_id in task["label_ids"]:
					new_na_tasks.append(task)
		
			# Handle compound tasks
			else:
				if (task["content"][-2:] == "::"):
					task_type = "parallel"
				else:
					task_type = "serial"
		
				for sub_task in sorted(open_sub_tasks, key = lambda x: x["order"]):
					if not wf_label_id in sub_task["label_ids"]:
						new_na_tasks.append(sub_task)
		
					if (task_type == "serial"):
						break
		
			if project_type == "serial":
				break

	# Find out which tasks should be updated
	remove_na_label = [x for x in old_na_tasks if x not in new_na_tasks]
	add_na_label = [x for x in new_na_tasks if x not in old_na_tasks]

	# Update the tasks
	for task in remove_na_label + add_na_label:
		if task in remove_na_label:
			task["label_ids"].remove(na_label_id)
		else:
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
