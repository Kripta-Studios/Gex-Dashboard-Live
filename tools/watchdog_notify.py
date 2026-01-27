from sdnotify import SystemdNotifier
import syslog

notifier = SystemdNotifier()


def send_watchdog():
    """Se llama cada vez que se envía una imagen."""
    notifier.notify("WATCHDOG=1")
    syslog.syslog(syslog.LOG_INFO, "WATCHDOG 1 SENT Per Minute Discord Bot")

