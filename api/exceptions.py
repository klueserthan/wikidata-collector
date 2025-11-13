from fastapi import HTTPException
from api.config import config

class APIException(HTTPException):
    """Base API exception."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)

class InvalidQIDException(APIException):
    """Invalid QID format."""
    def __init__(self):
        super().__init__(
            status_code=config.BAD_REQUEST_CODE,
            detail=config.ERROR_MESSAGES['invalid_qid']
        )

class InternalErrorException(APIException):
    """Internal server error."""
    def __init__(self, detail: str = None):
        super().__init__(
            status_code=config.INTERNAL_ERROR_CODE,
            detail=detail or config.ERROR_MESSAGES['internal_error']
        )

class EntityExpansionException(APIException):
    """Entity expansion failed."""
    def __init__(self, qid: str, detail: str):
        super().__init__(
            status_code=config.INTERNAL_ERROR_CODE,
            detail=f"Failed to expand entity {qid}: {detail}"
        )

