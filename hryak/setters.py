logs_path = None
test = False

def set_logs_path(path: str):
    global logs_path
    logs_path = path

def set_test_mode(mode: bool):
    global test
    test = mode