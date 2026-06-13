from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsTeamlead
from chat.models import Conversation
from chat.presence import get_presence_data
from chat.services import build_models_snapshot


class MonitorSnapshotView(APIView):
    permission_classes = [IsTeamlead]

    def get(self, request):
        chatters = User.objects.filter(role="chatter").order_by("id")
        result = []
        for chatter in chatters:
            presence = get_presence_data(chatter.id)
            dialogs_count = Conversation.objects.filter(chatter=chatter).count()
            waiting = list(
                Conversation.objects.filter(
                    chatter=chatter,
                    awaiting_reply_since__isnull=False,
                ).values("id", "awaiting_reply_since", "fan__name")
            )
            result.append(
                {
                    "id": chatter.id,
                    "display_name": chatter.display_name or chatter.username,
                    "connected": presence["connected"],
                    "last_seen": presence["last_seen"],
                    "dialogs_count": dialogs_count,
                    "waiting": [
                        {
                            "conversation_id": w["id"],
                            "fan_name": w["fan__name"],
                            "waiting_since": (
                                w["awaiting_reply_since"].isoformat()
                                if w["awaiting_reply_since"]
                                else None
                            ),
                        }
                        for w in waiting
                    ],
                }
            )
        return Response({"chatters": result, "models": build_models_snapshot()})
