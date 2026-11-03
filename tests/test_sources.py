import unittest
import pandas as pd
from pipeline.build import limites_fao_verificados
from pipeline.fontes import consolidar_anp, _anp_aba, validar_ies, contar_municipios_federais

class SourceValidationTests(unittest.TestCase):
    def test_anp_duplicate_identical_is_one_observation(self):
        a=pd.DataFrame({'data':pd.to_datetime(['2020-01-01']), 'valor':[5.]})
        self.assertEqual(len(consolidar_anp([a,a])),1)

    def test_anp_conflict_is_not_silently_discarded(self):
        a=pd.DataFrame({'data':pd.to_datetime(['2020-01-01']), 'valor':[5.]})
        b=a.copy();b['valor']=6.
        with self.assertRaisesRegex(ValueError,'conflitantes'):consolidar_anp([a,b])

    def anp_sheet(self, area='BRASIL', unit='R$/l'):
        return pd.DataFrame([[f'TIPO RELATÓRIO: {area}',None,None,None],
            ['MÊS','PRODUTO','UNIDADE DE MEDIDA','PREÇO MÉDIO REVENDA'],
            ['2024-01-01','GASOLINA COMUM',unit,5.5],
            ['2024-01-01','GASOLINA COMUM ADITIVADA',unit,6.]])

    def test_anp_exact_product(self):
        self.assertEqual(_anp_aba(self.anp_sheet()).valor.tolist(),[5.5])

    def test_anp_wrong_unit_and_geography_rejected(self):
        for sheet in [self.anp_sheet(unit='R$/m3'),self.anp_sheet(area='SUDESTE')]:
            with self.assertRaises(ValueError):_anp_aba(sheet)

    def test_inep_counts_identity_not_duplicate_rows(self):
        d=pd.DataFrame({'CO_IES':['1','1'],'CAT':['1','1'],'ORG':['1','1']})
        self.assertEqual(len(validar_ies(d,'CAT','ORG')),1)
        d.loc[1,'CAT']='2'
        with self.assertRaises(ValueError):validar_ies(d,'CAT','ORG')

    def test_inep_missing_modality_is_not_all_presential(self):
        d=pd.DataFrame({'TP_CATEGORIA':['1'],'CO_MUNICIPIO':['123']})
        with self.assertRaises(ValueError):contar_municipios_federais(d)
        self.assertEqual(contar_municipios_federais(d,presencial_no_arquivo=True),1)

    def test_inep_excludes_distance_private_and_duplicate_municipalities(self):
        d=pd.DataFrame({'TP_CATEGORIA':['1','1','1','4','1'],
                        'CO_MUNICIPIO':['123','123','456','789','0'],
                        'TP_MODALIDADE':['1','1','2','1','1']})
        self.assertEqual(contar_municipios_federais(d),1)

    def test_fao_censoring_requires_matching_period_and_value(self):
        a=pd.DataFrame({'ano':[2022,2023,2024],'valor':[2.5,2.7,2.5]})
        f=pd.DataFrame({'Year':['2021-2023','2022-2024','2023-2025'],'Value':['2.5','<2.5','<2.5']})
        self.assertEqual(limites_fao_verificados(a,f),{2024})
