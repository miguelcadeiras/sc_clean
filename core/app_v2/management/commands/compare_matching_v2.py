from django.core.management.base import BaseCommand

from app import pdQuery as legacy_pd_query
from app_v2 import pd_query_v2


class Command(BaseCommand):
    help = 'Compare legacy vs v2 matching outputs and +/-2 error counts for an inspection.'

    def add_arguments(self, parser):
        parser.add_argument('id_inspection', type=int)

    def handle(self, *args, **options):
        id_inspection = options['id_inspection']

        legacy = legacy_pd_query.decodeMachVR_noPD_levels_sorted(id_inspection).fillna('')
        v2 = pd_query_v2.decode_match_levels_sorted(id_inspection).fillna('')

        legacy_total = len(legacy)
        legacy_mismatch = int((legacy['match'] == False).sum())
        legacy_pm2 = int((legacy['desc'] == '2').sum())

        v2_total = len(v2)
        v2_mismatch = int((v2['match'] == False).sum())
        v2_pm2 = int((v2['desc'] == '2').sum())
        pm2_mask = v2['desc'] == '2'
        v2_pm2_wms_ai = int((pm2_mask & (v2['VerifiedAI'] == 'wmsAI')).sum()) if 'VerifiedAI' in v2.columns else 0
        v2_pm2_agv_ai = int((pm2_mask & (v2['VerifiedAI'] == 'agvAI')).sum()) if 'VerifiedAI' in v2.columns else 0
        v2_pm2_remaining = int((pm2_mask & ~v2['VerifiedAI'].isin(['wmsAI', 'agvAI'])).sum()) if 'VerifiedAI' in v2.columns else v2_pm2

        self.stdout.write('--- Legacy ---')
        self.stdout.write(f'total_rows: {legacy_total}')
        self.stdout.write(f'false_mismatch_rows: {legacy_mismatch}')
        self.stdout.write(f'plus_minus_2_rows: {legacy_pm2}')

        self.stdout.write('--- V2 ---')
        self.stdout.write(f'total_rows: {v2_total}')
        self.stdout.write(f'false_mismatch_rows: {v2_mismatch}')
        self.stdout.write(f'plus_minus_2_rows: {v2_pm2}')
        self.stdout.write(f'plus_minus_2_wmsAI: {v2_pm2_wms_ai}')
        self.stdout.write(f'plus_minus_2_agvAI: {v2_pm2_agv_ai}')
        self.stdout.write(f'plus_minus_2_remaining_to_check: {v2_pm2_remaining}')
