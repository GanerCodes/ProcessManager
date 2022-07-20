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
    name = argv[1]
    args_list = argv[2:]
    with open(fname, 'wb') as f:
        pickle.dump(args_list, f) # writes argument list
    
    run(["tmux", "new-session", "-ds", name, f"python {script_path} {h}"])
    while True:
        code = run(
            ["tmux", "has-session", "-t", name],
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