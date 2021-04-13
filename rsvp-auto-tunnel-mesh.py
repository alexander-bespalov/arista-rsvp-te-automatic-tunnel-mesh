#!/usr/bin/env python

import argparse
import re
import time
import syslog
from jsonrpclib import Server


def main():
    ### Parse arguments ###
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--protocol',    required=True, type=str, help='isis or ospf')
    parser.add_argument('-c', '--count',       required=True, type=int, help='Number of parallel LSPs')
    parser.add_argument('-t', '--timeout',     required=True, type=int, help='Time to keep LSPs to inactive destinations, minutes')
    parser.add_argument(      '--prefix_list', required=True, type=str, help='Prefix-list to restrict Loopbacks')
    parser.add_argument(      '--prefix',      required=True, type=str, help='Prefix for LSP names')
    parser.add_argument(      '--template',    required=True, type=str, help='LSP configuration template name')
    opts = parser.parse_args()

    api = Server('unix:/var/run/command-api.sock')

    show_run = api.runCmds(1, ['show running-config'])
    lsp_template_commands = show_run[0]['cmds']['router traffic-engineering']['cmds']['rsvp']['cmds']['tunnel ' + opts.template]['cmds'].keys()

    now = int(time.time())

    ### Get /32 routes ###
    cmd = 'show ip route %s' % (opts.protocol)
    routes = api.runCmds(1, [cmd])
    routes_32 = []
    for route in routes[0]['vrfs']['default']['routes'].keys():
        if re.match('[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/32', route):
            routes_32.append(route.split('/')[0])

    ### Apply prefix-list and generate RSVP targets ###
    cmd = 'show ip prefix-list %s' % (opts.prefix_list)
    prefix_list = api.runCmds(1, [cmd])
    targets = []
    for entry in prefix_list[0]['ipPrefixLists'][opts.prefix_list]['ipPrefixEntries']:
	routes_32_tmp = [r for r in routes_32]
        for route in routes_32_tmp:
            if addressInNetwork(route, entry['prefix']) == True:
                if entry['filterType'] == 'permit':
                    targets.append(route)
                    routes_32.remove(route)
                elif entry['filterType'] == 'deny':
                    routes_32.remove(route)

    ### Get existing tunnels ###
    existing_tunnels = []
    timeouts = {}
    show_te_tunnel = show_run[0]['cmds']['router traffic-engineering']['cmds']['rsvp']['cmds']
    for tunnel, options in show_te_tunnel.items():
        if re.match('^tunnel '+opts.prefix+'\-[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\-[0-9]+$', tunnel):
            tunnel = tunnel.split(' ')[1]
            existing_tunnels.append(tunnel)
            for comment in options['comments']:
                if re.match('^timeout: [0-9]+', comment):
                    timeout = comment.split(' ')[1]
                    timeouts[tunnel] = int(timeout)

    ### Proccess alive/new tunnels ###
    update_config = []
    required_tunnels = []
    for target in targets:
        for i in range(opts.count):
            tunnel = opts.prefix + '-' + str(target) + '-' + str(i)
            required_tunnels.append(tunnel)
            if tunnel in timeouts.keys():
                update_config.append('tunnel ' + tunnel)
                update_config.append('comment')
                log('RSVP auto-tunnel-mesh: tunnel ' + tunnel + ' timeout cleared')
            if tunnel not in existing_tunnels:
                update_config.append('tunnel ' + tunnel)
                update_config = update_config + lsp_template_commands
                update_config.append('comment')
                update_config.append('destination ip ' + target)
                update_config.append('no shutdown')
                update_config.append('exit')
                log('RSVP auto-tunnel-mesh: tunnel ' + tunnel + ' created')

    ### Process disappeared tunnels ###
    for tunnel in existing_tunnels:
        if tunnel not in required_tunnels:
            try:
                timeouts[tunnel]
            except:
                update_config.append('tunnel ' + tunnel)
                update_config.append('!! timeout: ' + str(now))
                log('RSVP auto-tunnel-mesh: tunnel ' + tunnel + ' timeout started')
            else:
                if now - timeouts[tunnel] > opts.timeout * 60:
                    update_config.append('no tunnel ' + tunnel)
                    log('RSVP auto-tunnel-mesh: tunnel ' +
                        tunnel + ' removed (timeout)')

    ### Update config if needed ###
    if len(update_config) > 0:
        update_config = ['configure', 'router traffic-engineering',
                         'rsvp'] + update_config + ['end', 'write']
        api.runCmds(1, update_config)


def log(message):
    syslog.syslog(syslog.LOG_INFO, message)


def addressInNetwork(ip, net):
    ipaddr = int(''.join([ '%02x' % int(x) for x in ip.split('.') ]), 16)
    netstr, bits = net.split('/')
    netaddr = int(''.join([ '%02x' % int(x) for x in netstr.split('.') ]), 16)
    mask = (0xffffffff << (32 - int(bits))) & 0xffffffff
    return (ipaddr & mask) == (netaddr & mask)


if __name__ == '__main__':
    main()
