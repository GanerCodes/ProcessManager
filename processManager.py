#!/usr/bin/python

# Tool to manage and log multiple processes

import subprocess, threading, datetime, select, signal, json, time, sys, os

def get_date(fmt):
    return datetime.datetime.now().strftime(fmt)

def create_log_msg(fmt, stream, log):
    return get_date(fmt).format(stream=stream, log=log)

def write_output(file_handler, fmt, prepend, buffer, final=False):
    if final and (b'\n' not in buffer):
        return buffer
    
    spl = buffer.split(b'\n')
    if final:
        segs = spl
    else:
        *segs, buffer = spl
    
    for seg in segs:
        try:
            decoded_seg = seg.decode()
        except UnicodeDecodeError:
            decoded_seg = str(seg)
        message = create_log_msg(fmt, prepend, decoded_seg) + '\n'
        file_handler.write(message)
    
    if not final:
        return buffer

def process_output(proc, file_handle, fmt, buffer_size=64):
    stdout, stderr = proc.stdout.fileno(), proc.stderr.fileno()
    stdout_buffer = stderr_buffer = b''
    while proc.poll() is None:
        r, w, e = select.select([stdout, stderr], [], [])
        
        if stdout in r:
            stdout_buffer = write_output(file_handle, fmt, "stdout",
                stdout_buffer + os.read(stdout, buffer_size))
        if stderr in r:
            stderr_buffer = write_output(file_handle, fmt, "stderr",
                stderr_buffer + os.read(stderr, buffer_size))
        
    write_output(file_handle, fmt, "stdout", stdout_buffer, final=True)
    write_output(file_handle, fmt, "stderr", stderr_buffer, final=True)

def run_process(config, itteration):
    cmd     = config['exec']
    fmt     = config['fmt']
    shell   = config['shell']
    
    if isinstance(cmd, str):
        cmd = shell + [cmd]
    
    popen_kwargs = { "cwd": config['cwd'] }
    if config['clean_env']:
        popen_kwargs['env'] = config['env']
    else:
        popen_kwargs['env'] = os.environ.copy() | config['env']
    
    if config['log']:
        with open(config['logfile'], 'a', buffering=1) as f:
            f.write(create_log_msg(fmt, "info", f"Starting process (iter={itteration}).")+'\n')
            config['process'] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs)
            output_processing = threading.Thread(
                target=process_output,
                args=(config['process'], f, fmt))
            output_processing.start()
            config['process'].wait()
            output_processing.join()
    else:
        config['process'] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **popen_kwargs)
        config['process'].wait()

def proc_runner(config):
    init_delay = config['delay']
    loop_delay = config['wait']
    
    time.sleep(init_delay)
    itteration = 0
    while True:
        run_process(config, itteration)
        if not config['loop']:
            break
        time.sleep(loop_delay)
        itteration += 1

def normalize_task_config(main_config, task_name, unclean_task_config):
    return {
        "cwd": ".",
        "delay": 0,
        "loop": False,
        "log": True,
        "logfile": f"{task_name}.log",
        "clean_env": False,
        "env": {},
        "wait": 1,
        "fmt": main_config['fmt']
    } | unclean_task_config

def normalize_config(unclean_main_config):
    main_config = {
        "shell": ["sh", "-c"],
        "paths": [],
        "logdir": "~/.log/",
        "fmt": "[%Y-%m-%d %H:%M:%S.%f] {stream}: {log}",
        "tasks": [],
    } | unclean_main_config
    
    for task_name, unclean_task_config in main_config['tasks'].items():
        main_config['tasks'][task_name] = normalize_task_config(main_config, task_name, unclean_task_config)
    
    return main_config

def create_tasks(config):
    sys.path.insert(0, config['paths'])
    
    task_threads = {}
    for name, task in config['tasks'].items():
        if '/' in task['logfile']:
            logfile = task['logfile']
        else:
            logfile = os.path.join(config['logdir'], task['logfile'])
        
        task_config = task | {
            "logfile"   : logfile,
            "shell"     : config['shell'],
            "process"   : None
        }
        thread = threading.Thread(target=proc_runner, args=(task_config, ))
        task_threads[name] = (thread, task_config)
        thread.start()
    return task_threads

def run_config(config):
    return create_tasks(normalize_config(config))

def input_loop(tasks):
    prompt_text = "> "
    while True:
        try:
            command = input(prompt_text).strip()
            if command == 'exit':
                raise
        except KeyboardInterrupt:
            print("Press ^C or type exit to exit.")
            try:
                command = input(prompt_text).strip()
                if command == 'exit':
                    raise
            except KeyboardInterrupt:
                os._exit(0)
        
        command = list(filter(None, command.split()))
        if len(command) == 0:
            continue
        
        try:
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
        except Exception as err:
            print("Command handler ran into an error? Error:", err)

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