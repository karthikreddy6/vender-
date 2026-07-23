import datetime
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.security import UnauthenticatedException

# --- Custom Exceptions ---
class NotFoundException(Exception):
    """Resource not found, maps to 404."""
    def __init__(self, message: str):
        self.message = message

class BadRequestException(Exception):
    """Bad request logic, maps to 400."""
    def __init__(self, message: str):
        self.message = message

# --- Spring Boot Error Formatter ---
def make_spring_error_response(status_code: int, error_name: str, message: str) -> JSONResponse:
    # Use ISO format without timezone or with +00:00 to match typical Java Jackson format
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Format: 2026-07-08T13:22:43
    # Slice off the microseconds if present to match the exact pattern "YYYY-MM-DDTHH:MM:SS"
    if "." in timestamp:
        timestamp = timestamp.split(".")[0]
        
    return JSONResponse(
        status_code=status_code,
        content={
            "timestamp": timestamp,
            "status": status_code,
            "error": error_name,
            "message": message
        }
    )

# --- Register Handlers ---
def register_exception_handlers(app: FastAPI):
    @app.exception_handler(NotFoundException)
    async def not_found_exception_handler(request: Request, exc: NotFoundException):
        return make_spring_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_name="Not Found",
            message=exc.message
        )

    @app.exception_handler(BadRequestException)
    async def bad_request_exception_handler(request: Request, exc: BadRequestException):
        return make_spring_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_name="Bad Request",
            message=exc.message
        )

    @app.exception_handler(UnauthenticatedException)
    async def unauthenticated_exception_handler(request: Request, exc: UnauthenticatedException):
        return make_spring_error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_name="Unauthorized",
            message=exc.message
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Maps FastAPI's built-in HTTPExceptions to Spring style
        error_name = "HTTP Error"
        if exc.status_code == 404:
            error_name = "Not Found"
        elif exc.status_code == 401:
            error_name = "Unauthorized"
        elif exc.status_code == 403:
            error_name = "Forbidden"
        elif exc.status_code == 400:
            error_name = "Bad Request"
        elif exc.status_code == 500:
            error_name = "Internal Server Error"
            
        return make_spring_error_response(
            status_code=exc.status_code,
            error_name=error_name,
            message=exc.detail
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Format Pydantic validation errors nicely
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            errors.append(f"Field '{loc}': {error['msg']}")
        message = "; ".join(errors)
        
        return make_spring_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_name="Bad Request",
            message=f"Validation failed: {message}"
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        # Catch all other unhandled exceptions
        return make_spring_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_name="Internal Server Error",
            message=str(exc)
        )
