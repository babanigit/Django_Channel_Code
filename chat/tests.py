from channels.testing import ChannelsLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatTests(ChannelsLiveServerTestCase):
    serve_static = True  # emulate StaticLiveServerTestCase

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            cls.driver = webdriver.Chrome(options=options)
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {e}")
            super().tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def test_when_chat_message_posted_then_seen_by_everyone_in_same_room(self):
        try:
            self._enter_chat_room("room_1")

            self._open_new_window()
            self._enter_chat_room("room_1")

            self._switch_to_window(0)
            self._post_message("hello")
            time.sleep(2)  # Add a 2-second delay
            self._assert_message_received("hello", "window 1", "window 1", timeout=10)

            self._switch_to_window(1)
            self._assert_message_received("hello", "window 2", "window 1", timeout=10)
        finally:
            self._close_all_new_windows()

    def test_when_chat_message_posted_then_not_seen_by_anyone_in_different_room(self):
        try:
            self._enter_chat_room("room_1")

            self._open_new_window()
            self._enter_chat_room("room_2")

            self._switch_to_window(0)
            self._post_message("hello")
            time.sleep(2)  # Add a 2-second delay
            self._assert_message_received("hello", "window 1", "window 1", timeout=10)

            self._switch_to_window(1)
            self._post_message("world")
            time.sleep(2)  # Add a 2-second delay
            self._assert_message_received("world", "window 2", "window 2", timeout=10)
            self._assert_message_not_received("hello", "window 2", "window 1")
        finally:
            self._close_all_new_windows()

    def _enter_chat_room(self, room_name):
        self.driver.get(self.live_server_url + "/chat/")
        logger.info(f"Entering chat room: {room_name}")
        ActionChains(self.driver).send_keys(room_name, Keys.ENTER).perform()
        WebDriverWait(self.driver, 10).until(
            lambda _: room_name in self.driver.current_url
        )
        logger.info(f"Entered chat room: {self.driver.current_url}")
        self._check_websocket_connection()

    def _open_new_window(self):
        self.driver.execute_script('window.open("about:blank", "_blank");')
        self._switch_to_window(-1)
        logger.info(f"Opened new window: {self.driver.current_url}")

    def _close_all_new_windows(self):
        while len(self.driver.window_handles) > 1:
            self._switch_to_window(-1)
            self.driver.execute_script("window.close();")
        if len(self.driver.window_handles) == 1:
            self._switch_to_window(0)
        logger.info("Closed all new windows")

    def _switch_to_window(self, window_index):
        self.driver.switch_to.window(self.driver.window_handles[window_index])
        logger.info(f"Switched to window {window_index}: {self.driver.current_url}")

    def _post_message(self, message):
        logger.info(f"Posting message: {message}")
        try:
            input_box = self.driver.find_element(by=By.CSS_SELECTOR, value="#chat-message-input")
            input_box.send_keys(message)
            input_box.send_keys(Keys.ENTER)
            logger.info(f"Message '{message}' sent successfully")
        except Exception as e:
            logger.error(f"Error posting message: {e}")

    def _assert_message_received(self, message, receiver, sender, timeout=10):
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda _: message in self._chat_log_value,
                f"Message '{message}' was not received by {receiver} from {sender}",
            )
            logger.info(f"Message '{message}' received by {receiver} from {sender}")
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.error(f"Current chat log: {self._chat_log_value}")
            self._log_page_source()
            raise

    def _assert_message_not_received(self, message, receiver, sender):
        self.assertTrue(
            message not in self._chat_log_value,
            f"Message '{message}' was improperly received by {receiver} from {sender}",
        )
        logger.info(f"Message '{message}' correctly not received by {receiver} from {sender}")

    @property
    def _chat_log_value(self):
        try:
            chat_log = self.driver.find_element(by=By.CSS_SELECTOR, value="#chat-log")
            logger.info(f"Chat log found: {chat_log.is_displayed()}")
            return chat_log.get_property("value")
        except Exception as e:
            logger.error(f"Error finding chat log: {e}")
            return ""

    def _check_js_errors(self):
        logs = self.driver.get_log('browser')
        for log in logs:
            if log['level'] == 'SEVERE':
                logger.error(f"JavaScript error: {log['message']}")
        return logs

    def _log_page_source(self):
        logger.info(f"Current page source:\n{self.driver.page_source}")

    def _check_websocket_connection(self):
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return window.chatSocket && window.chatSocket.readyState === 1")
            )
            logger.info("WebSocket connection established")
        except Exception as e:
            logger.error(f"WebSocket connection not established: {e}")
            self._log_page_source()