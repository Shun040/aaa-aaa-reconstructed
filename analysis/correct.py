import numpy as np, librosa, json
from scipy.ndimage import uniform_filter1d
sr=16000
o,_=librosa.load('analysis/audio.wav',sr=sr,mono=True)
U=np.fromfile('/tmp/U_full.raw',dtype=np.float32); M=np.fromfile('/tmp/M_full.raw',dtype=np.float32)
mix=librosa.resample(U+M,orig_sr=48000,target_sr=sr); n=min(len(o),len(mix)); o=o[:n]; mix=mix[:n]
f,eq=np.load('analysis/eq_db.npy')
X=librosa.stft(mix,n_fft=2048,hop_length=512); X*=10**(np.interp(librosa.fft_frequencies(sr=sr,n_fft=2048),f,eq)/20)[:,None]; mix=librosa.istft(X,hop_length=512,length=n)
def tiltc(x):
    S=np.abs(librosa.stft(x,n_fft=1024,hop_length=320)); fr=librosa.fft_frequencies(sr=sr,n_fft=1024)
    a=(S[(fr>1500)&(fr<4500)]**2).sum(0); b=(S[(fr>100)&(fr<1500)]**2).sum(0); return 10*np.log10(a+1e-9)-10*np.log10(b+1e-9), b
to,bo=tiltc(o); tm,_=tiltc(mix); t=np.arange(len(to))*320/sr
m=(bo>np.percentile(bo,35))&(t>16)&(t<572)
res=np.where(m,to-tm,np.nan); off=np.nanmedian(res); res=np.nan_to_num(res-off)
w=uniform_filter1d(m.astype(float),1000)+1e-6; rs=uniform_filter1d(res,1000)/w   # 20 s window
sc=json.load(open('build/score.json')); T=np.arange(sc['n'])/sc['fps']
de=np.interp(T,t,rs)/4.5
e=np.clip(np.array(sc['effort'])+de,0,1.35)
sc['effort']=np.round(e,3).tolist(); json.dump(sc,open('build/score.json','w'),separators=(',',':'))
for a,b in [(16,80),(80,150),(150,250),(250,380),(380,480),(480,572)]:
    k=(T>a)&(T<b); print(a,b,'mean Δe %.2f'%de[k].mean(), 'new e %.2f'%e[k].mean())
