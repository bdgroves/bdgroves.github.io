import pandas as pd, io
rows=[l.split(',') for l in open('data/irs_tuolumne.csv').read().splitlines()[1:]]
recs=[]
for r in rows:
    yrs,kind=r[0],r[1]; v=r[2:]
    if kind=='inflow':  y2s,y2c,y1s,y1c,st,name,n1,n2,agi=v[:9]
    else:               y1s,y1c,y2s,y2c,st,name,n1,n2,agi=v[:9]
    recs.append(dict(years=yrs,kind=kind,o=f"{int(y1s):02d}{int(y1c):03d}",d=f"{int(y2s):02d}{int(y2c):03d}",name=name.strip('"'),st=st,returns=int(n1),people=int(n2)))
df=pd.DataFrame(recs)
T='06109'
out=df[(df.kind=='outflow')&(df.o==T)]
inn=df[(df.kind=='inflow')&(df.d==T)]
