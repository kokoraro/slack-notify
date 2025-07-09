# Uptime Robot Bot

This is a Slack bot to monitor your site using the Uptime Robot API.


**/check-sites-in-db**

Check the status of all sites in the database.
<br><br>

**/monitor-site [site | api-key]** (eg. `/monitor-site subdomain.example.com | yourapikey-goeshere`)

Add the site to the database of sites to be monitored.
<br><br>

**/remove-monitor-site [site | api-key]** (eg. `/remove-monitor-site subdomain.example.com | yourapikey-goeshere`)

Remove the site from the database of sites to stop monitoring.
<br><br>
For all commands you can use any type of api key you like but if you use a read only api key anyone who finds it wouldn't be able to make any changes to your monitors.

## Installation
To set up the bot, clone the repository. Then install npm packages by running `npm install`. Next create a python venv named `venv` in the root directory of the folder using `python -m venv venv`. Activate the venv (`. ./venv/bin/activate`) and install the required libraries from the requirments.txt file in the root folder using `pip install -r ./requirments.txt`.

Next create a .env file in the `app` directory. These are the things you need to include in the file:
```
PORT=
DEBUG_MODE=

DB_PATH=

SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=
```
Setting the DEBUG_MODE to True will enable a bunch of print statements for logging. The rest of the variables should be self explanitory.

The app uses a sqlite DB that you will need to create with this schema to store the sites that should be monitored:
```
CREATE TABLE monitor_sites (
	id INTEGER PRIMARY KEY,
	time_added DATETIME DEFAULT CURRENT_TIMESTAMP,
	user_id text,
	channel_id TEXT,
	website TEXT,
	api_key TEXT,
	last_status TEXT
);
```
The final thing to add is the `logs` directory or you can dissable logging by removing the apropriate lines from the `start.sh` file.

Verify that the paths in the `start.sh` file are correct and then you should be able to start the app using it.
