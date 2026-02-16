from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from io import StringIO
import time

# Create layout
layout = Layout()
layout.split_row(Layout(name="main"), Layout(name="sidebar", size=30))

# Create a console that writes to a StringIO buffer
buffer = StringIO()
console = Console(file=buffer, force_terminal=True)

with Live(layout, refresh_per_second=10):
    for i in range(20):
        # Print to the console (goes to buffer)
        console.print(f"[green]Processing item {i}")
        console.print(f"Status: OK")

        # Update the main layout with buffer contents
        layout["main"].update(Panel(buffer.getvalue(), title="Output"))

        # Update sidebar independently
        layout["sidebar"].update(Panel(f"Count: {i}", title="Stats"))

        time.sleep(0.3)
