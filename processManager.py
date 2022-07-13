#!/usr/bin/python
import subprocess, threading, datetime, signal, json, time, sys, os

def get_date():
    return datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")

def process_output(buffer, file_handle, prepend):
    for i in buffer:
        i = i.decode()
        parts = i.split('\n')
        if parts[-1] == '':
            parts.pop(-1)
        
        for o in parts:
            file_handle.write(f"{get_date()} {prepend}{o}\n")

def run_process(cmd, logfile, cwd=".", shell=[], config={}):
    if isinstance(cmd, str):
        cmd = shell + [cmd]
    
    with open(logfile, 'a') as f:
        f.write(f"{get_date()} - Starting log\n")
        config['process'] = (proc := subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        (out := threading.Thread(target=process_output, args=(proc.stdout, f, "stdout: "))).start()
        (err := threading.Thread(target=process_output, args=(proc.stderr, f, "stderr: "))).start()
        out.join(), err.join()

def proc_runner(c):
    time.sleep(c['init_delay'])
    while True:
        run_process(c['cmd'], c['logfile'], c['cwd'], c['shell'], c)
        if not c['loop']:
            break
        time.sleep(c['loop_delay'])

def normalize_config(config):
    config = {
        "shell": ["sh", "-c"],
        "logdir": "~/.log/",
        "tasks": []
    } | config
    
    for k, v in config['tasks'].items():
        config['tasks'][k] = {
            "cwd": ".",
            "delay": 0,
            "loop": False,
            "wait": 1
        } | v
    
    return config

def create_tasks(tasks, logdir, shell=[]):
    task_threads = {}
    for name, t in tasks.items():
        logfile = os.path.join(logdir, name + '.log')
        config = {
            "cmd"       : t['exec'],
            "logfile"   : logfile,
            "shell"     : shell,
            "cwd"       : t['cwd'],
            "init_delay": t['delay'],
            "loop"      : t['loop'],
            "loop_delay": t['wait'],
            "process"   : None
        }
        thread = threading.Thread(target=proc_runner, args=(config, ))
        thread.start()
        task_threads[name] = (thread, config)
    return task_threads

def run_config(config):
    config = normalize_config(config)
    return create_tasks(config['tasks'], config['logdir'], config['shell'])

def input_loop(tasks):
    while True:
        try:
            if (command := input()).strip() == 'exit':
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            print("Press ^C or type exit to exit.")
            try:
                if (command := input()).strip() == 'exit':
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                for v in tasks.values():
                    v[1]['loop'] = False
                os._exit(0)
        
        command = list(filter(None, command.split(' ')))
        if len(command) == 0:
            continue
        
        match command:
            case "help", *_:
                print("info | Shows list of tasks")
                print("stop <task0> <task1> ... | Ends task loop if running")
                print("kill <task0> <task1> ... | Stops task then kills process")
            case "info", *_:
                for name, v in tasks.items():
                    sym = '✅' if v[0].is_alive() else '❌' 
                    print("%s %s 🠒 %s" % (sym, name, v[1]['logfile']))
            case ("stop"|"kill") as cmd, *names:
                for name in names:
                    if not tasks[name][1]['loop']:
                        print("Loop has already been disable for task %s" % name)
                    else:
                        tasks[name][1]['loop'] = False
                        print("Disabling task %s loop" % name)
                    if cmd == "kill":
                        if (proc := tasks[name][1]['process']) is not None:
                            try:
                                os.kill(proc.pid, signal.SIGUSR1)
                                print("Sent kill signal to PID %s" % proc.pid)
                            except ProcessLookupError:
                                print("Task %s does not have a currently running process.")
                        else:
                            print("Task %s does not have a currently running process.")

def check_threads_for_exit(threads):
    [v[0].join() for v in threads.values()]
    print("All tasks complete.")
    os._exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1]) as f:
                try:
                    config = json.load(f)
                    threads = run_config(config)
                    threading.Thread(target=check_threads_for_exit, args=(threads, )).start()
                    input_loop(threads)
                except json.JSONDecodeError:
                    print("Unable to parse json file.")
        except FileNotFoundError:
            print('Could not locate file "%s"' % sys.argv[1])
    else:
        print("Missing required argument: Config file name")