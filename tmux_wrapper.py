#!/usr/bin/python

# Tool to spawn tmux session and wait for its exit

import pickle, os
from sys import argv
from subprocess import run, DEVNULL

CHECK_TIME = 0.1
FPREFIX = "/tmp/tmux_wrapper"

if len(argv) < 2:
    print("Arguments: <name> [<arg1> <arg2> ...]")
    exit()

if not os.path.isdir(FPREFIX):
    os.mkdir(FPREFIX)
    print("Created tmux_wrapper temp path")

script_path = os.path.abspath(__file__)

if len(argv) > 2:
    from hashlib import sha256
    from random import randbytes
    h = sha256(randbytes(512)).digest().hex()[:24]
else:
    h = argv[1]
fname = os.path.join(FPREFIX, h)

if len(argv) > 2:
    from time import sleep
    
    args_list = argv.copy()
    args_list.pop(0)
    
    tacks = "-S -G -U".split()
    
    flags = {}
    while args_list[0] in tacks:
        arg, val = args_list.pop(0), args_list.pop(0)
        flags[arg] = val
    
    name = args_list.pop(0)
    
    print(flags, name, args_list)
    
    if '-S' in flags:
        arg = flags['-S']
        socket_file = arg if '/' in arg else os.path.join(FPREFIX, arg)
        sock_ins = ("-S", socket_file)
    else:
        sock_ins = ()
    
    with open(fname, 'wb') as f:
        pickle.dump(args_list, f) # writes argument list
    run(["tmux", *sock_ins, "new-session", "-ds", name, f"python {script_path} {h}"])
    
    if '-S' in flags:
        run(["chmod", "+774", socket_file])
        if '-G' in flags:
            run(["chgrp", flags['-G'], socket_file])
    if '-U' in flags:
        for user in filter(None, flags['-U'].split()):
            run(["tmux", *sock_ins, "server-access", "-a", user])
            # ok so maybe the virtualizer might be replacable with tmux's server-access -r flag but idc
    
    while True:
        code = run(
            ["tmux", *sock_ins, "has-session", "-t", name],
            stdout=DEVNULL,
            stderr=DEVNULL
        ).returncode
   
        if code != 0:
            break
        sleep(CHECK_TIME)
else:
    with open(fname, 'rb') as f:
        args = pickle.load(f) # loads argument list
    run(args)
    os.remove(fname)