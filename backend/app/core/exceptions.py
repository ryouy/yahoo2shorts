class AppError(RuntimeError):
    code = "app_error"


class YahooFetchError(AppError):
    code = "yahoo_fetch_error"


class YahooGeoBlockedError(YahooFetchError):
    code = "yahoo_geo_blocked"


class CommentFetchError(YahooFetchError):
    code = "comment_fetch_error"


class OpenAIServiceError(AppError):
    code = "openai_error"


class ValidationError(AppError):
    code = "validation_error"

