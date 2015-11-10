#!/usr/bin/env python
#
# This is a work in progress.
#  - Rex Roof <rex.roof@blue-newt.com>
#
#  yaml parsing code taken from:
#  https://github.com/ansible/ansible/blob/v1.2/plugins/inventory/yaml.py
# 

from optparse import OptionParser
from pprint import pprint
import datetime
import json
import os
import pickle
import sys
import time
import urllib
import yaml

class Host():
    def __init__(self, name):
        self.name = name
        self.groups = []
        self.vars = {}
    def __repr__(self):
        return "Host('%s')"%(self.name)

    def set_variable(self, key, value):
        self.vars[key] = value

    def get_variables(self):
        result = {}
        for group in self.groups:
            for k,v in group.get_variables().items():
                result[k] = v
        for k, v in self.vars.items():
            result[k] = v
        return result

    def add_group(self, group):
        if group not in self.groups:
            self.groups.append(group)

class Group():
    def __init__(self, name):
        self.name = name
        self.hosts = []
        self.vars = {}
        self.subgroups = []
        self.parents = []
    def __repr__(self):
        return "Group('%s')"%(self.name)

    def get_hosts(self):
        """ List all hosts in this group, including subgroups """
        result = [ host for host in self.hosts ]
        for group in self.subgroups:
            for host in group.get_hosts():
                if host not in result:
                    result.append(host)
        return result

    def add_host(self, host):
        if host not in self.hosts:
            self.hosts.append(host)
            host.add_group(self)

    def add_subgroup(self, group):
        if group not in self.subgroups:
            self.subgroups.append(group)
            group.add_parent(self)

    def add_parent(self, group):
        if group not in self.parents:
            self.parents.append(group)

    def set_variable(self, key, value):
        self.vars[key] = value

    def get_variables(self):
        result = {}
        for group in self.parents:
            result.update( group.get_variables() )
        result.update(self.vars)
        return result

def find_group(name, groups):
    for group in groups:
        if name == group.name:
            return group

def parse_vars(vars, obj):
    ### vars can be a list of dicts or a dictionary
    if type(vars) == dict:
        for k,v in vars.items():
            obj.set_variable(k, v)
    elif type(vars) == list:
        for var in vars:
            k,v = var.items()[0]
            obj.set_variable(k, v)

def parse_yaml(yaml_hosts):
    groups = []

    all_hosts = Group('all')

    ungrouped = Group('ungrouped')
    groups.append(ungrouped)

    ### groups first, so hosts can be added to 'ungrouped' if necessary
    subgroups = []
    for entry in yaml_hosts:
        if 'group' in entry and type(entry)==dict:
            group = find_group(entry['group'], groups)
            if not group:
                group = Group(entry['group'])
                groups.append(group)

            if 'vars' in entry:
                parse_vars(entry['vars'], group)

            if 'hosts' in entry:
                for host_name in entry['hosts']:
                    host = None
                    for test_host in all_hosts.get_hosts():
                        if test_host.name == host_name:
                            host = test_host
                            break
                    else:
                        host = Host(host_name)
                        all_hosts.add_host(host)
                    group.add_host(host)

            if 'groups' in entry:
                for subgroup in entry['groups']:
                    subgroups.append((group.name, subgroup))

    for name, sub_name in subgroups:
        group = find_group(name, groups)
        subgroup = find_group(sub_name, groups)
        group.add_subgroup(subgroup)

    for entry in yaml_hosts:
        ### a host is either a dict or a single line definition
        if type(entry) in [str, unicode]:
            for test_host in all_hosts.get_hosts():
                if test_host.name == entry:
                    break
            else:
                host = Host(entry)
                all_hosts.add_host(host)
                ungrouped.add_host(host)

        elif 'host' in entry:
            host = None
            no_group = False
            for test_host in all_hosts.get_hosts():
                ### all hosts contains only hosts already in groups
                if test_host.name == entry['host']:
                    host = test_host
                    break
            else:
                host = Host(entry['host'])
                all_hosts.add_host(host)
                no_group = True

            if 'vars' in entry:
                parse_vars(entry['vars'], host)

            if 'groups' in entry:
                for test_group in groups:
                    if test_group.name in entry['groups']:
                        test_group.add_host(host)
                        all_hosts.add_host(host)
                        no_group = False

            if no_group:
                ungrouped.add_host(host)

    return groups, all_hosts


# taken from stackoverflow
#  function to figure out next monday, tuesday, etc.
def next_weekday(d, weekday): # 0 = Monday, 1=Tuesday, 2=Wednesday...
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)

# pull down schedule
def grab_schedule():
  # switch two letters to make this work
  url = 'http://feeds.fnl.com/feeds-rs/schedules.json'
  pickfile = "/tmp/schedule-cache.pickle"
  # if file is over an hour old
  if os.path.isfile(pickfile) and os.stat(pickfile).st_mtime > time.time() - 3600:
    data = pickle.load(open(pickfile, "rb"))
  else:
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    pickle.dump(data, open(pickfile, "wb"))
  return data

parser = OptionParser()
parser.add_option('-l', '--list', default=False, dest="list_hosts", action="store_true")
parser.add_option('-s', '--ssh', default=False, dest="ssh_out", action="store_true")
parser.add_option('-H', '--host', default=None, dest="host")
parser.add_option('-e', '--extra-vars', default=None, dest="extra")
parser.add_option('-b', '--base-date', default=None, 
                     help="date to operate from, form of YYYY-MM-DD", 
                     dest="base_date")
options, args = parser.parse_args()

base_dir = os.path.dirname(os.path.realpath(__file__))
hosts_file = os.path.join(base_dir, 'venues.yml')

if options.base_date:
  today = datetime.datetime.strptime(options.base_date, '%Y-%m-%d')
elif 'SCHED_BASE' in os.environ:
  today = datetime.datetime.strptime(os.environ['SCHED_BASE'], '%Y-%m-%d')
else:
  today = datetime.datetime.today()

schedule = grab_schedule()
games = []
for game in schedule['gameSchedules']:
  gamedate = datetime.datetime.fromtimestamp( game['isoTime']/1000 )
  games.append({'when':gamedate,
                'hometeam': game['homeTeamAbbr'],
                'siteid': game['site']['siteId'],
                'gameid': game['gameId']
               })

# find the next monday, thursday, sunday.
next_monday   = next_weekday(today, 0)
next_thursday = next_weekday(today, 3)
next_sunday   = next_weekday(today, 6)

# generate arrays for siteids for each of these dates from the schedule.
monday_siteids = [ g['siteid'] for g 
                   in games 
                   if g['when'].date() == next_monday.date() ]
thursday_siteids = [ g['siteid'] for g 
                     in games 
                     if g['when'].date() == next_thursday.date() ]
sunday_siteids = [ g['siteid'] for g 
                   in games 
                   if g['when'].date() == next_sunday.date() ]

with open(hosts_file) as f:
    yaml_hosts = yaml.safe_load( f.read() )

groups, all_hosts = parse_yaml(yaml_hosts)

if options.ssh_out == True:
  for h in all_hosts.get_hosts():
    v = h.get_variables()
    print "Host {}".format(h.name)
    if "ansible_ssh_host" in v: print "\tHostname {}".format(v["ansible_ssh_host"]) 
    if "ansible_ssh_user" in v: print "\tUser {}".format(v["ansible_ssh_user"])
    print ""
  sys.exit(0)

if options.list_hosts == True:
    result = {}
    result['_meta'] = {}
    result['_meta']['hostvars'] = {}
    for group in groups:
        result[group.name] = [host.name for host in group.get_hosts()]
    for h in all_hosts.get_hosts():
      result['_meta']['hostvars'][h.name] = h.get_variables()

    # create result groups for each of monday, thursday, sunday.
    result['monday'] = [ name for name, vals
                         in result['_meta']['hostvars'].iteritems()
                         if int(vals['site_id']) in monday_siteids ]
    result['thursday'] = [ name for name, vals
                         in result['_meta']['hostvars'].iteritems()
                         if int(vals['site_id']) in thursday_siteids ]
    result['sunday'] = [ name for name, vals
                         in result['_meta']['hostvars'].iteritems()
                         if int(vals['site_id']) in sunday_siteids ]

    print json.dumps(result)
    sys.exit(0)

if options.host is not None:
    result = {}
    host = None
    for test_host in all_hosts.get_hosts():
        if test_host.name == options.host:
            host = test_host
            break
    result = host.get_variables()
    if options.extra:
        k,v = options.extra.split("=")
        result[k] = v
    print json.dumps(result)
    sys.exit(0)

parser.print_help()

sys.exit(1)
