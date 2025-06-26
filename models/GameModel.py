import threading

TICK_INTERVAL = 0.1
games = {}  # pin -> game_state
game_queues = {}  # pin -> [queue.Queue()]
lock = threading.Lock()
