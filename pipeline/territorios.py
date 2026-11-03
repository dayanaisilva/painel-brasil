"""Incrementos PRODES em recortes indígenas: edição fixada, sem inferir integridade."""
import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ORIG = ROOT / 'data/auditoria/originais'


def extrair_incrementos(dados, nomes, ultimo_ano=2025):
    if dados.get('name') != 'PRODES LEGAL AMAZON' or dados.get('clazz') != 'deforestation':
        raise ValueError('PRODES: recorte ou classe incompatível')
    if nomes.get('name') != 'indi' or nomes.get('gid') != 4:
        raise ValueError('PRODES: recorte não indígena')
    lookup = {n['gid']: n['loiname'] for n in nomes['loinames']}
    if len(lookup) != len(nomes['loinames']):
        raise ValueError('PRODES: identidade territorial duplicada')
    linhas, anos = [], set()
    for p in dados['periods']:
        inicio, fim = p['startDate'], p['endDate']
        ano = fim['year']
        if inicio['year'] == 1500 or ano > ultimo_ano:
            continue  # máscara acumulada não é incremento anual
        if inicio != {'year':ano-1,'month':8,'day':1} or fim != {'year':ano,'month':7,'day':31} or ano < 2008:
            raise ValueError('PRODES: ciclo anual inválido')
        if ano in anos:
            raise ValueError('PRODES: ciclo duplicado')
        anos.add(ano)
        vistos=set()
        for f in p['features']:
            gid=f['loiname']
            if f['loi'] != 4 or gid not in lookup or gid in vistos:
                raise ValueError('PRODES: território inválido ou duplicado')
            vistos.add(gid)
            if len(f['areas']) != 1 or f['areas'][0]['type'] != 1:
                raise ValueError('PRODES: tipo de área não reconhecido')
            area=f['areas'][0]['area']
            if isinstance(area,bool) or not isinstance(area,(int,float)) or not math.isfinite(area) or area < 0:
                raise ValueError('PRODES: área inválida')
            linhas.append({'ano':ano,'territorio_id':gid,'territorio':lookup[gid],'km2':float(area)})
    if anos != set(range(2008,ultimo_ano+1)) or not linhas:
        raise ValueError('PRODES: cobertura temporal incompleta')
    return pd.DataFrame(linhas).sort_values(['ano','territorio_id']).reset_index(drop=True)


def carregar():
    dados=json.loads((ORIG/'prodes_ti.json').read_text())
    nomes=json.loads((ORIG/'prodes_ti_nomes.json').read_text())
    d=extrair_incrementos(dados,nomes)
    agregado=d.groupby('ano',as_index=False).km2.sum()
    raw=pd.DataFrame({'data':pd.to_datetime(agregado.ano.astype(str)+'-01-01'),'valor':agregado.km2})
    # Ausência de feature permanece ausente na tabela, não vira certeza de área zero.
    territorios=[{'id':n['gid'],'nome':n['loiname'],
                  'valores':{str(int(x.ano)):float(x.km2) for x in d[d.territorio_id.eq(n['gid'])].itertuples()}}
                 for n in sorted(nomes['loinames'],key=lambda n:n['loiname'])]
    return raw,territorios,d
