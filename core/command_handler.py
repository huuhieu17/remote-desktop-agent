# core/command_handler.py
import queue

from core.command_executor import CommandExecutor

class CommandHandler:
    def __init__(self):
        self.commands = queue.Queue()

    from core.command_executor import CommandExecutor

    async def enqueue_command(self, cmd):
        print(f"📩 Received command: {cmd}")
        await CommandExecutor.execute(cmd['data'])

