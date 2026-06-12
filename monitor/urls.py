from django.urls import path

from monitor.views import MonitorSnapshotView

urlpatterns = [
    path("snapshot/", MonitorSnapshotView.as_view(), name="monitor-snapshot"),
]
