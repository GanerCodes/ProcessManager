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
    
    users = None
    if argv[1] == "-S":
        arg = argv[2]
        socket_file = arg if '/' in arg else os.path.join(FPREFIX, arg)
        sock_ins = ("-S", socket_file)
        if argv[3] == "-U":
            users = argv[4]
            name = argv[5]
            args_list = argv[6:]
        else:
            name = argv[3]
            args_list = argv[4:]
    else:
        sock_ins = ()
        name = argv[1]
        args_list = argv[2:]
    
    with open(fname, 'wb') as f:
        pickle.dump(args_list, f) # writes argument list
    
    run(["tmux", *sock_ins, "new-session", "-ds", name, f"python {script_path} {h}"])
    if users:
        run(["chmod", "+774", sock_ins[1]])
        for user in filter(None, users.split()):
            # ok so maybe the virtualizer might be replacable with tmux's server-access -r flag but idc
            run(["tmux", *sock_ins, "server-access", "-a", user])
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