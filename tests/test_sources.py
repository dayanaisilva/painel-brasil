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

class PublicationPolicyTests(unittest.TestCase):
    def test_partial_source_cannot_generate_government_ranking(self):
        from pipeline.build import aplicar_restricao_auditoria, ranquear
        d={'direcao':'menor','resumo':{'a':{'valor':1},'b':{'valor':2},'c':{'valor':3}},
           'auditoria':{'status':'Conciliação parcial','pendencia':'definição não conciliada'}}
        aplicar_restricao_auditoria(d);ranquear(d)
        self.assertEqual(d['resumo'],{})
        self.assertIsNone(d['direcao'])
        self.assertNotIn('melhor',d)

    def test_audited_source_keeps_summary(self):
        from pipeline.build import aplicar_restricao_auditoria
        d={'direcao':'menor','resumo':{'a':{'valor':1}},'auditoria':{'status':'Conciliado com ressalvas'}}
        aplicar_restricao_auditoria(d)
        self.assertTrue(d['resumo'])

    def test_endpoint_sensitivity_excludes_pre_government_base(self):
        from pipeline.build import resumo_ritmo
        d=pd.DataFrame({'ano':[2002,2003,2004,2005,2006],'valor':[100,50,50,50,50]})
        r=resumo_ritmo(d)['lula1']
        self.assertEqual(r['valor'],-12.5)
        self.assertEqual(r['sensibilidade']['valor'],0)
        self.assertEqual(r['sensibilidade']['periodo'],'2003 → 2006')

class AtlasTests(unittest.TestCase):
    def geo(self):
        return {'features':[{'properties':{'name':'Brasil','code':'1076'}}]}

    def row(self, region=1076, value=20.03):
        return {'serie_id':20,'tipo_regiao':1,'regiao_id':region,
                'periodo':'2024-01-15T00:00:00.000Z','valor':value}

    def test_selects_brazil_and_normalizes_annual_date(self):
        from pipeline.fontes import extrair_atlas_homicidios
        d=extrair_atlas_homicidios([self.row(1218,999),self.row()],self.geo())
        self.assertEqual(d.valor.tolist(),[20.03])
        self.assertEqual(d.data.iloc[0],pd.Timestamp('2024-01-01'))

    def test_rejects_duplicate_invalid_value_and_wrong_identity(self):
        from pipeline.fontes import extrair_atlas_homicidios
        for rows,geo in [([self.row(),self.row()],self.geo()),
                         ([self.row(value=None)],self.geo()),
                         ([self.row(value=float('nan'))],self.geo()),
                         ([self.row()],{'features':[]})]:
            with self.assertRaises(ValueError):extrair_atlas_homicidios(rows,geo)

    def test_archived_atlas_values_match_current_raw(self):
        import json
        from pathlib import Path
        from pipeline.fontes import extrair_atlas_homicidios
        root=Path(__file__).resolve().parent.parent
        values=json.loads((root/'data/auditoria/originais/atlas_homicidios_brasil.json').read_text())
        d=extrair_atlas_homicidios(values,self.geo())
        actual=pd.read_csv(root/'data/raw/homicidios.csv',parse_dates=['data'])
        pd.testing.assert_frame_equal(d,actual,check_dtype=False)
