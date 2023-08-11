def parse_web_driver_exception(e, url):
    reason = 'error'
    err_msg = ''

    if 'ERR_NAME_NOT_RESOLVED' in str(e):
        reason = 'unresolved'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: name cannot be resolved)'
    elif 'ERR_ADDRESS_UNREACHABLE' in str(e):
        reason = 'unreachable'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: address cannot be reached)'
    elif 'ERR_CONNECTION_TIMED_OUT' in str(e):
        reason = 'timed out'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: connection timed out)'
    elif 'stale element reference' in str(e):
        reason = 'stale'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: stale element)'
    elif 'ERR_SSL_VERSION_OR_CIPHER_MISMATCH' in str(e):
        reason = 'https not supported'
        err_msg = f'ERROR: cannot visit url "{url}" (reason: site does not support https)'
    else:
        err_msg = f'ERROR: {str(e)}'

    return err_msg, reason


class WebDriverException(Exception):
    """Custom exception to abstract WebDriverException from users."""

    def __init__(self, message, screen=None, stacktrace=None, filename=None, lineno=None):
        self.message = message
        self.screen = screen
        self.stacktrace = stacktrace
        self.filename = filename
        self.lineno = lineno
        super().__init__(self.message)

    @staticmethod
    def from_webdriver_exception(e):
        return WebDriverException(
            message=str(e),
            screen=getattr(e, 'screen', None),
            stacktrace=getattr(e, 'stacktrace', None),
            filename=getattr(e, 'filename', None),
            lineno=getattr(e, 'lineno', None)
        )


class StaleElementReferenceException(Exception):
    """Custom exception to abstract StaleElementReferenceException from users."""

    def __init__(self, message, screen=None, stacktrace=None, filename=None, lineno=None):
        self.message = message
        self.screen = screen
        self.stacktrace = stacktrace
        self.filename = filename
        self.lineno = lineno
        super().__init__(self.message)

    @staticmethod
    def from_stale_element_exception(e):
        return StaleElementReferenceException(
            message=str(e),
            screen=getattr(e, 'screen', None),
            stacktrace=getattr(e, 'stacktrace', None),
            filename=getattr(e, 'filename', None),
            lineno=getattr(e, 'lineno', None)
        )
