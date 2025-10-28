import queue
from core.command_executor import CommandExecutor

class CommandHandler:
    def __init__(self, ws_client):
        self.ws = ws_client
        self.commands = queue.Queue()

    async def enqueue_command(self, cmd):
        print(f"📩 Received command: {cmd}")
        response = await CommandExecutor.execute(cmd['data'])
        self.ws.send_result(response)
