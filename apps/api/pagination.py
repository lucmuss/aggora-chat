from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class AgoraCursorPagination(CursorPagination):
    page_size = 25
    ordering = "-created_at"
    cursor_query_param = "after"

    def get_paginated_response(self, data):
        return Response(
            {
                "items": data,
                "after": self.get_next_link(),
                "before": self.get_previous_link(),
                "count": len(data),
            }
        )
