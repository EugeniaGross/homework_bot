class MessageSentError(Exception):
    """Ошибка отправки сообщения."""

    pass


class JsonFormatError(Exception):
    """Формат отличный от json."""

    pass


class StatusHomeworkError(Exception):
    """Недокументированный статус домашней работы."""

    pass


class RequestError(Exception):
    """Ошибка запроса к API."""

    pass
