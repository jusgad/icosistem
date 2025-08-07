"""
Common Pydantic schemas for shared data structures.
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

T = TypeVar('T')


class BaseSchema(BaseModel):
    """Base schema with common configuration"""
    
    model_config = ConfigDict(
        # Modern Pydantic v2 configuration
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
        from_attributes=True,  # Replaces orm_mode
        arbitrary_types_allowed=True,
        populate_by_name=True
    )


class StatusEnum(str, Enum):
    """Common status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class PriorityEnum(str, Enum):
    """Priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorType(str, Enum):
    """Error type enumeration"""
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND_ERROR = "not_found_error"
    CONFLICT_ERROR = "conflict_error"
    INTERNAL_ERROR = "internal_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"


class BaseResponse(BaseSchema):
    """Base response schema"""
    
    success: bool = Field(default=True, description="Operation success status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")


class SuccessResponse(BaseResponse):
    """Success response schema"""
    
    message: str = Field(description="Success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")


class ErrorDetail(BaseSchema):
    """Error detail schema"""
    
    field: Optional[str] = Field(default=None, description="Field that caused the error")
    message: str = Field(description="Error message")
    code: Optional[str] = Field(default=None, description="Error code")


class ValidationError(BaseSchema):
    """Validation error schema"""
    
    field: str = Field(description="Field name with validation error")
    message: str = Field(description="Validation error message")
    value: Optional[Any] = Field(default=None, description="Invalid value")
    constraint: Optional[str] = Field(default=None, description="Violated constraint")


class ErrorResponse(BaseResponse):
    """Error response schema"""
    
    success: bool = Field(default=False)
    error_type: ErrorType = Field(description="Type of error")
    message: str = Field(description="Error message")
    details: Optional[List[ErrorDetail]] = Field(default=None, description="Detailed error information")
    validation_errors: Optional[List[ValidationError]] = Field(default=None, description="Validation errors")
    error_code: Optional[str] = Field(default=None, description="Application-specific error code")


class PaginationMeta(BaseSchema):
    """Pagination metadata"""
    
    current_page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")
    next_page: Optional[int] = Field(default=None, description="Next page number")
    prev_page: Optional[int] = Field(default=None, description="Previous page number")


class PaginatedResponse(BaseResponse, Generic[T]):
    """Generic paginated response"""
    
    items: List[T] = Field(description="List of items")
    pagination: PaginationMeta = Field(description="Pagination metadata")


class SortOrder(str, Enum):
    """Sort order enumeration"""
    ASC = "asc"
    DESC = "desc"


class FilterOperator(str, Enum):
    """Filter operator enumeration"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "startswith"
    ENDS_WITH = "endswith"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class FilterCriteria(BaseSchema):
    """Filter criteria schema"""
    
    field: str = Field(description="Field name to filter")
    operator: FilterOperator = Field(description="Filter operator")
    value: Optional[Union[str, int, float, bool, List[Any]]] = Field(
        default=None, 
        description="Filter value"
    )


class SortCriteria(BaseSchema):
    """Sort criteria schema"""
    
    field: str = Field(description="Field name to sort by")
    order: SortOrder = Field(default=SortOrder.ASC, description="Sort order")


class QueryRequest(BaseSchema):
    """Generic query request with filtering, sorting, and pagination"""
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    # Filtering
    filters: Optional[List[FilterCriteria]] = Field(
        default=None, 
        description="Filter criteria"
    )
    search: Optional[str] = Field(
        default=None, 
        min_length=1, 
        max_length=255, 
        description="Search query"
    )
    
    # Sorting
    sort: Optional[List[SortCriteria]] = Field(
        default=None, 
        description="Sort criteria"
    )
    
    # Field selection
    fields: Optional[List[str]] = Field(
        default=None, 
        description="Fields to include in response"
    )
    
    # Includes
    include: Optional[List[str]] = Field(
        default=None, 
        description="Related resources to include"
    )


class HealthCheckStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class ServiceHealth(BaseSchema):
    """Individual service health status"""
    
    name: str = Field(description="Service name")
    status: HealthCheckStatus = Field(description="Service status")
    response_time_ms: Optional[float] = Field(default=None, description="Response time in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional health details")


class HealthCheckResponse(BaseResponse):
    """Health check response"""
    
    overall_status: HealthCheckStatus = Field(description="Overall system health")
    services: List[ServiceHealth] = Field(description="Individual service health")
    uptime_seconds: float = Field(description="System uptime in seconds")
    version: str = Field(description="Application version")
    environment: str = Field(description="Environment name")


class ContactInfo(BaseSchema):
    """Contact information schema"""
    
    email: Optional[str] = Field(
        default=None, 
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="Email address"
    )
    phone: Optional[str] = Field(
        default=None,
        pattern=r'^\+?[1-9]\d{1,14}$',
        description="Phone number in E.164 format"
    )
    website: Optional[str] = Field(
        default=None,
        pattern=r'^https?://[^\s/$.?#].[^\s]*$',
        description="Website URL"
    )
    linkedin: Optional[str] = Field(
        default=None,
        description="LinkedIn profile URL"
    )


class Address(BaseSchema):
    """Address schema"""
    
    street: Optional[str] = Field(default=None, max_length=255, description="Street address")
    city: Optional[str] = Field(default=None, max_length=100, description="City")
    state: Optional[str] = Field(default=None, max_length=100, description="State/Province")
    country: Optional[str] = Field(default=None, max_length=100, description="Country")
    postal_code: Optional[str] = Field(default=None, max_length=20, description="Postal code")
    latitude: Optional[float] = Field(default=None, ge=-90, le=90, description="Latitude")
    longitude: Optional[float] = Field(default=None, ge=-180, le=180, description="Longitude")


class FileInfo(BaseSchema):
    """File information schema"""
    
    filename: str = Field(description="Original filename")
    file_path: str = Field(description="Stored file path")
    file_size: int = Field(ge=0, description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    upload_date: datetime = Field(description="Upload timestamp")
    uploaded_by: Optional[str] = Field(default=None, description="User who uploaded the file")


class AuditInfo(BaseSchema):
    """Audit information schema"""
    
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    created_by: Optional[str] = Field(default=None, description="Creator user ID")
    updated_by: Optional[str] = Field(default=None, description="Last updater user ID")
    version: int = Field(default=1, ge=1, description="Record version for optimistic locking")


class NotificationPreferences(BaseSchema):
    """Notification preferences schema"""
    
    email_notifications: bool = Field(default=True, description="Enable email notifications")
    sms_notifications: bool = Field(default=False, description="Enable SMS notifications")
    push_notifications: bool = Field(default=True, description="Enable push notifications")
    marketing_emails: bool = Field(default=False, description="Enable marketing emails")
    meeting_reminders: bool = Field(default=True, description="Enable meeting reminders")
    project_updates: bool = Field(default=True, description="Enable project update notifications")
    
    # Notification timing
    reminder_hours_before: int = Field(
        default=24, 
        ge=1, 
        le=168, 
        description="Hours before event to send reminder"
    )
    quiet_hours_start: Optional[int] = Field(
        default=22, 
        ge=0, 
        le=23, 
        description="Start of quiet hours (24h format)"
    )
    quiet_hours_end: Optional[int] = Field(
        default=8, 
        ge=0, 
        le=23, 
        description="End of quiet hours (24h format)"
    )


class MetricValue(BaseSchema):
    """Generic metric value"""
    
    name: str = Field(description="Metric name")
    value: Union[int, float, str] = Field(description="Metric value")
    unit: Optional[str] = Field(default=None, description="Metric unit")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metric timestamp")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Metric tags")


class BulkOperation(BaseSchema):
    """Bulk operation request"""
    
    operation: str = Field(description="Operation to perform")
    items: List[Dict[str, Any]] = Field(min_length=1, description="Items to process")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Operation options")


class BulkOperationResult(BaseSchema):
    """Bulk operation result"""
    
    total_items: int = Field(ge=0, description="Total items processed")
    successful_items: int = Field(ge=0, description="Successfully processed items")
    failed_items: int = Field(ge=0, description="Failed items")
    errors: Optional[List[ErrorDetail]] = Field(default=None, description="Processing errors")
    processing_time_ms: float = Field(description="Processing time in milliseconds")


class ConfigurationSetting(BaseSchema):
    """Configuration setting schema"""
    
    key: str = Field(description="Setting key")
    value: Union[str, int, float, bool, Dict[str, Any]] = Field(description="Setting value")
    description: Optional[str] = Field(default=None, description="Setting description")
    is_sensitive: bool = Field(default=False, description="Whether setting contains sensitive data")
    category: Optional[str] = Field(default=None, description="Setting category")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


# Utility functions for schema handling
def create_paginated_response(
    items: List[T], 
    pagination_meta: PaginationMeta,
    request_id: Optional[str] = None
) -> PaginatedResponse[T]:
    """Create a paginated response"""
    return PaginatedResponse(
        items=items,
        pagination=pagination_meta,
        request_id=request_id
    )


def create_error_response(
    error_type: ErrorType,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
    validation_errors: Optional[List[ValidationError]] = None,
    error_code: Optional[str] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """Create an error response"""
    return ErrorResponse(
        error_type=error_type,
        message=message,
        details=details,
        validation_errors=validation_errors,
        error_code=error_code,
        request_id=request_id
    )


def create_success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> SuccessResponse:
    """Create a success response"""
    return SuccessResponse(
        message=message,
        data=data,
        request_id=request_id
    )