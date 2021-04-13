# Arista RSVP-TE Automatic Tunnel Mesh
This application is configuring RSVP-TE tunnels towards egress routers (/32 routes from OSPF or ISIS routing table). Practically it allows to automate RSVP-TE full mesh provisioning in MPLS network.

## Notes
- The application must be scheduled for periodical execution (see example below).
- It is possible to scheule multiple instances of the application. In this case eash instance of the application **MUST** have unique `--prefix` parameter.

## Input parameters
```
usage: rsvp-auto-tunnel-mesh.py [-h] -p PROTOCOL -c COUNT -t TIMEOUT
                                --prefix_list PREFIX_LIST --prefix PREFIX
                                --template TEMPLATE

optional arguments:
  -h, --help            show this help message and exit
  -p PROTOCOL, --protocol PROTOCOL
                        isis or ospf
  -c COUNT, --count COUNT
                        Number of parallel LSPs
  -t TIMEOUT, --timeout TIMEOUT
                        Time to keep LSPs to inactive destinations, minutes
  --prefix_list PREFIX_LIST
                        Prefix-list to restrict Loopbacks                        
  --prefix PREFIX       Prefix for LSP names
  --template TEMPLATE   LSP configuration template name
```
| Parameter | Description |
| ------ | ------ |
| `protocol` | which protocol to monitor (`isis` or `ospf`), depends on which IGP is used in the MPLS network |
| `count` | number of parallel LSPs towards each egress router |
| `timeout` | how long (in minutes) to keep LSP in configuration if egress router disappeared from routing table |
| `prefix_list` | Prefix-list to search/monitor egress routers (/32 routes), in general it should be IP filter to match egress Loopbacks (evaluation is based on permit/deny and prefix value all other options are ignored) |
| `prefix` | LSP name prefix for generated LSPs (**each instance of application MUST have unique `prefix`, if multiple instances of application is scheduled**) |
| `template` | LSP template name, parameters from which are used for generated LSPs (see example below) |

## Required EOS configuration
Enable EOS API:
```
!
management api http-commands
  protocol unix-socket
  no shutdown
!
```

Add RSVP tunnel templates which will be referenced by the application (just a regular tunnel without `destination ip` statement). For example:
```
!
router traffic-engineering
  rsvp
    path DYNAMIC dynamic
    !
    tunnel TEMPLATE-1
      path DYNAMIC
      bandwidth auto min 0.00 bps max 10.00 gbps
      optimization interval 3600 seconds
!
```

Add prefix-list to identify egress routers. For example:
```
!
ip prefix-list RSVP-AUTO-TUNNEL
  seq 10 permit 200.1.0.0/16
  seq 20 deny 198.18.1.0/24
  seq 30 permit 198.18.1.0/16
!
```

Schedule application. For example:
```
!
schedule rsvp-auto-tunnel-mesh-ospf interval 2 timeout 1 max-log-files 1 command bash /mnt/flash/scripts/rsvp-auto-tunnel-mesh.py --protocol ospf --count 2 --timeout 10 --prefix_list RSVP-AUTO-TUNNEL --prefix AUTO-1 --template TEMPLATE-1
!
```

### Using RPM
Application could also be installed as RPM extension. Pre-built RPM is available in the RPM directory. Please follow this article to manage extensions:
https://www.arista.com/en/um-eos/eos-managing-eos-extensions

You don't need to specify full path to the application in shedule if it was installed as RPM. For example:
```
!
schedule rsvp-auto-tunnel-mesh-ospf interval 2 timeout 1 max-log-files 1 command bash rsvp-auto-tunnel-mesh.py --protocol ospf --count 2 --timeout 10 --prefix_list RSVP-AUTO-TUNNEL --prefix AUTO-1 --template TEMPLATE-1
!
```

### Troubleshooting
```
arista#show schedule summary
Maximum concurrent jobs  1
Prepend host name to logfile: Yes
Name                 At time     Last      Interval     Timeout       Max     Logfile Location                   Status
                                 time       (mins)       (mins)       log
                                                                     files
------------------ ----------- --------- ------------ ------------ ---------- ---------------------------------- ------
rsvp-auto-tunn\        now       23:20        2            1           1      flash:schedule/rsvp-auto-tunn\     Success
el-mesh-ospf                                                                  el-mesh-ospf/
```

Logging example:
```
arista#show logging system
### Tunnels initiation ###
Mar 16 23:17:59 ph107 rsvp-auto-tunnel-mesh.py: RSVP auto-tunnel: tunnel AUTO-1-200.1.0.255-0 created
Mar 16 23:17:59 ph107 rsvp-auto-tunnel-mesh.py: RSVP auto-tunnel: tunnel AUTO-1-200.1.0.255-1 created
Mar 16 23:17:59 ph107 Rsvp: %RSVP-6-TUNNEL_DOWN: Tunnel AUTO-1-200.1.0.255-0 to 200.1.0.255 is down
Mar 16 23:17:59 ph107 Rsvp: %RSVP-6-TUNNEL_DOWN: Tunnel AUTO-1-200.1.0.255-1 to 200.1.0.255 is down
Mar 16 23:17:59 ph107 Rsvp: %RSVP-6-TUNNEL_UP_USING_PRIMARY: Tunnel AUTO-1-200.1.0.255-0 to 200.1.0.255 is up using primary path
Mar 16 23:17:59 ph107 Rsvp: %RSVP-6-TUNNEL_UP_USING_PRIMARY: Tunnel AUTO-1-200.1.0.255-1 to 200.1.0.255 is up using primary path

### Tunnels go down (egress router unreachable) ###
Mar 16 23:19:47 ph107 Rsvp: %RSVP-6-TUNNEL_DOWN: Tunnel AUTO-1-200.1.0.255-0 to 200.1.0.255 is down
Mar 16 23:19:47 ph107 Rsvp: %RSVP-6-TUNNEL_DOWN: Tunnel AUTO-1-200.1.0.255-1 to 200.1.0.255 is down
Mar 16 23:20:56 ph107 rsvp-auto-tunnel-mesh.py: RSVP auto-tunnel: tunnel AUTO-1-200.1.0.255-0 timeout started
Mar 16 23:20:56 ph107 rsvp-auto-tunnel-mesh.py: RSVP auto-tunnel: tunnel AUTO-1-200.1.0.255-1 timeout started

### Tunnels removed on timeout ###
Mar 16 23:32:56 ph107 rsvp-auto-tunnel-mesh.py: RSVP auto-tunnel-mesh: tunnel AUTO-1-200.1.0.255-0 removed (timeout)
Mar 16 23:32:56 ph107 rsvp-auto-tunnel-mesh.py: RSVP auto-tunnel-mesh: tunnel AUTO-1-200.1.0.255-1 removed (timeout)
```
