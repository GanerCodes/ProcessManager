from sys import argv
from subprocess import run, DEVNULL
from os import environ
from time import sleep
from hashlib import sha256
from random import randbytes
import json, os

TMP_DIR = "/tmp/tmux_layout"

def random_hash(n=24):
    return sha256(randbytes(512 * max(1, n // 24))).digest().hex()[:n]

def config_socket(file, group=None, chmod=None, users=None):
    if group:
        run(["chgrp", group, file])
    if chmod:
        run(["chmod", f"+{chmod}", file])
    if users:
        for user in users:
            run(["tmux", "-S", file, "server-access", user], stdout=DEVNULL, stderr=DEVNULL)

def tmux(action, *args, socket=os.path.join(TMP_DIR, "tmuxsocketxd"), suppress_output=False):
    cmd = ["tmux", "-S", socket, action, *map(str, args)]
    return run(cmd, **({"stdout": DEVNULL, "stderr": DEVNULL} if suppress_output else {}))

def init_tmux_server(socket, name, perms, commands, size, kill=True):
    ts = lambda *x, **y: tmux(*x, socket=socket, **y)
    x_count, y_count = size
    ID = 0
    
    if kill and ts("kill-server", suppress_output=True).returncode == 0:
        sleep(0.2)
    
    ts("new-session", "-d", "-s", name, *commands[ID])
    for y in range(1, y_count):
        ID = y*x_count
        ts("split-window", "-v", *commands[ID])
    for y in range(y_count)[::-1]:
        for x in range(1, x_count)[::-1]:
            ID = y*x_count + x
            ts("select-pane", "-t", y)
            ts("split-window", "-h", *commands[ID])
    
    ts("set", "-g", "status", "off")
    ts("set", "-g", "pane-active-border-style", "bg=default,fg=white")
    ts("set", "-g", "pane-border-style", "fg=white")
    
    # ts("selectl", "tiled")
    config_socket(socket, **perms)

def generate_layout(layout, perms, base_dir, read_sockets, name=None):
    name = name or random_hash()
    path = os.path.join(base_dir, name)
    os.makedirs(base_dir, exist_ok=True)
    
    read_sockets[name] = path
    
    for row in layout:
        for col, val in enumerate(row):
            if isinstance(val, list):
                row[col] = generate_layout(val, perms, base_dir, read_sockets)
    
    h, w = len(layout), len(layout[0])
    flat = [(lambda s, n: (read_sockets[s], n))(
        *x.split('/', 1)) for y in layout for x in y]
    commands = [["tmux", "-S", s, "a", "-t", n] for s, n in flat]
    
    init_tmux_server(path, name, perms, commands, (w, h))
    
    return f"{name}/{name}"

def parse_config(config):
    sock, layout = config['socket'], config['layout']
    
    read_sockets = sock['read']
    name = sock['name']
    perms = {i: sock[i] for i in ('users', 'group', 'chmod')}
    generate_layout(layout, perms, TMP_DIR, read_sockets, name)

def main():
    if len(argv) < 2:
        return print("Usage: python tmux_layout <Config File>")
    with open(argv[1], 'r') as f:
        parse_config(json.load(f))

if __name__ == "__main__":
    main()