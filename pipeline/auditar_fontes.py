"""Conciliação reproduzível dos snapshots oficiais, sem utilizar os coletores do painel.
Executar após o build: python -m pipeline.auditar_fontes.
Não baixa nem substitui dados. Diferenças geram falha e CSV para investigação.
"""
import json
import hashlib
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
AUD=ROOT/'data/auditoria'
ORIG=AUD/'originais'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def comparar(nome, oficial, tolerancia=1e-8, nome_saida=None):
    local=pd.read_csv(ROOT/f'data/raw/{nome}.csv',parse_dates=['data'])
    if local.data.duplicated().any() or oficial.data.duplicated().any():
        raise ValueError(f'{nome}: períodos duplicados')
    d=local.merge(oficial,on='data',how='outer',validate='one_to_one',indicator=True)
    d['diferenca']=d.valor-d.oficial
    d['confere']=(d._merge=='both') & (d.diferenca.abs()<=tolerancia)
    d.to_csv(AUD/f'{nome_saida or nome}_comparacao.csv',index=False,date_format='%Y-%m-%d')
    return {'observacoes':len(d),'coincidentes':int(d.confere.sum()),
            'divergencias':int((~d.confere).sum()),'tolerancia_absoluta':tolerancia,
            'sha256_entrada':sha(ROOT/f'data/raw/{nome}.csv')}

def main():
    # Colunas e cabeçalhos conferidos nos dois documentos nacionais da ANP.
    partes=[]
    for arquivo,header,col in [('anp_antiga.xlsx',12,'PRECO MÉDIO REVENDA'),
                               ('anp_recente.xlsx',16,'PREÇO MÉDIO REVENDA')]:
        d=pd.read_excel(ORIG/arquivo,header=header)
        g=d[d.PRODUTO.eq('GASOLINA COMUM')]
        if set(g['UNIDADE DE MEDIDA'])!={'R$/l'}:raise ValueError('Unidade ANP alterada')
        partes.append(pd.DataFrame({'data':pd.to_datetime(g['MÊS']), 'oficial':pd.to_numeric(g[col])}))
    gas=pd.concat(partes)
    wb=json.loads((ORIG/'fome_bm.json').read_text())
    fome=pd.DataFrame([{'data':pd.Timestamp(x['date']+'-01-01'),'oficial':x['value']}
                       for x in wb[1] if x['value'] is not None])
    h=json.loads((ORIG/'atlas_homicidios_brasil.json').read_text())
    geo=json.loads((ORIG/'atlas_brasil_identidade.json').read_text())
    if geo != [{'name':'Brasil','code':'1076','nivel':98}]:raise ValueError('Identidade Brasil alterada')
    if any(x['serie_id']!=20 or x['tipo_regiao']!=1 or x['regiao_id']!=1076 for x in h):
        raise ValueError('Homicídios: série ou abrangência errada')
    hom=pd.DataFrame([{'data':pd.Timestamp(x['periodo'][:4]+'-01-01'),'oficial':x['valor']} for x in h])
    resultado={k:comparar(k,d) for k,d in [('gasolina',gas),('fome',fome),('homicidios',hom)]}
    # Diferenças entre edições são evidência preservada, não falha de transcrição do Atlas.
    antigo=json.loads((ORIG/'homicidios_brasil_extraido.json').read_text())
    historico=pd.DataFrame([{'data':pd.Timestamp(x['VALDATA'][:10]),'valor_ipeadata':x['VALVALOR']} for x in antigo])
    cruz=historico.merge(hom.rename(columns={'oficial':'valor_atlas'}),on='data',how='outer')
    cruz['diferenca_atlas_menos_ipeadata']=cruz.valor_atlas-cruz.valor_ipeadata
    cruz.to_csv(AUD/'homicidios_entre_fontes.csv',index=False,date_format='%Y-%m-%d')
    fao=pd.read_csv(ORIG/'fao_brasil.csv')
    f=pd.DataFrame({'data':pd.to_datetime((fao.Year.str[:4].astype(int)+1).astype(str)+'-01-01'),
                    'oficial':pd.to_numeric(fao.Value.str.replace('<','',regex=False))})
    if not fao.Year.str.match(r'^\d{4}-\d{4}$').all():raise ValueError('Triênio FAO inválido')
    resultado['fome_fao']=comparar('fome',f,nome_saida='fome_fao')
    # Mantém separadamente a evidência de censura, sem substituí-la por 2,5 exato.
    fao[['Year','Value','Flag']].to_csv(AUD/'fome_limites.csv',index=False)

    # Verificação independente do encadeamento do IPCA: produto das taxas posteriores ao mês.
    ipca=pd.read_csv(ROOT/'data/raw/ipca.csv',parse_dates=['data']).set_index('data').valor
    if ipca.index.duplicated().any():raise ValueError('IPCA duplicado')
    if len(pd.date_range(ipca.index.min(),ipca.index.max(),freq='MS'))!=len(ipca):raise ValueError('IPCA com lacuna')
    painel=json.loads((ROOT/'site/data/painel.json').read_text())
    exibido={p['x']:p['y'] for p in painel['indicadores']['gasolina']['serie']}
    linhas=[]
    for r in gas.itertuples():
        if r.data>ipca.index.max():continue
        esperado=float(r.oficial*(1+ipca[ipca.index>r.data]/100).prod())
        atual=exibido.get(r.data.strftime('%Y-%m'))
        linhas.append({'mes':r.data.strftime('%Y-%m'),'recalculado':esperado,'painel':atual,
                       'confere':atual is not None and abs(esperado-atual)<=0.000051})
    pd.DataFrame(linhas).to_csv(AUD/'gasolina_ipca_comparacao.csv',index=False)
    resultado['gasolina_ipca']={'observacoes':len(linhas),'coincidentes':sum(x['confere'] for x in linhas),
                               'divergencias':sum(not x['confere'] for x in linhas),'tolerancia_absoluta':0.000051,
                               'sha256_ipca':sha(ROOT/'data/raw/ipca.csv')}
    resultado['escopo']='Confronto com snapshots; não equivale a reestimar microdados nem conferir edições históricas.'
    resultado['origens']=[{'arquivo':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sorted(ORIG.iterdir()) if p.is_file()]
    (AUD/'resultado.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in resultado.items() if isinstance(v,dict)},ensure_ascii=False,indent=2))
    if any(v.get('divergencias') for v in resultado.values() if isinstance(v,dict)):
        raise SystemExit('Conciliação com divergências: consulte os CSVs; não substituir automaticamente.')

if __name__=='__main__':main()
