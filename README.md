<p align="center">
  <img src="ASSETS/winterm_nushell_example.gif" alt="ServerTracker.py running on windows-terminal using windows-curses" width="100%">
</p>

# MCSF

MCSF (Minecraft Server Finder) is a toolkit containing a few utilities for scanning and tracking Minecraft servers and the players.

> **Warning**
>
> The author or any contributors are not responsible for the misuse of this tool. The responsibility for ensuring ethical and legal use of this tool lies entirely with the end user.

## Table of contents

* [Usage](#usage)
  * [`ServerTracker.py`](#servertrackerpy)
    * [About](#about)
    * [Arguments](#arguments)
      * [`--state-file`/`-s`](#--state-file-s)
      * [`--runners`/`-r`](#--runners-r)
  * [`ServerScanner.py`](#serverscannerpy)
    * [About](#about-1)
    * [Arguments](#arguments-1)
      * [`--target`/`-t`](#--target-t)
      * [`--ports`/`-p`](#--target-t)
      * [`--timeout`/`-T`](#--target-t)
      * [`--output`/`-o`](#--output-o)
      * [`--randomize-ports`/`--randomize-hosts`](#--randomize-ports----randomize-hosts)
      * [`--ping-scan`](#--ping-scan)
      * [`--ping-scan-runners`](#--ping-scan-runners)
      * [`--nmap`](#--nmap)
      * [`--nmap-path`](#--nmap-path)

# Usage

## `ServerTracker.py`:

### About

The `ServerTracker.py` script tracks activity on various servers simultaneously and displays it in a text-based user interface using `curses` (or `windows-curses`), it also allows the end user to copy fields directly thanks to `pyperclip`.  
At the moment this script cannot be used to actually edit data, but there are plans to change this in the near future.

### Arguments

#### `--state-file`/`-s`:

Optional argument that defines which path to use for the state file.  
Default value is `save_state.pickle`

#### `--runners`/`-r`:

Optional argument used to set the amount of runners (co-routines that do the status request).  
Default value is `16`

## `ServerScanner.py`:

### About

`ServerScanner.py` is a script that helps with acquiring IP addresses of possible servers, it's also capable of using Nmap if you want a faster SYN scan.

### Arguments

#### `--target`/`-t`:

As the name suggests this argument defines the target, this can be a hostname, a IPv4 address (with or without the CIDR notation), and it also supports IPv6 (although IPv6 support wasn't widely checked).

#### `--ports`/`-p`:

Optional argument used to define the target ports, it supports the same notation as Nmap (`-p 0-65535`, `-p 80,65,10-20`, etc).  
Default value is `25565`

#### `--timeout`/`-T`:

Optional argument that defines how much time to wait before giving up on a host.  
Default value is `5`  

#### `--output`/`-o`:

Optional argument used to set the output file.  
Default value is `scan_results.pickle`  

#### `--randomize-ports` & `--randomize-hosts`:

Optional argument that defines if ports or hosts should be randomized.  
Default value is `False` (for both)  

#### `--ping-scan`:

Optional argument that defines if a ping scan should be done before testing the ports.  
Default value is `False`  

#### `--ping-scan-runners`:

Optional argument that defines if a ping scan should be done before testing the ports.  
Default value is `16`  

#### `--nmap`:

Optional argument that defines if Nmap should be used for the SYN scan.  
Default value is `False`  

#### `--nmap-path`:

Optional argument that defines the path in which Nmap is located.  
Default value is `nmap`