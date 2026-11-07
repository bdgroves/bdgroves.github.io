import pandas as pd
d=pd.read_csv('data/census/county-to-county-2016-2020-ins-outs-nets-gross_tuolumne.csv',dtype=str)
d=d[d.sheet=='California']
d=d[(d['0']=='006')&(d['1']=='109')]
num=lambda s: pd.to_numeric(s.str.replace(',',''),errors='coerce')
c=pd.DataFrame({'bst':d['2'],'bco':d['3'],'bstate':d['6'],'bname':d['7'],
  'in_est':num(d['8']),'in_moe':num(d['9']),'out_est':num(d['10']),'out_moe':num(d['11'])})
c['us']=c.bst.str.isdigit() & (pd.to_numeric(c.bst,errors='coerce')<=56)
c['geoid']=c.bst.str[-2:]+c.bco.fillna('')
