from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    """Opaque cursor pagination, newest first. `?limit=` is capped at 100."""

    ordering = "-created_at"
    page_size = 25
    page_size_query_param = "limit"
    max_page_size = 100
