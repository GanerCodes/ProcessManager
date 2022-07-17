# Intended usage: in ssh server config:
# ForceCommand /usr/bin/python /path/to/this/file.py /path/to/config.json
# Serves to block stdin from a program, acting as a simple viewer, but also reserves dynamic resizing

import json, time, sys, os

def virtualize(command):
    import tty, pty, fcntl, struct, select, termios, threading, subprocess
    
    def ctrl_break():
        os.system("clear")
        os._exit(0)
    
    tty.setraw(sys.stdin.fileno())
    master_fd, slave_fd = pty.openpty()
    p = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            universal_newlines=True)

    def set_winsize(fd, row, col):
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", row, col, 0, 0))

    def update_size_thread(refresh=1):
        while p.poll() is None:
            r, c = map(int, subprocess.run(
                ["stty", "size"],
                stdout=subprocess.PIPE
            ).stdout.decode().strip().split())
            
            set_winsize(master_fd, r, c)
            set_winsize(slave_fd, r, c)
            set_winsize(sys.stdout.fileno(), r, c)
            time.sleep(refresh)

    threading.Thread(target=update_size_thread).start()

    while p.poll() is None:
        r, w, e = select.select([sys.stdin, master_fd], [], [])
        if master_fd in r:
            o = os.read(master_fd, 10240)
            os.write(sys.stdout.fileno(), o)
        if sys.stdin in r:
            i = os.read(sys.stdin.fileno(), 10240)
            if b'\x03' in i:
                ctrl_break()

def main():
    if len(sys.argv) < 2:
        return print("Missing required argument: Config file name")
    
    if "SSH_ORIGINAL_COMMAND" in os.environ:
        choice = os.environ["SSH_ORIGINAL_COMMAND"]
    else:
        return print("Unable to find SSH command environment variable.")
    
    try:
        with open(sys.argv[1]) as f:
            try:
                config = json.load(f)
                if choice in config:
                    command = config[choice]
                    virtualize(command)
                else:
                    return print(f'Choice "{choice}" not found in config.')
            except json.JSONDecodeError:
                return print("Unable to parse json file.")
    except FileNotFoundError:
        return print('Could not locate file "%s"' % sys.argv[1])

if __name__ == "__main__":
    main()