from django.core.management.base import BaseCommand
from rbac.models import Company


NEW_COMPANIES = [
    {'name': 'Market-Xcel', 'code': 'market-xcel'},
    {'name': 'FICC',        'code': 'ficc'},
    {'name': 'Wepsol',      'code': 'wepsol'},
]


class Command(BaseCommand):
    help = 'Add Market-Xcel, FICC, and Wepsol companies'

    def handle(self, *args, **options):
        for data in NEW_COMPANIES:
            company, created = Company.objects.get_or_create(
                name=data['name'],
                defaults={'code': data['code']},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created: {company.name}"))
            else:
                self.stdout.write(f"Already exists: {company.name}")
