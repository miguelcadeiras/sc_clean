import time

from django.core.management.base import BaseCommand, CommandError

from app_v2 import pd_query_v2


class Command(BaseCommand):
    help = 'Build or refresh persisted v2 virtual rack cache for inspections.'

    def add_arguments(self, parser):
        parser.add_argument('id_inspection', nargs='*', type=int)
        parser.add_argument(
            '--all',
            action='store_true',
            help='Refresh cache for every inspection found in inspectiontbl.',
        )

    def handle(self, *args, **options):
        ids = options['id_inspection']
        if options['all']:
            inspections = pd_query_v2.pd_df(
                'select id_inspection from inspectiontbl order by id_inspection'
            )
            ids = [int(value) for value in inspections['id_inspection'].tolist()]

        if not ids:
            raise CommandError('Provide at least one id_inspection, or use --all.')

        for id_inspection in ids:
            start = time.time()
            df = pd_query_v2.virtual_rack(id_inspection, refresh_cache=True)
            legacy_summary = pd_query_v2.legacy_matching_summary(id_inspection, refresh_cache=True)
            elapsed = time.time() - start
            self.stdout.write(
                self.style.SUCCESS(
                    f'id_inspection={id_inspection} cached rows={len(df)} '
                    f'legacy_false={legacy_summary["legacyMismatchCount"]} '
                    f'legacy_pm2={legacy_summary["legacyPm2Count"]} elapsed={elapsed:.2f}s'
                )
            )
