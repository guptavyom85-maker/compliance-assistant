from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission
from qa.permissions import ROLE_PERMISSIONS


class Command(BaseCommand):
    help = 'Create application groups and set their permissions; does not assign users.'

    def handle(self, **options):
        for role, labels in ROLE_PERMISSIONS.items():
            permissions = []
            for label in labels:
                app, code = label.split('.')
                try:
                    permissions.append(Permission.objects.get(content_type__app_label=app, codename=code))
                except Permission.DoesNotExist as exc:
                    raise CommandError(f'Migrate first: missing {label}') from exc
            group, _ = Group.objects.get_or_create(name=role)
            group.permissions.set(permissions)
            self.stdout.write(f'{role}: {len(permissions)} permissions')
