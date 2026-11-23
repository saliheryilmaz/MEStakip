from django.contrib.messages import constants
from django.contrib.messages.storage.fallback import FallbackStorage


class NotificationStorage(FallbackStorage):
    def add(self, level, message, extra_tags=''):
        if level != constants.SUCCESS:
            super().add(level, message, extra_tags)

    def _get(self, *args, **kwargs):
        stored, complete = super()._get(*args, **kwargs)
        visible = [message for message in stored if message.level != constants.SUCCESS]
        if len(visible) != len(stored):
            # Rewrite older cookies/sessions even when the template finds no messages.
            self.added_new = True
        return visible, complete
