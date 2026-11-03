import unittest
import pandas as pd
from pipeline.build import resumo_ritmo, resumo_periodos, ipca_acumulado, crescimento_populacao, resumo_media_ponderada

class MethodologyTests(unittest.TestCase):
    def test_missing_endpoint_is_not_interpolated(self):
        a = pd.DataFrame({'ano': [1992, 1993, 1995], 'valor': [29.4,28.2,19.5]})
        self.assertNotIn('itamar', resumo_ritmo(a, relativo=True))

    def test_coverage_counts_only_observed_years(self):
        a = pd.DataFrame({'ano':[2002,2006], 'valor':[20.,10.]})
        self.assertNotIn('lula1', resumo_ritmo(a, relativo=True))

    def test_compound_rate_and_zero_endpoint(self):
        a = pd.DataFrame({'ano':[2002,2003,2004,2005,2006], 'valor':[100.,90.,80.,70.,50.]})
        self.assertAlmostEqual(resumo_ritmo(a, relativo=True)['lula1']['valor'], ((.5)**.25-1)*100)
        a.loc[a.ano==2006,'valor']=0
        self.assertEqual(resumo_ritmo(a, relativo=True)['lula1']['valor'], -100)

    def test_december_is_not_assigned_to_previous_government(self):
        a = pd.DataFrame({'ano':[2015,2016,2017,2018], 'valor':[10.,100.,100.,100.]})
        r = resumo_periodos(a,'dezembro')
        self.assertEqual(r['dilma2']['valor'],10)
        self.assertEqual(r['temer']['valor'],100)

    def test_prodes_uses_only_whole_consolidated_cycles(self):
        a = pd.DataFrame({'ano':[2023,2024,2025,2026], 'valor':[9000.,6000.,5000.,3000.],
                          'tipo':['consolidada']*3+['estimativa']})
        # Only 2024 and 2025 qualify: coverage 2/3, below the disclosed 75% rule.
        self.assertNotIn('lula3',resumo_periodos(a,'prodes'))
        a.loc[a.ano==2026,'tipo']='consolidada'
        r=resumo_periodos(a,'prodes')['lula3']
        self.assertAlmostEqual(r['valor'],14000/3)
        self.assertNotIn('2023',r['periodo'])

    def test_ipca_compounds_instead_of_summing(self):
        a=pd.DataFrame({'data':pd.date_range('2003-01-01',periods=12,freq='MS'),
                        'valor':[10.,-10.]+[0.]*10,'governo':['lula1']*12})
        self.assertAlmostEqual(ipca_acumulado(a)['lula1']['acumulado'],-1)

class PopulationTests(unittest.TestCase):
    @staticmethod
    def serie(years, values):
        return pd.DataFrame({'data': pd.to_datetime([f'{y}-01-01' for y in years]), 'valor': values})

    def test_projection_is_required_after_national_accounts(self):
        pop = self.serie([2020, 2021, 2022], [100, 110, 140])
        contas = self.serie([2020, 2021], [100, 105])
        rates = crescimento_populacao(pop, contas)
        self.assertAlmostEqual(rates[2021], 5)
        self.assertNotIn(2022, rates.index)

    def test_explicit_projection_replaces_incompatible_population_growth(self):
        pop = self.serie([2020, 2021, 2022], [100, 110, 140])
        contas = self.serie([2020, 2021], [100, 105])
        proj = self.serie([2021, 2022], [200, 202])
        self.assertAlmostEqual(crescimento_populacao(pop, contas, proj)[2022], 1)

    def test_missing_projection_year_does_not_become_annual_growth(self):
        pop = self.serie([2020, 2021, 2022, 2023], [100, 110, 140, 150])
        contas = self.serie([2020, 2021], [100, 105])
        proj = self.serie([2021, 2023], [200, 220])
        self.assertTrue(pd.isna(crescimento_populacao(pop, contas, proj)[2023]))

class SensitivityTests(unittest.TestCase):
    def test_transition_year_is_excluded_from_alternative(self):
        a = pd.DataFrame({'ano': [2016, 2017, 2018], 'valor': [100., 10., 20.]})
        r = resumo_media_ponderada(a)['temer']
        self.assertAlmostEqual(r['sensibilidade']['valor'], 15)
        self.assertGreater(r['valor'], 15)
        self.assertEqual(r['sensibilidade']['observacoes'], 2)

    def test_no_full_year_means_no_alternative(self):
        a = pd.DataFrame({'ano': [1992], 'valor': [100.]})
        self.assertIsNone(resumo_media_ponderada(a)['itamar']['sensibilidade']['valor'])

if __name__=='__main__':unittest.main()
