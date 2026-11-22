import numpy as np, librosa, json, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter1d
sr=16000
o,_=librosa.load('analysis/audio.wav',sr=sr,mono=True)
U=np.fromfile('/tmp/U_full.raw',dtype=np.float32); M=np.fromfile('/tmp/M_full.raw',dtype=np.float32)
mix48=U+M; mix=librosa.resample(mix48,orig_sr=48000,target_sr=sr); n=min(len(o),len(mix)); o=o[:n]; mix=mix[:n]
seg=slice(int(16*sr),int(572*sr))
def ltas(x,nf=2048): return (np.abs(librosa.stft(x[seg],n_fft=nf,hop_length=1024))**2).mean(1)
f=librosa.fft_frequencies(sr=sr,n_fft=2048)
Lo,Lm=ltas(o),ltas(mix)
eq=10*np.log10((Lo+1e-12)/(Lm+1e-12)); eq=uniform_filter1d(eq,9); eq-=np.median(eq[(f>300)&(f<2000)])
eq=np.clip(eq,-40,12)
np.save('analysis/eq_db.npy',np.stack([f,eq]))
def tiltc(x):
    S=np.abs(librosa.stft(x,n_fft=1024,hop_length=320)); fr=librosa.fft_frequencies(sr=sr,n_fft=1024)
    a=(S[(fr>1500)&(fr<4500)]**2).sum(0); b=(S[(fr>100)&(fr<1500)]**2).sum(0)
    return 10*np.log10(a+1e-9)-10*np.log10(b+1e-9), b
# apply eq to mix in freq domain
X=librosa.stft(mix,n_fft=2048,hop_length=512); X*=10**(np.interp(librosa.fft_frequencies(sr=sr,n_fft=2048),f,eq)/20)[:,None]
mixeq=librosa.istft(X,hop_length=512,length=len(mix))
to,bo=tiltc(o); tm,bm=tiltc(mixeq); t=np.arange(len(to))*320/sr
mo=bo>np.percentile(bo,35)
sm=lambda x,m: uniform_filter1d(np.where(m,x,np.nan_to_num(np.median(x[m]))),250)
plt.figure(figsize=(26,6)); plt.plot(t,sm(to,mo),label='original'); plt.plot(t,sm(tm,mo),label='reconstruction (eq)'); plt.legend(); plt.grid(alpha=.3); plt.xticks(np.arange(0,600,20)); plt.ylabel('tilt dB'); plt.savefig('analysis/fit_tilt.png',dpi=50)
def win(a,b): m=(t>a)&(t<b)&mo; return np.median(to[m]),np.median(tm[m])
for a,b in [(16,80),(80,150),(150,250),(250,380),(380,480),(480,572)]: print(a,b,'orig %.1f recon %.1f'%win(a,b))
plt.figure(figsize=(10,4)); plt.plot(f,eq); plt.grid(); plt.savefig('analysis/eq.png',dpi=60)
