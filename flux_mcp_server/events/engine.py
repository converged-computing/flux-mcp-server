import asyncio
import errno
import logging
import time

import flux
import flux.job

from flux_mcp_server.events.receiver import EventReceiver

logger = logging.getLogger(__name__)


class EventsEngine:
    def __init__(self, uri: str, receiver: EventReceiver):
        self.uri = uri
        self.receiver = receiver
        self._running = False
        self._loop = None
        self._task = None

    async def start(self):
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(asyncio.to_thread(self._sync_listen_loop))
        logger.info(f"EventsEngine started for {self.uri or 'local'}")

    async def stop(self):
        logger.info("EventsEngine stopping...")
        self._running = False
        if self._task:
            try:
                # Wait for the thread to exit cleanly
                await asyncio.wait_for(self._task, timeout=2.0)
                logger.info("EventsEngine thread stopped cleanly.")
            except asyncio.TimeoutError:
                logger.warning("EventsEngine thread shutdown timed out.")
            except Exception as e:
                logger.error(f"Error stopping EventsEngine: {e}")

    def _normalize_event(self, event) -> dict:
        data = dict(event)
        data["type"] = event.name
        data["id"] = event.jobid
        data["R"] = getattr(event, "R", None)
        data["jobspec"] = getattr(event, "jobspec", None)
        return data

    def _handle_async_error(self, future):
        """Callback to log errors from the async side."""
        try:
            future.result()
        except Exception as e:
            logger.error(f"Error in EventReceiver: {e}")

    def _sync_listen_loop(self):
        handle = None
        try:
            if self.uri:
                handle = flux.Flux(self.uri)
            else:
                handle = flux.Flux()

            consumer = flux.job.JournalConsumer(handle)
            consumer.start()
            logger.debug("JournalConsumer attached.")

            while self._running:
                try:
                    # Non-blocking poll
                    event = consumer.poll(timeout=0.1)

                    if event:
                        logger.debug(f"Flux Event Received: {event.get('name')}")
                        if not hasattr(event, "jobid"):
                            continue
                        clean_event = self._normalize_event(event)

                        if self._loop and self._loop.is_running():
                            # Schedule the DB write on the main loop
                            fut = asyncio.run_coroutine_threadsafe(
                                self.receiver.send(clean_event), self._loop
                            )
                            # Attach a callback to log any DB errors
                            fut.add_done_callback(self._handle_async_error)
                    else:
                        # Slight sleep to yield GIL if poll returns instantly
                        time.sleep(0.01)

                except EnvironmentError as e:
                    # Ignore timeouts (no data)
                    if e.errno == errno.ETIMEDOUT:
                        continue
                    logger.error(f"Flux connection error: {e}")
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Unexpected error in event loop: {e}")
                    time.sleep(1)

        except Exception as e:
            logger.critical(f"EventsEngine crashed: {e}")
        finally:
            del handle
            logger.info("EventsEngine thread exiting.")
