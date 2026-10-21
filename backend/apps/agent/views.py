from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agent import runner
from apps.core.permissions import IsMerchant, get_merchant


class ConversationListView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(operation_id="assistant_conversations_list", responses={200: dict}, tags=["assistant"])
    def get(self, request):
        merchant = get_merchant(request)
        items = [
            {"id": str(c.id), "title": c.title or "Untitled", "updated_at": c.updated_at}
            for c in runner.list_conversations(merchant)[:50]
        ]
        return Response({"results": items})

    @extend_schema(
        operation_id="assistant_conversations_create", request=dict, responses={201: dict}, tags=["assistant"]
    )
    def post(self, request):
        merchant = get_merchant(request)
        title = str(request.data.get("title") or "")
        convo = runner.create_conversation(merchant, title)
        return Response(
            {"id": str(convo.id), "title": convo.title, "updated_at": convo.updated_at}, status=status.HTTP_201_CREATED
        )


class ConversationDetailView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(operation_id="assistant_conversation_retrieve", responses={200: dict}, tags=["assistant"])
    def get(self, request, pk):
        convo = runner._owned(get_merchant(request), pk)
        messages = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "created_at": m.created_at,
            }
            for m in convo.messages.exclude(role="tool")
        ]
        return Response({"id": str(convo.id), "title": convo.title, "messages": messages})

    @extend_schema(operation_id="assistant_conversation_delete", responses={204: None}, tags=["assistant"])
    def delete(self, request, pk):
        convo = runner._owned(get_merchant(request), pk)
        convo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationMessageView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "assistant"

    @extend_schema(
        operation_id="assistant_conversation_message", request=dict, responses={200: dict}, tags=["assistant"]
    )
    def post(self, request, pk):
        content = str(request.data.get("content") or "")
        result = runner.run_turn(get_merchant(request), pk, content)
        return Response(result)
