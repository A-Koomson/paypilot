from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"

    def ready(self):
        from apps.core import schema  # noqa: F401 — register spectacular extensions
