# any given sunday

This github repo is meant to accompany my DevOpsDays Detroit 2015 Ignite talk.

If you have ansible installed, you should have all the prereqs required for
schedule.py

quick examples:

```sh
# venue for upcoming monday
ansible-playbook -i schedule.py playbook.yml --limit monday
```

```sh
# just primary (*-1) venues for upcoming sunday
ansible-playbook -i schedule.py playbook.yml --limit 'sunday,!*-2'
```

This is a very simple dynamic inventory example for ansible. 
This code reads in the schedule.yml file as an ansible inventory and
cross-references schedule.   It then generates dynamic inventory groups 
based on the upcoming monday, thursday and sunday games. 

files in this repo:

* schedule.py - python dynamic inventory script.  yaml parser.
* venues.yml - ansible inventory in yaml format.
* old_inventory.example - portion of a default ansible-style inventory
* playbook.yml - an ansible playbook that just prints out a hostname for each host

