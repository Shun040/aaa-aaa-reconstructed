import numpy as np, json
from scipy.ndimage import median_filter, uniform_filter1d
d=np.load('analysis/tracks3.npz'); t=d['t']; act=d['active'].astype(float); tilt=d['tilt']; db=d['db']
# breath segmentation: close short gaps (<0.12 s) and drop tiny islands
act=((d['db']>-31)&(t>15.4)&(t<573.3)).astype(float); a=median_filter(act,7)
# effort from spectral tilt during phonation, normalised over the performance
m=a>0.5
tl=uniform_filter1d(np.where(m,tilt,np.nan_to_num(np.median(tilt[m]))),25)
lo,hi=np.percentile(tl[m],[5,95]); eff=np.clip((tl-lo)/(hi-lo),0,1)
def voice(f,s):
    v=np.clip((median_filter(s,9)-0.55)/0.6,0,1)*a
    f=f.copy()
    # hold pitch through unvoiced frames
    last=f[0]
    for k in range(len(f)):
        if v[k]>0.15: last=f[k]
        else: f[k]=last
    f=median_filter(f,5)
    return f,v
fU,vU=voice(d['fU'],d['sU']); fM,vM=voice(d['fM'],d['sM'])
# resample to 25 Hz
T=np.arange(0,591.5,0.04)
R=lambda x: np.interp(T,t,x)
score={'fps':25,'t0':0,'n':len(T),
 'active':np.round(R(a),2).tolist(),'effort':np.round(R(eff),3).tolist(),
 'U':{'f0':np.round(R(fU),1).tolist(),'voiced':np.round(R(vU),2).tolist()},
 'M':{'f0':np.round(R(fM),1).tolist(),'voiced':np.round(R(vM),2).tolist()},
 'span':[15.4,573.3]}
json.dump(score,open('analysis/score.json','w'),separators=(',',':'))
# breaths
edges=np.flatnonzero(np.diff((a>0.5).astype(int)))
segs=[]; on=None
for k in edges:
    if a[k+1]>0.5: on=t[k+1]
    elif on is not None: segs.append((round(on,2),round(t[k+1],2))); on=None
print('phrases',len(segs)); print(segs[:6],'...',segs[-6:])
L=[b-a_ for a_,b in segs]; print('mean phrase len first 10 / last 30:',np.mean(L[:10]),np.mean(L[-30:]))
json.dump(segs,open('analysis/phrases.json','w'))
