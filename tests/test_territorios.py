import copy
import json
import unittest
from pathlib import Path
import pandas as pd
from pipeline.territorios import extrair_incrementos, carregar

class TerritorioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parent.parent
        cls.dados=json.loads((cls.root/'data/auditoria/originais/prodes_ti.json').read_text())
        cls.nomes=json.loads((cls.root/'data/auditoria/originais/prodes_ti_nomes.json').read_text())

    def test_excludes_accumulated_mask_and_unreviewed_2026(self):
        d=extrair_incrementos(self.dados,self.nomes)
        self.assertEqual(set(d.ano),set(range(2008,2026)))
        self.assertFalse(d.duplicated(['ano','territorio_id']).any())

    def test_missing_territory_observation_is_not_zero(self):
        raw,territorios,d=carregar()
        self.assertEqual(len(territorios),386)
        self.assertTrue(any(not t['valores'] for t in territorios))
        self.assertEqual(sum(len(t['valores']) for t in territorios),len(d))
        pd.testing.assert_frame_equal(raw,pd.read_csv(self.root/'data/raw/desmatamento_ti.csv',parse_dates=['data']))

    def test_rejects_unknown_identity_or_duplicate(self):
        for change in ['unknown','duplicate']:
            d=copy.deepcopy(self.dados)
            p=next(p for p in d['periods'] if p['endDate']['year']==2024)
            if change=='unknown':p['features'][0]['loiname']=-1
            else:p['features'].append(copy.deepcopy(p['features'][0]))
            with self.assertRaises(ValueError):extrair_incrementos(d,self.nomes)

    def test_rejects_negative_area_or_missing_cycle(self):
        d=copy.deepcopy(self.dados)
        p=next(p for p in d['periods'] if p['endDate']['year']==2024)
        p['features'][0]['areas'][0]['area']=-1
        with self.assertRaises(ValueError):extrair_incrementos(d,self.nomes)
        d=copy.deepcopy(self.dados)
        d['periods']=[p for p in d['periods'] if p['endDate']['year']!=2024]
        with self.assertRaises(ValueError):extrair_incrementos(d,self.nomes)
